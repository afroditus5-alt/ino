"""
DeviceProfile — генератор фингерпринтов Android/iOS для Instagram Private API.
"""
import random
import hashlib
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from assets.devices_catalog import ANDROID, IOS
from assets.ig_versions import (IG_ANDROID, IG_IOS, BLOKS_VERSIONS,
                                IG_ANDROID_APP_ID, IG_IOS_APP_ID,
                                IG_CAPABILITIES)
from assets.locale_map import (LOCALE_COUNTRY, pick_timezone_for_locale,
                                pick_carrier, region_suffix_for_locale)
from assets.real_builds import REAL_BUILDS


def _stable_uuid(seed: str, salt: str) -> str:
    return str(uuid.UUID(hashlib.md5(f"{salt}:{seed}".encode()).hexdigest()))


def _stable_hex(seed: str, salt: str, length: int = 16) -> str:
    return hashlib.sha256(f"{salt}:{seed}".encode()).hexdigest()[:length]


@dataclass
class DeviceProfile:
    platform: str
    seed: str

    ig_version: str
    ig_version_code: str
    bloks_version: str
    ig_app_id: str

    os_release: str
    os_api: str

    manufacturer: str
    brand: str
    model: str
    device: str
    board: str
    hardware: str
    cpu: str
    gpu: str
    chip_commercial: str
    supported_abis: list
    radio_version: str

    resolution: str
    dpi: str
    scale: str

    build_id: str
    build_incremental: str
    build_fingerprint: str
    security_patch: str

    locale: str
    language: str
    country: str
    timezone_offset: int

    carrier_name: str
    carrier_mcc: str
    carrier_mnc: str

    android_id: str
    device_id: str
    family_device_id: str
    phone_id: str
    advertising_id: str

    waterfall_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pigeon_session_id: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mid: str = ""

    # ============================================================
    def user_agent(self) -> str:
        if self.platform == "android":
            return (
                f"Instagram {self.ig_version} Android "
                f"({self.os_api}/{self.os_release}; "
                f"{self.dpi}; {self.resolution}; "
                f"{self.manufacturer}; {self.model}; {self.device}; "
                f"{self.hardware}; {self.locale}; {self.ig_version_code})"
            )
        else:
            ios_ver_ua = self.os_release.replace(".", "_")
            return (
                f"Instagram {self.ig_version} ({self.model}; "
                f"iOS {ios_ver_ua}; {self.locale}; {self.language}; "
                f"scale={self.scale}; {self.resolution}; {self.ig_version_code})"
            )

    # ============================================================
    @classmethod
    def generate(cls, seed: str, platform: Optional[str] = None,
                 locale: Optional[str] = None,
                 country_hint: Optional[str] = None,
                 tz_offset_hint: Optional[int] = None) -> "DeviceProfile":
        rng = random.Random(f"main:{seed}")

        if platform is None:
            platform = rng.choices(["android", "ios"], weights=[62, 38])[0]

        if platform == "android":
            return cls._make_android(rng, seed, locale, country_hint, tz_offset_hint)
        else:
            return cls._make_ios(rng, seed, locale, country_hint, tz_offset_hint)

    # ============================================================
    @classmethod
    def _make_android(cls, rng, seed, locale, country_hint, tz_hint):
        candidates = ANDROID
        if country_hint:
            filtered = [
                sku for sku in ANDROID
                if any(LOCALE_COUNTRY.get(l) == country_hint
                       for l, _ in sku["popular_locales"])
            ]
            if filtered:
                candidates = filtered
        sku = rng.choices(candidates, weights=[s["weight"] for s in candidates])[0]

        av = rng.choice(sku["android_versions"])

        if sku["resolutions_alt"] and rng.random() < 0.30:
            resolution = rng.choice(sku["resolutions_alt"])
        else:
            resolution = sku["resolution"]

        if sku["dpi_alt"] and rng.random() < 0.40:
            dpi = rng.choice(sku["dpi_alt"])
        else:
            dpi = sku["dpi_native"]

        if locale is None:
            locales_pool = sku["popular_locales"]
            if country_hint:
                matched = [(l, w) for l, w in locales_pool
                           if LOCALE_COUNTRY.get(l) == country_hint]
                if matched:
                    locales_pool = matched
            locale = rng.choices([l for l, _ in locales_pool],
                                 weights=[w for _, w in locales_pool])[0]
        language = locale[:2]
        country = LOCALE_COUNTRY.get(locale, "US")

        tz_offset = pick_timezone_for_locale(locale, tz_hint)
        mcc, mnc, carrier_name = pick_carrier(locale)

        real_builds = REAL_BUILDS.get((sku["model"], av["release"]), [])
        if real_builds:
            b = rng.choice(real_builds)
            if "{REGION}" in b:
                b = b.replace("{REGION}", region_suffix_for_locale(locale))
            build_incremental = b
        else:
            build_incremental = f"{sku['model']}-{av['release']}-{rng.randint(1000, 9999)}"

        build_fingerprint = (
            f"{sku['brand']}/{sku['device']}/{sku['device']}:"
            f"{av['release']}/{av['build_prefix']}/{build_incremental}:"
            f"user/release-keys"
        )

        radio = sku.get("radio_version", "")
        if "{mon}" in radio:
            radio = radio.replace("{mon}", rng.choice(["FA", "FB", "GA", "GB", "HA", "HB"]))
        if "{n}" in radio:
            radio = radio.replace("{n}", str(rng.randint(1, 6)))
        if "{XX}" in radio:
            radio = radio.replace("{XX}",
                                  rng.choice(["HB", "HC", "HD", "HE", "HF", "IA", "IB"]))

        ig_ver, ig_code = rng.choice(IG_ANDROID)
        bloks = rng.choice(BLOKS_VERSIONS)

        android_id = _stable_hex(seed, "android_id", 16)
        device_id = _stable_uuid(seed, "device_id")
        family_did = _stable_uuid(seed, "family_did")
        phone_id = _stable_uuid(seed, "phone_id")
        adid = _stable_uuid(seed, "adid")
        pigeon_seed = f"{seed}:{__import__('datetime').datetime.now():%Y-%m-%d}"
        pigeon_sid = f"UFS-{_stable_uuid(pigeon_seed, 'pigeon')}-0"
        return cls(
            platform="android", seed=seed,
            ig_version=ig_ver, ig_version_code=ig_code,
            bloks_version=bloks, ig_app_id=IG_ANDROID_APP_ID,
            os_release=av["release"], os_api=av["api"],
            manufacturer=sku["manufacturer"], brand=sku["brand"],
            model=sku["model"], device=sku["device"],
            board=sku["board"], hardware=sku["hardware"],
            cpu=sku["cpu"], gpu=sku.get("gpu", ""),
            chip_commercial="",
            supported_abis=sku.get("supported_abis", ["arm64-v8a"]),
            pigeon_session_id=pigeon_sid,
            radio_version=radio,
            resolution=resolution, dpi=dpi, scale="",
            build_id=av["build_prefix"],
            build_incremental=build_incremental,
            build_fingerprint=build_fingerprint,
            security_patch=av.get("security_patch", ""),
            locale=locale, language=language, country=country,
            timezone_offset=tz_offset,
            carrier_name=carrier_name, carrier_mcc=mcc, carrier_mnc=mnc,
            android_id=android_id, device_id=device_id,
            family_device_id=family_did, phone_id=phone_id,
            advertising_id=adid,
        )

    # ============================================================
    @classmethod
    def _make_ios(cls, rng, seed, locale, country_hint, tz_hint):
        candidates = IOS
        if country_hint:
            filtered = [
                sku for sku in IOS
                if any(LOCALE_COUNTRY.get(l) == country_hint
                       for l, _ in sku["popular_locales"])
            ]
            if filtered:
                candidates = filtered
        sku = rng.choices(candidates, weights=[s["weight"] for s in candidates])[0]

        ios_ver, ios_build = rng.choice(sku["ios_versions"])

        if locale is None:
            locales_pool = sku["popular_locales"]
            if country_hint:
                matched = [(l, w) for l, w in locales_pool
                           if LOCALE_COUNTRY.get(l) == country_hint]
                if matched:
                    locales_pool = matched
            locale = rng.choices([l for l, _ in locales_pool],
                                 weights=[w for _, w in locales_pool])[0]
        language = locale[:2]
        country = LOCALE_COUNTRY.get(locale, "US")

        tz_offset = pick_timezone_for_locale(locale, tz_hint)
        mcc, mnc, carrier_name = pick_carrier(locale)

        ig_ver, ig_code = rng.choice(IG_IOS)
        bloks = rng.choice(BLOKS_VERSIONS)

        device_id = _stable_uuid(seed, "device_id")
        family_did = _stable_uuid(seed, "family_did")
        phone_id = _stable_uuid(seed, "phone_id")
        adid = _stable_uuid(seed, "adid")
        pigeon_seed = f"{seed}:{__import__('datetime').datetime.now():%Y-%m-%d}"
        pigeon_sid = f"UFS-{_stable_uuid(pigeon_seed, 'pigeon')}-0"
        return cls(
            platform="ios", seed=seed,
            ig_version=ig_ver, ig_version_code=ig_code,
            bloks_version=bloks, ig_app_id=IG_IOS_APP_ID,
            os_release=ios_ver, os_api="",
            manufacturer="Apple", brand="Apple",
            model=sku["machine"], device=sku["machine"],
            board="", hardware=sku["chip"], cpu="arm64", gpu="Apple GPU",
            chip_commercial=sku["chip"],
            supported_abis=["arm64"], radio_version="",
            resolution=sku["resolution"],
            pigeon_session_id=pigeon_sid,
            dpi=f"{sku['native_dpi']}dpi",
            scale=sku["scale"],
            build_id=ios_build, build_incremental="",
            build_fingerprint=f"Apple/{sku['machine']}/{sku['machine']}:iOS "
                              f"{ios_ver}/{ios_build}",
            security_patch="",
            locale=locale, language=language, country=country,
            timezone_offset=tz_offset,
            carrier_name=carrier_name, carrier_mcc=mcc, carrier_mnc=mnc,
            android_id="", device_id=device_id,
            family_device_id=family_did, phone_id=phone_id,
            advertising_id=adid,
        )

    # ============================================================
    @classmethod
    def from_saved(cls, acc: dict) -> "DeviceProfile":
        """Восстановление из БД. Все поля через .get() с дефолтами."""
        platform = acc.get("platform") or "android"
        default_ig = IG_ANDROID[0] if platform == "android" else IG_IOS[0]

        return cls(
            platform=platform,
            seed=acc.get("login", ""),
            ig_version=acc.get("ig_version") or default_ig[0],
            ig_version_code=acc.get("ig_version_code") or default_ig[1],
            bloks_version=acc.get("bloks_version") or BLOKS_VERSIONS[0],
            ig_app_id=acc.get("ig_app_id") or (IG_ANDROID_APP_ID if platform == "android" else IG_IOS_APP_ID),
            os_release=acc.get("os_release") or "14",
            os_api=acc.get("os_api") or "34",
            manufacturer=acc.get("manufacturer") or "samsung",
            brand=acc.get("brand") or "samsung",
            model=acc.get("model") or "SM-S928B",
            device=acc.get("device_name") or "dm3q",
            board=acc.get("board") or "",
            hardware=acc.get("hardware") or "qcom",
            cpu=acc.get("cpu") or "qcom",
            gpu=acc.get("gpu") or "",
            chip_commercial=acc.get("chip_commercial") or "",
            supported_abis=acc.get("supported_abis") or ["arm64-v8a"],
            radio_version=acc.get("radio_version") or "",
            resolution=acc.get("resolution") or "1080x2340",
            dpi=acc.get("dpi") or "480dpi",
            scale=acc.get("scale") or "",
            build_id=acc.get("build_id") or "",
            build_incremental=acc.get("build_incremental") or "",
            build_fingerprint=acc.get("build_fingerprint") or "",
            security_patch=acc.get("security_patch") or "",
            locale=acc.get("locale") or "en_US",
            language=acc.get("language") or "en",
            country=acc.get("country") or "US",
            timezone_offset=acc.get("timezone_offset") or -18000,
            carrier_name=acc.get("carrier_name") or "",
            carrier_mcc=acc.get("carrier_mcc") or "",
            carrier_mnc=acc.get("carrier_mnc") or "",
            android_id=acc.get("android_id") or "",
            device_id=acc.get("device_id") or "",
            family_device_id=acc.get("family_device_id") or "",
            phone_id=acc.get("phone_id") or "",
            advertising_id=acc.get("advertising_id") or "",
        )

    # ============================================================
    def to_saved(self) -> dict:
        d = asdict(self)
        d["device_name"] = d.pop("device")
        return d