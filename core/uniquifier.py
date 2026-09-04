"""
Уникализатор с семафором на ffmpeg (защита от перегрузки CPU при 70+ потоках).
Универсальный пресет = быстрый + реально ломает pHash + чистит метаданные.
"""
import subprocess
import random
import tempfile
import os
import asyncio
from pathlib import Path


# Семафор для параллельных ffmpeg — независим от network threads
# 6 одновременных ffmpeg = ~90% загрузка 6-8 ядерного CPU
_FFMPEG_SEM = asyncio.Semaphore(6)


class ReelUniquifier:
    """
    Уровни:
        fast       — только remux + metadata strip (~0.5 сек, слабое изменение pHash)
        universal  — trim + micro-crop + audio pitch + metadata strip (~2-4 сек, СИЛЬНОЕ изменение pHash)
        light      — как universal но нежнее (~3-5 сек)
        medium     — universal + eq + rotate (~5-8 сек)
        heavy      — full processing, лучше не юзать на 70 потоков (~10-15 сек)
    """

    @staticmethod
    async def unique_async(src: str, dst: str = None, level: str = "universal",
                           audio: bool = True) -> str:
        """Async обёртка с семафором. Используй эту в orchestrator."""
        async with _FFMPEG_SEM:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, ReelUniquifier.unique, src, dst, level, audio
            )

    @staticmethod
    def unique(src: str, dst: str = None, level: str = "universal",
               audio: bool = True) -> str:
        dst = dst or tempfile.mktemp(suffix=".mp4")

        if level == "fast":
            return ReelUniquifier._fast(src, dst)

        if level == "universal":
            return ReelUniquifier._universal(src, dst, audio)

        if level == "light":
            return ReelUniquifier._light(src, dst, audio)

        if level == "medium":
            return ReelUniquifier._medium(src, dst, audio)

        if level == "heavy":
            return ReelUniquifier._heavy(src, dst, audio)

        # default → universal
        return ReelUniquifier._universal(src, dst, audio)

    # ─────────────────────────────────────
    @staticmethod
    def _random_encoder_signature():
        """Случайные метаданные — маскируем что это ffmpeg."""
        return {
            "encoder": random.choice([
                "Lavc60.31.102 libx264",       # ffmpeg
                "Apple H.264 Encoder",         # iPhone
                "Android MediaCodec",          # Android
                "InstagramAndroid 449.0.0",
                "InstagramiOS 449.0.0",
            ]),
            "comment": os.urandom(8).hex(),
            "title": f"video_{random.randint(100000, 999999)}",
            "software": random.choice([
                "Instagram", "com.instagram.android", "iOS Photos",
            ]),
        }

    # ─────────────────────────────────────
    @staticmethod
    def _fast(src, dst):
        """Только remux + metadata strip. Быстро но pHash слабо меняется."""
        meta = ReelUniquifier._random_encoder_signature()
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src,
            "-c", "copy",
            "-map_metadata", "-1",           # убираем ВСЕ метаданные из инпута
            "-movflags", "+faststart",
            "-metadata", f"encoder={meta['encoder']}",
            "-metadata", f"comment={meta['comment']}",
            "-metadata", f"title={meta['title']}",
            dst,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return dst

    # ─────────────────────────────────────
    @staticmethod
    def _universal(src, dst, audio):
        """
        Универсальный: быстрый + сильное изменение pHash.
        - Обрезка первых/последних кадров (сдвиг keyframes)
        - Микро-crop (сдвиг пикселей)
        - Micro-скорость видео/аудио
        - Полная зачистка + подмена метаданных
        Занимает 2-4 сек на 15-30 сек видео.
        """
        speed = random.uniform(0.99, 1.01)
        trim_start = random.uniform(0.10, 0.25)   # обрезаем 100-250мс с начала
        trim_end = random.uniform(0.10, 0.25)     # и с конца
        crop = random.randint(2, 6)               # микро-crop 2-6px по краям
        audio_semitones = random.uniform(-0.15, 0.15)  # ~10 центов тона

        vf = (
            f"trim=start={trim_start},setpts=PTS-STARTPTS,"
            f"crop=iw-{crop*2}:ih-{crop*2},"
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setpts={1/speed}*PTS"
        )

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", src, "-vf", vf]

        if audio:
            audio_speed = speed * (2 ** (audio_semitones / 12))
            af = (
                f"atrim=start={trim_start},asetpts=PTS-STARTPTS,"
                f"asetrate=44100*{2**(audio_semitones/12)},aresample=44100,"
                f"atempo={audio_speed / (2**(audio_semitones/12))}"
            )
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-an"]

        meta = ReelUniquifier._random_encoder_signature()
        cmd += [
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-g", str(random.choice([48, 60, 72])),
            "-t", "60",                            # лимит длины 60 сек (IG reels)
            "-map_metadata", "-1",
            "-metadata", f"encoder={meta['encoder']}",
            "-metadata", f"comment={meta['comment']}",
            "-metadata", f"title={meta['title']}",
            "-metadata", f"software={meta['software']}",
            "-movflags", "+faststart",
            dst,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return dst

    # ─────────────────────────────────────
    @staticmethod
    def _light(src, dst, audio):
        """Universal - минус trim (мягче для короткого контента)."""
        speed = random.uniform(0.995, 1.005)
        crop = random.randint(1, 3)
        brtn = random.uniform(-0.01, 0.01)
        satu = random.uniform(0.99, 1.01)

        vf = (
            f"crop=iw-{crop*2}:ih-{crop*2},"
            f"eq=brightness={brtn}:saturation={satu},"
            f"setpts={1/speed}*PTS"
        )
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", src, "-vf", vf]

        if audio:
            cmd += ["-af", f"atempo={speed}", "-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-an"]

        meta = ReelUniquifier._random_encoder_signature()
        cmd += [
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-g", "60", "-map_metadata", "-1",
            "-metadata", f"encoder={meta['encoder']}",
            "-metadata", f"comment={meta['comment']}",
            "-movflags", "+faststart",
            dst,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return dst

    # ─────────────────────────────────────
    @staticmethod
    def _medium(src, dst, audio):
        """Universal + eq + rotate. Заметно медленнее."""
        speed = random.uniform(0.98, 1.02)
        trim_start = random.uniform(0.15, 0.30)
        crop = random.randint(3, 8)
        rot = random.uniform(-0.4, 0.4)
        brtn = random.uniform(-0.03, 0.03)
        contr = random.uniform(0.97, 1.03)
        satu = random.uniform(0.95, 1.05)
        audio_semitones = random.uniform(-0.2, 0.2)

        vf = (
            f"trim=start={trim_start},setpts=PTS-STARTPTS,"
            f"crop=iw-{crop*2}:ih-{crop*2},"
            f"eq=brightness={brtn}:contrast={contr}:saturation={satu},"
            f"rotate={rot}*PI/180:fillcolor=black@0,"
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setpts={1/speed}*PTS"
        )
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", src, "-vf", vf]

        if audio:
            audio_speed = speed * (2 ** (audio_semitones / 12))
            af = (
                f"atrim=start={trim_start},asetpts=PTS-STARTPTS,"
                f"asetrate=44100*{2**(audio_semitones/12)},aresample=44100,"
                f"atempo={audio_speed / (2**(audio_semitones/12))}"
            )
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-an"]

        meta = ReelUniquifier._random_encoder_signature()
        cmd += [
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-g", "60", "-t", "60", "-map_metadata", "-1",
            "-metadata", f"encoder={meta['encoder']}",
            "-metadata", f"comment={meta['comment']}",
            "-movflags", "+faststart",
            dst,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return dst

    # ─────────────────────────────────────
    @staticmethod
    def _heavy(src, dst, audio):
        """Как medium но с более агрессивными изменениями. Не для 70 потоков."""
        speed = random.uniform(0.97, 1.03)
        trim_start = random.uniform(0.20, 0.40)
        crop = random.randint(5, 12)
        rot = random.uniform(-0.7, 0.7)
        brtn = random.uniform(-0.05, 0.05)
        contr = random.uniform(0.93, 1.07)
        satu = random.uniform(0.92, 1.08)
        audio_semitones = random.uniform(-0.3, 0.3)

        vf = (
            f"trim=start={trim_start},setpts=PTS-STARTPTS,"
            f"crop=iw-{crop*2}:ih-{crop*2},"
            f"eq=brightness={brtn}:contrast={contr}:saturation={satu},"
            f"rotate={rot}*PI/180:fillcolor=black@0,"
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setpts={1/speed}*PTS"
        )
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", src, "-vf", vf]

        if audio:
            audio_speed = speed * (2 ** (audio_semitones / 12))
            af = (
                f"atrim=start={trim_start},asetpts=PTS-STARTPTS,"
                f"asetrate=44100*{2**(audio_semitones/12)},aresample=44100,"
                f"atempo={audio_speed / (2**(audio_semitones/12))}"
            )
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-an"]

        meta = ReelUniquifier._random_encoder_signature()
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-g", "60", "-t", "60", "-map_metadata", "-1",
            "-metadata", f"encoder={meta['encoder']}",
            "-metadata", f"comment={meta['comment']}",
            "-movflags", "+faststart",
            dst,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return dst