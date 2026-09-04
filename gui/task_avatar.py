from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QGroupBox, QLineEdit, QPushButton, QCheckBox,
                             QFileDialog, QLabel, QSpinBox, QMessageBox)
from pathlib import Path


class AvatarPanel(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)

        # ─── Папка с аватарками ───
        gb_folder = QGroupBox("Папка с аватарками")
        fl = QFormLayout(gb_folder)

        info = QLabel(
            "На каждый аккаунт ставится случайная картинка из папки. "
            "Формат: JPG/PNG, квадрат или 4:5, минимум 320×320.\n"
            "Скачать пачкой можно через bulk_covers.py или download_avatars.py."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8ab4ff;")
        fl.addRow(info)

        h = QHBoxLayout()
        self.avatar_folder = QLineEdit()
        self.avatar_folder.setPlaceholderText("Путь к папке с аватарками")
        btn = QPushButton("Обзор…")
        btn.clicked.connect(self._pick_folder)
        h.addWidget(self.avatar_folder)
        h.addWidget(btn)
        fl.addRow("Папка:", h)

        v.addWidget(gb_folder)

        # ─── Настройки ───
        gb_opts = QGroupBox("Настройки")
        fo = QFormLayout(gb_opts)

        self.skip_if_set = QCheckBox(
            "Пропускать аккаунты у которых уже стоит аватар (по хэшу)"
        )
        self.skip_if_set.setChecked(True)
        fo.addRow(self.skip_if_set)

        self.mark_setup = QCheckBox(
            "Помечать аккаунт как first_setup_done (чтоб при заливе Reels био не ставилось повторно)"
        )
        self.mark_setup.setChecked(False)
        fo.addRow(self.mark_setup)

        self.delay_min = QSpinBox()
        self.delay_min.setRange(0, 3600)
        self.delay_min.setValue(15)
        self.delay_max = QSpinBox()
        self.delay_max.setRange(0, 3600)
        self.delay_max.setValue(60)
        dh = QHBoxLayout()
        dh.addWidget(self.delay_min)
        dh.addWidget(QLabel("—"))
        dh.addWidget(self.delay_max)
        dh.addWidget(QLabel("сек между акками"))
        fo.addRow("Задержки:", dh)

        self.retry = QSpinBox()
        self.retry.setRange(0, 5)
        self.retry.setValue(1)
        fo.addRow("Повторов при ошибке:", self.retry)

        v.addWidget(gb_opts)

        warn = QLabel(
            "⚠ IG не любит частую смену аватарки. Не гоняй эту задачу на одном "
            "аккаунте чаще 1 раза в 24 часа."
        )
        warn.setStyleSheet("color:#ffb84d;")
        v.addWidget(warn)
        v.addStretch()

        self.load_settings()
        self._wire_autosave()

    def _pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Папка с аватарками")
        if p:
            self.avatar_folder.setText(p)

    def get_task(self):
        folder = self.avatar_folder.text().strip()
        if not folder:
            QMessageBox.warning(self, "!", "Укажи папку с аватарками")
            return None, None
        if not Path(folder).is_dir():
            QMessageBox.warning(self, "!", "Папка не существует")
            return None, None

        return "set_avatar", {
            "avatar_folder": folder,
            "skip_if_set":   self.skip_if_set.isChecked(),
            "mark_setup":    self.mark_setup.isChecked(),
            "delay_min":     self.delay_min.value(),
            "delay_max":     self.delay_max.value(),
            "retry":         self.retry.value(),
        }

    # ─── Persist ───
    def _wire_autosave(self):
        self.avatar_folder.textChanged.connect(self.save_settings)
        for cb in (self.skip_if_set, self.mark_setup):
            cb.stateChanged.connect(self.save_settings)
        for sp in (self.delay_min, self.delay_max, self.retry):
            sp.valueChanged.connect(self.save_settings)

    def _cfg_path(self):
        p = Path(__file__).resolve().parent.parent / "data" / "avatar_settings.json"
        p.parent.mkdir(exist_ok=True)
        return p

    def save_settings(self):
        import json
        try:
            self._cfg_path().write_text(json.dumps({
                "avatar_folder": self.avatar_folder.text(),
                "skip_if_set":   self.skip_if_set.isChecked(),
                "mark_setup":    self.mark_setup.isChecked(),
                "delay_min":     self.delay_min.value(),
                "delay_max":     self.delay_max.value(),
                "retry":         self.retry.value(),
            }, ensure_ascii=False, indent=2), "utf-8")
        except Exception as e:
            print(f"[avatar save] {e}")

    def load_settings(self):
        import json
        p = self._cfg_path()
        if not p.exists():
            return
        try:
            cfg = json.loads(p.read_text("utf-8"))
        except Exception:
            return
        self.avatar_folder.setText(cfg.get("avatar_folder", ""))
        self.skip_if_set.setChecked(cfg.get("skip_if_set", True))
        self.mark_setup.setChecked(cfg.get("mark_setup", False))
        self.delay_min.setValue(cfg.get("delay_min", 15))
        self.delay_max.setValue(cfg.get("delay_max", 60))
        self.retry.setValue(cfg.get("retry", 1))