"""Импорт аккаунтов. IAM формат + смешанные login:pass:totp:...:android-XXX и другие."""
import re
import json


class AccountImporter:
    SEPS = [":", "|", ";", ","]

    UA_ANDROID_RE = re.compile(
        r"Instagram\s+(\S+)\s+Android\s+\("
        r"(\d+)/([\d.]+);\s*(\d+)dpi;\s*(\d+x\d+);\s*"
        r"([^;]+?);\s*([^;]+?);\s*([^;]+?);\s*([^;]+?);\s*"
        r"([\w_-]+);\s*(\d+)\)"
    )
    UA_IOS_RE = re.compile(
        r"Instagram\s+(\S+)\s+\("
        r"(iPhone[\d,]+);\s*iOS\s+([\d_]+);\s*"
        r"([\w_-]+);\s*([\w-]+);\s*scale=([\d.]+);\s*"
        r"(\d+x\d+);\s*(\d+)\)"
    )

    ANDROID_ID_RE = re.compile(r"android-([0-9a-fA-F]{16})")
    UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    TOTP_RE = re.compile(r"^[A-Z2-7]{16,32}$")
    IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    COOKIE_KEYS = ("sessionid", "ds_user_id", "csrftoken", "mid", "ig_did",
                   "rur", "Authorization", "authorization")

    @classmethod
    def parse_line(cls, line: str) -> dict | None:
        line = line.strip()

        if not line or line.startswith("#"):
            return None

        # ─── Extended/IAM формат детектится по наличию | и любого из маркеров ───
        is_extended = "|" in line and (
            "|Instagram " in line
            or "android-" in line
            or "sessionid=" in line
            or "Authorization=" in line.replace(" ", "")
            or ";ds_user_id=" in line
        )

        if is_extended:
            return cls._parse_iam(line)

        if line.startswith("{"):
            return cls._parse_json(line)

        return cls._parse_mixed(line)

    @classmethod
    def _parse_iam(cls, line: str) -> dict | None:
        """
        IAM-подобный формат: блоки разделены `|`.
        Поддерживает:
          login:pass|UA|uuids|cookies|...
          login|pass|2FA|cookies|email|
          login|pass|2FA|cookies||+phone
        """
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            return None

        acc = {"platform": "android"}

        # ─── Частый формат: login|pass|totp|cookies|email[|phone] ───
        # Если первый блок — просто логин (без ':'), разбираем позиционно.
        if (
            parts[0]
            and ":" not in parts[0]
            and not parts[0].startswith("Instagram ")
            and "=" not in parts[0]
        ):
            acc["login"] = parts[0]
            if len(parts) >= 2 and parts[1]:
                # второй блок — пароль (если это не cookies/UA)
                if "=" not in parts[1] and not parts[1].startswith("Instagram "):
                    acc["password"] = parts[1]
            if len(parts) >= 3 and parts[2] and cls.TOTP_RE.match(parts[2]):
                acc["totp_secret"] = parts[2]
            # остальное ниже по общим правилам (начиная с индекса 2/3)

        for i, block in enumerate(parts):
            if not block:
                continue

            # 1) login:pass — классический первый блок
            if i == 0 and ":" in block and "Instagram" not in block and "=" not in block:
                cred = block.split(":")
                acc["login"] = cred[0].strip()
                acc["password"] = cred[1].strip()
                if len(cred) >= 3:
                    third = cred[2].strip()
                    if cls.TOTP_RE.match(third):
                        acc["totp_secret"] = third
                    elif len(cred) > 3:
                        acc["password"] = ":".join(cred[1:]).strip()
                continue

            # уже разобрали login|pass позиционно — не перезаписываем
            if i == 0 and acc.get("login"):
                continue
            if i == 1 and acc.get("password") and block == acc.get("password"):
                continue
            if i == 2 and acc.get("totp_secret") and block == acc.get("totp_secret"):
                continue

            # 2) UA
            if block.startswith("Instagram "):
                cls._merge_ua(acc, block)
                continue

            # 3) UUID / android_id
            if (
                ("android-" in block or cls.UUID_RE.search(block))
                and ";" in block
                and "=" not in block
            ):
                cls._merge_uuids(acc, block)
                continue

            # 4) cookies / headers
            if "=" in block and (
                ";" in block
                or "sessionid" in block.lower()
                or "authorization" in block.lower()
                or "csrftoken" in block.lower()
            ):
                cls._merge_cookies_and_headers(acc, block)
                continue

            # 5) TOTP отдельно (если не поймали позиционно)
            if cls.TOTP_RE.match(block) and not acc.get("totp_secret"):
                acc["totp_secret"] = block
                continue

            # 6) email
            if "@" in block and "." in block and " " not in block and "=" not in block:
                acc["email"] = block
                continue

            # 7) phone (+...)
            if block.startswith("+") and any(c.isdigit() for c in block):
                acc["phone"] = block
                continue

            # 8) proxy
            if "://" in block or ("@" in block and "." in block):
                acc["proxy"] = block
                continue

            if (
                block.count(":") in (1, 3)
                and any(c.isdigit() for c in block.split(":")[0])
            ):
                if cls.IP_RE.match(block.split(":")[0]):
                    acc["proxy"] = block
                    continue

            # 9) email password
            if (
                acc.get("email")
                and not acc.get("email_password")
                and len(block) < 40
                and " " not in block
                and "=" not in block
                and not cls.TOTP_RE.match(block)
            ):
                acc["email_password"] = block

        return acc if acc.get("login") and acc.get("password") else None

    @classmethod
    def _merge_ua(cls, acc, ua):
        ua = ua.strip()
        acc["user_agent"] = ua
        m = cls.UA_ANDROID_RE.search(ua)
        if m:
            ig_ver, api, release, dpi, res, manu, dev, model, cpu, locale, code = m.groups()
            manu_part, brand_part = manu.split("/", 1) if "/" in manu else (manu, manu.lower())
            acc.update({
                "platform": "android",
                "ig_version": ig_ver, "ig_version_code": code,
                "os_api": api, "os_release": release,
                "dpi": f"{dpi}dpi", "resolution": res,
                "manufacturer": manu_part.strip(), "brand": brand_part.strip(),
                "device_name": dev.strip(), "model": model.strip(),
                "hardware": cpu.strip(), "cpu": cpu.strip(),
                "locale": locale, "language": locale[:2],
            })
            return
        m = cls.UA_IOS_RE.search(ua)
        if m:
            ig_ver, machine, ios_ver, locale, lang, scale, res, code = m.groups()
            acc.update({
                "platform": "ios",
                "ig_version": ig_ver, "ig_version_code": code,
                "os_release": ios_ver.replace("_", "."),
                "resolution": res, "scale": scale,
                "manufacturer": "Apple", "brand": "Apple",
                "model": machine, "device_name": machine,
                "locale": locale, "language": lang,
            })

    @classmethod
    def _merge_uuids(cls, acc, blob):
        toks = [t.strip() for t in blob.split(";") if t.strip()]
        uuid_slots = ["device_id", "family_device_id", "phone_id", "advertising_id"]
        idx = 0
        for t in toks:
            m = cls.ANDROID_ID_RE.match(t)
            if m:
                acc["android_id"] = m.group(1)
            elif cls.UUID_RE.fullmatch(t):
                if idx < len(uuid_slots):
                    acc[uuid_slots[idx]] = t
                    idx += 1

    @classmethod
    def _merge_cookies_and_headers(cls, acc: dict, blob: str):
        """
        Разбирает блок вида:
          mid=X;ds_user_id=Y;sessionid=Z;Authorization=Bearer IGT:2:...;X-MID=X;X-IG-WWW-Claim=0
        Реальные cookies → в acc['cookies']
        Заголовки (Authorization, X-MID, X-IG-WWW-Claim) → тоже в cookies dict,
        а IGSession уже разделит их сама.
        """
        cookies = acc.get("cookies") or {}

        for pair in blob.split(";"):
            pair = pair.strip()

            if "=" not in pair:
                continue

            k, v = pair.split("=", 1)
            k, v = k.strip(), v.strip()

            if not k or not v:
                continue

            cookies[k] = v

        if cookies:
            acc["cookies"] = cookies

    # ============================================================
    @classmethod
    def _parse_json(cls, line):
        try:
            j = json.loads(line)
        except Exception:
            return None
        return {
            "login":          j.get("username") or j.get("login"),
            "password":       j.get("password", ""),
            "email":          j.get("email"),
            "email_password": j.get("email_password"),
            "totp_secret":    j.get("totp") or j.get("totp_secret"),
            "proxy":          j.get("proxy"),
            "user_agent":     j.get("user_agent") or j.get("userAgent"),
            "device_id":      j.get("device_id"),
            "android_id":     j.get("android_id"),
            "cookies":        {k: v for k, v in j.items() if k in cls.COOKIE_KEYS},
        }

    # ============================================================
    @classmethod
    def _parse_mixed(cls, line):
        """
        Универсальный парсер, ловит:
          login:pass
          login:pass:totp
          login:pass:totp:email:emailpass
          login:pass:totp::android-XXX
          login:pass:email:emailpass:ip:port
          login:pass:email:emailpass:ip:port:user:pass
          login:pass:totp:email:emailpass:sessionid=X;ds_user_id=Y;...
          и любые перестановки — детектит каждый токен эвристически.
        """
        # определяем основной разделитель — обычно `:`, но может быть `|` для extended
        sep = max(cls.SEPS, key=lambda s: line.count(s))
        parts = [p.strip() for p in line.split(sep)]
        if len(parts) < 2:
            return None

        acc = {"login": parts[0], "password": parts[1]}
        rest = parts[2:]

        for t in rest:
            if not t:
                continue
            # cookies-блок целиком (содержит = и ;)
            if "=" in t and (";" in t or "sessionid" in t or "Authorization" in t):
                cls._merge_cookies(acc, t)
                continue
            # email + следующий пасс?
            if "@" in t and "." in t:
                acc["email"] = t
                # ждём чтобы след. токен был паролем; обрабатывается ниже
                continue
            # android-XXX
            m = cls.ANDROID_ID_RE.match(t)
            if m:
                acc["android_id"] = m.group(1)
                continue
            # чистый UUID
            if cls.UUID_RE.fullmatch(t):
                # первый — device_id, второй — family_did, и т.д.
                for slot in ("device_id", "family_device_id", "phone_id", "advertising_id"):
                    if slot not in acc:
                        acc[slot] = t
                        break
                continue
            # TOTP secret (base32, 16-32 симв)
            if cls.TOTP_RE.match(t):
                acc["totp_secret"] = t
                continue
            # прокси (URL или user:pass@ip:port или ip:port)
            if "://" in t or "@" in t:
                acc["proxy"] = t
                continue
            # proxy type
            if t.lower() in ("http", "https", "socks4", "socks5"):
                acc["proxy_type"] = t.lower()
                continue
            # UA (короткая проверка)
            if t.startswith("Instagram "):
                cls._merge_ua(acc, t)
                continue

        # ─── попытка «поженить» email + email_password если email найден ───
        if acc.get("email") and not acc.get("email_password"):
            # ищем в rest токен идущий сразу после email — если он не выглядит как что-то распознанное
            try:
                idx = rest.index(acc["email"])
                if idx + 1 < len(rest):
                    candidate = rest[idx + 1]
                    if candidate and not any(
                        cls.ANDROID_ID_RE.match(candidate),
                        cls.UUID_RE.fullmatch(candidate),
                        cls.TOTP_RE.match(candidate),
                    ):
                        acc["email_password"] = candidate
            except ValueError:
                pass

        return acc