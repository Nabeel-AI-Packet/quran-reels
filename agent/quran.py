"""Fetches verse text (alquran.cloud) and recitation audio (everyayah.com)."""
import re
import subprocess

import requests

from . import config

def parse_key(key):
    """'94:5-6' -> (94, [5, 6])"""
    surah, ayahs = key.split(":")
    first, _, last = ayahs.partition("-")
    return int(surah), list(range(int(first), int(last or first) + 1))


def _clean(text):
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_text(key):
    """Returns arabic [(n, text)], english_list, polish_list, and the surah's Arabic and English names."""
    surah, ayahs = parse_key(key)
    arabic, english, polish = [], [], []
    names = {}
    for n in ayahs:
        r = requests.get(
            f"https://api.alquran.cloud/v1/ayah/{surah}:{n}/editions/{','.join(config.EDITIONS)}",
            timeout=30)
        r.raise_for_status()
        data = r.json()["data"]
        got = [e["edition"]["identifier"] for e in data]
        if got != list(config.EDITIONS):                 # never show a wrong text silently
            raise RuntimeError(f"Verse source returned editions {got}, expected {list(config.EDITIONS)}")
        ar, en, pl = (_clean(e["text"]) for e in data)
        names = {"surah_ar": data[0]["surah"]["name"], "surah_en": data[0]["surah"]["englishName"]}
        if n == 1 and surah not in (1, 9):
            ar = " ".join(ar.split()[4:])        # the Bismillah is not part of ayah 1 here
        arabic.append((n, ar))
        english.append(en)
        polish.append(pl)
    span = str(ayahs[0]) if len(ayahs) == 1 else f"{ayahs[0]}–{ayahs[-1]}"
    return {"arabic": arabic, "english_list": english, "polish_list": polish, **names,
            "reference": f"{names['surah_en']} {surah}:{span}"}


def _duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def fetch_audio(key, reciter, out_path):
    """Downloads each ayah's MP3 and joins them into one file. Returns each ayah's length in seconds."""
    info = config.RECITERS[reciter]
    surah, ayahs = parse_key(key)
    if "qa" in info:
        from . import segment
        parts = segment.ayah_files(info["qa"], surah, ayahs, out_path)
        return _join(parts, out_path)
    folder = info["folder"]
    parts = []
    for n in ayahs:
        url = f"https://everyayah.com/data/{folder}/{surah:03d}{n:03d}.mp3"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        p = f"{out_path}.{n}.mp3"
        with open(p, "wb") as f:
            f.write(r.content)
        parts.append(p)
    return _join(parts, out_path)


def _join(parts, out_path):
    with open(out_path + ".txt", "w") as f:
        f.writelines(f"file '{p.split('/')[-1]}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", out_path + ".txt", "-c:a", "libmp3lame", "-q:a", "2", out_path], check=True)
    return [_duration(p) for p in parts]
