import os
import shutil
import logging
import hashlib
import argparse
import re
from pathlib import Path
from datetime import datetime

import exifread
from tqdm import tqdm
from PIL import Image

# ==============================
# CONFIG
# ==============================

Image.MAX_IMAGE_PIXELS = 300000000

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("sorting_log.txt", encoding='utf-8')]
)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.3gp', '.m4v', '.mts', '.m2ts'}
ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# ==============================
# UTILS
# ==============================

def is_file_corrupted(file_path, fast_mode=False):
    if file_path.stat().st_size == 0:
        return True

    if fast_mode:
        return False

    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        try:
            with Image.open(file_path) as img:
                img.verify()
            return False
        except Exception:
            return True

    return False


def get_md5(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


# ==============================
# DATE LOGIC (Google Photos-like)
# ==============================

def parse_date_from_filename(file_name):
    patterns = [
        r'(\d{4})(\d{2})(\d{2})[_\- ]?(\d{2})(\d{2})(\d{2})',
        r'(\d{4})[-_](\d{2})[-_](\d{2})[_\- ]?(\d{2})(\d{2})(\d{2})',
        r'(\d{4})(\d{2})(\d{2})'
    ]

    for pattern in patterns:
        match = re.search(pattern, file_name)
        if match:
            try:
                parts = list(map(int, match.groups()))
                if len(parts) == 6:
                    return datetime(*parts)
                elif len(parts) == 3:
                    return datetime(parts[0], parts[1], parts[2])
            except:
                pass
    return None


def get_best_date(file_path):
    # 1. EXIF
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

            for field in [
                'EXIF DateTimeOriginal',
                'EXIF DateTimeDigitized',
                'Image DateTime'
            ]:
                if field in tags:
                    return datetime.strptime(str(tags[field]), '%Y:%m:%d %H:%M:%S')
    except:
        pass

    # 2. filename
    filename_date = parse_date_from_filename(file_path.name)
    if filename_date:
        return filename_date

    # 3. filesystem
    stat = file_path.stat()
    timestamps = [stat.st_mtime, stat.st_ctime]

    if hasattr(stat, 'st_birthtime'):
        timestamps.append(stat.st_birthtime)

    return datetime.fromtimestamp(min(timestamps))


# ==============================
# MAIN LOGIC
# ==============================

def process_photos(
    source_dir,
    dest_dir,
    mode='media',
    fast_mode=False,
    split_by_type=False,
    move_files=False
):
    source_path = Path(source_dir)
    dest_path = Path(dest_dir)
    corrupted_path = dest_path / "_CORRUPTED"

    if not source_path.exists():
        print(f"Ошибка: {source_dir} не найден")
        return

    valid_exts = (
        ALL_MEDIA_EXTENSIONS if mode == 'media'
        else IMAGE_EXTENSIONS if mode == 'images'
        else VIDEO_EXTENSIONS if mode == 'videos'
        else None
    )

    files = [
        f for f in source_path.rglob('*')
        if f.is_file()
        and f.name != "sorting_log.txt"
        and (valid_exts is None or f.suffix.lower() in valid_exts)
    ]

    if not files:
        print("Файлы не найдены")
        return

    print(f"Найдено файлов: {len(files)}")

    for file in tqdm(files, desc="Обработка", unit="file"):
        try:
            # 1. corrupted
            if is_file_corrupted(file, fast_mode):
                corrupted_path.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), str(corrupted_path / file.name))
                continue

            # 2. дата
            date = get_best_date(file)
            folder_name = date.strftime('%Y-%m')

            ext = file.suffix.lower()

            if split_by_type:
                subfolder = (
                    "Images" if ext in IMAGE_EXTENSIONS
                    else "Videos" if ext in VIDEO_EXTENSIONS
                    else "Others"
                )
                target_folder = dest_path / folder_name / subfolder
            else:
                target_folder = dest_path / folder_name

            target_folder.mkdir(parents=True, exist_ok=True)

            # 3. hash
            source_hash = get_md5(file)
            if not source_hash:
                continue

            # 4. duplicate check
            duplicate_found = False

            for existing in target_folder.iterdir():
                if existing.is_file() and existing.stat().st_size == file.stat().st_size:
                    if get_md5(existing) == source_hash:
                        duplicate_found = True
                        if move_files:
                            file.unlink()
                        break

            if duplicate_found:
                continue

            # 5. имя файла
            target_file = target_folder / file.name
            i = 1
            while target_file.exists():
                target_file = target_folder / f"{file.stem}_{i}{file.suffix}"
                i += 1

            # 6. copy
            shutil.copy2(file, target_file)

            # 7. verify + move
            if get_md5(target_file) == source_hash:
                if move_files:
                    file.unlink()
                    logging.info(f"MOVE {file} -> {target_file}")
                else:
                    logging.info(f"COPY {file} -> {target_file}")
            else:
                logging.error(f"MD5 mismatch: {file}")

        except Exception as e:
            logging.error(f"ERROR {file}: {e}")


# ==============================
# CLI
# ==============================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("source")
    parser.add_argument("destination")

    parser.add_argument("--mode", choices=['media', 'images', 'videos', 'all_files'], default='media')
    parser.add_argument("--fast", action="store_true")

    parser.add_argument("--split-by-type", action="store_true")
    parser.add_argument("--move", action="store_true")

    args = parser.parse_args()

    process_photos(
        args.source,
        args.destination,
        args.mode,
        args.fast,
        args.split_by_type,
        args.move
    )

    print("DONE")