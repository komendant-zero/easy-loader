# easy-loader ![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=flat&logo=youtube&logoColor=white)

Минималистичный десктопный загрузчик YouTube на PySide6 и yt-dlp.

## Возможности

- Скачивание видео (до 4K)
- Скачивание аудио (MP3, AAC, FLAC, Opus и др.)
- Скачивание превью
- Прикрепление обложки к аудиофайлам
- Живое превью видео при вводе ссылки
- Выбор качества и папки сохранения
- Автоустановка ffmpeg при первом запуске

## Установка и запуск

```bash
pip install -r requirements.txt
python app.py
```

При первом запуске автоматически установятся PySide6 и yt-dlp, если их нет.

## Зависимости

- Python ≥ 3.11
- PySide6 ≥ 6.6
- yt-dlp ≥ 2024
- ffmpeg (скачивается автоматически при отсутствии)
