from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPlainTextEdit, QGroupBox,
                             QCheckBox, QLabel, QPushButton, QHBoxLayout, QMessageBox,
                             QFormLayout, QFileDialog, QLineEdit)
from PyQt6.QtGui import QFont


class BioChangePanel(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)

        # ─── Текст био ───
        gb = QGroupBox("Текст био (поддерживается CJK, эмодзи, спинтакс {a|b|c})")
        fl = QVBoxLayout(gb)

        info = QLabel(
            "💡 Если у тебя ломался JP-текст в IAM — здесь multipart с явным utf-8. "
            "Символы сохранятся как есть."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8ab4ff;")
        fl.addWidget(info)

        self.bio = QPlainTextEdit()
        self.bio.setPlaceholderText(
            "Введи био…  до 150 символов на каждый аккаунт после раскрытия спинтакса.\n"
            "Или многострочно: одна строка = одно био, распределится по аккаунтам."
        )
        self.bio.setFont(QFont("Consolas", 10))
        fl.addWidget(self.bio)

        # Быстрые вставки
        h = QHBoxLayout()
        self.btn_jp = QPushButton("Вставить JP anime-бустер")
        self.btn_jp.clicked.connect(self._insert_jp)
        self.btn_load = QPushButton("Загрузить био из файла")
        self.btn_load.clicked.connect(self._load_file)
        h.addWidget(self.btn_jp)
        h.addWidget(self.btn_load)
        h.addStretch()
        fl.addLayout(h)

        v.addWidget(gb)

        # ─── Дополнительно ───
        gb2 = QGroupBox("Дополнительно")
        fl2 = QFormLayout(gb2)
        self.set_name = QCheckBox("Также обновить full_name (первая непустая строка)")
        self.set_website = QCheckBox("Установить сайт (external_url)")
        self.website_url = QLineEdit()
        self.website_url.setPlaceholderText("https://…")
        fl2.addRow(self.set_name)
        fl2.addRow(self.set_website)
        fl2.addRow("URL:", self.website_url)
        self.multiline_distribute = QCheckBox(
            "Разделять на строки — каждая строка = отдельное био (иначе весь текст как одно)"
        )
        self.multiline_distribute.setChecked(False)
        fl2.addRow(self.multiline_distribute)
        self.skip_if_same = QCheckBox(
            "Пропускать аккаунты у которых уже стоит именно это био (по хэшу)"
        )
        self.skip_if_same.setChecked(True)
        fl2.addRow(self.skip_if_same)
        v.addWidget(gb2)

        # Предупреждение
        warn = QLabel("⚠ Не меняй био > 2 раз в час на один аккаунт — IG триггерит soft-lock.")
        warn.setStyleSheet("color:#ffb84d;")
        v.addWidget(warn)
        v.addStretch()

        # ─── Persist: подгружаем сохранённые + вешаем автосохранение ───
        self.load_settings()
        self._wire_autosave()

    # ============================================================
    def _insert_jp(self):
        txt = ("TVアニメ『ONE PIECE』エルバフ編\n"
               "オープニング主題歌\n"
               "ULE+Z-Luminous")
        self.bio.setPlainText((self.bio.toPlainText() + "\n" + txt).strip())

    def _load_file(self):
        from pathlib import Path
        p, _ = QFileDialog.getOpenFileName(self, "Био (одна строка = одно био)", filter="*.txt")
        if p:
            self.bio.setPlainText(Path(p).read_text("utf-8"))

    # ============================================================
    def get_task(self):
        bio_txt = self.bio.toPlainText().strip()
        if not bio_txt:
            QMessageBox.warning(self, "!", "Введи текст био")
            return None, None
        return "set_bio", {
            "bio": bio_txt,
            "set_name": self.set_name.isChecked(),
            "set_website": self.set_website.isChecked(),
            "website": self.website_url.text().strip(),
            "skip_if_same_bio": self.skip_if_same.isChecked(),
            "retry": 0,
            "multiline": self.multiline_distribute.isChecked() and "\n" in bio_txt,
        }

    # ============================================================ Persist
    def _wire_autosave(self):
        
        self.bio.textChanged.connect(self.save_settings)
        self.website_url.textChanged.connect(self.save_settings)
        for cb in (self.set_name, self.set_website, self.skip_if_same, self.multiline_distribute):
            cb.stateChanged.connect(self.save_settings)

    def _cfg_path(self):
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "data" / "bio_settings.json"
        p.parent.mkdir(exist_ok=True)
        return p

    def save_settings(self):
        import json
        try:
            self._cfg_path().write_text(json.dumps({
                "bio":         self.bio.toPlainText(),
                "set_name":    self.set_name.isChecked(),
                "set_website": self.set_website.isChecked(),
                "website":     self.website_url.text(),
                "skip_if_same_bio": self.skip_if_same.isChecked(),
                "multiline_distribute": self.multiline_distribute.isChecked(),
            }, ensure_ascii=False, indent=2), "utf-8")
        except Exception as e:
            print(f"[bio save] {e}")

    def load_settings(self):
        import json
        p = self._cfg_path()
        if not p.exists():
            return
        try:
            cfg = json.loads(p.read_text("utf-8"))
        except Exception as e:
            print(f"[bio load] {e}")
            return
        self.bio.setPlainText(cfg.get("bio", ""))
        self.set_name.setChecked(cfg.get("set_name", False))
        self.set_website.setChecked(cfg.get("set_website", False))
        self.website_url.setText(cfg.get("website", ""))
        self.skip_if_same.setChecked(cfg.get("skip_if_same_bio", True))
        self.multiline_distribute.setChecked(cfg.get("multiline_distribute", False))