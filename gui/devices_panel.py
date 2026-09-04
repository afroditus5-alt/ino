from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QSpinBox, QComboBox, QPushButton, QLabel, QFormLayout,
                             QTableWidget, QTableWidgetItem, QAbstractItemView,
                             QFileDialog, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt
import json
from pathlib import Path
from core.device import DeviceProfile

class DevicesPanel(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)

        info = QLabel("Генератор реальных device-профилей (Samsung / Xiaomi / Google / OnePlus / iPhone). "
                      "До 10 000 за раз. Каждый профиль — актуальная модель, DPI, разрешение, "
                      "CPU, версия IG APK/iOS.")
        info.setWordWrap(True)
        v.addWidget(info)

        gb = QGroupBox("Параметры генерации")
        fl = QFormLayout(gb)

        self.count = QSpinBox(); self.count.setRange(1, 100_000); self.count.setValue(1000)
        fl.addRow("Количество:", self.count)

        self.platform = QComboBox()
        self.platform.addItems(["Микс android/iOS 50/50", "Android 70% / iOS 30%",
                               "Только Android", "Только iOS"])
        fl.addRow("Платформа:", self.platform)

        self.locale = QComboBox()
        self.locale.addItems(["en_US", "ru_RU", "ja_JP", "ko_KR", "zh_CN", "es_ES", "pt_BR", "de_DE"])
        fl.addRow("Локаль:", self.locale)

        self.only_latest = QCheckBox("Только последние 3 версии IG APK (рекомендуется)")
        self.only_latest.setChecked(True)
        fl.addRow(self.only_latest)

        self.stable_seed = QCheckBox("Привязать к будущим аккаунтам (seed=login) — рекомендуется")
        self.stable_seed.setChecked(True)
        self.stable_seed.setToolTip("Если галка стоит — устройство ГЕНЕРИРУЕТСЯ ЗАНОВО на лету от логина. "
                                    "Тогда сохранённый пул нужен только чтобы полюбоваться. "
                                    "Обычно ты именно этого и хочешь.")
        fl.addRow(self.stable_seed)

        v.addWidget(gb)

        h = QHBoxLayout()
        self.btn_gen = QPushButton("Сгенерировать")
        self.btn_export = QPushButton("Экспорт JSON")
        self.btn_clear = QPushButton("Очистить")
        for b in (self.btn_gen, self.btn_export, self.btn_clear): h.addWidget(b)
        h.addStretch()
        v.addLayout(h)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["#", "Платформа", "Модель", "OS", "IG версия", "DPI", "Разрешение", "UA (preview)"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v.addWidget(self.table, 1)

        self.btn_gen.clicked.connect(self._generate)
        self.btn_export.clicked.connect(self._export)
        self.btn_clear.clicked.connect(lambda: self.table.setRowCount(0))

    def _generate(self):
        import random
        n = self.count.value()
        p_idx = self.platform.currentIndex()
        locale = self.locale.currentText()

        def pick_platform():
            if p_idx == 0: return random.choice(["android", "ios"])
            if p_idx == 1: return random.choices(["android", "ios"], weights=[70, 30])[0]
            if p_idx == 2: return "android"
            return "ios"

        self.table.setRowCount(0)
        self.table.setUpdatesEnabled(False)
        for i in range(n):
            dev = DeviceProfile.generate(platform=pick_platform(), locale=locale,
                                          seed=f"preview_{i}")
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(r, 1, QTableWidgetItem(dev.platform))
            self.table.setItem(r, 2, QTableWidgetItem(dev.model))
            self.table.setItem(r, 3, QTableWidgetItem(dev.os_release))
            self.table.setItem(r, 4, QTableWidgetItem(dev.ig_version))
            self.table.setItem(r, 5, QTableWidgetItem(dev.dpi))
            self.table.setItem(r, 6, QTableWidgetItem(dev.resolution))
            self.table.setItem(r, 7, QTableWidgetItem(dev.user_agent()[:120] + "…"))
        self.table.setUpdatesEnabled(True)

    def _export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Экспорт устройств", "devices_pool.json", "*.json")
        if not p: return
        rows = []
        for r in range(self.table.rowCount()):
            rows.append({
                "platform": self.table.item(r, 1).text(),
                "model":    self.table.item(r, 2).text(),
                "os":       self.table.item(r, 3).text(),
                "ig":       self.table.item(r, 4).text(),
                "dpi":      self.table.item(r, 5).text(),
                "resolution": self.table.item(r, 6).text(),
            })
        Path(p).write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        QMessageBox.information(self, "OK", f"Сохранено: {len(rows)}")