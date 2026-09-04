from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLineEdit,
                             QSpinBox, QCheckBox, QComboBox, QPushButton, QLabel,
                             QHBoxLayout, QMessageBox)
import json
from pathlib import Path

class SettingsPanel(QWidget):
    CFG = Path("data/settings.json")

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)

        # ---- Antibot ----
        gb1 = QGroupBox("Anti-detect")
        fl1 = QFormLayout(gb1)
        self.tls_impersonate = QComboBox()
        self.tls_impersonate.addItems([
            "auto (по платформе устройства) — рекомендуется",
            "chrome124_android",
            "safari17_ios",
            "chrome120",
            "firefox120",
        ])
        fl1.addRow("TLS impersonation:", self.tls_impersonate)

        self.h2_only = QCheckBox("Только HTTP/2 (рекомендуется — реальный IG использует H2)")
        self.h2_only.setChecked(True)
        fl1.addRow(self.h2_only)

        self.mimic_timing = QCheckBox("Log-normal распределение задержек (человеческое)")
        self.mimic_timing.setChecked(True)
        fl1.addRow(self.mimic_timing)

        self.bloks_version = QLineEdit("8ca95b3d0f292f637c8772a1b62b3a71a3c81a7e7c8f3b8f8c5f6c8f6b3f8a1c")
        fl1.addRow("X-Bloks-Version-Id:", self.bloks_version)

        self.ig_capabilities = QLineEdit("3brTv10=")
        fl1.addRow("X-IG-Capabilities:", self.ig_capabilities)

        v.addWidget(gb1)

        # ---- Captcha ----
        gb2 = QGroupBox("Обход капчи / UFAC")
        fl2 = QFormLayout(gb2)
        self.captcha_provider = QComboBox()
        self.captcha_provider.addItems(["Отключено", "rucaptcha", "capsolver", "anti-captcha", "2captcha"])
        fl2.addRow("Провайдер:", self.captcha_provider)
        self.captcha_key = QLineEdit(); self.captcha_key.setEchoMode(QLineEdit.EchoMode.Password)
        fl2.addRow("API key:", self.captcha_key)

        self.checkpoint_email = QCheckBox("Автопрохождение email-чекпоинта (через email:pass в аккаунте)")
        self.checkpoint_email.setChecked(True)
        fl2.addRow(self.checkpoint_email)

        self.checkpoint_sms = QCheckBox("Автопрохождение SMS-чекпоинта (через sms-hub/5sim/onlinesim)")
        fl2.addRow(self.checkpoint_sms)
        self.sms_provider = QComboBox()
        self.sms_provider.addItems(["5sim", "sms-hub", "sms-activate", "onlinesim"])
        fl2.addRow("SMS provider:", self.sms_provider)
        self.sms_key = QLineEdit(); self.sms_key.setEchoMode(QLineEdit.EchoMode.Password)
        fl2.addRow("SMS API key:", self.sms_key)

        v.addWidget(gb2)

        # ---- IMAP ----
        gb3 = QGroupBox("IMAP (для email-кода при чекпоинте)")
        fl3 = QFormLayout(gb3)
        self.imap_hint = QLabel("IMAP хосты определяются автоматически по домену email "
                               "(rambler/mail.ru/outlook/gmx/…). Ниже — override при необходимости.")
        self.imap_hint.setWordWrap(True)
        fl3.addRow(self.imap_hint)
        self.imap_override = QLineEdit()
        self.imap_override.setPlaceholderText("domain:host:port  (напр. rambler.ru:imap.rambler.ru:993)")
        fl3.addRow("Override:", self.imap_override)
        v.addWidget(gb3)

        # ---- Прочее ----
        gb4 = QGroupBox("Разное")
        fl4 = QFormLayout(gb4)
        self.log_level = QComboBox()
        self.log_level.addItems(["INFO", "DEBUG", "TRACE"])
        fl4.addRow("Уровень логов:", self.log_level)
        self.save_har = QCheckBox("Сохранять HAR каждого аккаунта (для дебага, ~5МБ на акк)")
        fl4.addRow(self.save_har)
        self.autosave_interval = QSpinBox(); self.autosave_interval.setRange(0, 3600); self.autosave_interval.setValue(60)
        fl4.addRow("Автосохранение состояния, сек:", self.autosave_interval)
        v.addWidget(gb4)

        # buttons
        h = QHBoxLayout()
        self.btn_save = QPushButton("Сохранить"); self.btn_save.clicked.connect(self._save)
        self.btn_load = QPushButton("Загрузить"); self.btn_load.clicked.connect(self._load)
        h.addWidget(self.btn_save); h.addWidget(self.btn_load); h.addStretch()
        v.addLayout(h)
        v.addStretch()

        self._load()

    def _save(self):
        self.CFG.parent.mkdir(exist_ok=True)
        cfg = {
            "tls": self.tls_impersonate.currentText(),
            "h2_only": self.h2_only.isChecked(),
            "mimic_timing": self.mimic_timing.isChecked(),
            "bloks_version": self.bloks_version.text(),
            "ig_capabilities": self.ig_capabilities.text(),
            "captcha_provider": self.captcha_provider.currentText(),
            "captcha_key": self.captcha_key.text(),
            "checkpoint_email": self.checkpoint_email.isChecked(),
            "checkpoint_sms": self.checkpoint_sms.isChecked(),
            "sms_provider": self.sms_provider.currentText(),
            "sms_key": self.sms_key.text(),
            "imap_override": self.imap_override.text(),
            "log_level": self.log_level.currentText(),
            "save_har": self.save_har.isChecked(),
            "autosave_interval": self.autosave_interval.value(),
        }
        self.CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
        QMessageBox.information(self, "OK", "Сохранено")

    def _load(self):
        if not self.CFG.exists(): return
        cfg = json.loads(self.CFG.read_text("utf-8"))
        # обратная выставка виджетов
        idx = self.tls_impersonate.findText(cfg.get("tls", ""))
        if idx >= 0: self.tls_impersonate.setCurrentIndex(idx)
        self.h2_only.setChecked(cfg.get("h2_only", True))
        self.mimic_timing.setChecked(cfg.get("mimic_timing", True))
        self.bloks_version.setText(cfg.get("bloks_version", ""))
        self.ig_capabilities.setText(cfg.get("ig_capabilities", ""))
        self.captcha_key.setText(cfg.get("captcha_key", ""))
        self.checkpoint_email.setChecked(cfg.get("checkpoint_email", True))
        self.checkpoint_sms.setChecked(cfg.get("checkpoint_sms", False))
        self.sms_key.setText(cfg.get("sms_key", ""))
        self.imap_override.setText(cfg.get("imap_override", ""))
        self.save_har.setChecked(cfg.get("save_har", False))
        self.autosave_interval.setValue(cfg.get("autosave_interval", 60))