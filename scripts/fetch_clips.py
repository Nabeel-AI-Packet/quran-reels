"""Builds the nature-footage library in assets/clips from free sources that need no account:

* Wikimedia Commons - only CC0, public domain, or CC BY (credited in captions)
* NASA Image and Video Library - Earth and space footage (not copyrighted; no endorsement implied)

Each clip is cut to 10 s from the middle of the video, center-cropped to 1080x1920, silent.
Licence details for every clip go into assets/clips/clips.json.
Run by the fetch-clips workflow. Safe to run again: clips already in the library are skipped.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "clips")
INDEX = os.path.join(OUT, "clips.json")
UA = {"User-Agent": "quran-reels/1.0 (github.com/Nabeel-AI-Packet/quran-reels)"}

COMMONS = ["waterfall", "ocean waves", "sea waves beach", "river stream", "mountains clouds timelapse",
           "clouds timelapse", "sunset timelapse", "sunrise", "forest", "rain drops", "lightning storm",
           "desert dunes", "snow mountains", "night sky stars timelapse", "aurora", "lake reflection"]
NASA = ["earth from space", "ISS earth view", "aurora from space", "galaxy", "nebula", "sunrise over earth"]
# never behind Quran recitation: people, music, worship of other faiths, flags, sport, vehicles
EXCLUDE = re.compile(r"\b(people|person|man|men|woman|women|girl|boy|child|kid|crowd|tourist|surf|swim|dance|"
                     r"music|concert|party|church|cathedral|temple|statue|buddha|cross|christmas|flag|"
                     r"football|car|cars|train|ship|boat|kayak|interview|logo|text|astronaut|crew)\b", re.I)
OK_LICENCE = re.compile(r"^(cc0|public domain|pd[- ].*|cc by \d(\.\d)?|cc-by-\d(\.\d)?)$", re.I)
PER_QUERY = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def commons(query):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=60, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"filetype:video {query}", "gsrlimit": 25, "prop": "videoinfo",
        "viprop": "url|size|extmetadata|derivatives"})
    r.raise_for_status()
    for p in (r.json().get("query", {}).get("pages") or {}).values():
        vi = (p.get("videoinfo") or [{}])[0]
        meta = vi.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value") or "").strip()
        title = p.get("title", "")
        desc = re.sub(r"<[^>]+>", " ", meta.get("ImageDescription", {}).get("value", ""))
        if not OK_LICENCE.match(lic) or EXCLUDE.search(f"{title} {desc}"):
            continue
        if max(vi.get("width", 0), vi.get("height", 0)) < 1280:
            continue
        # a transcode near 1080p keeps downloads small
        ders = [d for d in vi.get("derivatives", []) if d.get("height", 0) >= 720 and "webm" in d.get("type", "")]
        ders.sort(key=lambda d: abs(d.get("height", 0) - 1080))
        url = ders[0]["src"] if ders else vi.get("url")
        if not ders and vi.get("size", 0) > 300e6:
            continue
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip() or "unknown"
        needs = "by" in lic.lower()
        yield {"id": f"commons-{p['pageid']}", "url": url, "source": vi.get("descriptionurl", ""),
               "licence": lic, "author": artist, "credit": f"{artist} / Wikimedia Commons ({lic})" if needs else "",
               "topic": query}


def nasa(query):
    r = requests.get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "video"}, timeout=60)
    r.raise_for_status()
    for item in r.json().get("collection", {}).get("items", [])[:25]:
        d = (item.get("data") or [{}])[0]
        text = f"{d.get('title', '')} {d.get('description', '')}"
        if re.search(r"©|copyright|courtesy of", text, re.I) or EXCLUDE.search(text):
            continue
        try:
            files = requests.get(item["href"], timeout=60).json()
        except Exception:
            continue
        mp4 = [u for u in files if u.endswith(".mp4")]
        url = next((u for u in mp4 if "~large" in u), None) or next((u for u in mp4 if "~orig" in u), None)
        if url:
            yield {"id": f"nasa-{d['nasa_id']}", "url": url.replace("http://", "https://"),
                   "source": f"https://images.nasa.gov/details/{d['nasa_id']}", "licence": "NASA (not copyrighted)",
                   "author": d.get("center", "NASA"), "credit": "", "topic": query}


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def make_clip(c, dest):
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw")
        with requests.get(c["url"], headers=UA, stream=True, timeout=300) as r:
            r.raise_for_status()
            size = 0
            with open(raw, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    size += len(chunk)
                    if size > 400e6:
                        raise RuntimeError("too large")
        dur = duration(raw)
        if dur < 6:
            raise RuntimeError("too short")
        start = max(0.0, dur / 2 - 5)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", "10", "-i", raw, "-an",
                        "-vf", "scale=-2:1920:flags=lanczos,crop=1080:1920,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-movflags", "+faststart", dest],
                       check=True)
        # skip clips that are mostly black or frozen (title cards, slides)
        p = subprocess.run(["ffmpeg", "-hide_banner", "-i", dest, "-vf", "blackdetect=d=1:pix_th=0.1,freezedetect=d=3",
                            "-f", "null", "-"], capture_output=True, text=True)
        if "black_start" in p.stderr or "freeze_start" in p.stderr:
            os.remove(dest)
            raise RuntimeError("black or frozen footage")


def main():
    os.makedirs(OUT, exist_ok=True)
    index = json.load(open(INDEX)) if os.path.exists(INDEX) else []
    have = {c["id"] for c in index}
    jobs = [(q, commons) for q in COMMONS] + [(q, nasa) for q in NASA]
    for query, source in jobs:
        got = 0
        try:
            candidates = list(source(query))
        except Exception as e:
            print(f"{query}: search failed ({e})")
            continue
        for c in candidates:
            if got >= PER_QUERY:
                break
            if c["id"] in have:
                continue
            dest = os.path.join(OUT, f"{c['id']}.mp4")
            try:
                make_clip(c, dest)
            except Exception as e:
                print(f"skip {c['id']}: {e}")
                continue
            c["file"] = os.path.basename(dest)
            c.pop("url")
            index.append(c)
            have.add(c["id"])
            got += 1
            print(f"added {c['file']} ({query}, {c['licence']})")
            json.dump(index, open(INDEX, "w"), indent=1, ensure_ascii=False)
    print(f"library: {len(index)} clips")


if __name__ == "__main__":
    main()
