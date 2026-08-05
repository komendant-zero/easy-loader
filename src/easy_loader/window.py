from __future__ import annotations

import os
import sys
import re
import uuid
import logging
import urllib.request as urlreq
from pathlib import Path

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_path, relative_path)

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QLabel, QProgressBar,
    QFileDialog, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QIcon

from .worker import DownloadWorker, InfoWorker, VIDEO_QUALITY_MAP

log = logging.getLogger("ytdl")

TEMP = "downloads"

YT_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})"
)

VIDEO_ITEMS = ["2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"]
AUDIO_ITEMS = ["320 kbps", "256 kbps", "192 kbps", "128 kbps", "96 kbps", "64 kbps"]
AUDIO_CODECS = [
    "MP3 (libmp3lame)", "AAC (aac)", "OGG (libvorbis)",
    "FLAC (flac)", "Opus (libopus)",
]
VIDEO_FORMATS: dict[str, tuple[str, str]] = {
    "MP4 (H.264)": ("bestvideo[vcodec^=avc1]+bestaudio/best", "mp4"),
    "MKV (H.265)": ("bestvideo[vcodec^=hevc]+bestaudio/best", "mkv"),
    "WEBM (VP9)": ("bestvideo[vcodec^=vp9]+bestaudio/best", "webm"),
    "WEBM (AV1)": ("bestvideo[vcodec^=av01]+bestaudio/best", "webm"),
}
VIDEO_CODECS = list(VIDEO_FORMATS.keys())


class PreviewLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pix = None

    def setPixmap(self, p: QPixmap) -> None:
        self._pix = p
        self._update_pixmap()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._update_pixmap()

    def _update_pixmap(self) -> None:
        if self._pix and not self._pix.isNull():
            scaled = self._pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)


class ChipGroup(QWidget):
    picked = Signal(str)

    def __init__(self, title: str, items: list[str], columns: int = 3) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        lbl = QLabel(title)
        lbl.setObjectName("grouptitle")
        layout.addWidget(lbl)
        
        w = QWidget()
        self.grid = QGridLayout(w)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        layout.addWidget(w)
        
        self.buttons = {}
        for i, text in enumerate(items):
            b = QPushButton(text)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=text: self._sel(v))
            self.buttons[text] = b
            row, col = divmod(i, columns)
            self.grid.addWidget(b, row, col)
            
    def set_value(self, val: str):
        for k, b in self.buttons.items():
            b.setChecked(k == val)
            
    def _sel(self, val: str):
        self.set_value(val)
        self.picked.emit(val)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("easy-loader")
        self.setMinimumSize(440, 740)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        
        self._worker: DownloadWorker | None = None
        self._iworker: InfoWorker | None = None
        self._dtype = "video"
        self._vq = "1080p"
        self._aq = "192 kbps"
        self._thumb_path = ""
        self._acodec = "MP3 (libmp3lame)"
        self._vcodec = "MP4 (H.264)"
        
        self._url_timer = QTimer(self)
        self._url_timer.setSingleShot(True)
        self._url_timer.setInterval(500)
        self._url_timer.timeout.connect(self._process_url)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)

        w = QWidget()
        w.setObjectName("c")
        scroll.setWidget(w)
        
        r = QVBoxLayout(w)
        r.setContentsMargins(24, 24, 24, 24)
        r.setSpacing(24)

        # Header
        header = QHBoxLayout()
        title_lbl = QLabel("Easy Loader")
        title_lbl.setObjectName("title")
        header.addWidget(title_lbl)
        header.addStretch()
        r.addLayout(header)

        # URL Input
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://youtube.com/watch?v=…")
        self._url.textChanged.connect(self._on_url)
        r.addWidget(self._url)

        # Formats
        row = QHBoxLayout()
        row.setSpacing(8)
        self._btns: dict[str, QPushButton] = {}
        for k, t in [("video", "Видео"), ("audio", "Аудио"), ("thumb", "Превью")]:
            b = QPushButton(t)
            b.setObjectName("mo")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k2=k: self._tog(k2))
            self._btns[k] = b
            row.addWidget(b)
        r.addLayout(row)

        # Video Info Preview
        self._pv = QFrame()
        self._pv.setObjectName("bx")
        pv_lo = QVBoxLayout(self._pv)
        pv_lo.setContentsMargins(0, 0, 0, 0)
        pv_lo.setSpacing(0)
        self._th = PreviewLabel()
        self._th.setObjectName("th")
        pv_lo.addWidget(self._th)
        
        vi = QVBoxLayout()
        vi.setContentsMargins(16, 16, 16, 16)
        vi.setSpacing(8)
        self._tl = QLabel()
        self._tl.setObjectName("vt")
        self._tl.setWordWrap(True)
        vi.addWidget(self._tl)
        self._ml = QLabel()
        self._ml.setObjectName("vm")
        vi.addWidget(self._ml)
        pv_lo.addLayout(vi)
        r.addWidget(self._pv)
        self._pv.hide()

        # Dynamic options container
        self._opt_container = QWidget()
        opt_lo = QVBoxLayout(self._opt_container)
        opt_lo.setContentsMargins(0, 0, 0, 0)
        opt_lo.setSpacing(24)
        r.addWidget(self._opt_container)
        
        # Chip groups
        self._vq_group = ChipGroup("КАЧЕСТВО", VIDEO_ITEMS)
        self._vq_group.picked.connect(self._set_vq)
        opt_lo.addWidget(self._vq_group)
        
        self._vc_group = ChipGroup("КОДЕК", VIDEO_CODECS)
        self._vc_group.picked.connect(self._set_vc)
        opt_lo.addWidget(self._vc_group)
        
        self._aq_group = ChipGroup("БИТРЕЙТ", AUDIO_ITEMS)
        self._aq_group.picked.connect(self._set_aq)
        opt_lo.addWidget(self._aq_group)
        
        self._ac_group = ChipGroup("КОДЕК", AUDIO_CODECS)
        self._ac_group.picked.connect(self._set_ac)
        opt_lo.addWidget(self._ac_group)
        
        # Audio ID3 Tags
        self._id3_container = QWidget()
        id3_lo = QVBoxLayout(self._id3_container)
        id3_lo.setContentsMargins(0, 0, 0, 0)
        id3_lo.setSpacing(8)
        
        id3_lbl = QLabel("ТЕГИ (ID3)")
        id3_lbl.setObjectName("grouptitle")
        id3_lo.addWidget(id3_lbl)
        
        self._id3_title = QLineEdit()
        self._id3_title.setPlaceholderText("Название")
        id3_lo.addWidget(self._id3_title)
        
        self._id3_author = QLineEdit()
        self._id3_author.setPlaceholderText("Исполнитель")
        id3_lo.addWidget(self._id3_author)
        
        opt_lo.addWidget(self._id3_container)
        
        # Path & Download
        path_lo = QHBoxLayout()
        self._path = QLineEdit(str(Path.home() / "Downloads"))
        self._path.setReadOnly(True)
        path_lo.addWidget(self._path)
        self._br = QPushButton("📁")
        self._br.setObjectName("br")
        self._br.setCursor(Qt.PointingHandCursor)
        self._br.clicked.connect(self._brws)
        path_lo.addWidget(self._br)
        r.addLayout(path_lo)

        self._bar = QProgressBar()
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.hide()
        r.addWidget(self._bar)

        self._st = QLabel("")
        self._st.setObjectName("st")
        self._st.setAlignment(Qt.AlignCenter)
        r.addWidget(self._st)

        self._dl = QPushButton("СКАЧАТЬ В ГАЛЕРЕЮ")
        self._dl.setObjectName("dl")
        self._dl.setCursor(Qt.PointingHandCursor)
        self._dl.clicked.connect(self._go)
        r.addWidget(self._dl)

        r.addStretch()

        self._vq_group.set_value(self._vq)
        self._vc_group.set_value(self._vcodec)
        self._aq_group.set_value(self._aq)
        self._ac_group.set_value(self._acodec)

        self._tog("video")

    # ── video preview ───────────────────────────────────────

    def _on_url(self, text: str) -> None:
        self._url_timer.start()

    def _process_url(self) -> None:
        text = self._url.text()
        if self._iworker and self._iworker.isRunning():
            self._iworker.terminate()
            # Do not wait() here to avoid freezing the UI when deleting text

        m = YT_RE.search(text)
        if not m:
            self._pv.hide()
            return

        vid = m.group(1)
        os.makedirs(TEMP, exist_ok=True)
        self._thumb_path = os.path.join(TEMP, f"th_{uuid.uuid4().hex}.jpg")

        try:
            urlreq.urlretrieve(f"https://img.youtube.com/vi/{vid}/mqdefault.jpg", self._thumb_path)
            self._th.setPixmap(QPixmap(self._thumb_path))
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
            
            self._id3_title.setText(title)
            self._id3_author.setText(channel)
            
            if _tp and os.path.exists(_tp):
                self._th.setPixmap(QPixmap(_tp))

    # ── actions ─────────────────────────────────────────────

    def _tog(self, k: str) -> None:
        self._dtype = k
        for key, b in self._btns.items():
            b.setChecked(key == k)

        if k == "thumb":
            self._vq_group.hide()
            self._vc_group.hide()
            self._aq_group.hide()
            self._ac_group.hide()
            self._id3_container.hide()
        elif k == "video":
            self._vq_group.show()
            self._vc_group.show()
            self._aq_group.hide()
            self._ac_group.hide()
            self._id3_container.hide()
        elif k == "audio":
            self._vq_group.hide()
            self._vc_group.hide()
            self._aq_group.show()
            self._ac_group.show()
            self._id3_container.show()

    def _set_vq(self, v: str) -> None:
        self._vq = v

    def _set_vc(self, v: str) -> None:
        self._vcodec = v
        
    def _set_aq(self, v: str) -> None:
        self._aq = v
        
    def _set_ac(self, v: str) -> None:
        self._acodec = v

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
            self._st.setStyleSheet("color:#ef4444; font-size:14px;")
            return
        sd = self._path.text()
        if not os.path.isdir(sd):
            self._st.setText("Папка не найдена")
            self._st.setStyleSheet("color:#ef4444; font-size:14px;")
            return

        self._dl.setEnabled(False)
        self._dl.setText("ЗАГРУЗКА…")
        self._bar.show()
        self._bar.setValue(0)
        self._st.setText("Подготовка…")
        self._st.setStyleSheet("color:#8a8a9e; font-size:14px;")
        
        q = self._vq if self._dtype == "video" else self._aq
        vfmt = self._vcodec
        acodec_val = "libmp3lame"
        
        audio_map = {
            "MP3 (libmp3lame)": "libmp3lame",
            "AAC (aac)": "aac",
            "OGG (libvorbis)": "libvorbis",
            "FLAC (flac)": "flac",
            "Opus (libopus)": "libopus",
        }
        
        if self._dtype == "video":
            fmt_spec, ext = VIDEO_FORMATS.get(vfmt, ("bestvideo+bestaudio/best", "mp4"))
            vfmt = f"{fmt_spec}|{ext}"
            if "|" in vfmt:
                parts = vfmt.split("|", 1)
                base_fmt = parts[0]
                ext = parts[1]
                qfmt = VIDEO_QUALITY_MAP.get(q, "bestvideo+bestaudio/best")
                if "[height" in qfmt:
                    vfilter = base_fmt.replace("bestvideo", "", 1).replace("+bestaudio/best", "", 1)
                    combined = qfmt.replace("bestvideo", f"bestvideo{vfilter}", 1)
                else:
                    combined = base_fmt
                vfmt = f"{combined}|{ext}"
        else:
            acodec_val = audio_map.get(self._acodec, "libmp3lame")

        c_title = self._id3_title.text()
        c_author = self._id3_author.text()

        self._worker = DownloadWorker(url, sd, self._dtype, q, acodec_val, vfmt, c_title, c_author)
        self._worker.progress.connect(self._on_p)
        self._worker.finished.connect(self._on_f)
        self._worker.start()

    def _on_p(self, t: str, pct: float) -> None:
        self._st.setText(t)
        self._bar.setValue(int(pct))

    def _on_f(self, msg: str, ok: bool, filepath: str = "") -> None:
        self._bar.setValue(100 if ok else 0)
        QTimer.singleShot(1500, self._bar.hide)
        self._dl.setEnabled(True)
        self._dl.setText("СКАЧАТЬ В ГАЛЕРЕЮ")
        self._st.setStyleSheet(f"color:{'#10B981' if ok else '#ef4444'}; font-size:14px; font-weight:bold;")
        if ok:
            self._st.setText("Успешно сохранено!")
        else:
            self._st.setText(msg)

    def closeEvent(self, ev) -> None:
        if self._thumb_path and os.path.exists(self._thumb_path):
            try:
                os.remove(self._thumb_path)
            except Exception:
                pass
        if self._iworker and self._iworker.isRunning():
            self._iworker.terminate()
            self._iworker.wait()
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        super().closeEvent(ev)