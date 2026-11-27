"""Design system: Premium Islamic corporate documentary graphics (PIL).

Emerald #006B45 · Gold #D4AF37 · White · Dark green #003B2B · Black #171717
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from common import H, W, ease, ease_out, font, rgb


# --------------------------------------------------------------------------- patterns
def _star_points(cx, cy, r_out, r_in, n=8, rot=math.pi / 8):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


@lru_cache(maxsize=8)
def geometric_pattern(w: int, h: int, cell: int, color: tuple, alpha: int, line: int = 2) -> Image.Image:
    """Minimal 8-point star (Khatam) lattice as an RGBA line layer."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = color + (alpha,)
    for gy in range(-1, h // cell + 2):
        for gx in range(-1, w // cell + 2):
            cx, cy = gx * cell + (cell // 2 if gy % 2 else 0), gy * cell * 0.87
            pts = _star_points(cx, cy, cell * 0.42, cell * 0.30)
            d.line(pts + [pts[0]], fill=c, width=line)
            d.ellipse([cx - cell * 0.08, cy - cell * 0.08, cx + cell * 0.08, cy + cell * 0.08], outline=c, width=line)
    return layer


@lru_cache(maxsize=4)
def green_background(w: int = W, h: int = H, pattern_alpha: int = 22) -> Image.Image:
    """Dark-green radial gradient + faint gold geometric lattice (chapter cards, title cards)."""
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h / 2) / (h * 0.75)) ** 2)
    r = np.clip(r, 0, 1)[..., None]
    inner, outer = np.array(rgb("emerald")) * 0.78, np.array(rgb("dark_green")) * 0.62
    arr = (inner * (1 - r) + outer * r).astype("uint8")
    bg = Image.fromarray(arr, "RGB").convert("RGBA")
    pat = geometric_pattern(w, h, 180, rgb("gold"), pattern_alpha, 2)
    # fade pattern toward centre so text stays clean
    mask = Image.fromarray((np.clip(r[..., 0] * 1.6 - 0.25, 0, 1) * 255).astype("uint8"), "L")
    pat_a = pat.split()[3]
    pat.putalpha(Image.fromarray((np.array(pat_a, dtype="float32") * np.array(mask) / 255).astype("uint8")))
    bg.alpha_composite(pat)
    return bg


@lru_cache(maxsize=2)
def ivory_background(w: int, h: int) -> Image.Image:
    """White/ivory background with emerald corner lattice (org chart)."""
    import numpy as np
    bg = Image.new("RGBA", (w, h), rgb("ivory") + (255,))
    pat = geometric_pattern(w, h, int(h / 7), rgb("emerald"), 30, max(2, h // 700))
    yy, xx = np.mgrid[0:h, 0:w]
    dx = np.minimum(xx, w - xx) / (w * 0.22)
    dy = np.minimum(yy, h - yy) / (h * 0.30)
    m = np.clip(1.0 - np.minimum(np.hypot(dx, dy), 1.0) * 1.0, 0, 1)
    m = np.maximum(m, np.clip(1 - dx * 1.6, 0, 1) * 0.35)
    a = (np.array(pat.split()[3], dtype="float32") * m).astype("uint8")
    pat.putalpha(Image.fromarray(a))
    bg.alpha_composite(pat)
    return bg


# --------------------------------------------------------------------------- text helpers
def text_size(d: ImageDraw.ImageDraw, txt: str, f) -> tuple[int, int]:
    b = d.textbbox((0, 0), txt, font=f)
    return b[2] - b[0], b[3] - b[1]


def draw_center(d, cx, y, txt, f, fill, spacing=0):
    if spacing:
        widths = [text_size(d, ch, f)[0] + spacing for ch in txt]
        x = cx - (sum(widths) - spacing) / 2
        for ch, wd in zip(txt, widths):
            d.text((x, y), ch, font=f, fill=fill)
            x += wd
    else:
        tw, _ = text_size(d, txt, f)
        d.text((cx - tw / 2, y), txt, font=f, fill=fill)


def wrap(d, txt, f, max_w):
    words, lines, cur = txt.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if text_size(d, t, f)[0] <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def gold_rule(d, cx, y, half, alpha=255, diamond=True, width=3):
    g = rgb("gold", alpha)
    d.line([(cx - half, y), (cx + half, y)], fill=g, width=width)
    if diamond:
        s = 9
        d.polygon([(cx, y - s), (cx + s, y), (cx, y + s), (cx - s, y)], fill=g)


def with_alpha(layer: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return layer
    al = layer.split()[3].point(lambda v: int(v * max(0.0, a)))
    out = layer.copy()
    out.putalpha(al)
    return out


# --------------------------------------------------------------------------- cards
def chapter_card(t: float, dur: float, number: str, title: str, subtitle: str = "") -> Image.Image:
    """Animated chapter card frame at time t."""
    img = green_background().copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a_in = ease((t - 0.2) / 1.3)
    a_out = 1 - ease((t - (dur - 0.7)) / 0.7)
    a = a_in * a_out
    rise = (1 - ease_out((t - 0.2) / 1.5)) * 40
    cy = H / 2
    if number:
        draw_center(d, W / 2, cy - 150 + rise, number, font("title", 44, "Bold"), rgb("gold", int(255 * a)), spacing=10)
    lines = wrap(d, title, font("title", 86, "Bold"), W - 320)
    ty = cy - 60 + rise - (len(lines) - 1) * 50
    for ln in lines:
        draw_center(d, W / 2, ty, ln, font("title", 86, "Bold"), rgb("white", int(255 * a)))
        ty += 104
    half = 340 * ease_out((t - 0.5) / 1.2)
    gold_rule(d, W / 2, ty + 26, half, int(255 * a_out))
    if subtitle:
        draw_center(d, W / 2, ty + 56 + rise * 0.5, subtitle, font("serif", 38, "Regular"),
                    rgb("ivory", int(230 * ease((t - 0.9) / 1.0) * a_out)))
    img.alpha_composite(lay)
    return img


def lower_third_layer(title: str, sub: str, t: float, dur: float) -> Image.Image | None:
    """Slide-in emerald bar with gold accent; returns RGBA overlay or None if invisible."""
    if t < 0 or t > dur:
        return None
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ft, fs = font("sans", 40, "SemiBold"), font("sans", 27, "Medium")
    tw = max(text_size(d, title, ft)[0], text_size(d, sub, fs)[0] if sub else 0)
    bw, bh = tw + 110, (120 if sub else 82)
    slide = ease_out(t / 0.6)
    fade = 1 - ease((t - (dur - 0.45)) / 0.45)
    x0 = 90 - (1 - slide) * (bw + 120)
    y0 = H - 250 - bh
    a = int(235 * fade)
    d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=rgb("dark_green", int(a * 0.92)))
    d.rectangle([x0, y0, x0 + 10, y0 + bh], fill=rgb("gold", a))
    d.line([(x0 + 10, y0 + bh), (x0 + 10 + (bw - 10) * ease_out((t - 0.3) / 0.8), y0 + bh)], fill=rgb("gold", a), width=3)
    d.text((x0 + 48, y0 + 16), title, font=ft, fill=rgb("white", int(255 * fade)))
    if sub:
        d.text((x0 + 50, y0 + 72), sub, font=fs, fill=rgb("gold", int(255 * fade)))
    return lay


def text_card(t, dur, heading, items, sub="", bg: Image.Image | None = None) -> Image.Image:
    """Elegant list card (e.g. infrastructure improvements, acknowledgements)."""
    img = (bg.copy() if bg is not None else green_background().copy()).convert("RGBA")
    if bg is not None:
        img.alpha_composite(Image.new("RGBA", (W, H), rgb("dark_green", 205)))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    fade_out = 1 - ease((t - (dur - 0.6)) / 0.6)
    a0 = ease(t / 0.8) * fade_out
    draw_center(d, W / 2, 150, heading, font("title", 62, "Bold"), rgb("gold", int(255 * a0)))
    gold_rule(d, W / 2, 245, 300 * ease_out(t / 1.2), int(255 * fade_out))
    if sub:
        draw_center(d, W / 2, 272, sub, font("serif", 34, "Regular"), rgb("ivory", int(230 * a0)))
    n = len(items)
    y = 380 if n <= 5 else 340
    step = 100 if n <= 5 else 78
    for i, it in enumerate(items):
        ai = ease((t - 0.8 - i * 0.45) / 0.6) * fade_out
        dx = (1 - ease_out((t - 0.8 - i * 0.45) / 0.7)) * 40
        f = font("sans", 44 if n <= 5 else 38, "Medium")
        tw, _ = text_size(d, it, f)
        x = W / 2 - tw / 2 + dx
        s = 10
        cy = y + 28
        d.polygon([(x - 40, cy - s), (x - 40 + s, cy), (x - 40, cy + s), (x - 40 - s, cy)], fill=rgb("gold", int(255 * ai)))
        d.text((x, y), it, font=f, fill=rgb("white", int(255 * ai)))
        y += step
    img.alpha_composite(lay)
    return img


def opening_title(t: float, dur: float, cfg: dict) -> Image.Image:
    """School emblem-style title: gold star draws in, name types up, location fades."""
    img = green_background().copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    fo = 1 - ease((t - (dur - 0.7)) / 0.7)
    cx, cy = W / 2, H / 2 - 150
    k = ease_out(t / 1.6)
    pts = _star_points(cx, cy, 95 * k + 1, 70 * k + 1, rot=t * 0.15 + math.pi / 8)
    d.line(pts + [pts[0]], fill=rgb("gold", int(255 * fo)), width=4)
    pts2 = _star_points(cx, cy, 60 * k + 1, 44 * k + 1, rot=-t * 0.15)
    d.line(pts2 + [pts2[0]], fill=rgb("gold", int(200 * fo)), width=3)
    d.ellipse([cx - 112 * k, cy - 112 * k, cx + 112 * k, cy + 112 * k], outline=rgb("gold", int(180 * fo)), width=2)
    a = ease((t - 1.0) / 1.0) * fo
    rise = (1 - ease_out((t - 1.0) / 1.2)) * 30
    draw_center(d, W / 2, cy + 160 + rise, cfg["school_name"], font("title", 58, "Bold"), rgb("white", int(255 * a)), spacing=2)
    gold_rule(d, W / 2, cy + 260, 420 * ease_out((t - 1.6) / 1.0), int(255 * fo))
    a2 = ease((t - 2.0) / 1.0) * fo
    draw_center(d, W / 2, cy + 290, cfg["location"].upper(), font("sans", 32, "Medium"), rgb("gold", int(255 * a2)), spacing=6)
    img.alpha_composite(lay)
    return img


def main_title(t: float, dur: float, cfg: dict) -> Image.Image:
    """'DOKUMENTARI RASMI 2026' + slogan, letter-by-letter reveal."""
    img = green_background().copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    fo = 1 - ease((t - (dur - 0.8)) / 0.8)
    a = ease(t / 0.8) * fo
    draw_center(d, W / 2, 300, "VIDEO DOKUMENTARI RASMI", font("sans", 34, "SemiBold"), rgb("gold", int(255 * a)), spacing=8)
    big = f"{cfg['school_short']} {cfg['year']}"
    n = int(len(big) * ease((t - 0.4) / 1.8)) if t < 2.2 else len(big)
    shown = big[:n]
    f = font("title", 96, "Bold")
    tw, _ = text_size(d, big, f)
    d.text((W / 2 - tw / 2, 380), shown, font=f, fill=rgb("white", int(255 * fo)))
    gold_rule(d, W / 2, 540, 460 * ease_out((t - 1.8) / 1.0), int(255 * fo))
    a3 = ease((t - 2.4) / 1.0) * fo
    draw_center(d, W / 2, 580, f"“{cfg['slogan']}”", font("serif", 46, "Medium"), rgb("ivory", int(255 * a3)))
    img.alpha_composite(lay)
    return img


def big_badge_layer(t: float, dur: float, text: str, sub: str) -> Image.Image:
    """Large gold badge (e.g. '6A') over imagery."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a = ease((t - 0.6) / 0.8) * (1 - ease((t - (dur - 0.5)) / 0.5))
    s = 0.85 + 0.15 * ease_out((t - 0.6) / 0.9)
    cx, cy, r = W - 330, H / 2 - 40, 190 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb("dark_green", int(225 * a)), outline=rgb("gold", int(255 * a)), width=8)
    d.ellipse([cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18], outline=rgb("gold", int(160 * a)), width=2)
    f = font("title", int(150 * s), "Black")
    tw, th = text_size(d, text, f)
    d.text((cx - tw / 2, cy - th / 2 - 40 * s), text, font=f, fill=rgb("gold", int(255 * a)))
    draw_center(d, cx, cy + 70 * s, sub, font("sans", int(30 * s), "SemiBold"), rgb("white", int(255 * a)), spacing=3)
    return lay


def credits_frame(t: float, dur: float, blocks: list[tuple[str, list[str]]]) -> Image.Image:
    """Slow upward-scrolling credits on green."""
    img = green_background().copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    total = 0
    for head, lines in blocks:
        total += 80 + 56 * len(lines) + 60
    y = H - (H + total) * (t / dur) + 40
    fo = 1 - ease((t - (dur - 1.2)) / 1.2)
    for head, lines in blocks:
        if -100 < y < H + 100:
            draw_center(d, W / 2, y, head, font("title", 40, "Bold"), rgb("gold", int(255 * fo)), spacing=3)
        y += 80
        for ln in lines:
            if -80 < y < H + 80:
                draw_center(d, W / 2, y, ln, font("sans", 36, "Medium"), rgb("white", int(240 * fo)))
            y += 56
        y += 60
    img.alpha_composite(lay)
    return img
