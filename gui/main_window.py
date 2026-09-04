from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QComboBox, QCheckBox, QLineEdit,
    QTextEdit, QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QSplitter, QGroupBox, QFormLayout, QProgressBar, QStatusBar,
    QToolBar, QMenuBar, QMenu, QApplication, QPlainTextEdit,
    QRadioButton, QButtonGroup, QSlider, QInputDialog
)
from PyQt6.QtGui import QAction, QIcon, QFont, QTextCursor, QColor
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
import asyncio, qasync, json, csv
from datetime import datetime
from pathlib import Path

from .accounts_table import AccountsTable
from .log_viewer import LogViewer
from .task_reels import ReelsUploadPanel
from .task_bio import BioChangePanel
from .task_stats import StatsPanel
from .task_avatar import AvatarPanel
from .proxy_panel import ProxyPanel
from .devices_panel import DevicesPanel
from .settings_panel import SettingsPanel
from .import_dialog import ImportDialog
from core.orchestrator import Orchestrator
from storage.db import DB
from storage.importer import AccountImporter


class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str, str)          # (level, msg)
    status_signal = pyqtSignal(int, str, str)  # (row, status, err)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReelsForge — Instagram Reels Uploader")
        self.resize(1600, 950)
        self.db = DB("data/accounts.db")
        self.orchestrator: Orchestrator | None = None
        self._current_task: asyncio.Task | None = None
        self._running_tasks: list = []
        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()
        self._load_accounts_from_db()
        self._apply_dark_theme()

    # -------------------- UI --------------------
    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        # Левая колонка — таблица аккаунтов + импорт
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)

        # Панель импорта
        import_bar = QHBoxLayout()
        self.btn_import = QPushButton("＋ Импорт аккаунтов (IAM/txt/json)")
        self.btn_import.setMinimumHeight(34)
        self.btn_paste = QPushButton("Вставить из буфера")
        self.btn_export = QPushButton("Экспорт выделенных")
        self.btn_clear = QPushButton("Очистить всё")
        for b in (self.btn_import, self.btn_paste, self.btn_export, self.btn_clear):
            import_bar.addWidget(b)
        import_bar.addStretch()

        self.lbl_counter = QLabel("Аккаунтов: 0 / Выбрано: 0")
        self.lbl_counter.setStyleSheet("font-weight:600;")
        import_bar.addWidget(self.lbl_counter)
        lv.addLayout(import_bar)

        # Фильтр
        filter_bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Фильтр по логину/прокси/статусу…  (Ctrl+F)")
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Все", "idle", "running", "alive",
                                     "success", "error", "banned",
                                     "dead", "suspended", "checkpoint"])
        self.filter_batch = QComboBox()
        self.filter_batch.setMinimumWidth(200)
        self.filter_batch.addItem("Все пачки")
        filter_bar.addWidget(QLabel("🔍"))
        filter_bar.addWidget(self.search, 1)
        filter_bar.addWidget(QLabel("Статус:"))
        filter_bar.addWidget(self.filter_status)
        filter_bar.addWidget(QLabel("Пачка:"))
        filter_bar.addWidget(self.filter_batch)
        lv.addLayout(filter_bar)

        # Таблица
        self.table = AccountsTable()
        lv.addWidget(self.table, 1)

        # Правая колонка — вкладки задач + лог
        right = QSplitter(Qt.Orientation.Vertical)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.reels_panel = ReelsUploadPanel()
        self.bio_panel = BioChangePanel()
        self.avatar_panel = AvatarPanel()
        self.stats_panel = StatsPanel()
        self.proxy_panel = ProxyPanel(self.db)
        self.devices_panel = DevicesPanel()
        self.settings_panel = SettingsPanel()

        self.tabs.addTab(self.reels_panel, "📹 Reels")
        self.tabs.addTab(self.bio_panel, "✏  Био")
        self.tabs.addTab(self.avatar_panel, "🖼  Аватар")
        self.tabs.addTab(self.stats_panel, "📊 Статистика")
        self.tabs.addTab(self.proxy_panel, "🌐 Прокси")
        self.tabs.addTab(self.devices_panel, "📱 Устройства")
        self.tabs.addTab(self.settings_panel, "⚙  Настройки")

        right.addWidget(self.tabs)

        # Логгер
        self.log = LogViewer()
        right.addWidget(self.log)
        right.setSizes([600, 300])

        # Splitter между таблицей и правой панелью
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(left)
        main_split.addWidget(right)
        main_split.setSizes([900, 700])
        root.addWidget(main_split)

        self.setCentralWidget(central)

    def _build_menu(self):
        mb = self.menuBar()

        file_m = mb.addMenu("&Файл")
        file_m.addAction("Импорт аккаунтов…\tCtrl+I", self._open_import)
        file_m.addAction("Экспорт…\tCtrl+E", self._export_accounts)
        file_m.addSeparator()
        file_m.addAction("Выход\tCtrl+Q", self.close)

        edit_m = mb.addMenu("&Правка")
        edit_m.addAction("Выделить всё видимое\tCtrl+A", self.table._select_all_visible)
        edit_m.addAction("Инвертировать выделение", self._invert_selection)
        edit_m.addAction("Снять выделение\tEsc", self.table.clearSelection)
        edit_m.addSeparator()
        edit_m.addAction("Удалить выделенные\tDel", self.table._delete_selected)
        edit_m.addAction("Удалить banned", self._delete_banned)
        edit_m.addAction("Удалить с ошибками", self._delete_errors)

        run_m = mb.addMenu("&Запуск")
        run_m.addAction("Запустить задачу на выделенных\tF5", self._run_current_task)
        run_m.addAction("Запустить на всех", self._run_all)
        run_m.addAction("Остановить\tF6", self._stop_task)

        help_m = mb.addMenu("&Помощь")
        help_m.addAction("О программе", self._about)

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(tb.iconSize() * 1)
        self.act_start = QAction("▶  Старт", self); self.act_start.setShortcut("F5")
        self.act_stop = QAction("■  Стоп", self);  self.act_stop.setShortcut("F6")
        self.act_stop.setEnabled(False)
        tb.addAction(self.act_start)
        tb.addAction(self.act_stop)
        tb.addSeparator()

        tb.addWidget(QLabel(" Потоков: "))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 500)
        self.threads_spin.setValue(70)
        self.threads_spin.setMinimumWidth(80)
        tb.addWidget(self.threads_spin)

        tb.addWidget(QLabel("  Платформа: "))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["mix (рандом)", "только Android", "только iOS"])
        self.platform_combo.setMinimumWidth(150)
        tb.addWidget(self.platform_combo)

        tb.addSeparator()
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(300)
        self.progress.setFormat("%v / %m  (%p%)")
        tb.addWidget(self.progress)

        self.addToolBar(tb)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.sb_stats = QLabel("готов")
        sb.addPermanentWidget(self.sb_stats)

    def _connect_signals(self):
        self.btn_import.clicked.connect(self._open_import)
        self.btn_paste.clicked.connect(self._paste_accounts)
        self.btn_export.clicked.connect(self._export_accounts)
        self.btn_clear.clicked.connect(self._clear_all)

        self.act_start.triggered.connect(self._run_current_task)
        self.act_stop.triggered.connect(self._stop_task)

        self.search.textChanged.connect(self._apply_filter)
        self.filter_status.currentTextChanged.connect(self._apply_filter)
        self.filter_batch.currentTextChanged.connect(self._apply_filter)

        self.table.itemSelectionChanged.connect(self._update_counter)

        self.log_signal.connect(self.log.append_line)
        self.status_signal.connect(self._on_status_update)

        # F5/F6
        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Escape"), self, self.table.clearSelection)

    # -------------------- Импорт / экспорт --------------------
    def _open_import(self):
        dlg = ImportDialog(self.db, parent=self)
        if dlg.exec():
            self._load_accounts_from_db()
            self._log("info", f"Импортировано аккаунтов: {dlg.imported_count}")

    def _paste_accounts(self):
        text = QApplication.clipboard().text()
        if not text.strip():
            return
        added = 0
        for line in text.splitlines():
            acc = AccountImporter.parse_line(line)
            if acc and acc.get("login") and acc.get("password"):
                self.db.upsert_account(acc)
                added += 1
        self._load_accounts_from_db()
        self._log("info", f"Из буфера добавлено: {added}")
    def closeEvent(self, event):
        try:
            self.reels_panel.save_settings()
            self.bio_panel.save_settings()
            self.settings_panel._save()  # уже есть у настроек
        except Exception:
            pass
        super().closeEvent(event)
    def _export_accounts(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            rows = [self.table.model().index(r, 0) for r in range(self.table.rowCount())]
        if not rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", "accounts.txt",
                                              "IAM txt (*.txt);;JSON (*.json);;CSV (*.csv)")
        if not path: return
        accs = [self.table.get_account(r.row()) for r in rows]
        if path.endswith(".json"):
            Path(path).write_text(json.dumps(accs, ensure_ascii=False, indent=2), "utf-8")
        elif path.endswith(".csv"):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(accs[0].keys()))
                w.writeheader(); w.writerows(accs)
        else:
            lines = []
            for a in accs:
                line = f"{a['login']}:{a['password']}"
                if a.get("email"): line += f":{a['email']}:{a.get('email_password','')}"
                if a.get("proxy"): line += f":{a['proxy']}"
                lines.append(line)
            Path(path).write_text("\n".join(lines), "utf-8")
        self._log("info", f"Экспортировано: {len(accs)} → {path}")

    def _clear_all(self):
        if QMessageBox.question(self, "Очистка",
                                "Удалить ВСЕ аккаунты из базы?") != QMessageBox.StandardButton.Yes:
            return
        self.db.clear_accounts()
        self.table.setRowCount(0)
        self._update_counter()

     # -------------------- Запуск задач --------------------
    def _run_current_task(self):
        tab_idx = self.tabs.currentIndex()
        tab_widget = self.tabs.currentWidget()

        if not hasattr(tab_widget, "get_task"):
            QMessageBox.warning(
                self,
                "!",
                "Эта вкладка не запускаемая (это менеджер, не задача)."
            )
            return

        action, params = tab_widget.get_task()
# 0. Проверка — не бежит ли уже такая же задача на этих же аккаунтах
        running_logins_this_action = set()
        for info in self._running_tasks:
            if info["action"] == action:
                # для этой же action собираем логины уже в работе
                orch = info["orch"]
                running_logins_this_action.update(orch._running_logins)

        if running_logins_this_action:
            # если пользователь пытается запустить ту же задачу пока предыдущая ещё бежит
            reply = QMessageBox.warning(
                self, "Задача уже выполняется",
                f"Задача '{action}' уже запущена на {len(running_logins_this_action)} аккаунтах.\n\n"
                f"Yes — запустить на НОВЫХ аккаунтах (уже бегущие пропущены)\n"
                f"No — отменить, дождаться завершения",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        if action is None:
            return

        # фильтр — только живые аккаунты
        def _is_workable(acc):
            s = (acc.get("status") or "").lower()
            return s not in ("suspended", "dead", "banned")

        # 1. Собираем аккаунты
        selected_rows = self.table.selectionModel().selectedRows()

        if selected_rows:
            pairs = [
                (r.row(), self.table.get_account(r.row()))
                for r in selected_rows
            ]
        else:
            reply = QMessageBox.question(
                self,
                "Запуск на всех?",
                f"Нет выделенных строк. Запустить на всех "
                f"{self.table.rowCount()} аккаунтах?"
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            pairs = [
                (r, self.table.get_account(r))
                for r in range(self.table.rowCount())
            ]

        # 2. Фильтруем мёртвых/забаненных
        before = len(pairs)

        pairs = [
            (r, a)
            for r, a in pairs
            if _is_workable(a)
        ]

        filtered_out = before - len(pairs)

        if filtered_out:
            reply = QMessageBox.question(
                self,
                "Мёртвые аккаунты",
                f"Отфильтровано {filtered_out} мёртвых/забаненных.\n"
                f"Продолжить с оставшимися {len(pairs)}?"
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        if not pairs:
            QMessageBox.information(
                self,
                "Пусто",
                "Нет живых аккаунтов для запуска."
            )
            return

        row_indices = [r for r, _ in pairs]
        accounts = [a for _, a in pairs]
        # ─── если set_bio — фильтруем тех у кого уже стоит именно это био ───
        if action == "set_bio":
            import hashlib
            bio_text = params.get("bio", "")
            target_hash = hashlib.md5(bio_text.encode("utf-8")).hexdigest()

            # опция «пропустить если уже стоит это био» (по умолчанию включено)
            skip_matching = params.get("skip_if_same_bio", True)

            if skip_matching:
                before = len(pairs)
                pairs = [
                    (r, a)
                    for r, a in pairs
                    if a.get("bio_hash") != target_hash
                ]

                skipped = before - len(pairs)

                if skipped:
                    reply = QMessageBox.question(
                        self,
                        "Уже стоит это био",
                        f"У {skipped} аккаунтов уже установлено ровно это био "
                        f"(по хэшу). Пропустить их?\n\n"
                        f"Yes — пропустить, задача пойдёт на {len(pairs)} аккаунтов\n"
                        f"No — переустановить всем (включая с таким же био)"
                    )

                    if reply != QMessageBox.StandardButton.Yes:
                        # откатываем фильтр, ставим все
                        pairs = [
                            (r, self.table.get_account(r))
                            for r in range(self.table.rowCount())
                        ]

                        pairs = [
                            (r, a)
                            for r, a in pairs
                            if not (
                                (a.get("status") or "").lower()
                                in ("suspended", "dead", "banned")
                            )
                        ]

        if not pairs:
            QMessageBox.information(
                self,
                "Пусто",
                "Нет аккаунтов для запуска."
            )
            return

        row_indices = [r for r, _ in pairs]
        accounts = [a for _, a in pairs]
        # 3. Прокси
        without_proxy = [
            a["login"]
            for a in accounts
            if not a.get("proxy")
        ]

        if without_proxy:
            reply = QMessageBox.question(
                self,
                "Аккаунты без прокси",
                f"{len(without_proxy)} аккаунтов без прокси. "
                f"Привязать из пула?"
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.proxy_panel.bind_free_to(accounts)
            else:
                return

        # 4. Параметры и запуск
        threads = self.threads_spin.value()
        platform_choice = self.platform_combo.currentIndex()

        params["platform"] = {
            0: None,
            1: "android",
            2: "ios"
        }[platform_choice]

        self._start_run(
            accounts,
            row_indices,
            action,
            params,
            threads
        )
    def _run_all(self):
        self.table.selectAll()
        self._run_current_task()

    def _start_run(self, accounts, row_indices, action, params, threads):
        # НЕ отключаем start! Разрешаем несколько параллельных задач.
        self.act_stop.setEnabled(True)
        self.progress.setMaximum(self.progress.maximum() + len(accounts))
        self._log("info", f"Запуск: {action}, потоков {threads}, "
                         f"аккаунтов {len(accounts)} (parallel tasks: {len(self._running_tasks) + 1})")

        orchestrator = Orchestrator(
            threads=threads,
            on_status=self._make_status_emitter(row_indices),
            db=self.db,
            settings=self._collect_settings() if hasattr(self, '_collect_settings') else {},
            stats_sink=self.stats_panel.add_result,
            geo=self.geo if hasattr(self, 'geo') else None,
        )

        loop = asyncio.get_event_loop()
        task = loop.create_task(orchestrator.run_batch(accounts, action, params))

        task_info = {"task": task, "orch": orchestrator, "action": action,
                     "count": len(accounts)}
        self._running_tasks.append(task_info)
        task.add_done_callback(lambda t: self._on_task_finished(task_info, t))

    def _make_status_emitter(self, row_indices):
        """Каждая задача имеет свой маппинг batch_idx → row_in_table."""
        row_map = dict(enumerate(row_indices))
        def emit(batch_idx, status, err):
            row = row_map.get(batch_idx, batch_idx)
            self.status_signal.emit(row, status, err)
        return emit

    def _on_task_finished(self, info, task):
        try:
            task.result()
        except asyncio.CancelledError:
            self._log("warn", f"Задача {info['action']} остановлена")
        except Exception as e:
            self._log("error", f"Задача {info['action']} упала: {e}")
        else:
            self._log("info", f"Задача {info['action']} завершена ({info['count']} акков)")

        self._running_tasks.remove(info)
        if not self._running_tasks:
            self.act_stop.setEnabled(False)
            self.progress.setValue(self.progress.maximum())

    def _emit_status(self, batch_idx, status, err):
        # batch_idx — индекс в переданном списке accounts
        row = self._row_map.get(batch_idx, batch_idx)
        self.status_signal.emit(row, status, err)

    def _on_status_update(self, row, status, err):
        self.table.set_row_status(row, status, err)
        self.log.append_status(row, self.table.get_account(row)["login"], status, err)
        self.progress.setValue(self.progress.value() + 1 if status in ("success","error","banned") else self.progress.value())

    def _on_run_finished(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            self._log("warn", "Задача остановлена пользователем")
        except Exception as e:
            self._log("error", f"Задача завершилась с исключением: {e}")
        else:
            self._log("info", "Задача завершена")
        self.act_start.setEnabled(True)
        self.act_stop.setEnabled(False)

    def _stop_task(self):
        """Стопит ВСЕ активные задачи."""
        for info in list(self._running_tasks):
            if not info["task"].done():
                info["task"].cancel()
        self._log("warn", "Все задачи остановлены")
    def _refresh_batch_filter(self):
        current = self.filter_batch.currentText()
        self.filter_batch.blockSignals(True)
        self.filter_batch.clear()
        self.filter_batch.addItem("Все пачки")
        batches = set()
        for r in range(self.table.rowCount()):
            acc = self.table.get_account(r)
            b = acc.get("import_batch")
            if b:
                batches.add(b)
        for b in sorted(batches, reverse=True):
            self.filter_batch.addItem(b)
        idx = self.filter_batch.findText(current)
        if idx >= 0:
            self.filter_batch.setCurrentIndex(idx)
        self.filter_batch.blockSignals(False)
    # -------------------- Прочие --------------------
    def _load_accounts_from_db(self):
        self.table.setRowCount(0)
        for acc in self.db.list_accounts():
            self.table.add_account(acc)
        self._update_counter()
        self._refresh_batch_filter()

    def _update_counter(self, *_):
        total = self.table.rowCount()
        visible = sum(1 for r in range(total) if not self.table.isRowHidden(r))
        sel = len(self.table.selectionModel().selectedRows())
        self.lbl_counter.setText(f"Всего: {total} / Видно: {visible} / Выбрано: {sel}")

    def _apply_filter(self):
        text = self.search.text().lower()
        status_f = self.filter_status.currentText()
        batch_f = self.filter_batch.currentText()

        for r in range(self.table.rowCount()):
            acc = self.table.get_account(r)

            # ищем в тексте всех колонок
            row_data = " ".join(
                (self.table.item(r, c).text() if self.table.item(r, c) else "")
                for c in range(self.table.columnCount())
            ).lower()

            # каждый фильтр опционален
            match_text = (text in row_data) if text else True
            match_status = (status_f == "Все") or (status_f in row_data)
            match_batch = (batch_f == "Все пачки") or ((acc.get("import_batch") or "") == batch_f)

            show = match_text and match_status and match_batch
            self.table.setRowHidden(r, not show)

    def _invert_selection(self):
        sm = self.table.selectionModel()
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r): continue
            idx = self.table.model().index(r, 0)
            if sm.isSelected(idx):
                sm.select(idx, sm.SelectionFlag.Deselect | sm.SelectionFlag.Rows)
            else:
                sm.select(idx, sm.SelectionFlag.Select | sm.SelectionFlag.Rows)

    def _delete_banned(self):
        rows = [r for r in range(self.table.rowCount())
                if "banned" in (self.table.item(r, 5).text() if self.table.item(r, 5) else "")]
        self._delete_rows(rows)

    def _delete_errors(self):
        rows = [r for r in range(self.table.rowCount())
                if "error" in (self.table.item(r, 5).text() if self.table.item(r, 5) else "")]
        self._delete_rows(rows)

    def _delete_rows(self, rows):
        for r in sorted(rows, reverse=True):
            login = self.table.item(r, 1).text()
            self.db.delete_account(login)
            self.table.removeRow(r)
        self._update_counter()

    def _log(self, level, msg):
        self.log_signal.emit(level, msg)

    def _about(self):
        QMessageBox.about(self, "О программе",
                          "ReelsForge v1.0\nСамописный uploader Reels\n"
                          "TLS-mimicry + human-timing + Bloks-flow\n")

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e1f26; color: #e5e5e5; }
            QTableWidget { background: #262832; alternate-background-color: #2c2e39;
                           gridline-color: #3a3d4a; selection-background-color: #3d6bff; }
            QHeaderView::section { background: #2d2f3a; color: #cfd0d5; padding: 6px;
                                   border: 0; border-bottom: 1px solid #3a3d4a; }
            QPushButton { background: #2d5cff; color: white; border: 0;
                          padding: 6px 12px; border-radius: 4px; }
            QPushButton:hover { background: #4271ff; }
            QPushButton:disabled { background: #3a3d4a; color: #7a7d88; }
            QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {
                background: #262832; border: 1px solid #3a3d4a; padding: 4px;
                border-radius: 3px; color: #e5e5e5; }
            QTabBar::tab { background: #262832; padding: 8px 14px; border: 0; }
            QTabBar::tab:selected { background: #2d5cff; color: white; }
            QMenu, QMenuBar { background: #262832; color: #e5e5e5; }
            QMenu::item:selected, QMenuBar::item:selected { background: #2d5cff; }
            QToolBar { background: #262832; border: 0; padding: 4px; spacing: 6px; }
            QProgressBar { background: #262832; border: 1px solid #3a3d4a; border-radius: 3px;
                           text-align: center; }
            QProgressBar::chunk { background: #2d5cff; }
            QStatusBar { background: #262832; }
            QGroupBox { border: 1px solid #3a3d4a; border-radius: 4px; margin-top: 12px;
                        padding-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)