"""
GeoResolver без MaxMind. Три бесплатных провайдера с fallback:
1) ip-api.com     (45 rpm на IP, идём через прокси = per-proxy budget)
2) ipwho.is       (без лимитов, HTTPS)
3) freeipapi.com  (без лимитов, HTTPS)
4) Оффлайн: страна → типичная TZ (если сеть не отвечает)
"""

import asyncio, sqlite3, time, random
from pathlib import Path
from urllib.parse import urlparse

# Оффлайн-таблица: страна → типичный UTC-оффсет столицы (в секундах)
# Используется только когда все API не ответили.
COUNTRY_TZ_FALLBACK = {
    "US": -18000, "CA": -18000, "MX": -21600, "BR": -10800, "AR": -10800,
    "CO": -18000, "CL": -14400, "PE": -18000, "VE": -14400,
    "GB":     0,  "IE":     0,  "PT":     0,
    "DE":  3600,  "FR":  3600,  "ES":  3600,  "IT":  3600,  "NL":  3600,
    "PL":  3600,  "SE":  3600,  "NO":  3600,  "DK":  3600,  "BE":  3600,
    "CH":  3600,  "AT":  3600,  "CZ":  3600,  "HU":  3600,
    "FI":  7200,  "GR":  7200,  "RO":  7200,  "BG":  7200,  "UA":  7200,
    "IL":  7200,  "EG":  7200,
    "TR": 10800,  "RU": 10800,  "SA": 10800,  "KE": 10800,  "IQ": 10800,
    "IR": 12600,
    "AE": 14400,  "AZ": 14400,
    "PK": 18000,  "IN": 19800,
    "TH": 25200,  "VN": 25200,  "ID": 25200,
    "CN": 28800,  "MY": 28800,  "PH": 28800,  "TW": 28800, "SG": 28800,
    "JP": 32400,  "KR": 32400,
    "AU": 36000,  "NZ": 43200,
    "ZA":  7200,  "NG":  3600,  "MA":  3600,  "DZ":  3600,
}


class GeoResolver:
    def __init__(self, db_path: str = "data/geo_cache.db",
                 mmdb_path: str | None = None):
        Path(db_path).parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS geo_cache (
            ip TEXT PRIMARY KEY, country TEXT, tz_offset INTEGER,
            checked_at INTEGER)""")
        self.conn.commit()

        self.mmdb = None
        if mmdb_path and Path(mmdb_path).exists():
            try:
                import geoip2.database
                self.mmdb = geoip2.database.Reader(mmdb_path)
                print(f"[geo] mmdb loaded: {mmdb_path}")
            except Exception as e:
                print(f"[geo] mmdb load failed: {e}, using API fallback")

    @staticmethod
    def _extract_ip(proxy: str) -> str:
        u = urlparse(proxy)
        return u.hostname or ""

    async def resolve(self, proxy: str) -> tuple[str, int]:
        if not proxy or not isinstance(proxy, str):
            return "US", -18000
        ip = self._extract_ip(proxy)

        # 1. cache
        row = self.conn.execute(
            "SELECT country, tz_offset FROM geo_cache WHERE ip=?", (ip,)).fetchone()
        if row:
            return row[0], row[1]

        # 2. mmdb (только если файл есть)
        if self.mmdb:
            country, offset = self._resolve_mmdb(ip)
            if country:
                self._cache(ip, country, offset)
                return country, offset

        # 3. API fallback — три провайдера, случайный порядок
        providers = [self._api_ipapi, self._api_ipwho, self._api_freeipapi]
        random.shuffle(providers)
        for fn in providers:
            try:
                country, offset = await fn(proxy)
                if country:
                    self._cache(ip, country, offset)
                    return country, offset
            except Exception:
                continue

        # 4. Совсем никак — US default
        self._cache(ip, "US", -18000)
        return "US", -18000

    def _resolve_mmdb(self, ip: str) -> tuple[str | None, int]:
        try:
            r = self.mmdb.city(ip)
            country = r.country.iso_code or "US"
            tz_name = r.location.time_zone or "UTC"
            import pytz
            tz = pytz.timezone(tz_name)
            offset = int(tz.utcoffset(None).total_seconds())
            return country, offset
        except Exception:
            return None, 0

    async def _api_ipapi(self, proxy: str) -> tuple[str, int]:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome131",
                                proxies={"http": proxy, "https": proxy},
                                timeout=10) as s:
            r = await s.get("http://ip-api.com/json/?fields=countryCode,offset")
            j = r.json()
            return j["countryCode"], int(j.get("offset", 0))

    async def _api_ipwho(self, proxy: str) -> tuple[str, int]:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome131",
                                proxies={"http": proxy, "https": proxy},
                                timeout=10) as s:
            r = await s.get("https://ipwho.is/?fields=country_code,timezone")
            j = r.json()
            # timezone.utc = "UTC+03:00"
            tz_str = j["timezone"].get("utc", "UTC+00:00")
            sign = -1 if "-" in tz_str else 1
            hm = tz_str.replace("UTC", "").replace("+", "").replace("-", "")
            h, m = map(int, hm.split(":"))
            offset = sign * (h * 3600 + m * 60)
            return j["country_code"], offset

    async def _api_freeipapi(self, proxy: str) -> tuple[str, int]:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome131",
                                proxies={"http": proxy, "https": proxy},
                                timeout=10) as s:
            r = await s.get("https://freeipapi.com/api/json")
            j = r.json()
            # timeZone = "+03:00"
            tz_str = j.get("timeZone", "+00:00")
            sign = -1 if tz_str.startswith("-") else 1
            hm = tz_str.lstrip("+-")
            h, m = map(int, hm.split(":"))
            offset = sign * (h * 3600 + m * 60)
            return j["countryCode"], offset

    def _cache(self, ip: str, country: str, offset: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO geo_cache VALUES (?,?,?,?)",
            (ip, country, offset, int(time.time())))
        self.conn.commit()

    def close(self):
        self.conn.close()
        if self.mmdb:
            self.mmdb.close()