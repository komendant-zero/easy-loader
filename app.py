import subprocess
import sys
import importlib.util
import os

REQUIRED = ["PySide6", "yt_dlp"]

missing = [p for p in REQUIRED if importlib.util.find_spec(p) is None]
if missing:
    print(f"Installing: {', '.join(missing)}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", *missing, "--quiet", "--no-warn-script-location"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

from src.easy_loader.__main__ import main

if __name__ == "__main__":
    main()