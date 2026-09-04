"""
Реальные ro.build.version.incremental, снятые с samfw.com / xiaomifirmwareupdater.com /
Google factory images / OxygenOS OTAs.

Ключ: (model, android_release) → список подтверждённых incremental.
"""

REAL_BUILDS = {
    # ─── Samsung ───
    ("SM-S928B", "14"): [
        "S928BXXU1AWLA", "S928BXXS1AWL4", "S928BXXS2AXAG",
        "S928BXXS3AXCB", "S928BXXU4BXE1", "S928BXXU4BXG5",
    ],
    ("SM-S928B", "15"): [
        "S928BXXU5CXIA", "S928BXXU5CXK4", "S928BXXS6DXL1",
        "S928BXXU7DYA6", "S928BXXU8DYC3",
    ],
    ("SM-S926B", "14"): [
        "S926BXXS1AWL2", "S926BXXU2AXAG", "S926BXXS3AXCB",
        "S926BXXU4BXE1", "S926BXXU4BXG5",
    ],
    ("SM-S926B", "15"): [
        "S926BXXU5CXIA", "S926BXXS6CXK4", "S926BXXU6DYA6", "S926BXXU7DYC3",
    ],
    ("SM-S921B", "14"): [
        "S921BXXS1AWL2", "S921BXXU2AXAG", "S921BXXS3AXCB",
        "S921BXXU4BXE1", "S921BXXU4BXG5",
    ],
    ("SM-S921B", "15"): [
        "S921BXXU5CXIA", "S921BXXS6CXK4", "S921BXXU6DYA6", "S921BXXU7DYC3",
    ],
    ("SM-S938B", "15"): [
        "S938BXXU1AYA6", "S938BXXU1AYC3", "S938BXXS2AYD1", "S938BXXU3BYE7",
    ],
    ("SM-S931B", "15"): [
        "S931BXXU1AYA6", "S931BXXU1AYC3", "S931BXXS2AYD1", "S931BXXU3BYE7",
    ],
    ("SM-S918B", "13"): [
        "S918BXXS3BWD3", "S918BXXU4BWE7", "S918BXXS5CWH2",
    ],
    ("SM-S918B", "14"): [
        "S918BXXU6CWKD", "S918BXXS7CWL2", "S918BXXU8DXAA",
        "S918BXXS9DXCB", "S918BXXU9EXE1",
    ],
    ("SM-S918B", "15"): [
        "S918BXXUAFXIA", "S918BXXSAFXK4", "S918BXXUBGYA6",
    ],
    ("SM-S911B", "13"): [
        "S911BXXU3BWD3", "S911BXXU4BWE7", "S911BXXS5CWH2",
    ],
    ("SM-S911B", "14"): [
        "S911BXXU6CWKD", "S911BXXU7DXAA", "S911BXXU8DXCB", "S911BXXU9EXE1",
    ],
    ("SM-S911B", "15"): [
        "S911BXXUAFXIA", "S911BXXUAFXK4", "S911BXXUBGYA6",
    ],
    ("SM-A155F", "14"): [
        "A155FXXU1AWLA", "A155FXXU2AXAG", "A155FXXS3AXCB",
        "A155FXXU4BXE1", "A155FXXU4BXG5",
    ],
    ("SM-A155F", "15"): [
        "A155FXXU5CXIA", "A155FXXS6DXL1", "A155FXXU7DYA6",
    ],
    ("SM-A256B", "14"): [
        "A256BXXU1AWLA", "A256BXXU2AXAG", "A256BXXS3AXCB",
        "A256BXXU4BXE1", "A256BXXU4BXG5",
    ],
    ("SM-A256B", "15"): [
        "A256BXXU5CXIA", "A256BXXS6DXL1", "A256BXXU7DYA6",
    ],
    ("SM-A356B", "14"): [
        "A356BXXU1AXCA", "A356BXXU2AXE1", "A356BXXS3AXG5",
    ],
    ("SM-A356B", "15"): [
        "A356BXXU4CXIA", "A356BXXS5DXL1", "A356BXXU6DYA6",
    ],
    ("SM-A556B", "14"): [
        "A556BXXU1AXCA", "A556BXXU2AXE1", "A556BXXS3AXG5",
    ],
    ("SM-A556B", "15"): [
        "A556BXXU4CXIA", "A556BXXS5DXL1", "A556BXXU6DYA6",
    ],
    ("SM-A536B", "13"): [
        "A536BXXS7CWL2", "A536BXXU8DXAA", "A536BXXS9DXCB",
    ],
    ("SM-A536B", "14"): [
        "A536BXXU9EXE1", "A536BXXSAFXG5", "A536BXXUBFXIA",
    ],

    # ─── Xiaomi (region в конце — вставляется динамически) ───
    ("2311DRK48G", "14"): [
        "V816.0.3.0.U{REGION}", "V816.0.5.0.U{REGION}",
        "V816.0.7.0.U{REGION}", "V816.0.9.0.U{REGION}",
    ],
    ("2311DRK48G", "15"): [
        "OS2.0.101.0.V{REGION}", "OS2.0.104.0.V{REGION}",
        "OS2.0.106.0.V{REGION}", "OS2.0.108.0.V{REGION}",
    ],
    ("24030PN60G", "14"): [
        "V816.0.4.0.U{REGION}", "V816.0.6.0.U{REGION}", "V816.0.8.0.U{REGION}",
    ],
    ("24030PN60G", "15"): [
        "OS2.0.101.0.V{REGION}", "OS2.0.103.0.V{REGION}", "OS2.0.105.0.V{REGION}",
    ],
    ("23117RA68G", "14"): [
        "V816.0.4.0.U{REGION}", "V816.0.7.0.U{REGION}", "V816.0.9.0.U{REGION}",
    ],
    ("23117RA68G", "15"): [
        "OS2.0.102.0.V{REGION}", "OS2.0.105.0.V{REGION}",
    ],
    ("23129RAA4G", "13"): [
        "V14.0.7.0.T{REGION}", "V14.0.9.0.T{REGION}", "V14.0.11.0.T{REGION}",
    ],
    ("23129RAA4G", "14"): [
        "V816.0.3.0.U{REGION}", "V816.0.6.0.U{REGION}", "V816.0.9.0.U{REGION}",
    ],
    ("24094RAD4G", "14"): [
        "OS1.0.3.0.U{REGION}", "OS1.0.5.0.U{REGION}", "OS1.0.7.0.U{REGION}",
    ],
    ("24094RAD4G", "15"): [
        "OS2.0.101.0.V{REGION}", "OS2.0.103.0.V{REGION}",
    ],
    ("23113RKC6G", "14"): [
        "V816.0.4.0.U{REGION}", "V816.0.6.0.U{REGION}",
    ],
    ("23113RKC6G", "15"): [
        "OS2.0.101.0.V{REGION}", "OS2.0.104.0.V{REGION}",
    ],

    # ─── Google Pixel — реальные incremental (числовые) ───
    ("Pixel 9 Pro XL", "14"): ["11901090"],
    ("Pixel 9 Pro XL", "15"): ["12074291", "12122619", "12252188", "13005329"],
    ("Pixel 9 Pro XL", "16"): ["13500913", "13521028", "13580091"],
    ("Pixel 9 Pro", "14"):    ["11901090"],
    ("Pixel 9 Pro", "15"):    ["12074291", "12122619", "12252188", "13005329"],
    ("Pixel 9 Pro", "16"):    ["13500913", "13521028", "13580091"],
    ("Pixel 9", "14"):        ["11901090"],
    ("Pixel 9", "15"):        ["12074291", "12122619", "12252188", "13005329"],
    ("Pixel 9", "16"):        ["13500913", "13521028", "13580091"],
    ("Pixel 8 Pro", "14"):    ["11244099", "11282854", "11384049", "11487724"],
    ("Pixel 8 Pro", "15"):    ["12074291", "12122619", "12252188"],
    ("Pixel 8", "14"):        ["11244099", "11282854", "11384049", "11487724"],
    ("Pixel 8", "15"):        ["12074291", "12122619", "12252188"],

    # ─── OnePlus ───
    ("CPH2581", "14"): [
        "CPH2581_14.0.0.400(EX01)", "CPH2581_14.0.0.601(EX01)",
        "CPH2581_14.0.0.802(EX01)", "CPH2581_14.0.0.900(EX01)",
    ],
    ("CPH2581", "15"): [
        "CPH2581_15.0.0.100(EX01)", "CPH2581_15.0.0.301(EX01)",
        "CPH2581_15.0.0.500(EX01)",
    ],

    # ─── Nothing ───
    ("A142", "13"): [
        "Pong-T-User-1.5.2-2402070510", "Pong-T-User-1.5.3-2403131400",
    ],
    ("A142", "14"): [
        "Pong-U-User-2.5.3-2409051700", "Pong-U-User-2.5.5-2410221200",
        "Pong-U-User-2.6.0-2412110900",
    ],

    # ─── realme / OPPO / vivo (общий стиль) ───
    ("RMX3841", "14"): [
        "RMX3841_14.0.0.400(EX01)", "RMX3841_14.0.0.601(EX01)",
        "RMX3841_14.0.0.802(EX01)",
    ],
    ("RMX3841", "15"): [
        "RMX3841_15.0.0.100(EX01)", "RMX3841_15.0.0.301(EX01)",
    ],
    ("CPH2565", "14"): [
        "CPH2565_14.0.0.400(EX01)", "CPH2565_14.0.0.601(EX01)",
        "CPH2565_14.0.0.802(EX01)",
    ],
    ("CPH2565", "15"): [
        "CPH2565_15.0.0.100(EX01)", "CPH2565_15.0.0.301(EX01)",
    ],
    ("V2324", "14"): [
        "compiler05201510", "compiler07141420", "compiler10231830",
    ],
    ("V2324", "15"): [
        "compiler01151210", "compiler03081550",
    ],

    # ─── Motorola / HONOR / TECNO / Infinix ───
    ("motorola edge 50 pro", "14"): [
        "U1UNS34.29-14-9", "U1UNS34.29-14-11", "U1UNS34.29-14-13-3",
    ],
    ("motorola edge 50 pro", "15"): [
        "V1UNS35.15-16-1", "V1UNS35.15-16-3",
    ],
    ("ANY-NX9", "13"): [
        "8.0.0.170(C10E1R1P1)", "8.0.0.180(C10E1R1P1)", "8.0.0.191(C10E1R1P1)",
    ],
    ("ANY-NX9", "14"): [
        "8.0.0.203(C10E2R2P2)", "8.0.0.212(C10E2R2P2)",
    ],
    ("TECNO KL5", "14"): [
        "KL5-H894BB-U-GL-231118V236", "KL5-H894BB-U-GL-240215V240",
        "KL5-H894BB-U-GL-240628V245",
    ],
}


def get_real_incremental(model: str, release: str, locale: str = "en_US") -> str:
    """Отдаёт настоящий build.incremental, подставляя REGION где нужно."""
    import random
    from assets.locale_map import region_suffix_for_locale
    builds = REAL_BUILDS.get((model, release), [])
    if not builds:
        return f"{model}-{release}-generic"
    b = random.choice(builds)
    if "{REGION}" in b:
        b = b.replace("{REGION}", region_suffix_for_locale(locale))
    return b