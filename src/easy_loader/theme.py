QSS = """
QMainWindow { background:#0d0d14; }
QWidget#c { background:#0d0d14; }
QFrame#bx { background:#14141e; border:1px solid #24243a; border-radius:20px; }
QLineEdit {
    background:#16161f; color:#ffffff; border:1px solid #2a2a3a; border-radius:12px;
    padding:14px 16px; font-size:14px; selection-background-color:#3b82f6;
    font-family: "Inter", "Segoe UI", sans-serif;
}
QLineEdit:focus { border-color:#3b82f6; }

QPushButton#mo {
    background:#16161f; color:#8a8a9e; border:1px solid #2a2a3a; border-radius:16px;
    padding:12px 0; font-size:14px; font-weight:600;
    font-family: "Inter", "Segoe UI", sans-serif;
}
QPushButton#mo:hover { background:#1e1e2a; border-color:#3b82f6; }
QPushButton#mo:checked { background:#3b82f6; color:#ffffff; border-color:#3b82f6; }

QPushButton#chip {
    background:#16161f; color:#8a8a9e; border:1px solid #2a2a3a; border-radius:12px;
    padding:8px 12px; font-size:13px; font-weight:600;
    font-family: "Inter", "Segoe UI", sans-serif;
}
QPushButton#chip:hover { background:#1e1e2a; }
QPushButton#chip:checked { background:#16161f; color:#ffffff; border:1px solid #3b82f6; }

QPushButton#br {
    background:transparent; color:#ffffff; border:none; border-radius:12px;
    padding:8px; font-size:24px;
}
QPushButton#br:hover { background:#1e1e2a; }

QPushButton#dl {
    background:#3b82f6; color:#ffffff; border:none; border-radius:16px;
    padding:16px 0; font-size:16px; font-weight:bold; letter-spacing:1px;
    font-family: "Outfit", "Segoe UI", sans-serif;
}
QPushButton#dl:hover { background:#2563eb; }
QPushButton#dl:disabled { background:#1e1e2a; color:#5a5a6e; }

QProgressBar {
    background:#1e1e2a; border:none; border-radius:6px; height:12px;
}
QProgressBar::chunk { background:#3b82f6; border-radius:6px; }

QLabel#st { color:#8a8a9e; font-size:14px; font-family: "Inter", "Segoe UI", sans-serif; }
QLabel#th { background:#1a1a2a; border-top-left-radius:20px; border-top-right-radius:20px; }
QLabel#vt { color:#ffffff; font-size:16px; font-weight:bold; font-family: "Inter", "Segoe UI", sans-serif; }
QLabel#vm { color:#8a8a9e; font-size:14px; font-family: "Inter", "Segoe UI", sans-serif; }
QLabel#title { color:#ffffff; font-size:24px; font-weight:bold; font-family: "Outfit", "Segoe UI", sans-serif; }
QLabel#grouptitle { color:#8a8a9e; font-size:12px; font-weight:bold; font-family: "Inter", "Segoe UI", sans-serif; }

QScrollBar:vertical {
    border: none;
    background: #0d0d14;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #2a2a3a;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none; background: none; height: 0px;
}
QScrollArea { border: none; background: #0d0d14; }
"""