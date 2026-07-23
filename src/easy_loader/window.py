from __future__ import annotations

import os
import re
import uuid
import logging
import urllib.request as urlreq
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QProgressBar,
    QFileDialog, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from .worker import DownloadWorker, InfoWorker

log = logging.getLogger("ytdl")

TEMP = "downloads"

YT_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})"
)

VIDEO_ITEMS = ["Лучшее", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
AUDIO_ITEMS = ["320k", "256k", "192k", "128k", "96k", "64k"]
AUDIO_CODECS = [
    "MP3 (libmp3lame)", "AAC (aac)", "OGG (libvorbis)",
    "FLAC (flac)", "Opus (libopus)", "WMA (wmav2)",
    "AC3 (ac3)", "E-AC3 (eac3)", "ALAC (alac)",
    "GSM (libgsm)", "Speex (libspeex)", "WavPack (wavpack)", "TTA (tta)",
]

class QualityPopup(QFrame):
    picked = Signal(str)

    def __init__(self, items: list[str]) -> None:
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("popup")
        lo = QVBoxLayout(self)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(2)
        for v in items:
            b = QPushButton(v)
            b.setObjectName("pi")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, x=v: self._sel(x))
            lo.addWidget(b)

    def _sel(self, v: str) -> None:
        self.picked.emit(v)
        self.close()


def box(parent: QVBoxLayout) -> QVBoxLayout:
    f = QFrame()
    f.setObjectName("bx")
    lo = QVBoxLayout(f)
    lo.setContentsMargins(14, 12, 14, 12)
    lo.setSpacing(10)
    parent.addWidget(f)
    return lo


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("easy-loader")
        self.setFixedSize(440, 560)

        self._worker: DownloadWorker | None = None
        self._iworker: InfoWorker | None = None
        self._dtype = "audio"
        self._vq = "1080p"
        self._aq = "192k"
        self._thumb_path = ""
        self._popup = QualityPopup(AUDIO_ITEMS)
        self._popup.picked.connect(self._set_q)
        self._acodec = "libmp3lame"
        self._codec_popup = QualityPopup(AUDIO_CODECS)
        self._codec_popup.picked.connect(self._set_codec)

        w = QWidget()
        w.setObjectName("c")
        self.setCentralWidget(w)
        r = QVBoxLayout(w)
        r.setContentsMargins(20, 16, 20, 16)
        r.setSpacing(8)

        self._url = QLineEdit()
        self._url.setPlaceholderText("https://youtube.com/watch?v=…")
        self._url.textChanged.connect(self._on_url)
        box(r).addWidget(self._url)

        c2 = box(r)
        row = QHBoxLayout()
        row.setSpacing(6)
        self._btns: dict[str, QPushButton] = {}
        for k, t in [("video", "Видео"), ("audio", "Аудио"), ("thumb", "Превью")]:
            b = QPushButton(t)
            b.setObjectName("mo")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k2=k: self._tog(k2))
            self._btns[k] = b
            row.addWidget(b)
        c2.addLayout(row)

        c3 = box(r)
        h = QHBoxLayout()
        h.setSpacing(6)
        self._q = QPushButton("192k")
        self._q.setObjectName("q")
        self._q.setCursor(Qt.PointingHandCursor)
        self._q.clicked.connect(self._pop)
        h.addWidget(self._q)

        self._path = QLineEdit(str(Path.home() / "Downloads"))
        self._path.setReadOnly(True)
        h.addWidget(self._path)

        self._br = QPushButton("Обзор")
        self._br.setObjectName("br")
        self._br.setCursor(Qt.PointingHandCursor)
        self._br.clicked.connect(self._brws)
        h.addWidget(self._br)
        c3.addLayout(h)

        c4 = box(r)

        codec_row = QHBoxLayout()
        codec_row.setSpacing(6)
        self._codec_btn = QPushButton("MP3 (libmp3lame)")
        self._codec_btn.setObjectName("q")
        self._codec_btn.setCursor(Qt.PointingHandCursor)
        self._codec_btn.clicked.connect(self._pop_codec)
        codec_row.addWidget(self._codec_btn)

        self._dl = QPushButton("Скачать")
        self._dl.setObjectName("dl")
        self._dl.setCursor(Qt.PointingHandCursor)
        self._dl.clicked.connect(self._go)
        codec_row.addWidget(self._dl)
        c4.addLayout(codec_row)

        self._bar = QProgressBar()
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        c4.addWidget(self._bar)

        self._st = QLabel("")
        self._st.setObjectName("st")
        c4.addWidget(self._st)

        self._pv = QFrame()
        self._pv.setObjectName("bx")
        pv_lo = QHBoxLayout(self._pv)
        pv_lo.setContentsMargins(10, 8, 10, 8)
        pv_lo.setSpacing(12)
        self._th = QLabel()
        self._th.setFixedSize(120, 68)
        self._th.setObjectName("th")
        pv_lo.addWidget(self._th)
        vi = QVBoxLayout()
        vi.setSpacing(2)
        self._tl = QLabel()
        self._tl.setObjectName("vt")
        self._tl.setWordWrap(True)
        self._tl.setMaximumHeight(36)
        vi.addWidget(self._tl)
        self._ml = QLabel()
        self._ml.setObjectName("vm")
        vi.addWidget(self._ml)
        vi.addStretch()
        pv_lo.addLayout(vi, 1)
        self._pv.hide()
        c4.addWidget(self._pv)
        c4.addStretch()

        self._tog("audio")

    # ── video preview ───────────────────────────────────────

    def _on_url(self, text: str) -> None:
        if self._iworker and self._iworker.isRunning():
            self._iworker.terminate()

        m = YT_RE.search(text)
        if not m:
            self._pv.hide()
            return

        vid = m.group(1)
        os.makedirs(TEMP, exist_ok=True)
        self._thumb_path = os.path.join(TEMP, f"th_{uuid.uuid4().hex}.jpg")

        try:
            urlreq.urlretrieve(f"https://img.youtube.com/vi/{vid}/mqdefault.jpg", self._thumb_path)
            p = QPixmap(self._thumb_path).scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._th.setPixmap(p)
        except Exception:
            self._th.setText("🎬")

        self._tl.setText("Загрузка информации…")
        self._ml.setText("")
        self._pv.show()

        self._iworker = InfoWorker(text)
        self._iworker.ready.connect(self._on_info)
        self._iworker.start()

    def _on_info(self, title: str, channel: str, dur: str, _thumb_url: str, _tp: str) -> None:
        if title:
            self._tl.setText(title)
            meta = channel
            if dur:
                meta += f"  •  {dur}"
            self._ml.setText(meta)

    # ── actions ─────────────────────────────────────────────

    def _tog(self, k: str) -> None:
        self._dtype = k
        for key, b in self._btns.items():
            on = key == k
            b.setChecked(on)
            b.setStyleSheet('QPushButton#mo { background:#3b82f6; color:#fff; border-color:#3b82f6; }' if on else '')

        if k == "thumb":
            self._q.setText("—")
            self._q.setEnabled(False)
        else:
            self._q.setEnabled(True)
            items = VIDEO_ITEMS if k == "video" else AUDIO_ITEMS
            self._q.setText(self._vq if k == "video" else self._aq)
            self._popup = QualityPopup(items)
            self._popup.picked.connect(self._set_q)

    def _pop(self) -> None:
        p = self._q.mapToGlobal(self._q.rect().bottomLeft())
        p.setY(p.y() + 2)
        self._popup.move(p)
        self._popup.show()

    def _set_q(self, v: str) -> None:
        if self._dtype == "video":
            self._vq = v
        else:
            self._aq = v
        self._q.setText(v)

    def _pop_codec(self) -> None:
        p = self._codec_btn.mapToGlobal(self._codec_btn.rect().bottomLeft())
        p.setY(p.y() + 2)
        self._codec_popup.move(p)
        self._codec_popup.show()

    def _set_codec(self, v: str) -> None:
        codec_map = {
            "MP3 (libmp3lame)": "libmp3lame",
            "AAC (aac)": "aac",
            "OGG (libvorbis)": "libvorbis",
            "FLAC (flac)": "flac",
            "Opus (libopus)": "libopus",
        }
        self._acodec = codec_map.get(v, "libmp3lame")
        # для flac/opus меняем расширение
        ext_map = {"flac": "flac", "libopus": "opus"}
        ext = ext_map.get(self._acodec, "mp3")
        self._codec_btn.setText(v)

    def _brws(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Выбрать папку", self._path.text())
        if d:
            self._path.setText(d)

    def _go(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        url = self._url.text().strip()
        if not YT_RE.search(url):
            self._st.setText("Неверная ссылка YouTube")
            self._st.setStyleSheet("color:#ef4444; font-size:12px;")
            return
        sd = self._path.text()
        if not os.path.isdir(sd):
            self._st.setText("Папка не найдена")
            self._st.setStyleSheet("color:#ef4444; font-size:12px;")
            return

        q = self._vq if self._dtype == "video" else self._aq
        self._dl.setEnabled(False)
        self._dl.setText("Загрузка…")
        self._bar.setValue(0)
        self._st.setText("Подготовка…")
        self._st.setStyleSheet("color:#6a6a7e; font-size:12px;")

        self._worker = DownloadWorker(url, sd, self._dtype, q, self._acodec)
        self._worker.progress.connect(self._on_p)
        self._worker.finished.connect(self._on_f)
        self._worker.start()

    def _on_p(self, t: str, pct: float) -> None:
        self._st.setText(t)
        self._bar.setValue(int(pct))

    def _on_f(self, msg: str, ok: bool) -> None:
        self._bar.setValue(100 if ok else 0)
        self._dl.setEnabled(True)
        self._dl.setText("Скачать")
        self._st.setText("")
        self._st.setStyleSheet(f"color:{'#22c55e' if ok else '#ef4444'}; font-size:12px;")
        self._st.setText(msg)

    def closeEvent(self, ev) -> None:
        if self._thumb_path and os.path.exists(self._thumb_path):
            try:
                os.remove(self._thumb_path)
            except Exception:
                pass
        super().closeEvent(ev)