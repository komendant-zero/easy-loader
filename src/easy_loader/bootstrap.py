import os
import sys
import subprocess
import urllib.request
import zipfile
import tarfile
import shutil
import stat
import platform
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent  # рядом с bootstrap.py


def ensure_ffmpeg() -> str | None:
    which = shutil.which("ffmpeg")
    if which:
        return which

    local = BIN_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if local.is_file():
        _make_executable(local)
        return str(local)

    print("Downloading ffmpeg...")
    arch = platform.machine().lower()
    if sys.platform == "win32":
        tag = "win64-gpl" if "64" in arch else "win32-gpl"
        url = f"https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-{tag}.zip"
        dl = BIN_DIR / "ffmpeg.zip"
        urllib.request.urlretrieve(url, dl)
        with zipfile.ZipFile(dl) as z:
            for m in z.namelist():
                if m.endswith("/ffmpeg.exe") or m.endswith("\\ffmpeg.exe"):
                    z.extract(m, BIN_DIR)
                    src = BIN_DIR / m
                    shutil.move(str(src), str(local))
                    break
        dl.unlink(missing_ok=True)
    else:
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        dl = BIN_DIR / "ffmpeg.tar.xz"
        urllib.request.urlretrieve(url, dl)
        with tarfile.open(dl) as t:
            for m in t.getmembers():
                if m.name.endswith("/ffmpeg"):
                    t.extract(m, BIN_DIR)
                    src = BIN_DIR / m.name
                    shutil.move(str(src), str(local))
                    break
        dl.unlink(missing_ok=True)

    if local.is_file():
        _make_executable(local)
        return str(local)
    return None


def _make_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    except Exception:
        pass