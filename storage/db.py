"""SQLite слой с полной схемой + миграция + универсальный upsert."""
import sqlite3
import json
import threading
from pathlib import Path
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    login TEXT PRIMARY KEY,
    sort_order INTEGER,           -- ← ДОБАВЬ
    import_batch TEXT,            -- ← ДОБАВЬ
    password TEXT NOT NULL,
    email TEXT, email_password TEXT,
    proxy TEXT, proxy_type TEXT,
    totp_secret TEXT,
    cookies_json TEXT,
    

    ig_version TEXT, ig_version_code TEXT,
    bloks_version TEXT, ig_app_id TEXT,

    platform TEXT,
    os_release TEXT, os_api TEXT,

    manufacturer TEXT, brand TEXT,
    model TEXT, device_name TEXT,
    board TEXT, hardware TEXT, cpu TEXT, gpu TEXT,
    chip_commercial TEXT,
    supported_abis TEXT,
    radio_version TEXT,

    resolution TEXT, dpi TEXT, scale TEXT,

    build_id TEXT, build_incremental TEXT,
    build_fingerprint TEXT, security_patch TEXT,

    locale TEXT, language TEXT, country TEXT,
    timezone_offset INTEGER,
    carrier_name TEXT, carrier_mcc TEXT, carrier_mnc TEXT,

    android_id TEXT, device_id TEXT,
    family_device_id TEXT, phone_id TEXT, advertising_id TEXT,
    bio_hash TEXT,
        bio_updated_at TIMESTAMP,

    user_agent TEXT,

    status TEXT DEFAULT 'idle',
    last_error TEXT,
    total_views INTEGER DEFAULT 0,
    total_likes INTEGER DEFAULT 0,
    followers INTEGER DEFAULT 0,
    following INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_status ON accounts(status);

CREATE TABLE IF NOT EXISTS proxies (
    proxy TEXT PRIMARY KEY,
    type TEXT, geo TEXT,
    status TEXT DEFAULT 'unknown',
    latency INTEGER DEFAULT -1,
    bound_to TEXT,
    checked_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reels_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT, media_id TEXT, code TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0
);
"""


class DB:
    def __init__(self, path: str):
        Path(path).parent.mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        """Догоняет колонки если БД старая."""
        with self._cursor() as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(accounts)")}
        new_cols = {
            "ig_version": "TEXT", "ig_version_code": "TEXT",
            "bloks_version": "TEXT", "ig_app_id": "TEXT",
            "os_release": "TEXT", "os_api": "TEXT",
            "manufacturer": "TEXT", "brand": "TEXT",
            "model": "TEXT", "device_name": "TEXT",
            "board": "TEXT", "hardware": "TEXT",
            "cpu": "TEXT", "gpu": "TEXT",
            "chip_commercial": "TEXT",
            "first_setup_done": "INTEGER DEFAULT 0",
            "avatar_hash": "TEXT",
            "avatar_updated_at": "TIMESTAMP",
            "supported_abis": "TEXT", "radio_version": "TEXT",
            "resolution": "TEXT", "dpi": "TEXT", "scale": "TEXT",
            "build_id": "TEXT", "build_incremental": "TEXT",
            "build_fingerprint": "TEXT", "security_patch": "TEXT",
            "language": "TEXT", "country": "TEXT",
            "timezone_offset": "INTEGER",
            "carrier_name": "TEXT", "carrier_mcc": "TEXT", "carrier_mnc": "TEXT",
            "family_device_id": "TEXT", "phone_id": "TEXT",
            "bio_hash": "TEXT",
            "bio_updated_at": "TIMESTAMP",
            "sort_order": "INTEGER",
            "import_batch": "TEXT",
            "advertising_id": "TEXT",
        }
        with self._cursor() as c:
            for col, typ in new_cols.items():
                if col not in cols:
                    try:
                        c.execute(f"ALTER TABLE accounts ADD COLUMN {col} {typ}")
                    except sqlite3.OperationalError:
                        pass

    @contextmanager
    def _cursor(self):
        with self._lock:
            cur = self.conn.cursor()
            try:
                yield cur
            finally:
                cur.close()
    def mark_setup_done(self, login: str):
        with self._cursor() as c:
            c.execute(
                "UPDATE accounts SET first_setup_done=1 WHERE login=?",
                (login,)
            )
    # ============================================================ accounts
    def upsert_account(self, acc: dict):
        """Универсальный upsert. sort_order присваивается только при INSERT."""
        import json as _json

        def _safe_json(obj):
            """JSON dump с автоконвертацией set → list."""
            return _json.dumps(obj, default=lambda o:
                               list(o) if isinstance(o, (set, frozenset))
                               else str(o))

        acc = dict(acc)
        if acc.get("cookies") and not acc.get("cookies_json"):
            acc["cookies_json"] = _safe_json(acc.pop("cookies"))
        # supported_abis может быть list ИЛИ set — обе нормализуем
        sa = acc.get("supported_abis")
        if isinstance(sa, (list, set, frozenset)):
            acc["supported_abis"] = _safe_json(sa)

        # доп. защита — если в acc есть ЛЮБЫЕ set-значения, конвертим в list
        for k, v in list(acc.items()):
            if isinstance(v, (set, frozenset)):
                acc[k] = list(v)

        with self._cursor() as c:
            known = {r[1] for r in c.execute("PRAGMA table_info(accounts)")}

            # sort_order = следующий по счёту, только если аккаунта ещё нет
            exists = c.execute("SELECT 1 FROM accounts WHERE login=?",
                               (acc["login"],)).fetchone()
            if not exists and "sort_order" in known:
                max_order = c.execute("SELECT COALESCE(MAX(sort_order), 0) FROM accounts").fetchone()[0]
                acc["sort_order"] = max_order + 1

        payload = {k: v for k, v in acc.items() if k in known}
        if "login" not in payload or "password" not in payload:
            raise ValueError("login and password required")

        cols = list(payload.keys())
        placeholders = ",".join(f":{k}" for k in cols)
        # ВАЖНО: sort_order и import_batch в UPDATE не трогаем — сохраняем как было
        protected = {"sort_order", "import_batch"}
        updates = ",".join(f"{k}=excluded.{k}" for k in cols
                           if k != "login" and k not in protected)
        sql = (f"INSERT INTO accounts ({','.join(cols)}) VALUES ({placeholders}) "
               f"ON CONFLICT(login) DO UPDATE SET {updates}, "
               f"updated_at=CURRENT_TIMESTAMP")
        with self._cursor() as c:
            c.execute(sql, payload)

    def list_accounts(self) -> list[dict]:
        with self._cursor() as c:
            rows = c.execute(
                "SELECT * FROM accounts "
                "ORDER BY COALESCE(sort_order, 999999999), login"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("cookies_json"):
                try:
                    d["cookies"] = json.loads(d["cookies_json"])
                except Exception:
                    d["cookies"] = None
            if d.get("supported_abis"):
                try:
                    d["supported_abis"] = json.loads(d["supported_abis"])
                except Exception:
                    pass
            out.append(d)
        return out

    def list_logins(self) -> list[str]:
        with self._cursor() as c:
            return [r["login"] for r in c.execute("SELECT login FROM accounts")]

    def delete_account(self, login: str):
        with self._cursor() as c:
            c.execute("DELETE FROM accounts WHERE login=?", (login,))

    def clear_accounts(self):
        with self._cursor() as c:
            c.execute("DELETE FROM accounts")

    def set_status(self, login: str, status: str, err: str = ""):
        with self._cursor() as c:
            c.execute(
                "UPDATE accounts SET status=?, last_error=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE login=?", (status, err, login))

    def update_stats(self, login: str, followers: int, views: int, likes: int):
        with self._cursor() as c:
            c.execute(
                "UPDATE accounts SET followers=?, total_views=?, total_likes=? "
                "WHERE login=?", (followers, views, likes, login))

    def save_cookies(self, login: str, cookies: dict):
        # защита от set-значений
        safe = {k: (list(v) if isinstance(v, (set, frozenset)) else v)
                for k, v in cookies.items()}
        data = json.dumps(safe, default=lambda o:
                          list(o) if isinstance(o, (set, frozenset)) else str(o))
        with self._cursor() as c:
            c.execute("UPDATE accounts SET cookies_json=? WHERE login=?",
                      (data, login))

    def set_bio_hash(self, login: str, bio_hash: str):
        with self._cursor() as c:
            c.execute(
                "UPDATE accounts SET bio_hash=?, bio_updated_at=CURRENT_TIMESTAMP "
                "WHERE login=?", (bio_hash, login)
            )
    # ============================================================ proxies
    def upsert_proxy(self, p: dict):
        with self._cursor() as c:
            c.execute("""
                INSERT INTO proxies (proxy, type, geo, status, latency)
                VALUES (:proxy, :type, :geo, :status, :latency)
                ON CONFLICT(proxy) DO UPDATE SET
                    type=excluded.type, geo=COALESCE(excluded.geo, geo)
            """, {
                "proxy": p["proxy"], "type": p.get("type", "http"),
                "geo": p.get("geo"), "status": p.get("status", "unknown"),
                "latency": p.get("latency", -1),
            })

    def list_proxies(self) -> list[dict]:
        with self._cursor() as c:
            return [dict(r) for r in c.execute("SELECT * FROM proxies")]

    def delete_proxy(self, proxy: str):
        with self._cursor() as c:
            c.execute("DELETE FROM proxies WHERE proxy=?", (proxy,))

    def clear_proxies(self):
        with self._cursor() as c:
            c.execute("DELETE FROM proxies")

    def update_proxy_status(self, proxy: str, status: str, latency: int):
        with self._cursor() as c:
            c.execute(
                "UPDATE proxies SET status=?, latency=?, checked_at=CURRENT_TIMESTAMP "
                "WHERE proxy=?", (status, latency, proxy))

    def bind_proxy(self, proxy: str, login: str):
        with self._cursor() as c:
            c.execute("UPDATE proxies SET bound_to=? WHERE proxy=?", (login, proxy))

    def get_free_proxy(self) -> str | None:
        with self._cursor() as c:
            r = c.execute(
                "SELECT proxy FROM proxies WHERE status='ok' "
                "AND (bound_to IS NULL OR bound_to='') "
                "ORDER BY latency ASC LIMIT 1").fetchone()
        return r["proxy"] if r else None

    # ============================================================ uploads
    def log_upload(self, login: str, media_id: str, code: str):
        with self._cursor() as c:
            c.execute("INSERT INTO reels_uploads (login, media_id, code) "
                      "VALUES (?,?,?)", (login, media_id, code))
