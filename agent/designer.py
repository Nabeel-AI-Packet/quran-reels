"""Reel designer: turns one verse (Arabic + English + Polish) into a 1080x1920 MP4.

In production the agent passes in text fetched from Quran.com, the recitation
audio, and a background clip from Pexels. Without a background clip it draws
its own Islamic geometric background.
"""
import math
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 24

def _find(*names):
    """First installed font matching one of the names (fontconfig)."""
    for n in names:
        r = subprocess.run(["fc-match", "-f", "%{file}|%{family}", n], capture_output=True, text=True)
        path, _, fam = r.stdout.partition("|")
        if path and n.split(":")[0].lower() in fam.lower():
            return path
    raise RuntimeError(f"No font found for {names}")


FONT_AR = _find("Amiri Quran:style=Regular", "Amiri:style=Regular", "FreeSerif")
FONT_UI = _find("Inter:style=Medium", "DejaVu Sans")
FONT_UI_BOLD = _find("Inter:style=SemiBold", "DejaVu Sans:style=Bold")

# Background palettes (centre glow, edge). "Skip" in Telegram moves to the next one.
PALETTES = [
    ((16, 66, 72), (10, 24, 38)),    # teal / navy
    ((58, 40, 82), (16, 12, 30)),    # plum / night
    ((24, 58, 40), (8, 22, 16)),     # emerald / forest
    ((78, 52, 30), (22, 14, 10)),    # sand / dusk
]
GOLD = (214, 180, 110)
CREAM = (245, 238, 222)
SOFT = (200, 210, 205)


def font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def star_points(cx, cy, r_out, r_in, n=8, rot=0.0):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def make_background(variant=0):
    """Dark navy-to-teal gradient with a faint gold 8-point-star lattice and an arch."""
    TEAL, NAVY = PALETTES[variant % len(PALETTES)]
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        t = y / H
        for x in range(W):
            d = math.hypot((x - W / 2) / W, (y - H * 0.45) / H)
            k = min(1.0, d * 1.6)
            c = tuple(int(TEAL[i] * (1 - k) * (1 - t * 0.3) + NAVY[i] * k) for i in range(3))
            px[x, y] = c
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    step = 180
    for gy in range(-step, H + step, step):
        for gx in range(-step, W + step, step):
            ox = gx + (step / 2 if (gy // step) % 2 else 0)
            d.polygon(star_points(ox, gy, 62, 30), outline=GOLD + (34,), width=2)
            d.polygon(star_points(ox, gy, 62, 30, rot=math.pi / 8), outline=GOLD + (20,), width=1)
    # pointed arch framing the text
    arch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = ImageDraw.Draw(arch)
    left, right, base, peak = 90, W - 90, 1620, 330
    r = (right - left)
    a.arc((left, peak, left + r, peak + r), 200, 270, fill=GOLD + (120,), width=3)
    a.arc((right - r, peak, right, peak + r), 270, 340, fill=GOLD + (120,), width=3)
    a.line((left + 18, peak + r * 0.33, left + 18, base), fill=GOLD + (120,), width=3)
    a.line((right - 18, peak + r * 0.33, right - 18, base), fill=GOLD + (120,), width=3)
    # darken behind text for readability
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rounded_rectangle((110, 560, W - 110, 1500), 40, fill=(5, 12, 20, 120))
    shade = shade.filter(ImageFilter.GaussianBlur(30))
    out = bg.convert("RGBA")
    for l in (layer, shade, arch):
        out = Image.alpha_composite(out, l)
    return out


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def line_h(f):
    ascent, descent = f.getmetrics()
    return ascent + descent


def draw_centered(draw, lines, f, y, fill, gap, direction=None):
    for line in lines:
        w = draw.textlength(line, font=f, direction=direction)
        draw.text(((W - w) / 2, y), line, font=f, fill=fill, direction=direction)
        y += line_h(f) + gap
    return y


def frame(bg, verse, mode, alpha=1.0):
    """mode: 'hook' | 'verse' | 'close'."""
    img = bg.copy()
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    a = int(255 * alpha)

    # reference, always on top
    f_ref = font(FONT_UI, 34)
    ref = verse["reference"]
    d.text(((W - d.textlength(ref, font=f_ref)) / 2, 230), ref, font=f_ref, fill=GOLD + (230,))

    if mode == "hook":
        f = font(FONT_UI_BOLD, 76)
        lines = wrap(d, verse["hook"], f, W - 260)
        y = (H - len(lines) * 96) / 2
        draw_centered(d, lines, f, y, CREAM + (a,), 20)
    elif mode == "verse":
        for size in (92, 84, 76, 68, 60, 54):
            f_ar = font(FONT_AR, size)
        # one line per ayah (wrapped only if too long), each ending in its number ornament
            digits = "٠١٢٣٤٥٦٧٨٩"
            ar_lines = []
            for num, ayah in verse["arabic"]:
                mark = "\uFD3F" + "".join(digits[int(c)] for c in str(num)) + "\uFD3E"
                ar_lines += wrap(d, ayah + " " + mark, f_ar, W - 280)
            f_en = font(FONT_UI, int(size * 0.48))
            en_lines = wrap(d, verse["english"], f_en, W - 300)
            f_pl = font(FONT_UI, int(size * 0.37))
            pl_lines = wrap(d, verse["polish"], f_pl, W - 320)
            ar_gap = int(size * 0.15)
            total = (len(ar_lines) * (line_h(f_ar) + ar_gap) + 60 + len(en_lines) * (line_h(f_en) + 14)
                     + 40 + len(pl_lines) * (line_h(f_pl) + 12))
            if total <= 860:
                break
        y = 1030 - total / 2
        y = draw_centered(d, ar_lines, f_ar, y, CREAM + (a,), ar_gap, direction="rtl")
        d.line((W / 2 - 60, y + 20, W / 2 + 60, y + 20), fill=GOLD + (a,), width=2)
        y += 56
        y = draw_centered(d, en_lines, f_en, y, CREAM + (a,), 14)
        y += 30
        draw_centered(d, pl_lines, f_pl, y, SOFT + (int(a * 0.85),), 12)
    else:
        f = font(FONT_UI_BOLD, 56)
        f2 = font(FONT_UI, 38)
        draw_centered(d, ["Share as sadaqah jariyah"], f, 900, CREAM + (a,), 0)
        draw_centered(d, [verse["handle"]], f2, 990, GOLD + (a,), 0)

    f_rc = font(FONT_UI, 30)
    rc = "Recitation: " + verse["reciter"]
    d.text(((W - d.textlength(rc, font=f_rc)) / 2, 1560), rc, font=f_rc, fill=SOFT + (200,))
    return Image.alpha_composite(img, over).convert("RGB")


def render(verse, out_path, audio_path=None, verse_seconds=9.0, variant=0):
    bg = make_background(variant)
    hook_s, close_s, fade = 2.0, 2.5, 0.4
    total = hook_s + verse_seconds + close_s
    tmp = tempfile.mkdtemp()
    n = int(total * FPS)
    for i in range(n):
        t = i / FPS
        if t < hook_s:
            mode, local, dur = "hook", t, hook_s
        elif t < hook_s + verse_seconds:
            mode, local, dur = "verse", t - hook_s, verse_seconds
        else:
            mode, local, dur = "close", t - hook_s - verse_seconds, close_s
        alpha = min(1.0, local / fade, (dur - local) / fade if mode != "close" else 1.0)
        # slow zoom for movement
        z = 1.0 + 0.04 * (t / total)
        zb = bg.resize((int(W * z), int(H * z)), Image.BILINEAR)
        ox, oy = (zb.width - W) // 2, (zb.height - H) // 2
        frame(zb.crop((ox, oy, ox + W, oy + H)), verse, mode, max(0.0, alpha)).save(
            f"{tmp}/f{i:05d}.jpg", quality=90)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/f%05d.jpg"]
    if audio_path:
        cmd += ["-itsoffset", str(hook_s), "-i", audio_path, "-map", "0:v", "-map", "1:a", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", str(total), out_path]
    subprocess.run(cmd, check=True)
    return out_path


if __name__ == "__main__":
    sample = {
        "reference": "Ash-Sharh 94:5–6",
        "hook": "Feeling overwhelmed? Listen.",
        "arabic": [(5, "فَإِنَّ مَعَ ٱلْعُسْرِ يُسْرًا"), (6, "إِنَّ مَعَ ٱلْعُسْرِ يُسْرًا")],
        "english": "For indeed, with hardship [will be] ease. Indeed, with hardship [will be] ease.",
        "polish": "(sample) Zaprawdę, wraz z trudnością przychodzi ulga.",
        "reciter": "Yasser Al-Dosari",
        "handle": "@yourpage",
    }
    for v in range(len(PALETTES)):
        frame(make_background(v), sample, "verse").save(f"sample_{v}.png")
