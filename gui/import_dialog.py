from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QPlainTextEdit, QComboBox, QCheckBox,
                             QFileDialog, QMessageBox, QGroupBox, QFormLayout,
                             QDialogButtonBox, QLineEdit)
from pathlib import Path
from storage.importer import AccountImporter
from datetime import datetime

class ImportDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.imported_count = 0
        self.setWindowTitle("Импорт аккаунтов")
        self.resize(800, 700)

        v = QVBoxLayout(self)

        info = QLabel(
            "Поддерживаемые форматы (автоопределение разделителя `: | ;`):\n"
            "  • login:pass\n"
            "  • login:pass:email:emailpass\n"
            "  • login:pass:email:emailpass:ip:port[:proxyuser:proxypass]\n"
            "  • login:pass:email:emailpass:socks5:ip:port[:proxyuser:proxypass]\n"
            "  • login:pass:2FA_SECRET (base32)\n"
            "  • login:pass:ip:port  (без email)\n"
            "  • IAM API JSON  (полный дамп с cookies, user_agent, device_id)\n"
            "  • IAM экспорт (галки на скрине 12 — все принимаются)"
        )
        info.setStyleSheet("color:#8ab4ff;")
        v.addWidget(info)

        gb = QGroupBox("Вставь строки ниже или загрузи файл")
        fl = QVBoxLayout(gb)
        h = QHBoxLayout()
        self.btn_file = QPushButton("Загрузить из файла…")
        self.btn_paste = QPushButton("Вставить из буфера")
        h.addWidget(self.btn_file); h.addWidget(self.btn_paste); h.addStretch()
        fl.addLayout(h)

        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Одна запись на строку…")
        fl.addWidget(self.text, 1)
        v.addWidget(gb, 1)

        # опции
        default_name = f"batch_{datetime.now():%Y-%m-%d_%H-%M}"
        gb_batch = QGroupBox("Метка пачки (для сортировки в таблице)")
        fl_b = QFormLayout(gb_batch)
        self.batch_name = QLineEdit(default_name)
        self.batch_name.setPlaceholderText("название пачки — увидишь в колонке 'Пачка'")
        fl_b.addRow("Имя пачки:", self.batch_name)
        v.addWidget(gb_batch)
        gb2 = QGroupBox("Опции")
        fl2 = QFormLayout(gb2)
        self.dedupe = QCheckBox("Пропускать дубликаты (по логину)"); self.dedupe.setChecked(True)
        fl2.addRow(self.dedupe)
        self.auto_proxy = QCheckBox("Привязать свободные прокси из пула к акккаунтам без прокси")
        self.auto_proxy.setChecked(True)
        fl2.addRow(self.auto_proxy)
        self.trust_device = QCheckBox(
            "Использовать device_id/user_agent из строки (если есть) — не генерировать заново")
        self.trust_device.setChecked(True)
        fl2.addRow(self.trust_device)
        v.addWidget(gb2)

        # buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Импортировать")
        bb.accepted.connect(self._do_import)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        self.btn_file.clicked.connect(self._load_file)
        self.btn_paste.clicked.connect(self._paste)

    def _load_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Файл аккаунтов",
                                            filter="Text/JSON (*.txt *.json *.csv);;All (*)")
        if p:
            self.text.setPlainText(Path(p).read_text("utf-8"))

    def _paste(self):
        from PyQt6.QtWidgets import QApplication
        self.text.setPlainText(QApplication.clipboard().text())

    def _do_import(self):
        from datetime import datetime as _dt
        lines = self.text.toPlainText().splitlines()
        added = 0
        skipped = 0
        errors = 0
        existing = set(self.db.list_logins()) if self.dedupe.isChecked() else set()

        # ← ЭТА СТРОКА КРИТИЧНА — определяет batch_name до цикла
        batch_name = self.batch_name.text().strip() or f"batch_{_dt.now():%Y-%m-%d_%H-%M}"

        error_details = []
        for line in lines:
            try:
                acc = AccountImporter.parse_line(line)
                if not acc or not acc.get("login") or not acc.get("password"):
                    continue
                if acc["login"] in existing:
                    skipped += 1
                    continue
                if not self.trust_device.isChecked():
                    acc.pop("user_agent", None)
                    acc.pop("device_id", None)
                    acc.pop("android_id", None)
                acc["import_batch"] = batch_name
                self.db.upsert_account(acc)
                existing.add(acc["login"])
                added += 1
            except Exception as e:
                errors += 1
                error_details.append(
                    f"{type(e).__name__}: {str(e)[:100]} | line preview: {line[:80]}"
                )

        # если есть ошибки — покажем первые 5 в консоль
        if error_details:
            print("\n=== Import errors (first 5) ===")
            for err in error_details[:5]:
                print(f"  {err}")

        self.imported_count = added
        QMessageBox.information(
            self, "Импорт завершён",
            f"Добавлено: {added}\nПропущено (дубли): {skipped}\nОшибок парсинга: {errors}"
        )
        self.accept()