"""Renders sample Reels into previews/ without touching Telegram or the queue.
    python -m agent.preview "94:5-6|Yasser Al-Dosari|0" "112:1-4|Mishary Alafasy|3" ...
"""
import os
import sys
import tempfile

from . import config, designer, quran

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "previews")

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for spec in sys.argv[1:]:
        key, reciter, bg = spec.split("|")
        text = quran.fetch_text(key)
        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "a.mp3")
            durations = quran.fetch_audio(key, reciter, audio)
            verse = {**text, "hook": text["reference"], "reciter": reciter,
                     "reciter_ar": config.RECITERS[reciter]["ar"]}
            name = f"{key.replace(':', '_')}_{reciter.split()[0]}.mp4"
            secs = designer.render(verse, durations, audio, os.path.join(OUT, name), background=int(bg))
            print(name, f"{secs:.1f}s", "polish:", text["polish_list"][0][:60])
