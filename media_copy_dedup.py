#!/usr/bin/env python3

import os
import sqlite3
import hashlib
import shutil
import argparse
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = "media.db"

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.heic', '.webp'}
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

# ---------------- UTILS ----------------

def get_ext(path):
    return os.path.splitext(path)[1].lower()

def is_media(path):
    ext = get_ext(path)
    return ext in IMAGE_EXT or ext in VIDEO_EXT

def get_file_date(path):
    stat = os.stat(path)
    created = getattr(stat, "st_ctime", stat.st_mtime)
    modified = stat.st_mtime
    return datetime.fromtimestamp(min(created, modified))

# ---------------- HASH ----------------

def file_hash(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
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
        hash TEXT,
        location TEXT
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files(hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ext_size ON files(ext, size)")

    conn.commit()

# ---------------- SCAN ----------------

def scan(conn, root, location):
    cur = conn.cursor()

    files = []
    for r, _, fs in os.walk(root):
        for f in fs:
            path = os.path.join(r, f)
            if is_media(path):
                files.append(path)

    print(f"{location}: found {len(files)} media files")

    for path in tqdm(files, desc=f"Scan {location}", unit="file"):
        try:
            size = os.path.getsize(path)
            ext = get_ext(path)

            cur.execute("""
            INSERT OR IGNORE INTO files (path, size, ext, location)
            VALUES (?, ?, ?, ?)
            """, (path, size, ext, location))

        except Exception as e:
            tqdm.write(f"ERROR scan: {path} -> {e}")

    conn.commit()

# ---------------- HASH ----------------

def compute_hashes(conn, location, workers=8):
    cur = conn.cursor()

    cur.execute("""
    SELECT id, path FROM files
    WHERE location=? AND hash IS NULL
    """, (location,))

    rows = cur.fetchall()
    print(f"{location}: hashing {len(rows)} files")

    def process(row):
        file_id, path = row
        if not os.path.exists(path):
            return None
        h = file_hash(path)
        if h:
            return (file_id, h)
        return None

    results = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(process, r) for r in rows]

        for f in tqdm(as_completed(futures),
                      total=len(futures),
                      desc=f"Hash {location}",
                      unit="file"):
            r = f.result()
            if r:
                results.append(r)

    cur.executemany(
        "UPDATE files SET hash=? WHERE id=?",
        [(h, i) for i, h in results]
    )

    conn.commit()

# ---------------- COPY ----------------

def copy_missing(conn, src_root, dst_root, dry_run=False):
    cur = conn.cursor()

    # все hash в destination
    cur.execute("""
    SELECT hash FROM files WHERE location='dst'
    """)
    existing = {row[0] for row in cur.fetchall() if row[0]}

    # файлы из source
    cur.execute("""
    SELECT path, size, ext, hash FROM files
    WHERE location='src'
    """)

    rows = cur.fetchall()

    print(f"Source files: {len(rows)}")
    print(f"Destination hashes: {len(existing)}")

    copied = 0

    for path, size, ext, h in tqdm(rows, desc="Copying", unit="file"):

        if not h:
            continue

        if h in existing:
            continue

        if not os.path.exists(path):
            continue

        # дата → папка
        d = get_file_date(path)
        folder = f"{d.year}-{str(d.month).zfill(2)}"

        target_dir = os.path.join(dst_root, folder)
        target_path = os.path.join(target_dir, os.path.basename(path))

        if not dry_run:
            os.makedirs(target_dir, exist_ok=True)

        # защита от конфликтов
        base, ext_ = os.path.splitext(target_path)
        i = 1
        while os.path.exists(target_path):
            target_path = f"{base}_{i}{ext_}"
            i += 1

        if dry_run:
            tqdm.write(f"[DRY] {path} -> {target_path}")
        else:
            try:
                shutil.copy2(path, target_path)
                copied += 1
                existing.add(h)
            except Exception as e:
                tqdm.write(f"ERROR copy: {path} -> {e}")

    print(f"\nCopied: {copied}")

# ---------------- MAIN ----------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--hash", action="store_true")
    parser.add_argument("--copy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if args.scan:
        scan(conn, args.src, "src")
        scan(conn, args.dst, "dst")

    if args.hash:
        compute_hashes(conn, "src")
        compute_hashes(conn, "dst")

    if args.copy:
        copy_missing(conn, args.src, args.dst, args.dry_run)

    conn.close()


if __name__ == "__main__":
    main()