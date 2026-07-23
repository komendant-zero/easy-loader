from __future__ import annotations

import os
import re
import random
import subprocess
import time
import urllib.request as urlreq
import uuid
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

log = logging.getLogger("ytdl")

_ffmpeg_path: str | None = None


def set_ffmpeg_path(path: str) -> None:
    global _ffmpeg_path
    _ffmpeg_path = path


USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.142 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5.1 Mobile/15E148 Safari/604.1",
]

COOKIES_FILE: str = "cookies.txt"
TEMP_DIR: str = "downloads"

VIDEO_QUALITY_MAP: dict[str, str] = {
    "Лучшее": "bestvideo+bestaudio/best",
    "2160p (4K)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440p (2K)": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

AUDIO_BITRATE_MAP: dict[str, str] = {
    "320 kbps": "320",
    "256 kbps": "256",
    "192 kbps": "192",
    "128 kbps": "128",
    "96 kbps": "96",
    "64 kbps": "64",
}


class InfoWorker(QThread):
    ready = Signal(str, str, str, str, str)  # title, channel, duration, thumb_url, thumb_path

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            import yt_dlp

            ua = random.choice(USER_AGENTS)
            opts: dict[str, Any] = {
                "quiet": True, "no_warnings": True, "extract_flat": False,
                "ignoreerrors": False, "retries": 2, "socket_timeout": 20,
                "http_headers": {"User-Agent": ua, "Accept-Language": "ru,en;q=0.9"},
            }
            if os.path.exists(COOKIES_FILE):
                opts["cookiefile"] = COOKIES_FILE

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if not info:
                    raise ValueError("No info")

                title: str = info.get("title", "")
                channel: str = info.get("channel") or info.get("uploader") or ""
                duration: int = info.get("duration") or 0
                dur_str = f"{duration // 60}:{duration % 60:02d}"
                thumb_url: str = info.get("thumbnail") or ""

                thumb_path = ""
                if thumb_url:
                    try:
                        os.makedirs(TEMP_DIR, exist_ok=True)
                        thumb_path = os.path.join(TEMP_DIR, f"preview_{uuid.uuid4().hex}.jpg")
                        urlreq.urlretrieve(thumb_url, thumb_path)
                    except Exception:
                        thumb_path = ""

                self.ready.emit(title, channel, dur_str, thumb_url, thumb_path)
        except Exception as exc:
            log.error("Info fetch failed: %s", exc)
            self.ready.emit("", "", "", "", "")


CODEC_EXT_MAP: dict[str, str] = {
    "libmp3lame": "mp3",
    "aac": "m4a",
    "libvorbis": "ogg",
    "flac": "flac",
    "libopus": "opus",
}


class DownloadWorker(QThread):
    progress = Signal(str, float)
    finished = Signal(str, bool)

    def __init__(
        self,
        url: str,
        save_dir: str,
        download_type: str,
        quality: str,
        codec: str = "libmp3lame",
        vcodec: str = "mp4",
    ) -> None:
        super().__init__()
        self.url = url
        self.save_dir = save_dir
        self.download_type = download_type
        self.quality = quality
        self.codec = codec
        self.vcodec = vcodec

    def run(self) -> None:
        try:
            {
                "thumb": self._download_thumb,
                "audio": self._download_audio,
                "video": self._download_video,
            }[self.download_type]()
        except Exception as exc:
            log.error("Download failed: %s", exc)
            self.finished.emit(str(exc), False)

    # ── yt-dlp helpers ──────────────────────────────────────

    def _ydl_opts(self, **extra: Any) -> dict[str, Any]:
        ua = random.choice(USER_AGENTS)
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "ignoreerrors": False,
            "retries": 5,
            "fragment_retries": 10,
            "socket_timeout": 20,
            "http_headers": {"User-Agent": ua, "Accept-Language": "ru,en;q=0.9"},
        }
        if os.path.exists(COOKIES_FILE):
            opts["cookiefile"] = COOKIES_FILE
        opts.update(extra)
        return opts

    def _extract_info(self) -> dict[str, Any]:
        import yt_dlp

        for attempt in range(3):
            try:
                with yt_dlp.YoutubeDL(self._ydl_opts()) as ydl:
                    info = ydl.extract_info(self.url, download=False)
                    if info:
                        return info
            except Exception as exc:
                log.warning("Extract attempt %d: %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(5)
        raise ValueError("Не удалось получить информацию о видео")

    def _progress_hook(self, d: dict[str, Any]) -> None:
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            pct = (downloaded / total * 100) if total else 0
            speed = d.get("speed", 0)
            speed_str = (
                f"{speed / 1024 / 1024:.1f} MB/s"
                if speed and speed > 1024 * 1024
                else f"{speed / 1024:.0f} KB/s" if speed else ""
            )
            eta = d.get("eta", 0)
            eta_str = f"осталось {eta // 60}м {eta % 60}с" if eta else ""
            parts = [f"Загрузка… {pct:.0f}%"]
            if speed_str:
                parts.append(speed_str)
            if eta_str:
                parts.append(eta_str)
            self.progress.emit(" • ".join(parts), pct)
        elif d["status"] == "finished":
            self.progress.emit("Обработка…", 90)

    # ── File helpers ─────────────────────────────────────────

    @staticmethod
    def _sanitize(name: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*]', "_", name)
        return safe.strip().strip(".")[:100] or "untitled"

    def _unique_path(self, base: str, ext: str) -> str:
        path = os.path.join(self.save_dir, f"{base}.{ext}")
        if not os.path.exists(path):
            return path
        for i in range(1, 100):
            path = os.path.join(self.save_dir, f"{base}_{i}.{ext}")
            if not os.path.exists(path):
                return path
        return os.path.join(self.save_dir, f"{base}_{uuid.uuid4().hex[:6]}.{ext}")

    # ── Thumbnail ────────────────────────────────────────────

    def _download_thumb(self) -> None:
        self.progress.emit("Получаю информацию…", 5)
        info = self._extract_info()
        thumb_url: str | None = info.get("thumbnail")
        if not thumb_url:
            raise ValueError("Превью не найдено")

        title: str = info.get("title", "thumbnail")
        ext = thumb_url.rsplit(".", 1)[-1].split("?")[0] or "jpg"
        path = self._unique_path(self._sanitize(title) + "_thumb", ext)

        self.progress.emit("Скачиваю превью…", 30)
        urlreq.urlretrieve(thumb_url, path)

        size = os.path.getsize(path)
        self.progress.emit("Готово", 100)
        self.finished.emit(
            f"Превью: {os.path.basename(path)} ({_fmt_size(size)})", True
        )

    # ── Audio ────────────────────────────────────────────────

    def _download_audio(self) -> None:
        import yt_dlp

        self.progress.emit("Получаю информацию…", 5)
        info = self._extract_info()
        title: str = info.get("title", "audio")
        thumb_url: str | None = info.get("thumbnail")
        safe = self._sanitize(title)
        ext = CODEC_EXT_MAP.get(self.codec, "mp3")
        final = self._unique_path(safe, ext)

        thumb_path: str | None = None
        if thumb_url:
            try:
                os.makedirs(TEMP_DIR, exist_ok=True)
                thumb_path = os.path.join(TEMP_DIR, f"thumb_{uuid.uuid4().hex}.jpg")
                urlreq.urlretrieve(thumb_url, thumb_path)
            except Exception:
                thumb_path = None

        os.makedirs(TEMP_DIR, exist_ok=True)
        tmp_tmpl = os.path.join(TEMP_DIR, f"yt_{uuid.uuid4().hex}.%(ext)s")

        fmt_ids = list(
            dict.fromkeys(
                f["format_id"]
                for f in info.get("formats", [])
                if f.get("vcodec") == "none" and f.get("acodec") != "none"
            )
        )
        fmt_ids.append("bestaudio")
        abr = AUDIO_BITRATE_MAP.get(self.quality, "192")

        for fmt_id in fmt_ids:
            for attempt in range(3):
                try:
                    opts = self._ydl_opts(
                        format=fmt_id,
                        outtmpl=tmp_tmpl,
                        progress_hooks=[self._progress_hook],
                    )
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info2 = ydl.extract_info(self.url, download=True)
                        if not info2:
                            continue
                        dl_path: str = ydl.prepare_filename(info2)

                    self.progress.emit("Конвертирую…", 85)

                    if not _ffmpeg_path:
                        raise ValueError("ffmpeg не найден — конвертация аудио недоступна")

                    if thumb_path and os.path.exists(thumb_path):
                        cmd = [
                            _ffmpeg_path, "-y",
                            "-i", dl_path, "-i", thumb_path,
                            "-c:a", self.codec, "-ab", f"{abr}k",
                            "-c:v", "mjpeg", "-q:v", "5",
                            "-map", "0:a", "-map", "1:v",
                            "-id3v2_version", "3",
                        ]
                        if self.codec == "libmp3lame":
                            cmd.insert(4, "-f")
                            cmd.insert(5, "mp3")
                        subprocess.run(
                            cmd + [final],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    else:
                        subprocess.run(
                            [
                                _ffmpeg_path, "-y", "-i", dl_path,
                                "-vn", "-c:a", self.codec, "-ab", f"{abr}k",
                                final,
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )

                    if os.path.exists(dl_path):
                        os.remove(dl_path)

                    size = os.path.getsize(final)
                    self.progress.emit("Готово", 100)
                    self.finished.emit(
                        f"Аудио: {os.path.basename(final)} ({_fmt_size(size)})",
                        True,
                    )
                    return

                except Exception as exc:
                    log.warning("Format %s attempt %d: %s", fmt_id, attempt + 1, exc)
                    time.sleep(3)
                finally:
                    if thumb_path and os.path.exists(thumb_path):
                        try:
                            os.remove(thumb_path)
                        except Exception:
                            pass
            time.sleep(3)

        raise ValueError("Не удалось скачать аудио")

    # ── Video ────────────────────────────────────────────────

    def _download_video(self) -> None:
        import yt_dlp

        self.progress.emit("Получаю информацию…", 5)
        info = self._extract_info()
        title: str = info.get("title", "video")
        safe = self._sanitize(title)
        ext = self.vcodec
        final = self._unique_path(safe, ext)

        os.makedirs(TEMP_DIR, exist_ok=True)
        tmp_tmpl = os.path.join(TEMP_DIR, f"yt_{uuid.uuid4().hex}.%(ext)s")

        fmt = VIDEO_QUALITY_MAP.get(self.quality, "bestvideo+bestaudio/best")
        opts = self._ydl_opts(
            format=fmt,
            outtmpl=tmp_tmpl,
            progress_hooks=[self._progress_hook],
            merge_output_format=ext,
        )

        with yt_dlp.YoutubeDL(opts) as ydl:
            info2 = ydl.extract_info(self.url, download=True)
            dl_path: str = ydl.prepare_filename(info2)

        src = dl_path if dl_path.endswith(f".{ext}") else dl_path.rsplit(".", 1)[0] + f".{ext}"
        if not os.path.exists(src):
            src = dl_path
        if src != final:
            import shutil

            try:
                shutil.move(src, final)
            except shutil.Error:
                shutil.copy2(src, final)
                os.remove(src)

        size = os.path.getsize(final)
        self.progress.emit("Готово", 100)
        self.finished.emit(
            f"Видео: {os.path.basename(final)} ({_fmt_size(size)})", True
        )


def _fmt_size(bytes_: int) -> str:
    if bytes_ >= 1024 * 1024 * 1024:
        return f"{bytes_ / (1024**3):.2f} GB"
    if bytes_ >= 1024 * 1024:
        return f"{bytes_ / (1024**2):.1f} MB"
    return f"{bytes_ / 1024:.0f} KB"