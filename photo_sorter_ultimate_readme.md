# 📸 Photo Sorter Ultimate
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)
![Performance](https://img.shields.io/badge/performance-optimized-orange)

Профессиональный Python-скрипт для автоматической организации фото и видео в структурированную файловую систему по датам (YYYY-MM) с использованием логики определения даты, аналогичной Google Photos.

---

## 🚀 Описание

Photo Sorter Ultimate предназначен для обработки больших архивов медиафайлов (фото и видео) и приведения их к понятной и чистой структуре хранения.

Скрипт автоматически:
- определяет наиболее точную дату создания файла
- сортирует файлы по папкам вида ГОД-МЕСЯЦ (например 2024-01)
- устраняет дубликаты
- проверяет целостность файлов
- поддерживает безопасный режим работы без риска потери данных

---

## 🧠 Как определяется дата файла

Скрипт использует приоритетную логику (как Google Photos):

1. EXIF DateTimeOriginal (дата съёмки)
2. EXIF DateTimeDigitized  
3. EXIF Image DateTime  
4. Дата из имени файла (например IMG_20240101_123456.jpg)
5. Дата файловой системы (самая ранняя из доступных)

---

## 🔒 Режимы работы

### 1. COPY (по умолчанию — безопасный режим)

Файлы копируются в архив, оригиналы остаются на месте.

### 2. MOVE (режим перемещения)

Файлы удаляются из исходной папки после успешного копирования и проверки.

Флаг:
--move

---

## ♻️ Обработка дубликатов

- используется MD5-хэш
- в COPY режиме → файл пропускается
- в MOVE режиме → оригинал удаляется

---

## 🗂 Структура папок

По умолчанию:
2024-01/
2024-02/

С флагом --split-by-type:
2024-01/
  Images/
  Videos/
  Others/

---

## ⚡ Быстрый режим

Флаг:
--fast

Отключает глубокую проверку и ускоряет обработку

---

## 🧪 Поврежденные файлы

Перемещаются в папку:
_CORRUPTED/

---

## 📦 Установка

pip install exifread pillow tqdm

---

## ▶️ Использование

Базовый запуск:
python photo_sorter_ultimate.py SOURCE DEST

Перемещение:
python photo_sorter_ultimate.py SOURCE DEST --move

Разделение:
python photo_sorter_ultimate.py SOURCE DEST --split-by-type

Быстрый режим:
python photo_sorter_ultimate.py SOURCE DEST --fast

Комбинация:
python photo_sorter_ultimate.py D:\Photos D:\Archive --move --split-by-type --fast

---

## 📁 Результат

Archive/
  2024-01/
  2024-02/
  _CORRUPTED/

---

## ⚠️ Нюансы

- В Windows ctime ≠ дата создания
- EXIF используется как основной источник
- Поддержка HEIC и больших изображений

---

## 📜 Лицензия

MIT
