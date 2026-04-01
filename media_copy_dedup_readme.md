media_copy_dedup.py production-скрипт, который:

✔ сканирует source и destination в SQLite
✔ сравнивает по (ext + size + hash)
✔ копирует только отсутствующие файлы
✔ кладёт их в destination/YYYY-MM/
✔ дата = min(created, modified)
✔ есть progress bar + multi-thread hashing
✔ безопасный (--dry-run)

Установка
pip install tqdm

Как запускать (правильный pipeline)
# 1. индексируем
python media_copy_dedup.py --src "F:\Media" --dst "G:\Sorted" --scan

# 2. считаем хэши
python media_copy_dedup.py --src "F:\Media" --dst "G:\Sorted" --hash

# 3. смотрим что будет
python media_copy_dedup.py --src "F:\Media" --dst "G:\Sorted" --copy --dry-run

# 4. копируем
python media_copy_dedup.py --src "F:\Media" --dst "G:\Sorted" --copy