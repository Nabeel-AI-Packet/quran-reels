"""Reel designer: the recitation over calm nature and space scenes, with no text on screen.

Each Reel uses several scenes from assets/scenes (Canva designs), each with a slow
zoom, joined by soft crossfades. The audio fades in and out gently.
"""
import glob
import os
import subprocess
import tempfile

from PIL import Image

W, H = 1080, 1920
FPS = 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, "assets", "scenes")
XFADE = 1.2          # seconds of crossfade between scenes
SCENE_LEN = 9.0      # target seconds per scene


def scene_files():
    return sorted(glob.glob(os.path.join(SCENES, "*.png")) + glob.glob(os.path.join(SCENES, "*.jpg")))


def _prepare(path, out):
    """Crops to 9:16 and saves 15% larger, so the slow zoom never shows an edge."""
    img = Image.open(path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    img.resize((round(W * 1.15), round(H * 1.15)), Image.LANCZOS).save(out, quality=95)


def render(durations, audio_path, out_path, start=0):
    """durations: seconds per ayah. start: which scene to begin with (rotates through the pool).
    Returns the video length in seconds."""
    files = scene_files()
    if not files:
        raise RuntimeError("No scenes in assets/scenes")
    lead, tail = 0.8, 1.5
    total = lead + sum(durations) + tail
    n = max(1, min(len(files), round(total / SCENE_LEN)))
    seg = (total + (n - 1) * XFADE) / n          # each scene's own length, overlaps included
    with tempfile.TemporaryDirectory() as tmp:
        inputs, filters = [], []
        frames = int(seg * FPS) + 2
        for i in range(n):
            src = files[(start + i) % len(files)]
            img = os.path.join(tmp, f"s{i}.jpg")
            _prepare(src, img)
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seg:.3f}", "-i", img]
            # alternate zoom in / zoom out for variety
            z = f"1+0.10*on/{frames}" if i % 2 == 0 else f"1.10-0.10*on/{frames}"
            filters.append(f"[{i}:v]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                           f":d=1:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p,trim=duration={seg:.3f}[s{i}]")
        last, t = "s0", seg
        for i in range(1, n):
            filters.append(f"[{last}][s{i}]xfade=transition=fade:duration={XFADE}:offset={t - XFADE:.3f}[x{i}]")
            last, t = f"x{i}", t + seg - XFADE
        filters.append(f"[{last}]fade=in:st=0:d=0.8,fade=out:st={total - 1.2:.3f}:d=1.2[vout]")
        inputs += ["-i", audio_path]
        filters.append(f"[{n}:a]adelay={int(lead * 1000)}:all=1,apad,afade=in:st=0:d=0.5,"
                       f"afade=out:st={total - 1.0:.3f}:d=1.0[aout]")
        cmd = (["ffmpeg", "-y", "-loglevel", "error"] + inputs +
               ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", out_path])
        subprocess.run(cmd, check=True)
    return total
