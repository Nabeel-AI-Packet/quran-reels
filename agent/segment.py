"""Cuts single verses out of a full-surah recording (quranicaudio.com).

Verses in murattal recitation are separated by pauses. The recording may start with the
isti'adha and/or basmala, so for 0, 1 and 2 leading extra parts we split at the longest pauses
and keep the split whose part lengths best follow the verse text lengths (recitation time grows
with text length). If even the best split agrees poorly, it stops instead of guessing.
"""
import re
import subprocess

import requests

BASE = "https://download.quranicaudio.com/quran/"
MIN_CORR = 0.8


def _verse_lengths(surah):
    r = requests.get(f"https://api.alquran.cloud/v1/surah/{surah}/quran-simple-clean", timeout=60)
    r.raise_for_status()
    texts = [a["text"] for a in r.json()["data"]["ayahs"]]
    if surah not in (1, 9) and texts[0].startswith("بسم"):
        texts[0] = " ".join(texts[0].split(" ")[4:])        # the basmala is recited as its own part
    return [len(t.replace(" ", "")) for t in texts]


def _pauses(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                        "silencedetect=noise=-38dB:d=0.3", "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return [((s + e) / 2, e - s) for s, e in zip(starts, ends)]


def _duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _corr(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if not vx or not vy:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (vx * vy) ** 0.5


def split(path, lengths, has_basmala):
    """Returns [(start, end)] per verse of the whole surah."""
    total = _duration(path)
    pauses = [(m, d) for m, d in _pauses(path) if 0.8 < m < total - 0.8]
    best = None
    for extra in ((1, 0, 2) if has_basmala else (0, 1)):
        k = len(lengths) + extra - 1
        if k < 0 or len(pauses) < k:
            continue
        mids = sorted(m for m, _ in sorted(pauses, key=lambda p: -p[1])[:k])
        bounds = [0.0] + mids + [total]
        segs = list(zip(bounds[:-1], bounds[1:]))[extra:]
        r = _corr(lengths, [e - s for s, e in segs]) if len(lengths) >= 3 else 1.0
        if best is None or r > best[0]:
            best = (r, segs)
    if best is None or best[0] < MIN_CORR:
        raise RuntimeError("could not find the verse boundaries reliably in this recording")
    return best[1]


def ayah_files(qa_path, surah, ayahs, out_path):
    full = out_path + ".surah.mp3"
    r = requests.get(f"{BASE}{qa_path}{surah:03d}.mp3", timeout=300)
    r.raise_for_status()
    with open(full, "wb") as f:
        f.write(r.content)
    segs = split(full, _verse_lengths(surah), has_basmala=surah not in (1, 9))
    parts = []
    for n in ayahs:
        s, e = segs[n - 1]
        s, e = max(0.0, s - 0.1), e + 0.1             # never clip the first or last sound
        p = f"{out_path}.{n}.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", full,
                        "-c:a", "libmp3lame", "-q:a", "2", p], check=True)
        parts.append(p)
    return parts
