import os
import sys
import logging
import shutil

from PySide6.QtWidgets import QApplication

from .bootstrap import ensure_ffmpeg
from .worker import set_ffmpeg_path, TEMP_DIR
from .theme import QSS
from .window import MainWindow


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if os.path.isdir(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    ffmpeg = ensure_ffmpeg()
    if ffmpeg:
        set_ffmpeg_path(ffmpeg)
    else:
        logging.getLogger("ytdl").warning("ffmpeg not found — audio conversion disabled")

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()