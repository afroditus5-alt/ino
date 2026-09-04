"""
Обработчик всего того, из-за чего аккаунты 'отлетают после первого пролива'.

IG сейчас использует 4 основных барьера:
1. Обычный checkpoint (challenge_required)     — код на email/sms
2. UFAC (User Feedback Anti-abuse Checkpoint)  — 'подтвердите что вы это вы'
3. Captcha bloks (recaptcha_challenge)          — visual/audio
4. suspicious_login_attempt                     — доверить устройство (кнопка "It Was Me")
"""

import asyncio, re, json, time, imaplib, email
from email.header import decode_header
from dataclasses import dataclass

class CheckpointError(Exception): pass
class LoginError(Exception): pass
class TwoFactorRequired(Exception): pass

@dataclass
class CheckpointContext:
    challenge_url: str
    challenge_type: str   # email | sms | captcha | select_verify
    api: object           # IGClient

class CheckpointSolver:
    def __init__(self, cli, acc, settings: dict):
        self.cli = cli
        self.acc = acc
        self.cfg = settings

    async def solve(self, response_json: dict) -> bool:
        """Возвращает True если чекпоинт пройден и login можно retry."""
        from core.ig_client import LoginError

        challenge = response_json.get("challenge") or response_json.get("checkpoint_url")
        if not challenge:
            raise CheckpointError(f"unknown response: {response_json}")

        # 1. Если challenge — dict с URL suspended → аккаунт мёртв, не пытаемся решить
        if isinstance(challenge, dict):
            challenge_url = challenge.get("url", "")
            if "suspended" in challenge_url or "disabled" in challenge_url:
                raise LoginError(f"account_suspended: {challenge_url}")

        # 2. Забираем страницу challenge
        url = challenge if isinstance(challenge, str) else challenge.get("api_path", "")
        r = await self.cli.s.request("GET", f"{self.cli.BASE}{url}")

        # если тело пустое → аккаунт скорее всего suspended, не решается
        if not r.text or not r.text.strip():
            raise LoginError(
                f"account_suspended: empty challenge response HTTP {r.status_code}"
            )

        # если HTML вместо JSON — аккаунт мёртв
        ctype = r.headers.get("content-type", "")
        if "text/html" in ctype and not r.text.strip().startswith("{"):
            raise LoginError(
                f"account_suspended: HTML challenge (not JSON) HTTP {r.status_code}"
            )

        try:
            j = r.json()
        except Exception as e:
            raise LoginError(f"account_suspended: cannot parse challenge: {e}")

        # 3. step_name → что от нас хотят
        step = j.get("step_name", "")
        step_data = j.get("step_data", {})

        if step in ("select_verify_method", "verify_email"):
            return await self._solve_email(url, step_data)
        if step in ("verify_sms_code_sms", "verify_phone_number"):
            return await self._solve_sms(url, step_data)
        if step == "captcha":
            return await self._solve_captcha(url, j)
        if step == "review_kyc":
            raise CheckpointError("kyc_required")
        if step == "verify_business_email":
            return await self._solve_email(url, step_data, business=True)

        raise CheckpointError(f"unhandled step: {step}")

    # ---------- email ----------
    async def _solve_email(self, url: str, step_data: dict, business: bool = False) -> bool:
        # выбираем метод email
        await self.cli.s.request("POST", f"{self.cli.BASE}{url}",
                                 data={"choice": "1"})  # 1 = email, 0 = sms

        if not self.acc.get("email") or not self.acc.get("email_password"):
            raise CheckpointError("email_challenge but no email creds")

        # ждём код в почте
        code = await self._fetch_email_code(
            self.acc["email"], self.acc["email_password"], timeout=90
        )
        if not code:
            raise CheckpointError("email_code_timeout")

        r = await self.cli.s.request("POST", f"{self.cli.BASE}{url}",
                                     data={"security_code": code})
        return r.json().get("status") == "ok"

    async def _fetch_email_code(self, email_addr: str, password: str, timeout: int = 90) -> str | None:
        """IMAP-фетчер, ищет код в письме от Instagram."""
        host_map = {
            "gmail.com":     ("imap.gmail.com", 993),
            "rambler.ru":    ("imap.rambler.ru", 993),
            "mail.ru":       ("imap.mail.ru", 993),
            "outlook.com":   ("imap-mail.outlook.com", 993),
            "hotmail.com":   ("imap-mail.outlook.com", 993),
            "yahoo.com":     ("imap.mail.yahoo.com", 993),
            "gmx.com":       ("imap.gmx.com", 993),
            "gmx.us":        ("imap.gmx.com", 993),
            "yandex.ru":     ("imap.yandex.ru", 993),
            "icloud.com":    ("imap.mail.me.com", 993),
            "firstmail.ltd": ("imap.firstmail.ltd", 993),
            "rambler.ua":    ("imap.rambler.ru", 993),
            "autorambler.ru":("imap.rambler.ru", 993),
            "myrambler.ru":  ("imap.rambler.ru", 993),
            "ro.ru":         ("imap.rambler.ru", 993),
        }
        domain = email_addr.split("@", 1)[1].lower()
        host_port = host_map.get(domain)
        if not host_port:
            # override из настроек
            override = self.cfg.get("imap_override", "")
            for pair in override.split(";"):
                parts = pair.split(":")
                if len(parts) == 3 and parts[0].lower() == domain:
                    host_port = (parts[1], int(parts[2]))
                    break
        if not host_port:
            raise CheckpointError(f"no IMAP host for {domain}")

        host, port = host_port

        def _fetch_sync() -> str | None:
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    with imaplib.IMAP4_SSL(host, port, timeout=15) as m:
                        m.login(email_addr, password)
                        m.select("INBOX")
                        typ, data = m.search(None, '(FROM "instagram" UNSEEN)')
                        if typ != "OK" or not data or not data[0]:
                            m.search(None, '(FROM "security@mail.instagram.com")')
                        for num in reversed(data[0].split()):
                            typ, msg_data = m.fetch(num, "(RFC822)")
                            if typ != "OK": continue
                            msg = email.message_from_bytes(msg_data[0][1])
                            body = _extract_body(msg)
                            match = re.search(r"\b(\d{6})\b", body)
                            if match:
                                return match.group(1)
                except Exception:
                    pass
                time.sleep(5)
            return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch_sync)

    # ---------- SMS ----------
    async def _solve_sms(self, url: str, step_data: dict) -> bool:
        if self.cfg.get("sms_provider") == "5sim":
            code = await self._sms_5sim(step_data)
        elif self.cfg.get("sms_provider") == "sms-activate":
            code = await self._sms_activate(step_data)
        else:
            raise CheckpointError("sms_challenge but no provider configured")
        r = await self.cli.s.request("POST", f"{self.cli.BASE}{url}",
                                     data={"security_code": code})
        return r.json().get("status") == "ok"

    async def _sms_5sim(self, step_data): 
        # запрос номера, ожидание кода — стандартный REST 5sim.net
        raise NotImplementedError  # ← заполни своим ключом

    async def _sms_activate(self, step_data):
        raise NotImplementedError

    # ---------- captcha ----------
    async def _solve_captcha(self, url: str, j: dict) -> bool:
        provider = self.cfg.get("captcha_provider", "").lower()
        if provider == "отключено" or not provider:
            raise CheckpointError("captcha but no solver")

        sitekey = j.get("captcha", {}).get("sitekey") or j.get("step_data", {}).get("sitekey")
        page_url = f"https://i.instagram.com{url}"
        token = await self._solve_recaptcha(provider, sitekey, page_url)
        r = await self.cli.s.request("POST", f"{self.cli.BASE}{url}",
                                     data={"g-recaptcha-response": token})
        return r.json().get("status") == "ok"

    async def _solve_recaptcha(self, provider: str, sitekey: str, page_url: str) -> str:
        import httpx
        key = self.cfg.get("captcha_key")
        if provider == "capsolver":
            async with httpx.AsyncClient(timeout=180) as c:
                r = await c.post("https://api.capsolver.com/createTask", json={
                    "clientKey": key,
                    "task": {"type": "ReCaptchaV2TaskProxyLess",
                             "websiteURL": page_url, "websiteKey": sitekey}
                })
                task_id = r.json()["taskId"]
                for _ in range(60):
                    await asyncio.sleep(3)
                    r = await c.post("https://api.capsolver.com/getTaskResult",
                                     json={"clientKey": key, "taskId": task_id})
                    j = r.json()
                    if j["status"] == "ready":
                        return j["solution"]["gRecaptchaResponse"]
                raise CheckpointError("captcha_timeout")
        # аналогично 2captcha/rucaptcha:
        elif provider in ("rucaptcha", "2captcha"):
            base = "https://rucaptcha.com" if provider == "rucaptcha" else "https://2captcha.com"
            async with httpx.AsyncClient(timeout=180) as c:
                r = await c.get(f"{base}/in.php", params={
                    "key": key, "method": "userrecaptcha",
                    "googlekey": sitekey, "pageurl": page_url, "json": "1"
                })
                task_id = r.json()["request"]
                for _ in range(60):
                    await asyncio.sleep(5)
                    r = await c.get(f"{base}/res.php", params={
                        "key": key, "action": "get", "id": task_id, "json": "1"
                    })
                    j = r.json()
                    if j.get("status") == 1:
                        return j["request"]
                raise CheckpointError("captcha_timeout")
        raise CheckpointError(f"unknown provider {provider}")


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                except: continue
        return ""
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "ignore")
