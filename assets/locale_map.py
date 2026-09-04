"""
Локали → возможные таймзоны + MCC/MNC + carrier.
X-IG-Timezone-Offset должен соответствовать гео прокси, не рандом.
"""

# locale → список возможных TZ-оффсетов в секундах
# (страна большая → несколько зон)
LOCALE_TZ = {
    # Americas
    "en_US": [-18000, -21600, -25200, -28800, -32400],  # EST/CST/MST/PST/AKST
    "en_CA": [-18000, -21600, -25200, -28800],
    "es_MX": [-21600, -25200, -28800],                  # Ciudad de Mexico + border
    "pt_BR": [-10800, -14400],                          # Brasilia + Amazonas
    "es_AR": [-10800],
    "es_CO": [-18000],
    "es_CL": [-14400, -10800],
    "es_PE": [-18000],
    # Europe
    "en_GB":  [0],
    "en_IE":  [0],
    "pt_PT":  [0],
    "de_DE":  [3600],
    "fr_FR":  [3600],
    "es_ES":  [3600],
    "it_IT":  [3600],
    "nl_NL":  [3600],
    "pl_PL":  [3600],
    "sv_SE":  [3600],
    "no_NO":  [3600],
    "da_DK":  [3600],
    "fi_FI":  [7200],
    "el_GR":  [7200],
    "ro_RO":  [7200],
    "uk_UA":  [7200],
    "tr_TR":  [10800],
    "ru_RU":  [10800, 14400, 18000, 21600, 25200, 28800, 32400, 36000],  # Msk → Kamchatka
    # Asia
    "hi_IN":  [19800],
    "en_IN":  [19800],
    "ja_JP":  [32400],
    "ko_KR":  [32400],
    "zh_CN":  [28800],
    "zh_TW":  [28800],
    "zh_HK":  [28800],
    "th_TH":  [25200],
    "vi_VN":  [25200],
    "id_ID":  [25200, 28800, 32400],  # WIB/WITA/WIT
    "ms_MY":  [28800],
    "fil_PH": [28800],
    # MENA / Africa
    "ar_SA":  [10800],
    "ar_AE":  [14400],
    "ar_EG":  [7200],
    "ar_MA":  [3600],
    "ar_DZ":  [3600],
    "he_IL":  [7200],
    "en_NG":  [3600],
    "en_KE":  [10800],
    "en_ZA":  [7200],
    # Oceania
    "en_AU":  [36000, 34200, 28800],
    "en_NZ":  [43200],
}

# locale → (MCC, MNC, carrier_name)   — типичный оператор
LOCALE_CARRIER = {
    "en_US":  [("310", "260", "T-Mobile"), ("310", "410", "AT&T"), ("311", "480", "Verizon")],
    "en_CA":  [("302", "610", "Bell"), ("302", "720", "Rogers")],
    "es_MX":  [("334", "020", "Telcel"), ("334", "050", "Movistar")],
    "pt_BR":  [("724", "05", "Claro BR"), ("724", "10", "VIVO"), ("724", "03", "TIM")],
    "en_GB":  [("234", "10", "O2"), ("234", "15", "Vodafone UK"), ("234", "30", "EE")],
    "de_DE":  [("262", "01", "T-Mobile.de"), ("262", "02", "Vodafone.de"), ("262", "03", "O2 - de")],
    "fr_FR":  [("208", "01", "Orange F"), ("208", "10", "SFR"), ("208", "20", "Bouygues")],
    "es_ES":  [("214", "01", "Vodafone ES"), ("214", "07", "Movistar")],
    "it_IT":  [("222", "01", "TIM"), ("222", "10", "Vodafone IT")],
    "ru_RU":  [("250", "01", "MTS-RUS"), ("250", "02", "MegaFon RUS"), ("250", "99", "Beeline")],
    "uk_UA":  [("255", "01", "MTS UKR"), ("255", "03", "Kyivstar")],
    "tr_TR":  [("286", "01", "Turkcell"), ("286", "02", "Vodafone TR")],
    "hi_IN":  [("405", "854", "Jio"), ("404", "10", "Airtel"), ("405", "51", "Vi")],
    "en_IN":  [("405", "854", "Jio"), ("404", "10", "Airtel")],
    "ja_JP":  [("440", "10", "docomo"), ("440", "20", "SoftBank"), ("440", "50", "KDDI")],
    "ko_KR":  [("450", "05", "SKTelecom"), ("450", "06", "KT"), ("450", "08", "LG U+")],
    "zh_CN":  [("460", "00", "CHINA MOBILE"), ("460", "01", "CHN-UNICOM")],
    "id_ID":  [("510", "10", "Telkomsel"), ("510", "11", "XL")],
    "th_TH":  [("520", "03", "AIS"), ("520", "18", "DTAC")],
    "vi_VN":  [("452", "01", "Mobifone"), ("452", "04", "Viettel")],
    "ar_SA":  [("420", "03", "Zain SA"), ("420", "01", "STC")],
    "ar_AE":  [("424", "02", "Etisalat")],
    "ar_EG":  [("602", "01", "Orange EG"), ("602", "02", "Vodafone EG")],
    "en_NG":  [("621", "20", "Airtel NG"), ("621", "30", "MTN NG")],
    "en_KE":  [("639", "02", "Safaricom")],
    "en_ZA":  [("655", "01", "Vodacom SA"), ("655", "10", "MTN-SA")],
    "en_AU":  [("505", "01", "Telstra"), ("505", "02", "YES OPTUS")],
    "pt_PT":  [("268", "01", "vodafone P"), ("268", "06", "NOS")],
    "pl_PL":  [("260", "01", "Plus"), ("260", "02", "T-Mobile PL")],
    "nl_NL":  [("204", "04", "Vodafone NL"), ("204", "08", "KPN")],
}

# locale → страна (ISO-2) для X-IG-App-Startup-Country и гео прокси match
LOCALE_COUNTRY = {
    "en_US": "US", "en_CA": "CA", "es_MX": "MX", "pt_BR": "BR",
    "es_AR": "AR", "es_CO": "CO", "es_CL": "CL", "es_PE": "PE",
    "en_GB": "GB", "en_IE": "IE", "pt_PT": "PT",
    "de_DE": "DE", "fr_FR": "FR", "es_ES": "ES", "it_IT": "IT",
    "nl_NL": "NL", "pl_PL": "PL", "sv_SE": "SE", "no_NO": "NO",
    "da_DK": "DK", "fi_FI": "FI", "el_GR": "GR", "ro_RO": "RO",
    "uk_UA": "UA", "tr_TR": "TR", "ru_RU": "RU",
    "hi_IN": "IN", "en_IN": "IN", "ja_JP": "JP", "ko_KR": "KR",
    "zh_CN": "CN", "zh_TW": "TW", "zh_HK": "HK",
    "th_TH": "TH", "vi_VN": "VN", "id_ID": "ID", "ms_MY": "MY",
    "fil_PH": "PH", "ar_SA": "SA", "ar_AE": "AE", "ar_EG": "EG",
    "ar_MA": "MA", "ar_DZ": "DZ", "he_IL": "IL",
    "en_NG": "NG", "en_KE": "KE", "en_ZA": "ZA",
    "en_AU": "AU", "en_NZ": "NZ",
}


def pick_timezone_for_locale(locale: str, geo_tz_offset: int | None = None) -> int:
    """
    Если известен реальный TZ страны прокси — используем его.
    Иначе — случайный из возможных для локали.
    """
    import random
    options = LOCALE_TZ.get(locale, [0])
    if geo_tz_offset is not None:
        # ищем ближайший
        return min(options, key=lambda x: abs(x - geo_tz_offset))
    return random.choice(options)


def pick_carrier(locale: str) -> tuple[str, str, str]:
    import random
    carriers = LOCALE_CARRIER.get(locale, [("310", "260", "T-Mobile")])
    return random.choice(carriers)


def region_suffix_for_locale(locale: str) -> str:
    """Регион для build.incremental Xiaomi/OPPO/HONOR."""
    country = LOCALE_COUNTRY.get(locale, "US")
    return {
        "RU": "RUXM", "UA": "RUXM", "BY": "RUXM",
        "IN": "INXM",
        "CN": "CNXM", "HK": "CNXM", "TW": "CNXM",
        "US": "MIXM", "CA": "MIXM", "MX": "MIXM", "BR": "MIXM",
        "TR": "TREEA", "SA": "MEAEA", "AE": "MEAEA",
        "ID": "IDXM", "TH": "IDXM", "VN": "IDXM", "MY": "IDXM",
    }.get(country, "EUEEA")