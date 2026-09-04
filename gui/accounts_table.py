from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QAbstractItemView,
                             QMenu, QApplication, QInputDialog, QFileDialog, QMessageBox)
from PyQt6.QtGui import QKeySequence, QColor, QShortcut, QAction
from PyQt6.QtCore import Qt, QItemSelection, QItemSelectionModel
import json

class AccountsTable(QTableWidget):
    STATUS_COLORS = {
        "idle":    QColor(38, 40, 50),
        "running": QColor(46, 92, 55),
        "success": QColor(35, 100, 45),
        "error":   QColor(140, 45, 45),
        "banned":  QColor(90, 25, 25),
    }
    COLUMNS = ["№", "Аккаунт", "Пароль", "Email", "Прокси", "Устройство",
               "Платформа", "Пачка", "Статус", "Последняя ошибка",
               "Просмотры", "Лайки", "Подписчики"]

    def __init__(self):
        super().__init__(0, len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setColumnHidden(2, True)  # пароль скрыт по умолчанию

        # data storage: row → account dict
        self._accounts: dict[str, dict] = {}

        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all_visible)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_selected)
        QShortcut(QKeySequence("Ctrl+V"), self, self._paste_accounts)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+H"), self,
                  lambda: self.setColumnHidden(2, not self.isColumnHidden(2)))

    # ---------- data API ----------
    def add_account(self, acc: dict):
        was = self.isSortingEnabled()
        self.setSortingEnabled(False)
        r = self.rowCount()
        self.insertRow(r)
        login = acc.get("login", f"__unknown_{r}")
        self._accounts[login] = acc
        self._render_row(r, acc)
        self.setSortingEnabled(was)

    def get_account(self, row: int) -> dict:
        """Читает login из первой колонки (устойчиво к сортировке)."""
        it = self.item(row, 1)   # колонка "Аккаунт"
        if not it:
            return {}
        login = it.text()
        return self._accounts.get(login, {})

    def _render_row(self, r, acc):
        num_item = QTableWidgetItem()
        num_item.setData(Qt.ItemDataRole.DisplayRole, r + 1)
        self.setItem(r, 0, num_item)
        self.setItem(r, 1, QTableWidgetItem(acc.get("login", "")))
        self.setItem(r, 2, QTableWidgetItem(acc.get("password", "")))
        self.setItem(r, 3, QTableWidgetItem(acc.get("email", "")))
        proxy_val = acc.get("proxy", "") or ""
        proxy_item = QTableWidgetItem(proxy_val)
        proxy_item.setToolTip(proxy_val)   # полный прокси при наведении
        self.setItem(r, 4, proxy_item)
        self.setItem(r, 5, QTableWidgetItem(acc.get("device_summary", "auto")))
        self.setItem(r, 6, QTableWidgetItem(acc.get("platform", "auto")))
        self.setItem(r, 7, QTableWidgetItem(acc.get("import_batch") or ""))   # ← новая
        status = (acc.get("status") or "idle").lower()
        self.set_row_status(r, status, acc.get("last_error") or "")
        self.setItem(r, 10, QTableWidgetItem(str(acc.get("total_views") or "")))
        self.setItem(r, 11, QTableWidgetItem(str(acc.get("total_likes") or "")))
        self.setItem(r, 12, QTableWidgetItem(str(acc.get("followers") or "")))

    # ---------- menu ----------
    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("Запустить только выделенные\tF5", self._run_selected_signal)
        m.addAction("Копировать (login:pass:proxy)\tCtrl+C", self._copy_selected)
        m.addAction("Показать/скрыть пароли\tCtrl+H",
                    lambda: self.setColumnHidden(2, not self.isColumnHidden(2)))
        m.addSeparator()
        m.addAction("Назначить пачку выделенным…", self._assign_batch)
        m.addAction("Привязать прокси выделенным (только без прокси)", self._bind_selected)
        m.addAction("ПЕРЕ-привязать прокси выделенным (замена)", self._rebind_selected)
        m.addSeparator()
        m.addAction("Открыть в браузере (профиль)", self._open_in_browser)
        m.addAction("Сбросить статус", self._reset_status)
        m.addAction("Сбросить прокси у выделенных", self._clear_proxy_selected)
        m.addAction("Пересгенерировать устройство", self._regen_device)
        m.addSeparator()
        m.addAction("Экспорт выделенных (IAM txt)", self._export_iam)
        m.addAction("Экспорт с cookies (JSON)", self._export_json)
        m.addSeparator()
        m.addAction("Удалить\tDel", self._delete_selected)
        m.exec(self.viewport().mapToGlobal(pos))

    # ---------- операции ----------
    def _selected_rows(self):
        return sorted({i.row() for i in self.selectedIndexes()})

    def _delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        db = None
        p = self.parent()
        while p is not None:
            if hasattr(p, "db"):
                db = p.db
                break
            p = p.parent()

        # собираем логины ПЕРЕД удалением строк (индексы сдвинутся)
        logins_to_delete = []
        for r in rows:
            it = self.item(r, 1)
            if it:
                logins_to_delete.append(it.text())

        for r in reversed(rows):
            self.removeRow(r)
        for login in logins_to_delete:
            self._accounts.pop(login, None)
            if db:
                db.delete_account(login)

        # обновим нумерацию № (для видимого порядка)
        for r in range(self.rowCount()):
            it = self.item(r, 0)
            if it:
                from PyQt6.QtCore import Qt
                it.setData(Qt.ItemDataRole.DisplayRole, r + 1)
    def _select_all_visible(self):
        """Ctrl+A — выделяет ТОЛЬКО видимые строки (не скрытые фильтром)."""
        sm = self.selectionModel()
        sm.clearSelection()

        selection = QItemSelection()
        for r in range(self.rowCount()):
            if not self.isRowHidden(r):
                top_left = self.model().index(r, 0)
                bottom_right = self.model().index(r, self.columnCount() - 1)
                selection.select(top_left, bottom_right)

        sm.select(
            selection,
            QItemSelectionModel.SelectionFlag.Select |
            QItemSelectionModel.SelectionFlag.Rows
        )
    def _copy_selected(self):
        lines = []
        for r in self._selected_rows():
            a = self._accounts[r]
            line = f"{a['login']}:{a['password']}"
            if a.get("proxy"): line += f":{a['proxy']}"
            lines.append(line)
        QApplication.clipboard().setText("\n".join(lines))
    def _assign_batch(self):
        from PyQt6.QtWidgets import QInputDialog, QTableWidgetItem
        rows = self._selected_rows()
        if not rows:
            return
        name, ok = QInputDialog.getText(self, "Пачка", "Название пачки:")
        if not ok or not name.strip():
            return
        name = name.strip()

        db = None
        p = self.parent()
        while p is not None:
            if hasattr(p, "db"):
                db = p.db
                break
            p = p.parent()
        if not db:
            return

        for r in rows:
            acc = self.get_account(r)
            login = acc.get("login")
            if not login:
                continue
            db.conn.execute(
                "UPDATE accounts SET import_batch=? WHERE login=?",
                (name, login)
            )
            self._accounts[login]["import_batch"] = name
            self.setItem(r, 7, QTableWidgetItem(name))
        db.conn.commit()
    def _paste_accounts(self):
        # прокидывается в MainWindow — там доступ к БД
        # тут просто эмулируем
        from storage.importer import AccountImporter
        txt = QApplication.clipboard().text()
        for line in txt.splitlines():
            acc = AccountImporter.parse_line(line)
            if acc and acc.get("login"):
                self.add_account(acc)

    def _focus_search(self):
        # обрабатывается MainWindow — эмитим сигнал через parent
        pass

    def _run_selected_signal(self):
        # MainWindow слушает
        pass

    def _reset_status(self):
        for r in self._selected_rows():
            self.set_row_status(r, "idle", "")

    def _regen_device(self):
        from PyQt6.QtWidgets import QTableWidgetItem
        for r in self._selected_rows():
            acc = self.get_account(r)   # ← теперь через метод
            acc.pop("device_id", None)
            acc.pop("android_id", None)
            acc.pop("user_agent", None)
            self.setItem(r, 5, QTableWidgetItem("auto (regen)"))

    def _open_in_browser(self):
        import webbrowser
        for r in self._selected_rows():
            acc = self.get_account(r)
            if acc.get("login"):
                webbrowser.open(f"https://instagram.com/{acc['login']}")

    def _export_iam(self):
        p, _ = QFileDialog.getSaveFileName(self, "Экспорт", "accounts.txt", "*.txt")
        if not p: return
        lines = []
        for r in self._selected_rows() or range(self.rowCount()):
            a = self._accounts[r]
            line = f"{a['login']}:{a['password']}"
            if a.get("email"): line += f":{a['email']}:{a.get('email_password','')}"
            if a.get("proxy"): line += f":{a['proxy']}"
            lines.append(line)
        from pathlib import Path
        Path(p).write_text("\n".join(lines), "utf-8")

    def _export_json(self):
        p, _ = QFileDialog.getSaveFileName(self, "Экспорт JSON", "accounts.json", "*.json")
        if not p: return
        rows = [self._accounts[r] for r in (self._selected_rows() or range(self.rowCount()))]
        from pathlib import Path
        Path(p).write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), "utf-8")

    # ---------- статус ----------
    def set_row_status(self, row: int, status: str, error: str = ""):
        color = self.STATUS_COLORS.get(status, QColor(38, 40, 50))
        for col in range(self.columnCount()):
            it = self.item(row, col)
            if it: it.setBackground(color)
        dot_color = {"running": "#7bd88f", "success": "#7bd88f",
                     "error": "#ff6b6b", "banned": "#ff4a4a",
                     "idle": "#7a7d88"}.get(status, "#c0c0c0")
        it = QTableWidgetItem(f"● {status}")
        it.setForeground(QColor(dot_color))
        it.setBackground(color)
        self.setItem(row, 8, it)
        if error:
            e = QTableWidgetItem(error[:200])
            e.setBackground(color)
            e.setToolTip(error)
            self.setItem(row, 9, e)
    def _get_main_window(self):
        p = self.parent()
        while p is not None:
            if hasattr(p, "proxy_panel"):
                return p
            p = p.parent()
        return None

    def _bind_selected(self):
        mw = self._get_main_window()
        if not mw:
            return
        rows = self._selected_rows()
        accs = [self.get_account(r) for r in rows]
        accs = [a for a in accs if a.get("login")]
        mw.proxy_panel.bind_free_to(accs)
        # обновим отображение
        for r in rows:
            acc = self.get_account(r)
            proxy_val = acc.get("proxy", "") or ""
            it = QTableWidgetItem(proxy_val)
            it.setToolTip(proxy_val)
            self.setItem(r, 4, it)

    def _rebind_selected(self):
        from PyQt6.QtWidgets import QMessageBox
        mw = self._get_main_window()
        if not mw:
            return
        rows = self._selected_rows()
        if not rows:
            return
        reply = QMessageBox.question(
            self, "Пере-привязка",
            f"ЗАМЕНИТЬ прокси у {len(rows)} акков на новые из пула?\n"
            f"Старые прокси станут свободными."
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        accs = [self.get_account(r) for r in rows]
        accs = [a for a in accs if a.get("login")]
        mw.proxy_panel.rebind_to(accs, force=True)
        for r in rows:
            acc = self.get_account(r)
            proxy_val = acc.get("proxy", "") or ""
            it = QTableWidgetItem(proxy_val)
            it.setToolTip(proxy_val)
            self.setItem(r, 4, it)

    def _clear_proxy_selected(self):
        mw = self._get_main_window()
        db = mw.db if mw else None
        for r in self._selected_rows():
            acc = self.get_account(r)
            login = acc.get("login")
            old = acc.get("proxy")
            if not login:
                continue
            if db:
                db.conn.execute("UPDATE accounts SET proxy=NULL WHERE login=?", (login,))
                if old:
                    db.conn.execute("UPDATE proxies SET bound_to=NULL WHERE proxy=?", (old,))
            acc.pop("proxy", None)
            self.setItem(r, 4, QTableWidgetItem(""))
        if db:
            db.conn.commit()
