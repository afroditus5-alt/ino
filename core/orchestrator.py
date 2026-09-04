"""
Оркестратор задач с трекингом активных логинов (защита от дублей),
поддержкой first_setup (avatar + bio перед первым заливом).
"""
import asyncio
import random
import hashlib
from asyncio import Semaphore
from pathlib import Path

from core.device import DeviceProfile
from core.session import IGSession
from core.geo import GeoResolver
from core.ig_client import (IGClient, LoginError, UploadError,
                            TwoFactorRequired, CheckpointError)
from core.checkpoint import CheckpointSolver
from core.uniquifier import ReelUniquifier


class Orchestrator:
    # Общий на ВСЕ инстансы: логины что сейчас в работе (защита от дублей запусков)
    _running_logins: set = set()
    _running_lock = None

    def __init__(self, threads: int, on_status, db=None, settings: dict = None,
                 stats_sink=None, geo: GeoResolver = None):
        self.sem = Semaphore(threads)
        self.on_status = on_status
        self.db = db
        self.settings = settings or {}
        self.stats_sink = stats_sink
        self.geo = geo or GeoResolver(db_path="data/geo_cache.db")

    @classmethod
    def _get_lock(cls):
        if cls._running_lock is None:
            cls._running_lock = asyncio.Lock()
        return cls._running_lock

    # ============================================================
    async def run_batch(self, accounts: list, action: str, params: dict):
        # фильтруем аккаунты которые уже обрабатываются другой задачей
        async with self._get_lock():
            skipped_logins = []
            actual_accounts = []
            actual_indices = []
            for i, a in enumerate(accounts):
                login = a.get("login", "")
                if login in self._running_logins:
                    skipped_logins.append(login)
                else:
                    self._running_logins.add(login)
                    actual_accounts.append(a)
                    actual_indices.append(i)

        if skipped_logins:
            print(f"[orchestrator] пропущено {len(skipped_logins)} акков "
                  f"— уже в работе другой задачи")

        if not actual_accounts:
            return

        try:
            tasks = [asyncio.create_task(self._run_one(actual_indices[k], a, action, params))
                     for k, a in enumerate(actual_accounts)]
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            async with self._get_lock():
                for a in actual_accounts:
                    self._running_logins.discard(a.get("login", ""))

    # ============================================================
    async def _run_one(self, row, acc, action, params):
        async with self.sem:
            spread = min(8.0, params.get("delay_max", 90) / 3)
            await asyncio.sleep(random.uniform(0.3, spread))
            self.on_status(row, "running", "")

            retry = int(params.get("retry", 1))
            for attempt in range(retry + 1):
                try:
                    result = await self._do_action(acc, action, params)
                    self.on_status(row, "success", "")
                    if action == "collect_stats" and self.stats_sink and result:
                        self.stats_sink(acc["login"], result)
                    return result

                except TwoFactorRequired:
                    self.on_status(row, "error", "2FA required, no totp_secret")
                    if self.db:
                        self.db.set_status(acc["login"], "error", "2FA no secret")
                    return

                except LoginError as e:
                    if attempt < retry:
                        await asyncio.sleep(random.uniform(3, 8))
                        continue
                    self.on_status(row, "banned", f"login: {str(e)[:120]}")
                    if self.db:
                        self.db.set_status(acc["login"], "banned", str(e)[:200])
                    return

                except CheckpointError as e:
                    self.on_status(row, "error", f"checkpoint: {str(e)[:120]}")
                    if self.db:
                        self.db.set_status(acc["login"], "error", f"checkpoint: {str(e)[:200]}")
                    if params.get("rotate_proxy_on_ban") and self.db:
                        new_proxy = self.db.get_free_proxy()
                        if new_proxy and attempt < retry:
                            acc["proxy"] = new_proxy
                            self.db.upsert_account(acc)
                            self.db.bind_proxy(new_proxy, acc["login"])
                            await asyncio.sleep(random.uniform(10, 25))
                            continue
                    return

                except Exception as e:
                    msg = str(e).lower()

                    hard_signals = (
                        "feedback_required", "spam", "action_blocked",
                        "we restrict certain", "biography_length",
                        "url_missing", "cannot_be_uploaded", "invalid",
                        "not_allowed",
                    )
                    is_hard = any(sig in msg for sig in hard_signals)

                    is_proxy = ("407" in msg or "connect tunnel" in msg
                                or "curl: (28)" in msg or "curl: (7)" in msg
                                or "curl: (56)" in msg or "timed out" in msg
                                or "connection reset" in msg or "429" in msg)

                    is_soft_action = ("transcode" in msg or "mismatch" in msg
                                      or "server error" in msg or "500" in msg
                                      or "502" in msg or "503" in msg
                                      or "504" in msg)

                    if is_hard:
                        self.on_status(row, "error", f"hard: {str(e)[:150]}")
                        if self.db:
                            self.db.set_status(acc["login"], "error", f"hard: {str(e)[:200]}")
                        return

                    if attempt < retry:
                        if is_proxy:
                            await asyncio.sleep(random.uniform(15, 45))
                        elif is_soft_action:
                            await asyncio.sleep(random.uniform(10, 25))
                        else:
                            await asyncio.sleep(random.uniform(3, 8))
                        continue

                    self.on_status(row, "error", str(e)[:200])
                    if self.db:
                        self.db.set_status(acc["login"], "error", str(e)[:200])
                    return

    # ============================================================
    async def _do_action(self, acc, action, params):
        if not acc.get("proxy"):
            raise ValueError("no proxy assigned to account")

        country, tz_offset = await self.geo.resolve(acc["proxy"])

        has_full_device = (
            acc.get("device_id") and acc.get("model") and
            acc.get("ig_version") and acc.get("os_release")
        )
        device = None
        if has_full_device:
            try:
                device = DeviceProfile.from_saved(acc)
            except Exception:
                device = None

        if device is None:
            device = DeviceProfile.generate(
                seed=acc["login"],
                platform=acc.get("platform") or params.get("platform"),
                country_hint=country,
                tz_offset_hint=tz_offset,
            )
            if self.db:
                saved = device.to_saved()
                acc.update({k: v for k, v in saved.items()
                           if k not in ("seed", "waterfall_id", "pigeon_session_id",
                                        "session_id", "mid")})
                self.db.upsert_account(acc)

        if country and country != device.country:
            device.country = country
            from assets.locale_map import pick_timezone_for_locale
            device.timezone_offset = pick_timezone_for_locale(device.locale, tz_offset)

        sess = IGSession(device, acc["proxy"], acc.get("cookies"))
        cli = IGClient(sess, acc)

        try:
            # Login (с обработкой чекпоинта)
            try:
                uid = await cli.login()
            except CheckpointError as ce:
                solver = CheckpointSolver(cli, acc, self.settings)
                payload = ce.args[0] if ce.args else {}
                if await solver.solve(payload):
                    uid = await cli.login()
                else:
                    raise

            # Прогрев только для password-flow (без куков)
            if not acc.get("cookies"):
                try:
                    await cli.warm_qe_sync(str(uid))
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                except Exception:
                    pass

            # Целевое действие
            if action == "upload_reel":
                # First setup — био и/или аватар перед первым заливом
                need_setup = (
                    params.get("first_setup_enable") or
                    params.get("first_setup_avatar")
                )
                if need_setup and not acc.get("first_setup_done"):
                    await self._do_first_setup(cli, acc, params)
                return await self._upload(cli, params)

            if action == "set_bio":
                bio_text = self._pick_bio(params, acc["login"])
                result = await cli.set_biography(bio_text)
                if self.db and result.get("status") == "ok":
                    h = hashlib.md5(bio_text.encode("utf-8")).hexdigest()
                    self.db.set_bio_hash(acc["login"], h)
                return result
                
            if action == "set_avatar":
                return await self._do_avatar_only(cli, acc, params)
            if action == "collect_stats":
                return await cli.get_self_stats(str(uid))

            raise ValueError(f"unknown action: {action}")

        finally:
            # сохраняем свежие куки после ЛЮБОГО действия
            try:
                if self.db:
                    fresh_cookies = {c.name: c.value for c in sess._session.cookies.jar}
                    if sess._auth_header:
                        fresh_cookies["Authorization"] = sess._auth_header
                    if sess.mid:
                        fresh_cookies["X-MID"] = sess.mid
                    if fresh_cookies.get("sessionid"):
                        self.db.save_cookies(acc["login"], fresh_cookies)
            except Exception:
                pass
            try:
                await sess.close()
            except Exception:
                pass

    # ============================================================
    async def _do_first_setup(self, cli, acc, params):
        """
        Ставит био и/или аватарку перед первым заливом рилса.
        Обе операции проверяют хэш — если уже стоит то же самое, пропускается.
        """
        import hashlib
        login = acc.get("login", "?")

        do_bio = params.get("first_setup_enable", False)
        do_avatar = params.get("first_setup_avatar", False)

        # ─── 1. Аватар (если включено) ───
        if do_avatar:
            avatar_folder = params.get("avatar_folder", "")
            if avatar_folder and Path(avatar_folder).is_dir():
                avatars = (list(Path(avatar_folder).glob("*.jpg")) +
                           list(Path(avatar_folder).glob("*.jpeg")) +
                           list(Path(avatar_folder).glob("*.png")) +
                           list(Path(avatar_folder).glob("*.JPG")) +
                           list(Path(avatar_folder).glob("*.JPEG")) +
                           list(Path(avatar_folder).glob("*.PNG")))
                if avatars:
                    chosen = str(random.choice(avatars))
                    with open(chosen, "rb") as f:
                        new_avatar_hash = hashlib.md5(f.read()).hexdigest()

                    # skip если уже стоит эта же аватарка
                    if acc.get("avatar_hash") == new_avatar_hash:
                        pass
                    else:
                        try:
                            await cli.change_profile_picture(chosen)
                            if self.db:
                                self.db.conn.execute(
                                    "UPDATE accounts SET avatar_hash=?, "
                                    "avatar_updated_at=CURRENT_TIMESTAMP WHERE login=?",
                                    (new_avatar_hash, login)
                                )
                                self.db.conn.commit()
                            await asyncio.sleep(random.uniform(8, 20))
                        except Exception as e:
                            print(f"[first_setup:{login}] avatar fail: {e}")

        # ─── 2. Био (если включено) ───
        if do_bio:
            try:
                import json
                bio_path = Path("data/bio_settings.json")
                if bio_path.exists():
                    bio_cfg = json.loads(bio_path.read_text("utf-8"))
                    bio_text = bio_cfg.get("bio", "").strip()
                    if bio_text:
                        bio_final = self._spin(bio_text)
                        new_bio_hash = hashlib.md5(bio_final.encode("utf-8")).hexdigest()

                        # skip если уже стоит это же био
                        if acc.get("bio_hash") == new_bio_hash:
                            pass
                        else:
                            result = await cli.set_biography(bio_final)
                            if result.get("status") == "ok" and self.db:
                                self.db.set_bio_hash(login, new_bio_hash)
                            await asyncio.sleep(random.uniform(10, 25))
            except Exception as e:
                print(f"[first_setup:{login}] bio fail: {e}")

        # ─── 3. Помечаем setup_done только если хоть что-то было запрошено ───
        if (do_bio or do_avatar) and self.db:
            try:
                self.db.mark_setup_done(login)
                acc["first_setup_done"] = 1
            except Exception:
                pass
    async def _do_avatar_only(self, cli, acc, params):
        """
        Задача только на смену аватарки.
        skip_if_set = пропускать если на аккаунте УЖЕ ЕСТЬ любая аватарка.
        """
        import hashlib
        login = acc.get("login", "?")

        avatar_folder = params.get("avatar_folder", "")
        if not avatar_folder or not Path(avatar_folder).is_dir():
            raise ValueError("avatar_folder not set or does not exist")

        avatars = (list(Path(avatar_folder).glob("*.jpg")) +
                   list(Path(avatar_folder).glob("*.jpeg")) +
                   list(Path(avatar_folder).glob("*.png")) +
                   list(Path(avatar_folder).glob("*.JPG")) +
                   list(Path(avatar_folder).glob("*.JPEG")) +
                   list(Path(avatar_folder).glob("*.PNG")))
        if not avatars:
            raise ValueError(f"no images in {avatar_folder}")

        # Если стоит галка "пропускать если уже стоит" — проверяем IG
        if params.get("skip_if_set"):
            uid_str = ""
            try:
                for c in cli.s._session.cookies.jar:
                    if c.name == "ds_user_id":
                        uid_str = c.value
                        break
                if uid_str:
                    r = await cli.s.request(
                        "GET", f"{cli.BASE}/api/v1/users/{uid_str}/info/"
                    )
                    j = r.json()
                    if j.get("status") == "ok" and j.get("user"):
                        has_avatar = not j["user"].get("has_anonymous_profile_picture", True)
                        if has_avatar:
                            return {"status": "skipped", "reason": "avatar already set on IG"}
            except Exception as e:
                print(f"[avatar:{login}] info fetch fail: {e}")

        chosen = str(random.choice(avatars))
        with open(chosen, "rb") as f:
            new_hash = hashlib.md5(f.read()).hexdigest()

        # человек-пауза
        await asyncio.sleep(random.uniform(
            params.get("delay_min", 15),
            params.get("delay_max", 60),
        ))

        result = await cli.change_profile_picture(chosen)

        if self.db:
            try:
                self.db.conn.execute(
                    "UPDATE accounts SET avatar_hash=?, avatar_updated_at=CURRENT_TIMESTAMP "
                    "WHERE login=?",
                    (new_hash, login)
                )
                if params.get("mark_setup"):
                    self.db.conn.execute(
                        "UPDATE accounts SET first_setup_done=1 WHERE login=?",
                        (login,)
                    )
                self.db.conn.commit()
            except Exception:
                pass

        return result

    # ============================================================
    async def _upload(self, cli: IGClient, params: dict):
        # 1. Видео
        src = params.get("video_path")
        if not src and params.get("video_folder"):
            folder = Path(params["video_folder"])
            files = (list(folder.glob("*.mp4")) + list(folder.glob("*.mov")) +
                     list(folder.glob("*.m4v")) + list(folder.glob("*.mkv")))
            if not files:
                raise ValueError("empty video folder")
            src = str(random.choice(files))
        if not src:
            raise ValueError("no video source")
        if not Path(src).exists():
            raise ValueError(f"video not found: {src}")

        # 2. Кастомная обложка (мисс-клик)
        custom_cover = None
        cover_folder = params.get("cover_folder", "")
        cover_path = params.get("cover_path", "")
        if cover_path and Path(cover_path).exists():
            custom_cover = cover_path
        elif cover_folder and Path(cover_folder).is_dir():
            covers = (list(Path(cover_folder).glob("*.jpg")) +
                      list(Path(cover_folder).glob("*.jpeg")) +
                      list(Path(cover_folder).glob("*.png")))
            if covers:
                custom_cover = str(random.choice(covers))

        # 3. Уникализация видео
        if params.get("uniquify"):
            level = params.get("uniquify_level", "universal")
            audio = params.get("uniquify_audio", True)
            src = await ReelUniquifier.unique_async(src, level=level, audio=audio)

        # 4. Caption
        caption = self._spin(params.get("caption", ""))

        # 5. Human delay
        await asyncio.sleep(random.uniform(
            params.get("delay_min", 25),
            params.get("delay_max", 90)
        ))

        # 6. Публикация
        result = await cli.upload_reel(
            src,
            caption=caption,
            share_to_feed=params.get("share_to_feed", False),
            disable_comments=params.get("disable_comments", False),
            custom_cover_path=custom_cover,
        )
        if self.db and result.get("media"):
            self.db.log_upload(
                cli.acc["login"],
                result["media"].get("id", ""),
                result["media"].get("code", ""),
            )
        return result

    # ============================================================
    @staticmethod
    def _spin(text: str) -> str:
        """Раскрытие {a|b|c} спинтакса."""
        import re
        def repl(m):
            return random.choice(m.group(1).split("|"))
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r"\{([^{}]+)\}", repl, text)
        return text

    def _pick_bio(self, params: dict, login: str) -> str:
        bio = params.get("bio", "")
        if params.get("multiline"):
            lines = [l for l in bio.splitlines() if l.strip()]
            if lines:
                idx = hash(login) % len(lines)
                return lines[idx]
        return self._spin(bio)