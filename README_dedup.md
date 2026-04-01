# 📦 Dedup CLI — Incremental File Deduplication Tool

Высокопроизводительный CLI-инструмент для поиска и удаления дубликатов файлов с поддержкой:

- ⚡ инкрементальной (batch) обработки  
- 🧠 умной фильтрации (type → size → hash)  
- 🚀 многопоточного hashing  
- 📊 SQLite базы для масштабируемости  
- 🔁 безопасного удаления  

---

# 🚀 Основные возможности

## 🔍 Точное определение дубликатов

Файлы считаются дубликатами, если совпадают:

расширение (ext)  
+ размер (size)  
+ SHA256 хэш (full_hash)

---

## ⚡ Инкрементальная обработка

Можно обрабатывать данные частями:

--limit-groups  
--limit-files  

---

## 📊 SQLite база

Файл: files.db

| поле | описание |
|------|--------|
| path | путь |
| size | размер |
| ext | расширение |
| full_hash | SHA256 |
| delete_flag | пометка |

---

# 📦 Установка

pip install tqdm

---

# ▶️ Использование

python dedup.py [options]

---

# 🔧 Команды

## Сканирование

python dedup.py --scan "D:\Media"

## Поиск

python dedup.py --find

## Ограничения

--limit-groups 100  
--limit-files 200  
--workers 2  

## Просмотр

python dedup.py --review

## Удаление

python dedup.py --delete --dry-run  
python dedup.py --delete  

---

# 🔁 Workflow

--scan → --find → --review → --delete

---

# ⚡ Производительность

- Multi-thread hashing  
- ext → size → hash  
- ORDER BY size ASC  

---

# 🧠 Pipeline

SCAN → GROUP → LIMIT → HASH → GROUP → MARK → REVIEW → DELETE

---

# ⚠️ Важно

- full_hash может быть NULL — это нормально  
- используйте limit_files вместе с limit_groups  
- повторные запуски безопасны  

---

# 🎯 Итог

Production-ready incremental dedup system
