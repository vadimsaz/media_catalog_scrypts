#!/usr/bin/env python3

import os
import sqlite3
import hashlib
import argparse
import sys
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# UTF-8 fix (Windows)
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "files.db"

# ---------------- HASH ----------------

def hash_full(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024*8), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        tqdm.write(f"Hash error: {path} -> {e}")
        return None


# ---------------- DB ----------------

def init_db(conn):
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY,
        path TEXT UNIQUE,
        size INTEGER,
        ext TEXT,
        full_hash TEXT,
        delete_flag INTEGER DEFAULT 0
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_ext_size ON files(ext, size)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files(full_hash)")

    conn.commit()


# ---------------- SCAN ----------------

def scan(conn, root):
    cur = conn.cursor()

    if not os.path.exists(root):
        print(f"ERROR: path not found: {root}")
        return

    total = 0

    for root_dir, _, files in os.walk(root):
        print(f"\nProcessing folder: {root_dir} ({len(files)} files)")

        for name in files:
            path = os.path.join(root_dir, name)

            try:
                size = os.path.getsize(path)
                ext = os.path.splitext(name)[1].lower()

                cur.execute("""
                INSERT OR IGNORE INTO files (path, size, ext)
                VALUES (?, ?, ?)
                """, (path, size, ext))

                total += 1

            except Exception as e:
                print(f"ERROR: {path} -> {e}")

    conn.commit()
    print(f"\nScan complete. Files indexed: {total}")


# ---------------- FIND ----------------

def find_duplicates(conn, max_workers=4, limit_groups=None, limit_files=None):
    cur = conn.cursor()

    # 🔥 FIX: сначала маленькие файлы
    cur.execute("""
    SELECT ext, size
    FROM files
    GROUP BY ext, size
    HAVING COUNT(*) > 1
    ORDER BY size ASC
    """)

    groups = cur.fetchall()

    if limit_groups is not None:
        groups = groups[:limit_groups]

    tqdm.write(f"Groups to process: {len(groups)}")

    tasks = []

    for ext, size in groups:
        cur.execute("""
        SELECT id, path FROM files
        WHERE ext=? AND size=? AND full_hash IS NULL
        """, (ext, size))

        tasks.extend(cur.fetchall())

    if limit_files is not None:
        tasks = tasks[:limit_files]

    tqdm.write(f"Files to hash: {len(tasks)}")

    def process(row):
        file_id, path = row

        if not os.path.exists(path):
            return None

        try:
            # быстрый доступ (анти-зависание)
            with open(path, "rb") as f:
                f.read(1)
        except Exception:
            return None

        h = hash_full(path)
        if h:
            return (file_id, h)

        return None

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(process, t) for t in tasks]

        for f in tqdm(as_completed(futures),
                      total=len(futures),
                      desc="Hashing",
                      unit="file"):
            r = f.result()
            if r:
                results.append(r)

    cur.executemany(
        "UPDATE files SET full_hash=? WHERE id=?",
        [(h, i) for i, h in results]
    )

    conn.commit()

    # 🔥 FIX: группировка по hash + ext (ВАЖНО)
    cur.execute("""
    SELECT full_hash, ext
    FROM files
    WHERE full_hash IS NOT NULL
    GROUP BY full_hash, ext
    HAVING COUNT(*) > 1
    """)

    dup_groups = cur.fetchall()
    tqdm.write(f"Duplicate groups found: {len(dup_groups)}")

    for (h, ext) in dup_groups:
        cur.execute("""
        SELECT id FROM files
        WHERE full_hash=? AND ext=?
        ORDER BY LENGTH(path), path
        """, (h, ext))

        rows = cur.fetchall()

        for (file_id,) in rows[1:]:
            cur.execute("UPDATE files SET delete_flag=1 WHERE id=?", (file_id,))

    conn.commit()
    tqdm.write("Duplicates marked")


# ---------------- REVIEW ----------------

def review(conn):
    cur = conn.cursor()

    cur.execute("""
    SELECT full_hash, ext
    FROM files
    WHERE delete_flag=1
    GROUP BY full_hash, ext
    """)

    groups = cur.fetchall()

    print(f"\nDuplicate groups: {len(groups)}\n")

    for (h, ext) in groups:
        print(f"\n=== GROUP {h[:10]} ({ext}) ===")

        cur.execute("""
        SELECT path, delete_flag
        FROM files
        WHERE full_hash=? AND ext=?
        ORDER BY delete_flag, path
        """, (h, ext))

        for path, flag in cur.fetchall():
            mark = "KEEP" if flag == 0 else "DEL "
            print(f"[{mark}] {path}")


# ---------------- DELETE ----------------

def delete(conn, dry_run=False):
    cur = conn.cursor()

    cur.execute("SELECT id, path FROM files WHERE delete_flag=1")
    rows = cur.fetchall()

    print(f"Files to delete: {len(rows)}")

    deleted = 0

    for file_id, path in tqdm(rows, desc="Deleting", unit="file"):
        try:
            if not os.path.exists(path):
                if not dry_run:
                    cur.execute("DELETE FROM files WHERE id=?", (file_id,))
                continue

            if dry_run:
                tqdm.write(f"[DRY] {path}")
                continue

            os.remove(path)

            # удаляем из БД
            cur.execute("DELETE FROM files WHERE id=?", (file_id,))
            deleted += 1

        except Exception as e:
            tqdm.write(f"ERROR deleting {path}: {e}")

    conn.commit()
    print(f"\nDeleted: {deleted}")


# ---------------- MAIN ----------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--scan", help="Scan directory")
    parser.add_argument("--find", action="store_true")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    # 🔥 управление нагрузкой
    parser.add_argument("--limit-groups", type=int)
    parser.add_argument("--limit-files", type=int)
    parser.add_argument("--workers", type=int, default=4)

    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if args.scan:
        scan(conn, args.scan)

    if args.find:
        find_duplicates(
            conn,
            max_workers=args.workers,
            limit_groups=args.limit_groups,
            limit_files=args.limit_files
        )

    if args.review:
        review(conn)

    if args.delete:
        confirm = input("Type YES to confirm deletion: ")
        if confirm == "YES":
            delete(conn, args.dry_run)
        else:
            print("Cancelled")

    conn.close()


if __name__ == "__main__":
    main()