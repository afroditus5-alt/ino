from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QLabel,
    QFormLayout, QPushButton, QHBoxLayout, QSpinBox,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QHeaderView
)
from PyQt6.QtCore import Qt
import csv
import json
from pathlib import Path


class StatsPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # ===== Что собирать =====
        gb = QGroupBox("Что собирать")
        fl = QFormLayout(gb)

        self.cb_followers = QCheckBox("Подписчики / подписки")
        self.cb_followers.setChecked(True)

        self.cb_views = QCheckBox("Суммарные просмотры Reels")
        self.cb_views.setChecked(True)

        self.cb_likes = QCheckBox("Лайки на Reels")
        self.cb_likes.setChecked(True)

        self.cb_comments = QCheckBox("Комментарии на Reels")
        self.cb_comments.setChecked(True)

        self.cb_reposts = QCheckBox("Репосты (share_count)")
        self.cb_reposts.setChecked(True)

        self.cb_perreel = QCheckBox("Разбивка по каждому Reels (медленнее)")

        for cb in (
            self.cb_followers,
            self.cb_views,
            self.cb_likes,
            self.cb_comments,
            self.cb_reposts,
            self.cb_perreel,
        ):
            fl.addRow(cb)

        self.reels_limit = QSpinBox()
        self.reels_limit.setRange(1, 50)
        self.reels_limit.setValue(12)
        fl.addRow("Последних Reels анализировать:", self.reels_limit)

        layout.addWidget(gb)

        # ===== Результаты =====
        gb2 = QGroupBox("Результаты")
        fl2 = QVBoxLayout(gb2)

        self.result_table = QTableWidget(0, 8)
        self.result_table.setHorizontalHeaderLabels([
            "Аккаунт", "Подписч.", "Подписки", "Reels",
            "Просмотры", "Лайки", "Комм.", "Репосты"
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        fl2.addWidget(self.result_table)

        # Кнопки
        h = QHBoxLayout()

        self.btn_export_csv = QPushButton("Экспорт CSV")
        self.btn_export_csv.clicked.connect(self._export_csv)

        self.btn_export_json = QPushButton("Экспорт JSON")
        self.btn_export_json.clicked.connect(self._export_json)

        self.btn_summary = QPushButton("Показать сводку")
        self.btn_summary.clicked.connect(self._summary)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.clicked.connect(self.clear_results)

        h.addWidget(self.btn_export_csv)
        h.addWidget(self.btn_export_json)
        h.addWidget(self.btn_summary)
        h.addWidget(self.btn_clear)
        h.addStretch()

        fl2.addLayout(h)
        layout.addWidget(gb2, 1)

    def add_result(self, login: str, stats: dict):
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        values = [
            login,
            str(stats.get("followers", "-")),
            str(stats.get("following", "-")),
            str(stats.get("reels_count", "-")),
            str(stats.get("total_views", "-")),
            str(stats.get("total_likes", "-")),
            str(stats.get("total_comments", "-")),
            str(stats.get("total_reposts", "-")),
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.result_table.setItem(row, col, item)

    def clear_results(self):
        self.result_table.setRowCount(0)

    def _export_csv(self):
        if self.result_table.rowCount() == 0:
            QMessageBox.information(self, "Пусто", "Нет данных для экспорта")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Сохранить CSV", "stats.csv", "CSV (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = [
                    self.result_table.horizontalHeaderItem(i).text()
                    for i in range(self.result_table.columnCount())
                ]
                writer.writerow(headers)

                for r in range(self.result_table.rowCount()):
                    row = []
                    for c in range(self.result_table.columnCount()):
                        item = self.result_table.item(r, c)
                        row.append(item.text() if item else "")
                    writer.writerow(row)

            QMessageBox.information(self, "Готово", f"Сохранено:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _export_json(self):
        if self.result_table.rowCount() == 0:
            QMessageBox.information(self, "Пусто", "Нет данных для экспорта")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Сохранить JSON", "stats.json", "JSON (*.json)")
        if not path:
            return

        try:
            cols = [
                self.result_table.horizontalHeaderItem(i).text()
                for i in range(self.result_table.columnCount())
            ]
            rows = []
            for r in range(self.result_table.rowCount()):
                row = {}
                for c in range(self.result_table.columnCount()):
                    item = self.result_table.item(r, c)
                    row[cols[c]] = item.text() if item else ""
                rows.append(row)

            Path(path).write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            QMessageBox.information(self, "Готово", f"Сохранено:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _summary(self):
        if self.result_table.rowCount() == 0:
            QMessageBox.information(self, "Пусто", "Нет данных")
            return

        total = {
            "followers": 0,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "reposts": 0,
        }

        for r in range(self.result_table.rowCount()):
            try:
                total["followers"] += int(self.result_table.item(r, 1).text() or 0)
                total["views"]     += int(self.result_table.item(r, 4).text() or 0)
                total["likes"]     += int(self.result_table.item(r, 5).text() or 0)
                total["comments"]  += int(self.result_table.item(r, 6).text() or 0)
                total["reposts"]   += int(self.result_table.item(r, 7).text() or 0)
            except Exception:
                pass

        QMessageBox.information(
            self,
            "Сводка",
            f"Аккаунтов: {self.result_table.rowCount()}\n\n"
            f"Всего подписчиков: {total['followers']:,}\n"
            f"Суммарные просмотры: {total['views']:,}\n"
            f"Лайки: {total['likes']:,}\n"
            f"Комментарии: {total['comments']:,}\n"
            f"Репосты: {total['reposts']:,}"
        )

    def get_task(self):
        return "collect_stats", {
            "collect": {
                "followers": self.cb_followers.isChecked(),
                "views":     self.cb_views.isChecked(),
                "likes":     self.cb_likes.isChecked(),
                "comments":  self.cb_comments.isChecked(),
                "reposts":   self.cb_reposts.isChecked(),
                "per_reel":  self.cb_perreel.isChecked(),
            },
            "reels_limit": self.reels_limit.value(),
        }