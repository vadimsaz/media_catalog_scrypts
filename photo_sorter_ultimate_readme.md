# 📸 Photo Sorter Ultimate

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![Performance](https://img.shields.io/badge/performance-optimized-orange)

> Smart photo & video organizer with Google Photos–like date detection, safe processing pipeline, and duplicate handling.

---

## ✨ Demo

### 📂 Input (unsorted media dump)
```
DCIM/
  IMG_001.jpg
  VID_20240101.mp4
  random.png
```

### 📁 Output (organized archive)
```
Archive/
  2024-01/
  2024-02/
  _CORRUPTED/
```

---

## 🖼 Screenshots

### Before
![Before](docs/screenshots/before.png)

### After
![After](docs/screenshots/after.png)

### With --split-by-type
![Split](docs/screenshots/split.png)

> 📌 Add your screenshots to: docs/screenshots/

---

## 🚀 Features

### 🧠 Smart Date Detection (like Google Photos)

Priority order:

1. EXIF DateTimeOriginal  
2. EXIF DateTimeDigitized  
3. EXIF Image DateTime  
4. Date from filename  
5. File system timestamps  

---

### 🔒 Safe Processing Pipeline

- Default mode: COPY (safe)
- Optional: --move
- MD5 verification
- No data loss

---

### ♻️ Duplicate Detection

- Hash-based (MD5)
- Skips duplicates in copy mode
- Deletes duplicates in move mode

---

### 🗂 Flexible Folder Structure

Default:
```
2024-01/
2024-02/
```

With --split-by-type:
```
2024-01/
  Images/
  Videos/
  Others/
```

---

### ⚡ Fast Mode

--fast → skips deep validation (3–5x faster)

---

### 🧪 Corrupted File Handling

_CORRUPTED/ folder for broken files

---

## 📦 Installation

```
pip install exifread pillow tqdm
```

---

## ▶️ Usage

Basic:
```
python photo_sorter_ultimate.py SOURCE DEST
```

Move mode:
```
python photo_sorter_ultimate.py SOURCE DEST --move
```

Split:
```
python photo_sorter_ultimate.py SOURCE DEST --split-by-type
```

Fast:
```
python photo_sorter_ultimate.py SOURCE DEST --fast
```

---

## 📁 Project Structure

```
photo-sorter-ultimate/
├── photo_sorter_ultimate.py
├── README.md
├── docs/screenshots/
└── sorting_log.txt
```

---

## 📜 License

MIT
