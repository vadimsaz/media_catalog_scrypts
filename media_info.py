#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import mimetypes
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from PIL import Image, ExifTags
except ImportError:
    Image = None
    ExifTags = None

try:
    from pymediainfo import MediaInfo
except ImportError:
    MediaInfo = None

# Опциональная поддержка HEIC/HEIF
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass


EXIF_TAGS_REVERSE = {}
GPS_TAGS_REVERSE = {}

if ExifTags:
    EXIF_TAGS_REVERSE = {v: k for k, v in ExifTags.TAGS.items()}
    GPS_TAGS_REVERSE = {v: k for k, v in ExifTags.GPSTAGS.items()}


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def safe_datetime(ts: float | None) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def file_system_info(path: Path) -> dict:
    stat = path.stat()
    mime_type, encoding = mimetypes.guess_type(str(path))

    info = {
        "name": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "absolute_path": str(path.resolve()),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "size_bytes": stat.st_size,
        "size_human": human_size(stat.st_size),
        "mime_type": mime_type,
        "mime_encoding": encoding,
        "created": safe_datetime(get_creation_time(path, stat)),
        "modified": safe_datetime(stat.st_mtime),
        "accessed": safe_datetime(stat.st_atime),
        "os": platform.system(),
    }

    if hasattr(stat, "st_ctime"):
        info["ctime_raw"] = safe_datetime(stat.st_ctime)

    return info


def get_creation_time(path: Path, stat_result) -> float | None:
    try:
        if platform.system() == "Windows":
            return stat_result.st_ctime
        return getattr(stat_result, "st_birthtime", stat_result.st_ctime)
    except Exception:
        return None


def rational_to_float(value):
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return value[0] / value[1] if value[1] else None
        return float(value)
    except Exception:
        return None


def format_fraction(value):
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return f"{value[0]}/{value[1]}"
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            return f"{value.numerator}/{value.denominator}"
        return str(value)
    except Exception:
        return str(value)


def dms_to_decimal(dms, ref):
    try:
        def conv(x):
            if hasattr(x, "numerator") and hasattr(x, "denominator"):
                return x.numerator / x.denominator
            if isinstance(x, tuple) and len(x) == 2:
                return x[0] / x[1]
            return float(x)

        degrees = conv(dms[0])
        minutes = conv(dms[1])
        seconds = conv(dms[2])

        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except Exception:
        return None


def reverse_geocode(lat: float, lon: float) -> dict | None:
    try:
        params = urlencode({
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "zoom": 18,
            "addressdetails": 1,
        })
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
        req = Request(
            url,
            headers={
                "User-Agent": "media-info-script/1.0"
            }
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "display_name": data.get("display_name"),
                "address": data.get("address"),
            }
    except Exception:
        return None


def parse_exif_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def image_info(path: Path, do_reverse_geocode: bool = False) -> dict:
    if Image is None:
        return {"error": "Pillow не установлен. Установите: pip install Pillow"}

    result = {
        "image": {},
        "camera": {},
        "shooting": {},
        "gps": {},
    }

    try:
        with Image.open(path) as img:
            result["image"] = {
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "resolution": f"{img.width}x{img.height}",
                "is_animated": getattr(img, "is_animated", False),
                "frames": getattr(img, "n_frames", 1),
                "has_transparency": "A" in img.mode if isinstance(img.mode, str) else None,
            }

            exif_data = {}
            raw = None
            try:
                raw = img.getexif()
                if raw:
                    for tag_id, value in raw.items():
                        tag = ExifTags.TAGS.get(tag_id, tag_id)
                        exif_data[tag] = value
            except Exception:
                pass

            result["camera"] = {
                "make": exif_data.get("Make"),
                "model": exif_data.get("Model"),
                "lens_model": exif_data.get("LensModel"),
                "software": exif_data.get("Software"),
                "artist": exif_data.get("Artist"),
                "copyright": exif_data.get("Copyright"),
            }

            result["shooting"] = {
                "datetime_original": parse_exif_datetime(exif_data.get("DateTimeOriginal")),
                "datetime_digitized": parse_exif_datetime(exif_data.get("DateTimeDigitized")),
                "datetime_file_exif": parse_exif_datetime(exif_data.get("DateTime")),
                "orientation": exif_data.get("Orientation"),
                "iso": exif_data.get("ISOSpeedRatings") or exif_data.get("PhotographicSensitivity"),
                "exposure_time": format_fraction(exif_data.get("ExposureTime")) if exif_data.get("ExposureTime") else None,
                "f_number": f"f/{rational_to_float(exif_data.get('FNumber')):.1f}" if exif_data.get("FNumber") else None,
                "focal_length": f"{rational_to_float(exif_data.get('FocalLength')):.1f} mm" if exif_data.get("FocalLength") else None,
                "max_aperture_value": rational_to_float(exif_data.get("MaxApertureValue")),
                "exposure_program": exif_data.get("ExposureProgram"),
                "metering_mode": exif_data.get("MeteringMode"),
                "flash": exif_data.get("Flash"),
                "white_balance": exif_data.get("WhiteBalance"),
                "digital_zoom_ratio": rational_to_float(exif_data.get("DigitalZoomRatio")),
                "color_space": exif_data.get("ColorSpace"),
                "x_resolution": exif_data.get("XResolution"),
                "y_resolution": exif_data.get("YResolution"),
                "resolution_unit": exif_data.get("ResolutionUnit"),
            }

            gps_ifd = None
            try:
                gps_tag_id = EXIF_TAGS_REVERSE.get("GPSInfo")
                if gps_tag_id is not None and raw and gps_tag_id in raw:
                    gps_ifd = raw.get_ifd(gps_tag_id)
            except Exception:
                gps_ifd = None

            if gps_ifd:
                gps_named = {}
                for key, value in gps_ifd.items():
                    name = ExifTags.GPSTAGS.get(key, key)
                    gps_named[name] = value

                lat = None
                lon = None

                if gps_named.get("GPSLatitude") and gps_named.get("GPSLatitudeRef"):
                    lat = dms_to_decimal(gps_named["GPSLatitude"], gps_named["GPSLatitudeRef"])

                if gps_named.get("GPSLongitude") and gps_named.get("GPSLongitudeRef"):
                    lon = dms_to_decimal(gps_named["GPSLongitude"], gps_named["GPSLongitudeRef"])

                altitude = None
                if gps_named.get("GPSAltitude") is not None:
                    altitude = rational_to_float(gps_named["GPSAltitude"])

                result["gps"] = {
                    "latitude": lat,
                    "longitude": lon,
                    "altitude_m": altitude,
                    "latitude_ref": gps_named.get("GPSLatitudeRef"),
                    "longitude_ref": gps_named.get("GPSLongitudeRef"),
                    "timestamp_utc": gps_named.get("GPSTimeStamp"),
                    "date_stamp": gps_named.get("GPSDateStamp"),
                }

                if lat is not None and lon is not None and do_reverse_geocode:
                    location = reverse_geocode(lat, lon)
                    if location:
                        result["gps"]["reverse_geocoded"] = location

    except Exception as e:
        result["error"] = f"Ошибка чтения изображения: {e}"

    return result


def simplify_for_json(obj):
    if isinstance(obj, dict):
        return {str(k): simplify_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [simplify_for_json(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def mediainfo_from_library(path: Path) -> dict | None:
    if MediaInfo is None:
        return None

    try:
        media_info = MediaInfo.parse(str(path))
        tracks_data = []

        for track in media_info.tracks:
            data = {
                "track_type": track.track_type,
            }

            for key, value in track.to_data().items():
                if value not in (None, "", [], {}):
                    data[key] = value

            tracks_data.append(data)

        return {"tracks": tracks_data}
    except Exception as e:
        return {"error": f"Ошибка pymediainfo: {e}"}


def ffprobe_info(path: Path) -> dict | None:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except FileNotFoundError:
        return None
    except Exception as e:
        return {"error": f"Ошибка ffprobe: {e}"}


def guess_media_kind(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type:
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"

    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".heic", ".heif", ".avif"}:
        return "image"
    if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mts"}:
        return "video"
    if ext in {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"}:
        return "audio"

    return "unknown"


def build_report(path: Path, reverse_gps: bool = False) -> dict:
    report = {
        "file_system": file_system_info(path),
        "media_kind": guess_media_kind(path),
        "image_metadata": None,
        "media_tracks": None,
    }

    kind = report["media_kind"]

    if kind == "image":
        report["image_metadata"] = image_info(path, do_reverse_geocode=reverse_gps)
        extra_media = mediainfo_from_library(path) or ffprobe_info(path)
        if extra_media:
            report["media_tracks"] = extra_media
    elif kind in {"video", "audio"}:
        report["media_tracks"] = mediainfo_from_library(path) or ffprobe_info(path)
    else:
        report["media_tracks"] = mediainfo_from_library(path) or ffprobe_info(path)

    return report


def print_section(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_dict(d: dict, indent: int = 0):
    prefix = " " * indent
    for key, value in d.items():
        if value in ({}, [], None):
            continue
        if isinstance(value, dict):
            if not value:
                continue
            print(f"{prefix}{key}:")
            print_dict(value, indent + 2)
        elif isinstance(value, list):
            if not value:
                continue
            print(f"{prefix}{key}:")
            for i, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    print(f"{prefix}  [{i}]")
                    print_dict(item, indent + 4)
                else:
                    print(f"{prefix}  - {item}")
        else:
            print(f"{prefix}{key}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description="Чтение полной информации о медиафайле: EXIF, файловая система, GPS, параметры съёмки, видео/аудио-треки."
    )
    parser.add_argument("file", help="Путь к медиафайлу")
    parser.add_argument(
        "--reverse-gps",
        action="store_true",
        help="Попробовать определить адрес по GPS через OpenStreetMap Nominatim"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести результат в JSON"
    )

    args = parser.parse_args()
    path = Path(args.file)

    if not path.exists():
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)

    report = build_report(path, reverse_gps=args.reverse_gps)

    if args.json:
        print(json.dumps(simplify_for_json(report), ensure_ascii=False, indent=2, default=str))
        return

    print_section("ОБЩИЕ ДАННЫЕ ФАЙЛА")
    print_dict(report["file_system"])

    print_section("ТИП МЕДИА")
    print(report["media_kind"])

    if report.get("image_metadata"):
        img_meta = report["image_metadata"]

        if img_meta.get("image"):
            print_section("ОСНОВНЫЕ ДАННЫЕ ИЗОБРАЖЕНИЯ")
            print_dict(img_meta["image"])

        if img_meta.get("camera"):
            print_section("КАМЕРА / АВТОР / ПО")
            print_dict(img_meta["camera"])

        if img_meta.get("shooting"):
            print_section("ПАРАМЕТРЫ СЪЁМКИ")
            print_dict(img_meta["shooting"])

        if img_meta.get("gps"):
            print_section("GPS / МЕСТО СЪЁМКИ")
            print_dict(img_meta["gps"])

    if report.get("media_tracks"):
        print_section("ДОПОЛНИТЕЛЬНЫЕ МЕДИАДАННЫЕ / ТРЕКИ")
        print_dict(simplify_for_json(report["media_tracks"]))

    print()


if __name__ == "__main__":
    main()
