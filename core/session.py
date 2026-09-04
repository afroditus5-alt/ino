"""IGSession — с корректной обработкой Authorization Bearer из IAM-куков."""
import re
import time
import random
from curl_cffi.requests import AsyncSession

from assets.ig_versions import IG_CAPABILITIES


class IGSession:
    IMPERSONATE = {
        "android": "chrome131_android",
        "ios":     "safari184_ios",
    }

    _ANDROID_ORDER = [
        "X-IG-App-Locale", "X-IG-Device-Locale", "X-IG-Mapped-Locale",
        "X-Pigeon-Session-Id", "X-Pigeon-Rawclienttime",
        "X-IG-Connection-Speed", "X-IG-Bandwidth-Speed-KBPS",
        "X-IG-Bandwidth-TotalBytes-B", "X-IG-Bandwidth-TotalTime-MS",
        "X-IG-App-Startup-Country", "X-Bloks-Version-Id",
        "X-IG-WWW-Claim", "Authorization",
        "X-Bloks-Is-Layout-RTL", "X-Bloks-Is-Panorama-Enabled",
        "X-IG-Device-ID", "X-IG-Family-Device-ID", "X-IG-Android-ID",
        "X-Ig-Nav-Chain",
        "X-IG-Timezone-Offset", "X-IG-Connection-Type",
        "X-IG-Capabilities", "X-IG-App-ID", "Priority",
        "User-Agent", "Accept-Language", "X-MID",
        "Accept-Encoding", "Accept",
        "X-FB-HTTP-Engine", "X-FB-Client-IP", "X-FB-Server-Cluster",
    ]

    _IOS_ORDER = [
        "X-IG-App-Locale", "X-IG-Device-Locale", "X-IG-Mapped-Locale",
        "X-Pigeon-Session-Id", "X-Pigeon-Rawclienttime",
        "X-IG-Connection-Speed", "X-IG-Bandwidth-Speed-KBPS",
        "X-IG-Bandwidth-TotalBytes-B", "X-IG-Bandwidth-TotalTime-MS",
        "X-IG-App-Startup-Country", "X-Bloks-Version-Id",
        "X-IG-WWW-Claim", "Authorization",
        "X-Ig-Nav-Chain",
        "X-IG-Device-ID", "X-IG-Family-Device-ID",
        "X-IG-Timezone-Offset", "X-IG-Connection-Type",
        "X-IG-Capabilities", "X-IG-App-ID", "Priority",
        "User-Agent", "Accept-Language", "X-MID",
        "Accept-Encoding", "Accept",
    ]

    _HIGH_PRIORITY_PATHS = (
        "/api/v1/accounts/login/",
        "/api/v1/accounts/two_factor_login/",
        "/api/v1/media/configure_to_clips/",
        "/api/v1/media/configure/",
        "/rupload_igvideo/", "/rupload_igphoto/",
    )

    _HOST_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-.]*[a-zA-Z0-9]$")
    _HEADER_KEYS = {"Authorization", "X-IG-WWW-Claim", "X-MID",
                    "authorization", "x-ig-www-claim", "x-mid"}

    def __init__(self, device, proxy: str, cookies: dict | None = None):
        self.device = device
        self.proxy = self._normalize_proxy(proxy)
        self._session = AsyncSession(
            impersonate=self.IMPERSONATE[device.platform],
            proxies={"http": self.proxy, "https": self.proxy},
            timeout=30,
            verify=True,
        )

        # session state (обновляется по ответам)
        # connection type фиксируется на сессию, не меняется per-request
        self._conn_type = random.choices(
            ["WIFI", "MOBILE(LTE)", "MOBILE(5G)"],
            weights=[72, 20, 8]
        )[0]
        self._bw_total_bytes = 0
        self._bw_total_ms = 0
        self.www_claim: str = "0"
        self.mid: str = ""
        self.rur: str = ""
        self._auth_header: str | None = None

        # разделяем импортированные "cookies": часть → jar, часть → headers
        # словарь для IG-U-* → шлём их как ХЕДЕРЫ (реальный клиент делает так)
        self._ig_u_headers: dict[str, str] = {}

        if cookies:
            for k, v in cookies.items():
                if not v:
                    continue
                kl = k.lower()

                if kl == "authorization":
                    self._auth_header = v if v.startswith("Bearer ") else f"Bearer {v}"
                elif kl in ("x-ig-www-claim", "www-claim"):
                    self.www_claim = v
                elif kl == "x-mid":
                    self.mid = v
                elif kl == "mid":
                    self.mid = v
                    self._session.cookies.set("mid", v, domain=".instagram.com")
                elif kl.startswith("ig-u-"):
                    # шлём как HTTP-заголовки И в jar одновременно
                    self._ig_u_headers[k] = v
                    self._session.cookies.set(k, v, domain=".instagram.com")
                else:
                    self._session.cookies.set(k, v, domain=".instagram.com")

    @classmethod
    def _normalize_proxy(cls, p) -> str:
        if not p or not isinstance(p, str):
            raise ValueError("no proxy assigned to account")
        p = p.strip()
        scheme = "http"
        for s in ("http://", "https://", "socks5://", "socks4://"):
            if p.startswith(s):
                scheme = s.rstrip("://")
                p = p[len(s):]
                break
        if "@" in p:
            return f"{scheme}://{p}"
        parts = p.split(":")
        if len(parts) == 2:
            return f"{scheme}://{p}"
        if len(parts) == 4:
            if cls._IP_RE.match(parts[0]) and parts[1].isdigit():
                ip, port, user, pw = parts
            elif cls._IP_RE.match(parts[2]) and parts[3].isdigit():
                user, pw, ip, port = parts
            else:
                raise ValueError(f"Cannot parse proxy: {p}")
            return f"{scheme}://{user}:{pw}@{ip}:{port}"
        if len(parts) == 3:
            if cls._IP_RE.match(parts[0]) and parts[1].isdigit():
                return f"{scheme}://{parts[2]}@{parts[0]}:{parts[1]}"
        raise ValueError(f"Cannot parse proxy: {p}")

    def _is_high_priority(self, url: str) -> bool:
        return any(p in url for p in self._HIGH_PRIORITY_PATHS)

    def _build_headers(self, url: str, extra: dict | None = None) -> dict:
        d = self.device
        conn_type = self._conn_type

        raw = {
            "X-IG-App-Locale":               d.locale,
            "X-IG-Device-Locale":            d.locale,
            "X-IG-Mapped-Locale":            d.locale,
            "X-Pigeon-Session-Id":           d.pigeon_session_id,
            "X-Pigeon-Rawclienttime":        f"{time.time():.3f}",
            "X-IG-Connection-Speed":         f"{random.randint(800, 6500)}kbps",
            "X-IG-Bandwidth-Speed-KBPS":     f"{random.uniform(1500, 4500):.3f}",
            "X-IG-Bandwidth-TotalBytes-B":   str(self._bw_total_bytes),
            "X-IG-Bandwidth-TotalTime-MS":   str(self._bw_total_ms),
            "X-IG-App-Startup-Country":      d.country,
            "X-Bloks-Version-Id":            d.bloks_version,
            "X-IG-WWW-Claim":                self.www_claim,
            "X-Bloks-Is-Layout-RTL":         "true" if d.language in ("ar", "he", "fa", "ur") else "false",
            "X-Bloks-Is-Panorama-Enabled":   "true",
            "X-IG-Device-ID":                d.device_id,
            "X-IG-Family-Device-ID":         d.family_device_id,
            "X-IG-Timezone-Offset":          str(d.timezone_offset),
            "X-IG-Connection-Type":          conn_type,
            "X-IG-Capabilities":             IG_CAPABILITIES,
            "X-IG-App-ID":                   d.ig_app_id,
            "Priority":                      "u=1, i" if self._is_high_priority(url) else "u=3",
            "User-Agent":                    d.user_agent(),
            "Accept-Language":               f"{d.locale.replace('_','-')}, {d.language};q=0.9",
            "Accept":                        "*/*",
        }

        # платформо-специфичные
        if d.platform == "android":
            raw["Accept-Encoding"] = "gzip, deflate"
            raw["X-IG-Android-ID"] = f"android-{d.android_id}"
            raw["X-FB-HTTP-Engine"] = "Liger"
            raw["X-FB-Client-IP"] = "True"
            raw["X-FB-Server-Cluster"] = "True"
        else:
            raw["Accept-Encoding"] = "gzip, deflate, br"

        # X-Ig-Nav-Chain — след навигации для реализма при заливе рилса
        if "/configure_to_clips/" in url or "/rupload_igvideo" in url:
            nav_time = f"{time.time():.3f}"
            raw["X-Ig-Nav-Chain"] = (
                f"MainFeedFragment:feed_timeline:1:cold_start:{nav_time}::,"
                f"IgCameraFragment:ig_camera:2:button:{float(nav_time)+random.randint(30,120):.3f}::,"
                f"ClipsShareSheetFragment:clips_share_sheet:3:button:{float(nav_time)+random.randint(60,180):.3f}::"
            )

        # X-MID если есть
        if self.mid:
            raw["X-MID"] = self.mid

        # Authorization Bearer из импортированных данных
        if self._auth_header:
            raw["Authorization"] = self._auth_header

        # IG-U-* заголовки — реальный клиент шлёт их отдельными хедерами
        for hk, hv in self._ig_u_headers.items():
            raw[hk] = hv

        # X-CSRFToken — IG некоторые endpoint'ы требуют в header-е, не только в cookie
        for c in self._session.cookies.jar:
            if c.name == "csrftoken" and c.value:
                raw["X-CSRFToken"] = c.value
                break

        # экстра-хедеры от вызывающего кода
        if extra:
            raw.update(extra)

        # выстраиваем в правильном порядке (как в реальном IG клиенте)
        order = self._ANDROID_ORDER if d.platform == "android" else self._IOS_ORDER
        ordered = {}
        for k in order:
            if k in raw:
                ordered[k] = raw.pop(k)
        # что осталось (кастомные extra которых нет в шаблоне порядка) — в конец
        ordered.update(raw)
        return ordered

    def _absorb_response(self, r):
        set_claim = r.headers.get("X-IG-Set-WWW-Claim") or r.headers.get("x-ig-set-www-claim")
        if set_claim:
            self.www_claim = set_claim
        set_mid = r.headers.get("ig-set-x-mid") or r.headers.get("X-IG-Set-Mid")
        if set_mid:
            self.mid = set_mid
        # Authorization обновляется в некоторых редких ответах
        set_auth = r.headers.get("ig-set-authorization")
        if set_auth:
            self._auth_header = set_auth if set_auth.startswith("Bearer ") else f"Bearer {set_auth}"

        try:
            for c in self._session.cookies.jar:
                if c.name == "mid" and c.value:
                    self.mid = c.value
                elif c.name == "rur" and c.value:
                    self.rur = c.value
        except Exception:
            pass

    async def request(self, method, url, **kw):
        extra = kw.pop("headers", {}) or {}
        headers = self._build_headers(url, extra)

        import time as _t
        _start = _t.monotonic()

        r = await self._session.request(
            method,
            url,
            headers=headers,
            **kw
        )

        # обновляем bandwidth-аккумуляторы
        elapsed_ms = int((_t.monotonic() - _start) * 1000)

        try:
            content_len = int(
                r.headers.get("content-length", 0)
            ) or len(r.content)
        except Exception:
            content_len = 0

        self._bw_total_bytes += content_len
        self._bw_total_ms += elapsed_ms

        self._absorb_response(r)
        return r

    async def close(self):
        await self._session.close()