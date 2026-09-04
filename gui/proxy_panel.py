from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLabel, QFileDialog,
                             QGroupBox, QCheckBox, QSpinBox, QFormLayout, QMessageBox,
                             QAbstractItemView, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QShortcut, QKeySequence
import asyncio
from pathlib import Path


class ProxyPanel(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        v = QVBoxLayout(self)

        info = QLabel("Пул прокси. Поддержка http/https/socks5. При бане/чекпоинте "
                      "аккаунт получает новую прокси автоматически (если включено).")
        info.setWordWrap(True)
        v.addWidget(info)

        # действия
        h = QHBoxLayout()
        self.btn_import = QPushButton("＋ Импорт из файла")
        self.btn_paste = QPushButton("Вставить из буфера")
        self.btn_check = QPushButton("Проверить рабочие (async)")
        self.btn_del_bad = QPushButton("Удалить нерабочие")
        self.btn_del_free = QPushButton("Удалить свободные (не привязанные)")
        self.btn_del_selected = QPushButton("Удалить выделенные")
        self.btn_del_all = QPushButton("Очистить пул")
        for b in (self.btn_import, self.btn_paste, self.btn_check,
                  self.btn_del_bad, self.btn_del_free,
                  self.btn_del_selected, self.btn_del_all):
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)

        # опции чекера
        gb = QGroupBox("Проверка")
        fl = QFormLayout(gb)
        self.check_url = QLabel("i.instagram.com/api/v1/qe/sync/  "
                                "(проверка что домен доступен через прокси)")
        fl.addRow("Тестовый URL:", self.check_url)
        self.check_timeout = QSpinBox()
        self.check_timeout.setRange(3, 60)
        self.check_timeout.setValue(10)
        fl.addRow("Таймаут, сек:", self.check_timeout)
        self.check_threads = QSpinBox()
        self.check_threads.setRange(1, 200)
        self.check_threads.setValue(50)
        fl.addRow("Потоков чекера:", self.check_threads)
        v.addWidget(gb)

        # таблица прокси
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Прокси", "Тип", "Гео", "Задержка (мс)", "Статус", "Привязан к"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        v.addWidget(self.table, 1)

        # горячие клавиши
        QShortcut(QKeySequence("Ctrl+A"), self.table, self.table.selectAll)
        QShortcut(QKeySequence("Delete"), self.table, self._delete_selected)
        QShortcut(QKeySequence("Ctrl+C"), self.table, self._copy_selected)

        # сигналы
        self.btn_import.clicked.connect(self._import_file)
        self.btn_paste.clicked.connect(self._paste)
        self.btn_check.clicked.connect(self._start_check)
        self.btn_del_bad.clicked.connect(self._delete_bad)
        self.btn_del_free.clicked.connect(self._delete_free)     # ← НОВЫЙ
        self.btn_del_selected.clicked.connect(self._delete_selected)
        self.btn_del_all.clicked.connect(self._delete_all)

        self._load()

    # ---------- data ----------
    def _load(self):
        self.table.setRowCount(0)
        for p in self.db.list_proxies():
            self._add_row(p)

    def _add_row(self, p: dict):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(p["proxy"]))
        self.table.setItem(r, 1, QTableWidgetItem(p.get("type", "http")))
        self.table.setItem(r, 2, QTableWidgetItem(p.get("geo", "?")))
        self.table.setItem(r, 3, QTableWidgetItem(str(p.get("latency", "-"))))
        status = p.get("status", "unknown")
        it = QTableWidgetItem(status)
        it.setForeground(QColor(
            {"ok": "#7bd88f", "bad": "#ff6b6b", "unknown": "#c0c0c0"}.get(status, "#c0c0c0")))
        self.table.setItem(r, 4, it)
        self.table.setItem(r, 5, QTableWidgetItem(p.get("bound_to") or ""))

    # ---------- import ----------
    def _import_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Прокси-файл", filter="*.txt")
        if not p:
            return
        added = 0
        for line in Path(p).read_text("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            proxy = self._normalize(line)
            if proxy:
                self.db.upsert_proxy({"proxy": proxy, "type": self._detect_type(proxy)})
                added += 1
        self._load()
        QMessageBox.information(self, "OK", f"Импортировано: {added}")

    def _paste(self):
        txt = QApplication.clipboard().text()
        if not txt:
            return
        added = 0
        for line in txt.splitlines():
            line = line.strip()
            if not line:
                continue
            proxy = self._normalize(line)
            if proxy:
                self.db.upsert_proxy({"proxy": proxy, "type": self._detect_type(proxy)})
                added += 1
        self._load()
        QMessageBox.information(self, "OK", f"Из буфера: {added}")

    @staticmethod
    def _normalize(s: str) -> str | None:
        """Принимает host:port:user:pass ИЛИ user:pass@host:port ИЛИ ip:port и т.д."""
        import re
        s = s.strip()
        scheme = "http"
        for pfx in ("http://", "https://", "socks5://", "socks4://"):
            if s.startswith(pfx):
                scheme = pfx.rstrip("://")
                s = s[len(pfx):]
                break
        if "@" in s:
            return f"{scheme}://{s}"

        parts = s.split(":")

        # host = либо IP, либо hostname (буквы/цифры/дефисы/точки)
        host_re = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-.]*[a-zA-Z0-9]$")

        if len(parts) == 2:
            # host:port
            if parts[1].isdigit() and host_re.match(parts[0]):
                return f"{scheme}://{s}"
            return None

        if len(parts) == 4:
            # host:port:user:pass  ← Byteful, IPRoyal, Bright Data
            if host_re.match(parts[0]) and parts[1].isdigit():
                host, port, u, pw = parts
                return f"{scheme}://{u}:{pw}@{host}:{port}"
            # user:pass:host:port
            if host_re.match(parts[2]) and parts[3].isdigit():
                u, pw, host, port = parts
                return f"{scheme}://{u}:{pw}@{host}:{port}"

        return None

    @staticmethod
    def _detect_type(p: str) -> str:
        return p.split("://", 1)[0]

    # ---------- delete ----------
    def _delete_selected(self):
        """Удаляет выделенные строки. Привязанные к аккаунтам — с предупреждением."""
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "!", "Ничего не выделено")
            return

        # проверяем какие из выделенных привязаны
        bound_map = {p["proxy"]: p.get("bound_to")
                     for p in self.db.list_proxies()}
        bound_selected = []
        for r in rows:
            proxy = self.table.item(r, 0).text()
            if bound_map.get(proxy):
                bound_selected.append(proxy)

        if bound_selected:
            reply = QMessageBox.question(
                self, "Внимание",
                f"{len(bound_selected)} из {len(rows)} выделенных прокси "
                f"уже привязаны к аккаунтам.\n"
                f"Удаление отвяжет их — аккаунты останутся без прокси.\n\n"
                f"Продолжить?"
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for r in rows:
            proxy = self.table.item(r, 0).text()
            self.db.delete_proxy(proxy)
            # снимаем прокси у аккаунтов
            self.db.conn.execute(
                "UPDATE accounts SET proxy=NULL WHERE proxy=?", (proxy,)
            )
            self.db.conn.commit()
            self.table.removeRow(r)

        QMessageBox.information(self, "OK", f"Удалено: {len(rows)}")

    def _delete_bad(self):
        for r in range(self.table.rowCount() - 1, -1, -1):
            if self.table.item(r, 4).text() == "bad":
                self.db.delete_proxy(self.table.item(r, 0).text())
                self.table.removeRow(r)

    def _delete_all(self):
        if QMessageBox.question(self, "?", "Очистить весь пул прокси?") != QMessageBox.StandardButton.Yes:
            return
        self.db.clear_proxies()
        self.table.setRowCount(0)

    def _copy_selected(self):
        lines = [self.table.item(r, 0).text()
                 for r in sorted({i.row() for i in self.table.selectedIndexes()})]
        QApplication.clipboard().setText("\n".join(lines))
    def _delete_free(self):
        """Удаляет прокси без bound_to. Также сбрасывает proxy у аккаунтов
        которые на них ссылаются (осиротевших чинит)."""
        free_proxies = [
            p["proxy"] for p in self.db.list_proxies()
            if not p.get("bound_to")
        ]
        # ещё проверяем: возможно acc.proxy ссылается на "свободный" прокси
        # без bound_to — это ошибка синхронизации, лечим при удалении
        if not free_proxies:
            QMessageBox.information(self, "OK", "Нет свободных прокси")
            return
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить {len(free_proxies)} свободных прокси?\n"
            f"Также сброшу proxy у аккаунтов на них ссылающихся."
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        c = self.db.conn
        cleared_accs = 0
        for p in free_proxies:
            # если какой-то акк на него ссылается — сбросим
            r = c.execute(
                "UPDATE accounts SET proxy=NULL WHERE proxy=?", (p,)
            )
            cleared_accs += r.rowcount
            self.db.delete_proxy(p)
        c.commit()

        self._load()
        QMessageBox.information(
            self, "OK",
            f"Удалено прокси: {len(free_proxies)}\n"
            f"Сброшено привязок у аккаунтов: {cleared_accs}"
        )
    # ---------- check ----------
    def _start_check(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._run_check())

    async def _run_check(self):
        """Проверка + определение гео → сохраняем оба в БД."""
        from curl_cffi.requests import AsyncSession
        import time as t
        from core.geo import GeoResolver

        geo = GeoResolver()
        sem = asyncio.Semaphore(self.check_threads.value())
        timeout = self.check_timeout.value()

        async def check_one(row):
            proxy = self.table.item(row, 0).text()
            async with sem:
                start = t.monotonic()
                # 1. ping
                ok = False
                try:
                    async with AsyncSession(
                        impersonate="chrome131_android",
                        proxies={"http": proxy, "https": proxy},
                        timeout=timeout,
                    ) as s:
                        r = await s.get("https://i.instagram.com/api/v1/qe/sync/")
                        ok = r.status_code in (200, 400, 403, 405)
                    latency = int((t.monotonic() - start) * 1000)
                except Exception:
                    latency = -1

                status = "ok" if ok else "bad"
                self._update_row_status(row, status, latency)

                # 2. если рабочий — определяем гео и сохраняем
                if ok:
                    try:
                        country, _ = await geo.resolve(proxy)
                        # обновим колонку "Гео" в таблице
                        from PyQt6.QtWidgets import QTableWidgetItem
                        self.table.setItem(row, 2, QTableWidgetItem(country or "?"))
                        # и в БД
                        self.db.conn.execute(
                            "UPDATE proxies SET geo=? WHERE proxy=?",
                            (country or "?", proxy)
                        )
                        self.db.conn.commit()
                    except Exception:
                        pass

        await asyncio.gather(*[check_one(r) for r in range(self.table.rowCount())])
        QMessageBox.information(self, "OK", "Проверка + гео завершены")

    def _update_row_status(self, row, status, latency):
        it = QTableWidgetItem(status)
        it.setForeground(QColor({"ok": "#7bd88f", "bad": "#ff6b6b"}.get(status, "#c0c0c0")))
        self.table.setItem(row, 4, it)
        self.table.setItem(row, 3, QTableWidgetItem(str(latency)))
        proxy = self.table.item(row, 0).text()
        self.db.update_proxy_status(proxy, status, latency)

    # ---------- используется MainWindow ----------
    def bind_free_to(self, accounts: list[dict]):
        """
        Умная привязка с учётом гео:
          1) Прокси из страны аккаунта, не занятый другим → приоритет
          2) Прокси из страны аккаунта, любой (если свободных нет)
          3) Прокси из US/GB/CA/AU не занятый
          4) Любой не занятый
          5) Любой (даже уже занятый)
        """
        import random

        # все живые прокси (не bad)
        all_p = [p for p in self.db.list_proxies() if p.get("status") != "bad"]
        if not all_p:
            return

        # группируем по гео
        by_country: dict[str, list[dict]] = {}
        for p in all_p:
            geo = (p.get("geo") or "?").upper()
            by_country.setdefault(geo, []).append(p)

        # какие прокси уже привязаны
        used = {p["proxy"] for p in all_p if p.get("bound_to")}

        english_fallback = ("US", "GB", "CA", "AU", "IE", "NZ")

        def _pick(target_country: str) -> str | None:
            tc = (target_country or "US").upper()

            # 1. своя страна, не занятый
            pool = [p for p in by_country.get(tc, []) if p["proxy"] not in used]
            if pool:
                return random.choice(pool)["proxy"]

            # 2. своя страна, любой (даже занятый)
            pool = by_country.get(tc, [])
            if pool:
                return random.choice(pool)["proxy"]

            # 3. английский регион, не занятый
            pool = []
            for c in english_fallback:
                pool.extend(p for p in by_country.get(c, []) if p["proxy"] not in used)
            if pool:
                return random.choice(pool)["proxy"]

            # 4. любой не занятый
            pool = [p for p in all_p if p["proxy"] not in used]
            if pool:
                return random.choice(pool)["proxy"]

            # 5. любой
            return random.choice(all_p)["proxy"]

        # раздаём
        assigned = 0
        for acc in accounts:
            if acc.get("proxy"):
                continue
            target = acc.get("country") or "US"
            chosen = _pick(target)
            if not chosen:
                continue
            acc["proxy"] = chosen
            self.db.upsert_account(acc)
            self.db.bind_proxy(chosen, acc["login"])
            used.add(chosen)
            assigned += 1

        self._load()
        QMessageBox.information(
            self, "OK",
            f"Привязано {assigned} акков к прокси (с учётом гео)"
        )
    def rebind_to(self, accounts: list[dict], force: bool = False):
        """
        Как bind_free_to, но с force=True перепривязывает даже те у кого уже есть прокси.
        Освобождает старые прокси перед новой привязкой.
        """
        import random

        all_p = [p for p in self.db.list_proxies() if p.get("status") != "bad"]
        if not all_p:
            QMessageBox.warning(self, "!", "В пуле нет живых прокси")
            return

        by_country: dict[str, list[dict]] = {}
        for p in all_p:
            geo = (p.get("geo") or "?").upper()
            by_country.setdefault(geo, []).append(p)

        used = {p["proxy"] for p in all_p if p.get("bound_to")}
        english_fallback = ("US", "GB", "CA", "AU", "IE", "NZ")

        def _pick(target_country: str) -> str | None:
            tc = (target_country or "US").upper()
            pool = [p for p in by_country.get(tc, []) if p["proxy"] not in used]
            if pool: return random.choice(pool)["proxy"]
            pool = by_country.get(tc, [])
            if pool: return random.choice(pool)["proxy"]
            pool = []
            for c in english_fallback:
                pool.extend(p for p in by_country.get(c, []) if p["proxy"] not in used)
            if pool: return random.choice(pool)["proxy"]
            pool = [p for p in all_p if p["proxy"] not in used]
            if pool: return random.choice(pool)["proxy"]
            return random.choice(all_p)["proxy"]

        assigned = 0
        for acc in accounts:
            if acc.get("proxy") and not force:
                continue

            # освобождаем старый прокси если был
            old = acc.get("proxy")
            if old:
                self.db.conn.execute(
                    "UPDATE proxies SET bound_to=NULL WHERE proxy=?", (old,)
                )
                used.discard(old)

            target = acc.get("country") or "US"
            chosen = _pick(target)
            if not chosen:
                continue

            acc["proxy"] = chosen
            self.db.upsert_account(acc)
            self.db.bind_proxy(chosen, acc["login"])
            used.add(chosen)
            assigned += 1

        self.db.conn.commit()
        self._load()
        QMessageBox.information(
            self, "OK", f"Пере-привязано: {assigned}"
        )