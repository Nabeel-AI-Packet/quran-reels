"""Reel designer: one 1080x1920 MP4 per post.

Layout (top to bottom): surah name in Arabic and English, the ayah in Arabic,
the English and Polish translations, the reciter. Each ayah gets its own page,
shown for exactly as long as the reciter takes to recite it. Backgrounds are the
Canva designs in assets/backgrounds, rotated, with a slow zoom.
"""
import glob
import os
import random
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG_DIR = os.path.join(ROOT, "assets", "backgrounds")

DARK_THEME = {"main": (250, 245, 232), "accent": (222, 190, 120), "soft": (214, 220, 216),
              "shadow": (0, 0, 0, 150), "panel": (0, 0, 0, 120), "shade": 150}
LIGHT_THEME = {"main": (28, 34, 52), "accent": (150, 104, 40), "soft": (60, 66, 80),
               "shadow": (255, 255, 255, 0), "panel": (255, 250, 240, 120), "shade": 0}
THEME = dict(DARK_THEME)


def _c(name, alpha=255):
    return THEME[name] + (alpha,)


def _find(*names):
    """First installed font matching one of the names (fontconfig)."""
    for n in names:
        r = subprocess.run(["fc-match", "-f", "%{file}|%{family}", n], capture_output=True, text=True)
        path, _, fam = r.stdout.partition("|")
        if path and n.split(":")[0].lower() in fam.lower():
            return path
    raise RuntimeError(f"No font found for {names}")


_bundled = os.path.join(ROOT, "assets", "fonts", "AmiriQuran.ttf")
FONT_AR = _bundled if os.path.exists(_bundled) else _find("Amiri Quran:style=Regular", "Amiri:style=Regular", "FreeSerif")
FONT_AR_UI = _find("Amiri:style=Regular", "FreeSerif")
FONT_UI = _find("Inter:style=Regular", "DejaVu Sans")
FONT_UI_MED = _find("Inter:style=Medium", "DejaVu Sans")
FONT_UI_BOLD = _find("Inter:style=SemiBold", "DejaVu Sans:style=Bold")


def font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def line_h(f):
    ascent, descent = f.getmetrics()
    return ascent + descent


def wrap(draw, text, f, max_w, direction=None):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=f, direction=direction) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def centered(draw, lines, f, y, fill, gap=0, direction=None, shadow=True):
    for line in lines:
        w = draw.textlength(line, font=f, direction=direction)
        x = (W - w) / 2
        if shadow:
            draw.text((x + 2, y + 3), line, font=f, fill=THEME["shadow"], direction=direction)
        draw.text((x, y), line, font=f, fill=fill, direction=direction)
        y += line_h(f) + gap
    return y


# ---------- background ----------

def background_files():
    return sorted(glob.glob(os.path.join(BG_DIR, "*.png")) + glob.glob(os.path.join(BG_DIR, "*.jpg")))


def _fallback_background():
    img = Image.new("RGB", (W, H), (12, 30, 40))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(int(14 + 10 * t), int(46 - 20 * t), int(56 - 20 * t)))
    return img


def prepare_background(choice, out_path):
    """Crops the chosen background to 9:16, darkens it for readable text, saves it slightly larger for zooming."""
    files = background_files()
    img = Image.open(files[choice % len(files)]).convert("RGB") if files else _fallback_background()
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H)).convert("RGBA")
    centre = img.crop((200, 500, W - 200, 1400)).convert("L").resize((1, 1)).getpixel((0, 0))
    THEME.clear()
    THEME.update(LIGHT_THEME if centre > 150 else DARK_THEME)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H):                     # darker at top and bottom, where buttons sit
        edge = min(y, H - y) / (H / 2)
        sd.line((0, y, W, y), fill=(0, 0, 0, int(max(0, THEME["shade"] - 60 * edge))))
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle((70, 430, W - 70, 1480), 48, fill=THEME["panel"])
    panel = panel.filter(ImageFilter.GaussianBlur(40))
    out = Image.alpha_composite(Image.alpha_composite(img, shade), panel).convert("RGB")
    out.resize((round(W * 1.1), round(H * 1.1)), Image.LANCZOS).save(out_path, quality=95)


# ---------- pages ----------

def _header(d, verse):
    f_ar = font(FONT_AR_UI, 54)
    centered(d, [verse["surah_ar"]], f_ar, 150, _c("accent", 255,), direction="rtl")
    f = font(FONT_UI_MED, 32)
    centered(d, [verse["reference"]], f, 245, _c("soft", 235))


def _footer(d, verse):
    f_ar = font(FONT_AR_UI, 40)
    centered(d, [verse["reciter_ar"]], f_ar, 1530, _c("main", 240,), direction="rtl")
    f = font(FONT_UI, 28)
    centered(d, [f"Recitation · {verse['reciter']}"], f, 1600, _c("soft", 220))


def _ayah_mark(n):
    digits = "٠١٢٣٤٥٦٧٨٩"
    return "﴿" + "".join(digits[int(c)] for c in str(n)) + "﴾"


def _layout(d, arabic, english, polish):
    """Largest text size at which the page fits the panel; None if even the smallest is too big."""
    for size in (96, 88, 80, 72, 64, 58, 52, 46):
        f_ar = font(FONT_AR, size)
        f_en = font(FONT_UI_MED, max(30, int(size * 0.46)))
        f_pl = font(FONT_UI, max(26, int(size * 0.38)))
        ar = wrap(d, arabic, f_ar, W - 240, direction="rtl")
        en = wrap(d, english, f_en, W - 260)
        pl = wrap(d, polish, f_pl, W - 280) if polish else []
        h = (len(ar) * (line_h(f_ar) + 6) + 70 + len(en) * (line_h(f_en) + 8)
             + (40 + len(pl) * (line_h(f_pl) + 6) if pl else 0))
        if h <= 960:
            return f_ar, f_en, f_pl, ar, en, pl, h
    return None


def split_page(arabic, english, polish):
    """Halves an ayah that is too long for one page (text only; the timing is split by word count)."""
    def halves(t):
        w = t.split()
        m = (len(w) + 1) // 2
        return " ".join(w[:m]), " ".join(w[m:])
    a1, a2 = halves(arabic)
    e1, e2 = halves(english)
    p1, p2 = halves(polish)
    return [(a1, e1 + " …", p1 + " …"), (a2, "… " + e2, "… " + p2)]


def verse_page(verse, arabic, english, polish):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _header(d, verse)
    f_ar, f_en, f_pl, ar, en, pl, h = _layout(d, arabic, english, polish)
    y = 955 - h / 2
    y = centered(d, ar, f_ar, y, _c("main", 255,), gap=6, direction="rtl")
    y += 22
    d.line((W / 2 - 70, y, W / 2 + 70, y), fill=_c("accent", 230,), width=2)
    d.ellipse((W / 2 - 5, y - 5, W / 2 + 5, y + 5), fill=_c("accent", 255))
    y += 48
    y = centered(d, en, f_en, y, _c("main", 255,), gap=8)
    if pl:
        y += 40
        centered(d, pl, f_pl, y, _c("soft", 240,), gap=6)
    _footer(d, verse)
    return img


def title_page(verse):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(FONT_UI_BOLD, 74)
    lines = wrap(d, verse["hook"], f, W - 240)
    y = 960 - len(lines) * line_h(f) / 2
    centered(d, lines, f, y, _c("main", 255,), gap=6)
    _header(d, verse)
    _footer(d, verse)
    return img


def end_page(verse):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    centered(d, ["صدقة جارية"], font(FONT_AR_UI, 84), 790, _c("accent", 255,), direction="rtl")
    centered(d, ["Share as sadaqah jariyah"], font(FONT_UI_BOLD, 52), 930, _c("main", 255))
    centered(d, ["Udostępnij jako sadaka dżarija"], font(FONT_UI, 36), 1010, _c("soft", 235))
    return img


def build_pages(verse, durations):
    """Returns [(image, seconds)] for every page, ayah pages timed to the recitation."""
    pages = []
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for (n, arabic), english, polish, secs in zip(verse["arabic"], verse["english_list"],
                                                   verse["polish_list"], durations):
        arabic = f"{arabic} {_ayah_mark(n)}"
        parts = [(arabic, english, polish)]
        while any(_layout(d, *p) is None for p in parts) and len(parts) < 8:
            parts = [q for p in parts for q in (split_page(*p) if _layout(d, *p) is None else [p])]
        words = [max(1, len(p[0].split())) for p in parts]
        for p, wc in zip(parts, words):
            pages.append((verse_page(verse, *p), secs * wc / sum(words)))
    return pages


# ---------- video ----------

def render(verse, durations, audio_path, out_path, background=None):
    """durations: seconds of recitation per ayah, in order. Returns the video length in seconds."""
    if background is None:
        background = random.randrange(max(1, len(background_files())))
    intro, outro, fade = 2.0, 2.5, 0.3
    with tempfile.TemporaryDirectory() as tmp:
        bg = os.path.join(tmp, "bg.jpg")
        prepare_background(background, bg)
        pages = [(title_page(verse), intro)] + build_pages(verse, durations) + [(end_page(verse), outro)]
        total = sum(s for _, s in pages)
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", bg]
        filters = [f"[0:v]zoompan=z='min(1+0.00025*on,1.09)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                   f":d=1:s={W}x{H}:fps={FPS},format=yuv420p[v0]"]
        t, last = 0.0, "v0"
        for i, (img, secs) in enumerate(pages, start=1):
            p = os.path.join(tmp, f"p{i}.png")
            img.save(p)
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", p]
            s, e = t, t + secs
            filters.append(f"[{i}:v]format=rgba,fade=in:st={s:.3f}:d={fade}:alpha=1,"
                           f"fade=out:st={max(s, e - fade):.3f}:d={fade}:alpha=1[o{i}]")
            filters.append(f"[{last}][o{i}]overlay=enable='between(t,{s:.3f},{e:.3f})'[v{i}]")
            last, t = f"v{i}", e
        audio_idx = len(pages) + 1
        inputs += ["-i", audio_path]
        cmd = (["ffmpeg", "-y", "-loglevel", "error"] + inputs +
               ["-filter_complex", ";".join(filters),
                "-map", f"[{last}]", "-map", f"{audio_idx}:a",
                "-af", f"adelay={int(intro * 1000)}:all=1,apad",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", out_path])
        subprocess.run(cmd, check=True)
    return total
