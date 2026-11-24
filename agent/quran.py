"""Fetches verse text (alquran.cloud) and recitation audio (everyayah.com)."""
import re
import subprocess

import requests

from . import config

SURAH_NAMES = {
    2: "Al-Baqarah", 13: "Ar-Ra'd", 39: "Az-Zumar", 40: "Ghafir", 65: "At-Talaq",
    94: "Ash-Sharh", 112: "Al-Ikhlas",
}


def parse_key(key):
    """'94:5-6' -> (94, [5, 6])"""
    surah, ayahs = key.split(":")
    first, _, last = ayahs.partition("-")
    return int(surah), list(range(int(first), int(last or first) + 1))


def reference(key):
    surah, ayahs = parse_key(key)
    name = SURAH_NAMES.get(surah, f"Surah {surah}")
    span = str(ayahs[0]) if len(ayahs) == 1 else f"{ayahs[0]}–{ayahs[-1]}"
    return f"{name} {surah}:{span}"


def _clean(text):
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_text(key):
    """Returns {'arabic': [(n, text), ...], 'english': str, 'polish': str}."""
    surah, ayahs = parse_key(key)
    arabic, english, polish = [], [], []
    for n in ayahs:
        r = requests.get(
            f"https://api.alquran.cloud/v1/ayah/{surah}:{n}/editions/{','.join(config.EDITIONS)}",
            timeout=30)
        r.raise_for_status()
        ar, en, pl = (_clean(e["text"]) for e in r.json()["data"])
        if n == 1 and surah not in (1, 9):
            ar = " ".join(ar.split()[4:])        # the Bismillah is not part of ayah 1 here
        arabic.append((n, ar))
        english.append(en)
        polish.append(pl)
    return {"arabic": arabic, "english": " ".join(english), "polish": " ".join(polish)}


def fetch_audio(key, reciter, out_path):
    """Downloads each ayah's MP3 and joins them into one file. Returns its length in seconds."""
    folder = config.RECITERS[reciter]
    surah, ayahs = parse_key(key)
    parts = []
    for n in ayahs:
        url = f"https://everyayah.com/data/{folder}/{surah:03d}{n:03d}.mp3"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        p = f"{out_path}.{n}.mp3"
        with open(p, "wb") as f:
            f.write(r.content)
        parts.append(p)
    with open(out_path + ".txt", "w") as f:
        f.writelines(f"file '{p.split('/')[-1]}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", out_path + ".txt", "-c:a", "libmp3lame", "-q:a", "2", out_path], check=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", out_path], capture_output=True, text=True, check=True)
    return float(dur.stdout.strip())
