from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                             QPushButton, QComboBox, QLabel, QCheckBox, QLineEdit)
from PyQt6.QtGui import QColor, QTextCharFormat, QFont, QTextCursor
from PyQt6.QtCore import Qt
from datetime import datetime

LEVEL_COLORS = {
    "info":    QColor("#a0c0ff"),
    "warn":    QColor("#ffb84d"),
    "error":   QColor("#ff6b6b"),
    "success": QColor("#7bd88f"),
    "banned":  QColor("#ff4a4a"),
    "debug":   QColor("#7a7d88"),
}

class LogViewer(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 4, 0, 0)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Лог:"))
        self.filter = QComboBox()
        self.filter.addItems(["Всё", "info", "success", "warn", "error", "banned", "debug"])
        bar.addWidget(self.filter)
        self.search = QLineEdit(); self.search.setPlaceholderText("Поиск в логе…")
        bar.addWidget(self.search, 1)
        self.autoscroll = QCheckBox("Автоскролл"); self.autoscroll.setChecked(True)
        bar.addWidget(self.autoscroll)
        self.btn_clear = QPushButton("Очистить")
        bar.addWidget(self.btn_clear)
        self.btn_save = QPushButton("Сохранить в файл")
        bar.addWidget(self.btn_save)
        v.addLayout(bar)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(50_000)  # ring buffer
        f = QFont("Consolas", 9); self.view.setFont(f)
        v.addWidget(self.view)

        self.btn_clear.clicked.connect(self.view.clear)
        self.btn_save.clicked.connect(self._save)

    def append_line(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color = LEVEL_COLORS.get(level, QColor("#e5e5e5"))
        cur = self.view.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(color)
        cur.insertText(f"[{ts}] {level.upper():7} {msg}\n", fmt)
        if self.autoscroll.isChecked():
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def append_status(self, row: int, login: str, status: str, err: str = ""):
        level = {"running": "info", "success": "success",
                 "error": "error", "banned": "banned"}.get(status, "info")
        msg = f"#{row+1:04d}  {login:30s}  → {status}"
        if err: msg += f"   [{err}]"
        self.append_line(level, msg)

    def _save(self):
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path
        p, _ = QFileDialog.getSaveFileName(self, "Лог", f"log_{datetime.now():%Y%m%d_%H%M}.txt", "*.txt")
        if p: Path(p).write_text(self.view.toPlainText(), "utf-8")