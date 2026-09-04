"""
IGClient — обёртка Instagram Private API. Login/warmup/upload/bio/stats.
"""
import asyncio, json, time, hashlib, random, subprocess, tempfile
from pathlib import Path


class LoginError(Exception): pass
class UploadError(Exception): pass
class TwoFactorRequired(Exception): pass
class CheckpointError(Exception): pass


class IGClient:
    BASE = "https://i.instagram.com"

    def __init__(self, session, account):
        self.s = session
        self.acc = account

    # ─────────────── PRELOGIN ───────────────
    async def warm_launcher(self):
        await self.s.request(
            "POST", f"{self.BASE}/api/v1/launcher/mobileconfig/",
            data={
                "bool_opt_policy": "0",
                "mobileconfigsessionless": "",
                "api_version": "3",
                "unit_type": "1",
                "ts": str(int(time.time())),
            })

    async def warm_qe_sync(self, uid=None):
        await self.s.request(
            "POST", f"{self.BASE}/api/v1/qe/sync/",
            data={
                "id": uid or self.s.device.device_id,
                "server_config_retrieval": "1",
                "experiments": "ig_android_login_identifier_fuzzy_match",
            })

    async def warm_contact_prefill(self):
        await self.s.request(
            "POST", f"{self.BASE}/api/v1/accounts/contact_point_prefill/",
            data={"phone_id": self.s.device.phone_id, "usage": "prefill"})

    async def warm_full_prelogin(self):
        await self.warm_launcher()
        await self._pause(0.4, 0.9)
        await self.warm_qe_sync()
        await self._pause(0.3, 0.7)
        await self.warm_contact_prefill()
        await self._pause(0.5, 1.1)

    # ─────────────── LOGIN ───────────────
    async def login(self):
        """Если есть куки → валидируем без /login/. Иначе — полный flow."""

        # ─── путь через куки/токен ───
        if self.acc.get("cookies") or self.s._auth_header:
            try:
                r = await self.s.request(
                    "GET", f"{self.BASE}/api/v1/accounts/current_user/"
                )
                try:
                    j = r.json()
                except Exception:
                    j = {}

                # 200 + user → всё ок
                if r.status_code == 200 and j.get("status") == "ok" and j.get("user"):
                    return j["user"]["pk"]

                # 400 + challenge_required — часто suspended/banned
                if r.status_code == 400 and j.get("message") == "challenge_required":
                    challenge = j.get("challenge", {})
                    url = challenge.get("url", "")
                    if "suspended" in url or "disabled" in url:
                        raise LoginError(f"account_suspended: {url}")
                    raise CheckpointError(j)

                # 403 + login_required — сессия умерла
                if r.status_code == 403 and j.get("message") == "login_required":
                    # проваливаемся в password-flow ниже
                    pass
                else:
                    # неожиданный ответ на current_user — тоже фоллбэк
                    pass

            except (LoginError, CheckpointError):
                raise
            except Exception:
                pass  # молча падаем в password

        # ─── password-flow ───
        await self.warm_full_prelogin()

        import time
        ts = int(time.time())
        enc_pwd = f"#PWD_INSTAGRAM:0:{ts}:{self.acc['password']}"
        dev = self.s.device

        payload = {
            "jazoest": "2" + str(sum(ord(c) for c in dev.phone_id)),
            "country_codes": '[{"country_code":"1","source":["default"]}]',
            "phone_id": dev.phone_id,
            "enc_password": enc_pwd,
            "username": self.acc["login"],
            "adid": dev.advertising_id,
            "guid": dev.device_id,
            "device_id": dev.android_id or dev.device_id,
            "google_tokens": "[]",
            "login_attempt_count": "0",
        }

        r = await self.s.request(
            "POST",
            f"{self.BASE}/api/v1/accounts/login/",
            data=payload
        )

        try:
            j = r.json()
        except Exception:
            raise LoginError(f"non-JSON: {r.text[:200]}")

        if j.get("two_factor_required"):
            return await self._pass_2fa(j["two_factor_info"])

        if (
            j.get("message") == "checkpoint_required"
            or j.get("error_type", "").startswith("checkpoint")
        ):
            raise CheckpointError(j)

        if j.get("status") != "ok" or not j.get("logged_in_user"):
            raise LoginError(j.get("message") or str(j)[:200])

        return j["logged_in_user"]["pk"]

    async def _pass_2fa(self, info):
        secret = self.acc.get("totp_secret")
        if not secret:
            raise TwoFactorRequired(info)
        import pyotp
        code = pyotp.TOTP(secret).now()
        dev = self.s.device
        r = await self.s.request(
            "POST", f"{self.BASE}/api/v1/accounts/two_factor_login/",
            data={
                "verification_code": code,
                "phone_id": dev.phone_id,
                "two_factor_identifier": info["two_factor_identifier"],
                "username": self.acc["login"],
                "trust_signal": "true",
                "device_id": dev.android_id or dev.device_id,
                "guid": dev.device_id,
                "verification_method": "3",
            })
        j = r.json()
        if j.get("status") != "ok":
            raise LoginError(f"2FA failed: {j}")
        return j["logged_in_user"]["pk"]
    
    # ─────────────── WARMUP AFTER LOGIN ───────────────
    async def warm_postlogin(self, uid, intensity="medium"):
        counts = {"min": 3, "medium": 6, "max": 10}.get(intensity, 6)
        endpoints = [
            ("GET",  "/api/v1/feed/timeline/", None),
            ("GET",  "/api/v1/direct_v2/inbox/", None),
            ("GET",  "/api/v1/news/inbox/", None),
            ("GET",  "/api/v1/feed/reels_tray/", None),
            ("GET",  f"/api/v1/users/{uid}/info/", None),
            ("POST", "/api/v1/qe/sync/", {"id": uid, "server_config_retrieval": "1"}),
            ("GET",  "/api/v1/scores/", None),
            ("GET",  "/api/v1/notifications/badge/", None),
            ("GET",  "/api/v1/media/blocked/", None),
            ("GET",  "/api/v1/feed/saved/", None),
        ]
        random.shuffle(endpoints)
        for method, path, data in endpoints[:counts]:
            try:
                await self.s.request(method, self.BASE + path, data=data)
            except Exception:
                pass
            await self._pause(0.6, 2.4)
    async def change_profile_picture(self, image_path: str):
        """
        Двухшаговый flow как в реальном IG Android клиенте:
        1) rupload_igphoto — заливаем фото, получаем upload_id
        2) change_profile_picture — активируем как аватар
        """
        from pathlib import Path
        import time as _t
        import json as _json

        if not Path(image_path).exists():
            raise UploadError(f"avatar not found: {image_path}")

        with open(image_path, "rb") as f:
            img_bytes = f.read()

        upload_id = str(int(_t.time() * 1000))
        dev = self.s.device
        entity_name = f"{upload_id}_0_{random.randint(1_000_000_000, 9_999_999_999)}"

        # ─── Шаг 1: rupload_igphoto ───
        rupload_params = {
            "media_type": "1",
            "upload_id": upload_id,
            "image_compression": _json.dumps({
                "lib_name": "moz",
                "lib_version": "3.1.m",
                "quality": "80",
            }),
            "retry_context": '{"num_step_auto_retry":0,"num_reupload":0,"num_step_manual_retry":0}',
            "xsharing_user_ids": "[]",
        }

        headers = {
            "Offset": "0",
            "X-Entity-Length": str(len(img_bytes)),
            "X-Entity-Name": entity_name,
            "X-Entity-Type": "image/jpeg",
            "X-Instagram-Rupload-Params": _json.dumps(rupload_params),
            "Content-Type": "application/octet-stream",
        }

        r = await self.s.request(
            "POST",
            f"{self.BASE}/rupload_igphoto/{entity_name}",
            data=img_bytes,
            headers=headers,
            timeout=60,
        )
        if r.status_code != 200:
            raise UploadError(f"photo rupload: HTTP {r.status_code} {r.text[:200]}")

        # даём серверу время обработать
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # ─── Шаг 2: change_profile_picture ───
        from curl_cffi import CurlMime
        mp = CurlMime()
        mp.addpart(name="_uuid",
                   content_type="text/plain; charset=utf-8",
                   data=dev.device_id.encode("utf-8"))
        mp.addpart(name="use_fbuploader",
                   content_type="text/plain; charset=utf-8",
                   data=b"true")
        mp.addpart(name="upload_id",
                   content_type="text/plain; charset=utf-8",
                   data=upload_id.encode("utf-8"))

        r = await self.s.request(
            "POST",
            f"{self.BASE}/api/v1/accounts/change_profile_picture/",
            multipart=mp,
        )

        try:
            j = r.json()
        except Exception:
            raise UploadError(
                f"change_pfp non-JSON HTTP {r.status_code}: {r.text[:200]}"
            )

        if j.get("status") != "ok":
            raise UploadError(f"change_pfp failed: {j.get('message', str(j)[:200])}")
        return j
    # ─────────────── BIO ───────────────
    async def set_biography(self, bio: str):
        """Multipart через CurlMime → JP/CJK сохраняется корректно."""
        from curl_cffi import CurlMime

        device_id_val = (self.s.device.android_id or self.s.device.device_id or "")

        mp = CurlMime()
        mp.addpart(name="raw_text",
                   content_type="text/plain; charset=utf-8",
                   data=bio.encode("utf-8"))
        mp.addpart(name="device_id",
                   content_type="text/plain; charset=utf-8",
                   data=device_id_val.encode("utf-8"))

        r = await self.s.request(
            "POST",
            f"{self.BASE}/api/v1/accounts/set_biography/",
            multipart=mp,
        )

        try:
            j = r.json()
        except Exception:
            raise UploadError(f"set_biography non-JSON: HTTP {r.status_code} {r.text[:200]}")

        # проверяем что реально сработало
        if j.get("status") != "ok":
            msg = j.get("message", "unknown")
            # feedback_required часто означает soft-ban на смену био
            raise UploadError(f"set_biography failed: {msg} | {str(j)[:200]}")

        # доп. проверка — прочитанное био действительно совпадает
        actual = (j.get("user") or {}).get("biography", "")
        if actual.strip() != bio.strip():
            # некоторые эмодзи/спецсимволы IG нормализует — считаем ошибкой только если разница > 5 символов
            if abs(len(actual) - len(bio)) > 5:
                raise UploadError(f"set_biography mismatch: sent={len(bio)} got={len(actual)} chars")

        return j
    async def _probe_resolution(self, path: str) -> tuple[int, int]:
        try:
            out = subprocess.check_output([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0", path,
            ]).decode().strip()
            w, h = out.split("x")
            return int(w), int(h)
        except Exception:
            return 1080, 1920  # fallback
    # ─────────────── UPLOAD REEL ───────────────
    async def upload_reel(
        self,
        video_path: str,
        caption: str = "",
        share_to_feed: bool = False,
        disable_comments: bool = False,
        custom_cover_path: str = None,
    ):
        # защита + диагностика: если в payload есть set — находим и конвертим
        def _deep_convert(obj):
            if isinstance(obj, (set, frozenset)):
                return list(obj)
            if isinstance(obj, dict):
                return {k: _deep_convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_deep_convert(x) for x in obj]
            return obj

        upload_id = str(int(time.time() * 1000))
        duration_ms = await self._probe_duration(video_path)
        width, height = await self._probe_resolution(video_path)
        dev = self.s.device

        # 1. rupload video
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        entity_name = (
            f"{upload_id}_0_"
            f"{random.randint(1_000_000_000, 9_999_999_999)}"
        )

        rupload_params = {
            "is_clips_video": "1",
            "for_direct_story": "0",
            "video_format": "video/mp4",
            "upload_id": upload_id,
            "upload_media_duration_ms": str(duration_ms),
            "upload_media_height": str(height),
            "upload_media_width": str(width),
            "media_type": "2",
            "retry_context": '{"num_step_auto_retry":0,"num_reupload":0,"num_step_manual_retry":0}',
            "xsharing_user_ids": "[]",
        }

        headers = {
            "Offset": "0",
            "X_FB_VIDEO_WATERFALL_ID": dev.waterfall_id,
            "X-Entity-Length": str(len(video_bytes)),
            "X-Entity-Name": entity_name,
            "X-Entity-Type": "video/mp4",
            "X-Instagram-Rupload-Params": json.dumps(_deep_convert(rupload_params)) if isinstance(rupload_params, dict) else str(rupload_params),
            "Content-Type": "application/octet-stream",
        }

        r = await self.s.request(
            "POST",
            f"{self.BASE}/rupload_igvideo/{entity_name}",
            data=video_bytes,
            headers=headers,
            timeout=120,
        )

        if r.status_code != 200:
            raise UploadError(
                f"video rupload: {r.status_code} {r.text[:200]}"
            )

        # 2. cover (первый кадр)
        if custom_cover_path and Path(custom_cover_path).exists():
            cover_path = custom_cover_path
        else:
            cover_path = await self._extract_frame(video_path)
        await self._upload_cover(upload_id, cover_path)

        # 3. wait for encoding + retry configure_to_clips до 5 раз
        payload = {
            "upload_id": upload_id,
            "caption": caption,
            "clips_share_preview_to_feed": "1" if share_to_feed else "0",
            "source_type": "library",
            "device_id": dev.android_id or dev.device_id,
            "_uid": str(dev.device_id[:16]),
            "_uuid": dev.device_id,
            "client_timestamp": str(int(time.time())),
            "client_shared_at": str(int(time.time()) - random.randint(5, 15)),
            "device": {
                "manufacturer":     dev.manufacturer,
                "model":            dev.model,
                "android_version":  dev.os_api,
                "android_release":  dev.os_release,
            },
            "clips": [{"length": duration_ms / 1000, "source_type": "library"}],
            "extra": {"source_width": width, "source_height": height},
            "audio_muted": False,
            "poster_frame_index": 0,
            "disable_comments": "1" if disable_comments else "0",
        }

        # ждём и поллим — IG нужно время на транскодирование
        last_err = None
        wait_sequence = [4, 8, 15, 25, 40]

        # ждём и поллим — IG нужно время на транскодирование
        last_err = None
        wait_sequence = [4, 8, 15, 25, 40]

        # payload уже готов, готовим body_json один раз (это стабильно)
        try:
            body_json = json.dumps(payload, separators=(",", ":"))
        except TypeError:
            body_json = json.dumps(
                _deep_convert(payload),
                separators=(",", ":")
            )

        for wait_sec in wait_sequence:
            await asyncio.sleep(
                wait_sec + random.uniform(-0.5, 1.5)
            )

            try:
                r = await self.s.request(
                    "POST",
                    f"{self.BASE}/api/v1/media/configure_to_clips/",
                    data={"signed_body": f"SIGNATURE.{body_json}"},
                    headers={
                        "Content-Type":
                            "application/x-www-form-urlencoded; charset=UTF-8"
                    }
                )
            except Exception as e:
                last_err = (
                    f"network: {type(e).__name__}: {str(e)[:150]}"
                )
                continue

            # пустое тело — транзиент, ретраим
            if not r.text or not r.text.strip():
                last_err = f"empty response HTTP {r.status_code}"
                continue

            # не-JSON — транзиент
            try:
                j = r.json()
            except Exception:
                last_err = (
                    f"non-JSON HTTP {r.status_code}: "
                    f"{r.text[:150]}"
                )
                continue

            if j.get("status") == "ok":
                return j

            msg = j.get("message", "")
            last_err = j

            if (
                "Transcode not finished" in msg
                or "transcoded" in msg.lower()
            ):
                continue

            # содержательная ошибка — не ретраим
            raise UploadError(f"configure: {j}")

        raise UploadError(
            f"configure failed after {sum(wait_sequence)}s: {last_err}"
        )
    async def _upload_cover(self, upload_id: str, cover_path: str):
        with open(cover_path, "rb") as f:
            data = f.read()
        entity_name = f"{upload_id}_0_{random.randint(1_000_000_000, 9_999_999_999)}"
        headers = {
            "X-Entity-Length": str(len(data)),
            "X-Entity-Name": entity_name,
            "X-Entity-Type": "image/jpeg",
            "X-Instagram-Rupload-Params": json.dumps({
                "media_type": "1",
                "upload_id": upload_id,
                "image_compression": json.dumps({
                    "lib_name": "moz", "lib_version": "3.1.m", "quality": "80"
                }),
            }),
            "Offset": "0",
            "Content-Type": "application/octet-stream",
        }
        await self.s.request(
            "POST",
            f"{self.BASE}/rupload_igphoto/{entity_name}",
            data=data, headers=headers)

    # ─────────────── STATS ───────────────
    async def get_self_stats(self, user_id: str) -> dict:
        """
        Статистика через /feed/user/ (GET, надёжный) + /clips/user/ (POST) как fallback.
        Устойчиво к 405/пустым ответам.
        """

        # 1. Инфо профиля
        r = await self.s.request(
            "GET", f"{self.BASE}/api/v1/users/{user_id}/info/"
        )
        try:
            j = r.json()
        except Exception:
            raise UploadError(f"stats info non-JSON: HTTP {r.status_code}")

        if j.get("status") != "ok" or not j.get("user"):
            raise UploadError(f"stats info fail: {j.get('message', str(j)[:200])}")

        info = j["user"]
        media_count = info.get("media_count", 0)

        # 2. /feed/user/ — GET, основной источник постов
        views = likes = comments = reposts = 0
        reels_count = 0
        seen_ids = set()

        try:
            r = await self.s.request(
                "GET", f"{self.BASE}/api/v1/feed/user/{user_id}/",
                params={"count": "50"}
            )
            if r.text and r.text.strip():
                feed_j = r.json()
                for item in feed_j.get("items", []):
                    is_reel = (
                        item.get("product_type") == "clips"
                        or item.get("media_type") == 2
                        or "clips_metadata" in item
                    )
                    if not is_reel:
                        continue

                    mid = item.get("id") or item.get("pk")
                    if mid in seen_ids:
                        continue
                    seen_ids.add(mid)

                    reels_count += 1
                    views    += int(item.get("play_count", 0) or item.get("view_count", 0) or 0)
                    likes    += int(item.get("like_count", 0) or 0)
                    comments += int(item.get("comment_count", 0) or 0)
                    reposts  += int(item.get("reshare_count", 0)
                                   or item.get("share_count", 0) or 0)
        except Exception as e:
            print(f"[stats] feed/user error: {e}")

        # 3. /clips/user/ — POST (не GET!)
        try:
            r = await self.s.request(
                "POST",
                f"{self.BASE}/api/v1/clips/user/",
                data={
                    "target_user_id": str(user_id),
                    "page_size": "50",
                    "include_feed_video": "true",
                }
            )
            if r.text and r.text.strip():
                clips_j = r.json()
                for item in clips_j.get("items", []):
                    m = item.get("media") or item
                    mid = m.get("id") or m.get("pk")
                    if mid in seen_ids:
                        continue
                    seen_ids.add(mid)

                    reels_count += 1
                    views    += int(m.get("play_count", 0) or 0)
                    likes    += int(m.get("like_count", 0) or 0)
                    comments += int(m.get("comment_count", 0) or 0)
                    reposts  += int(m.get("reshare_count", 0) or 0)
        except Exception as e:
            print(f"[stats] clips/user error: {e}")

        return {
            "followers":      info.get("follower_count", 0),
            "following":      info.get("following_count", 0),
            "reels_count":    reels_count,
            "total_views":    views,
            "total_likes":    likes,
            "total_comments": comments,
            "total_reposts":  reposts,
            "media_count":    media_count,
            "username":       info.get("username"),
        }

    # ─────────────── utils ───────────────
    async def _pause(self, lo: float, hi: float):
        mu = (lo + hi) / 2
        val = random.lognormvariate(mu * 0.6, 0.35)
        await asyncio.sleep(max(lo, min(hi * 1.5, val)))

    async def _probe_duration(self, path: str) -> int:
        try:
            out = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", path,
            ]).decode().strip()
            return int(float(out) * 1000)
        except Exception:
            return 15_000  # fallback 15 сек

    async def _extract_frame(self, video_path: str) -> str:
        tmp = tempfile.mktemp(suffix=".jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-vframes", "1",
                 "-q:v", "2", tmp],
                check=True, capture_output=True)
            return tmp
        except Exception:
            # если ffmpeg упал — генерим чёрный кадр 1080x1920
            from PIL import Image
            img = Image.new("RGB", (1080, 1920), color=(0, 0, 0))
            img.save(tmp, "JPEG", quality=85)
            return tmp