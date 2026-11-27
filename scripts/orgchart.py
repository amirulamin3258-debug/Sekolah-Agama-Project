"""Chapter 1 — animated organisation chart.

Sequence: chapter card → chart builds level by level → for each member: camera zooms to their box,
a full portrait card opens (portrait left, name typewriter + role), holds, closes back into the box
(now marked gold), camera returns to the full chart → final gold shimmer over the completed chart.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

import graphics as G
from common import CFG, FPS, H, W, FrameWriter, ROOT, code_version, ease, ease_out, lerp, load_json, path, rgb, spec_hash

S = 2  # chart supersampling factor (chart drawn at 3840x2160 for crisp zooms)
CW, CH = W * S, H * S
PORTRAITS = path("portraits")


def members() -> tuple[dict, list[list[str]]]:
    org = load_json("organization.json")["committee"]
    mem = {k: v for k, v in org["members"].items() if v.get("verified")}
    levels = [[k for k in row if k in mem] for row in org["levels"]]
    return org, mem, [r for r in levels if r]


# --------------------------------------------------------------------------- portraits
def _portrait_still(m: dict) -> Image.Image:
    p = PORTRAITS / m["portrait"]
    if p.suffix.lower() in (".mp4", ".mov"):
        out = subprocess.run(["ffmpeg", "-v", "error", "-ss", "3.3", "-i", str(p), "-frames:v", "1",
                              "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        import io
        return Image.open(io.BytesIO(out)).convert("RGB")
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def portrait_view(im: Image.Image, m: dict, aspect=3 / 4) -> Image.Image:
    """Crop a 3:4 window around the configured focus point (no face alteration, crop only)."""
    fx, fy = m.get("focus", [0.5, 0.5])
    vh = m.get("view_h", 1.0) * im.height
    vw = vh * aspect
    if vw > im.width:
        vw = im.width
        vh = vw / aspect
    x0 = min(max(fx * im.width - vw / 2, 0), im.width - vw)
    y0 = min(max(fy * im.height - vh / 2, 0), im.height - vh)
    return im.crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh)))


def portrait_frames(m: dict, n: int, size: tuple[int, int]):
    """Yields n portrait frames (slow push-in). Video portraits play their original clip."""
    p = PORTRAITS / m["portrait"]
    pw, ph = size
    if p.suffix.lower() in (".mp4", ".mov"):
        cmd = ["ffmpeg", "-v", "error", "-i", str(p), "-vf",
               f"fps={FPS},scale={pw}:{ph}:force_original_aspect_ratio=increase:flags=lanczos,crop={pw}:{ph},unsharp=5:5:0.6",
               "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        last = None
        for _ in range(n):
            b = proc.stdout.read(pw * ph * 3)
            if len(b) == pw * ph * 3:
                last = Image.frombytes("RGB", (pw, ph), b)
            yield last
        proc.stdout.close()
        proc.wait()
        return
    view = portrait_view(_portrait_still(m), m)
    big = view.resize((int(pw * 1.08), int(ph * 1.08)), Image.LANCZOS)
    for i in range(n):
        z = 1 + 0.06 * ease(i / max(1, n - 1))
        vw, vh = big.width / 1.08 / z, big.height / 1.08 / z
        x0, y0 = (big.width - vw) / 2, (big.height - vh) / 2 - (big.height - vh) * 0.15
        yield big.transform((pw, ph), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)


def circle_thumb(m: dict, d: int) -> Image.Image:
    view = portrait_view(_portrait_still(m), m, aspect=1.0) if m.get("view_h", 1) < 1 else _square_top(_portrait_still(m), m)
    t = view.resize((d, d), Image.LANCZOS)
    mask = Image.new("L", (d * 4, d * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, d * 4, d * 4], fill=255)
    out = Image.new("RGBA", (d, d))
    out.paste(t, (0, 0), mask.resize((d, d), Image.LANCZOS))
    return out


def _square_top(im, m):
    fx, fy = m.get("focus", [0.5, 0.5])
    s = min(im.width, im.height)
    s2 = int(s * 0.75)
    x0 = int(min(max(fx * im.width - s2 / 2, 0), im.width - s2))
    y0 = int(min(max(im.height * 0.38 - s2 / 2, 0), im.height - s2))
    return im.crop((x0, y0, x0 + s2, y0 + s2))


# --------------------------------------------------------------------------- chart layout
def layout(levels):
    top, bottom = 250 * S, 1040 * S
    n = len(levels)
    row_h = (bottom - top) / n
    bw, bh = 400 * S, 128 * S
    rects = {}
    for r, row in enumerate(levels):
        k = len(row)
        gap = 50 * S
        total = k * bw + (k - 1) * gap
        x0 = (CW - total) / 2
        y = top + r * row_h + (row_h - bh) / 2
        for i, key in enumerate(row):
            rects[key] = (x0 + i * (bw + gap), y, x0 + i * (bw + gap) + bw, y + bh)
    return rects


def draw_chart(org, mem, levels, rects, done: set, reveal: float = 1.0, thumbs=None) -> Image.Image:
    img = G.ivory_background(CW, CH).copy()
    d = ImageDraw.Draw(img)
    a_title = ease(reveal * 3)
    G.draw_center(d, CW / 2, 58 * S, org["title"], G.font("title", 58 * S, "Bold"), rgb("emerald", int(255 * a_title)))
    G.gold_rule(d, CW / 2, 145 * S, 420 * S * ease_out(reveal * 2), int(255 * a_title), width=3 * S)
    G.draw_center(d, CW / 2, 165 * S, org.get("subtitle", ""), G.font("serif", 30 * S, "Medium"), rgb("dark_green", int(220 * a_title)))
    nlev = len(levels)
    # connectors (gold)
    for r in range(nlev - 1):
        lv_a = ease((reveal * (nlev + 1) - r - 1))
        if lv_a <= 0:
            continue
        up = [rects[k] for k in levels[r]]
        dn = [rects[k] for k in levels[r + 1]]
        ybus = (max(u[3] for u in up) + min(q[1] for q in dn)) / 2
        g = rgb("gold", int(255 * lv_a))
        for u in up:
            d.line([((u[0] + u[2]) / 2, u[3]), ((u[0] + u[2]) / 2, ybus)], fill=g, width=3 * S)
        xs = [(q[0] + q[2]) / 2 for q in dn] + [(u[0] + u[2]) / 2 for u in up]
        d.line([(min(xs), ybus), (max(xs), ybus)], fill=g, width=3 * S)
        for q in dn:
            d.line([((q[0] + q[2]) / 2, ybus), ((q[0] + q[2]) / 2, q[1])], fill=g, width=3 * S)
    for r, row in enumerate(levels):
        a = ease(reveal * (nlev + 1) - r)
        if a <= 0:
            continue
        for key in row:
            x0, y0, x1, y1 = rects[key]
            m = mem[key]
            box = Image.new("RGBA", (int(x1 - x0) + 24 * S, int(y1 - y0) + 24 * S), (0, 0, 0, 0))
            bd = ImageDraw.Draw(box)
            fill = rgb("white", 255)
            is_done = key in done
            border = rgb("gold") if is_done else rgb("emerald")
            bd.rounded_rectangle([12 * S + 4, 16 * S + 4, box.width - 12 * S, box.height - 8 * S], 18 * S, fill=(0, 0, 0, 40))
            box = box.filter(ImageFilter.GaussianBlur(6 * S))
            bd = ImageDraw.Draw(box)
            bd.rounded_rectangle([12 * S, 12 * S, box.width - 12 * S, box.height - 12 * S], 18 * S, fill=fill,
                                 outline=border + (255,), width=(5 if is_done else 3) * S)
            bd.rectangle([12 * S, 12 * S + 18 * S, 20 * S, box.height - 12 * S - 18 * S], fill=border + (255,))
            dth = int((y1 - y0) - 28 * S)
            if thumbs and key in thumbs:
                th = thumbs[key].resize((dth, dth), Image.LANCZOS)
                box.alpha_composite(th, (12 * S + 26 * S, 12 * S + 14 * S))
                bd.ellipse([12 * S + 26 * S - 2 * S, 12 * S + 14 * S - 2 * S, 12 * S + 26 * S + dth + 2 * S, 12 * S + 14 * S + dth + 2 * S],
                           outline=rgb("gold") + (255,), width=3 * S)
            tx = 12 * S + 26 * S + dth + 22 * S
            maxw = box.width - tx - 26 * S
            role = m["role"].upper()
            fr = G.font("sans", 21 * S, "Bold")
            while G.text_size(bd, role, fr)[0] > maxw and fr.size > 14 * S:
                fr = G.font("sans", fr.size - S, "Bold")
            bd.text((tx, 12 * S + 22 * S), role, font=fr, fill=rgb("emerald") + (255,))
            fn = G.font("serif", 25 * S, "SemiBold")
            lines = G.wrap(bd, m["name"], fn, maxw)
            if len(lines) > 2:
                fn = G.font("serif", 21 * S, "SemiBold")
                lines = G.wrap(bd, m["name"], fn, maxw)
            yy = 12 * S + 56 * S
            for ln in lines[:2]:
                bd.text((tx, yy), ln, font=fn, fill=rgb("black") + (255,))
                yy += fn.size + 6 * S
            box = G.with_alpha(box, a)
            img.alpha_composite(box, (int(x0 - 12 * S), int(y0 - 12 * S + (1 - a) * 20 * S)))
    return img


def cam(img: Image.Image, cx, cy, z) -> Image.Image:
    vw, vh = CW / z, CH / z
    x0 = min(max(cx - vw / 2, 0), CW - vw)
    y0 = min(max(cy - vh / 2, 0), CH - vh)
    return img.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)


# --------------------------------------------------------------------------- person card
def card_frame(m: dict, portrait: Image.Image, t: float, hold_t0: float) -> Image.Image:
    img = G.green_background().copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    px, py = 200, 150
    pw, ph = portrait.size
    d.rectangle([px - 10, py - 10, px + pw + 10, py + ph + 10], outline=rgb("gold", 255), width=4)
    d.rectangle([px - 22, py - 22, px + pw + 22, py + ph + 22], outline=rgb("gold", 110), width=2)
    img.alpha_composite(lay)
    img.paste(portrait, (px, py))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    tx = px + pw + 130
    tt = t - hold_t0
    a_role = ease(tt / 0.6)
    role = m["role"].upper()
    d.text((tx, 330 + (1 - ease_out(tt / 0.7)) * 20), role, font=G.font("title", 50, "Bold"), fill=rgb("gold", int(255 * a_role)))
    if m.get("role_sub"):
        d.text((tx, 395), m["role_sub"], font=G.font("serif", 36, "Regular"), fill=rgb("ivory", int(220 * a_role)))
    ln = (W - tx - 140) * ease_out((tt - 0.2) / 0.9)
    d.line([(tx, 470), (tx + ln, 470)], fill=rgb("gold", 255), width=3)
    name = m["name"]
    k = int(len(name) * ease((tt - 0.4) / 1.3))
    fn = G.font("serif", 66, "Bold")
    lines = G.wrap(d, name, fn, W - tx - 120)
    shown, y, left = [], 500, k
    for line in lines:
        part = line[:max(0, left)]
        left -= len(line) + 1
        d.text((tx, y), part, font=fn, fill=rgb("white", 255))
        y += 86
    sch = CFG["school_short"] + " · " + str(CFG["year"])
    d.text((tx, y + 40), sch, font=G.font("sans", 28, "Medium"), fill=rgb("ivory", int(200 * ease((tt - 1.6) / 0.8))))
    img.alpha_composite(lay)
    return img


# --------------------------------------------------------------------------- segments
def render_member(key: str, idx: int, out: Path):
    org, mem, levels = members()
    rects = layout(levels)
    keys = [k for row in levels for k in row]
    done_before = set(keys[:idx])
    thumbs = {k: circle_thumb(mem[k], 200 * S) for k in keys}
    chart_a = draw_chart(org, mem, levels, rects, done_before, 1.0, thumbs).convert("RGB")
    chart_b = draw_chart(org, mem, levels, rects, done_before | {key}, 1.0, thumbs).convert("RGB")
    m = mem[key]
    T = CFG["timing"]["portrait_intro_leader" if m.get("leader") else "portrait_intro"]
    n = int(T * FPS)
    x0, y0, x1, y1 = rects[key]
    bx, by = (x0 + x1) / 2, (y0 + y1) / 2
    zbox = min(CW / ((x1 - x0) * 2.4), 3.2)
    t_in, t_open, t_close, t_out = 1.1, 1.7, T - 1.6, T - 1.0
    pf = portrait_frames(m, n, (600, 780))
    fw = FrameWriter(out)
    for i in range(n):
        t = i / FPS
        por = next(pf)
        if t < t_in:  # zoom to box
            u = ease(t / t_in)
            fr = cam(chart_a, lerp(CW / 2, bx, u), lerp(CH / 2, by, u), lerp(1.0, zbox, u))
        elif t < t_open:  # card opens out of the box
            u = ease_out((t - t_in) / (t_open - t_in))
            base = cam(chart_a, bx, by, zbox).convert("RGBA")
            card = card_frame(m, por, t, t_open)
            fr = _grow(base, card, u)
        elif t < t_close:
            fr = card_frame(m, por, t, t_open)
        elif t < t_out:  # card closes back into the (now gold) box
            u = ease((t - t_close) / (t_out - t_close))
            base = cam(chart_b, bx, by, zbox).convert("RGBA")
            fr = _grow(base, card_frame(m, por, t, t_open), 1 - u)
        else:  # zoom back out
            u = ease((t - t_out) / (T - t_out))
            fr = cam(chart_b, lerp(bx, CW / 2, u), lerp(by, CH / 2, u), lerp(zbox, 1.0, u))
        fw.write(fr)
    fw.close()


def _grow(base: Image.Image, card: Image.Image, u: float) -> Image.Image:
    if u <= 0.001:
        return base.convert("RGB")
    s = 0.3 + 0.7 * u
    cw, ch = int(W * s), int(H * s)
    c = card.convert("RGB").resize((cw, ch), Image.BILINEAR).convert("RGBA")
    c = G.with_alpha(c, min(1.0, u * 1.6))
    out = base.copy()
    out.alpha_composite(c, ((W - cw) // 2, (H - ch) // 2))
    return out.convert("RGB")


def render_intro(out: Path, dur=5.0):
    org, mem, levels = members()
    rects = layout(levels)
    thumbs = {k: circle_thumb(mem[k], 200 * S) for row in levels for k in row}
    fw = FrameWriter(out)
    n = int(dur * FPS)
    for i in range(n):
        t = i / FPS
        rv = min(1.0, t / (dur - 0.8))
        img = draw_chart(org, mem, levels, rects, set(), rv, thumbs).convert("RGB")
        fw.write(img.resize((W, H), Image.LANCZOS))
    fw.close()


def render_finale(out: Path, dur=5.0):
    org, mem, levels = members()
    rects = layout(levels)
    keys = [k for row in levels for k in row]
    thumbs = {k: circle_thumb(mem[k], 200 * S) for k in keys}
    chart = draw_chart(org, mem, levels, rects, set(keys), 1.0, thumbs).resize((W, H), Image.LANCZOS).convert("RGBA")
    fw = FrameWriter(out)
    n = int(dur * FPS)
    xs = np.arange(W)[None, :]
    ys = np.arange(H)[:, None]
    for i in range(n):
        t = i / FPS
        pos = lerp(-400, W + 400, ease(t / (dur * 0.7)))
        band = np.exp(-((xs + ys * 0.5 - pos) / 120.0) ** 2) * 0.55
        lay = np.zeros((H, W, 4), dtype="uint8")
        lay[..., :3] = rgb("gold")
        lay[..., 3] = (band * 255).astype("uint8")
        fr = chart.copy()
        fr.alpha_composite(Image.fromarray(lay, "RGBA"))
        z = 1 + 0.03 * ease(t / dur)
        fw.write(cam(fr.resize((CW, CH), Image.BILINEAR), CW / 2, CH / 2, z))
    fw.close()


def build_parts(cache: Path) -> list[tuple[str, Path, float]]:
    """Return ordered (label, clip, duration) parts for chapter 1, rendering only what changed."""
    org, mem, levels = members()
    keys = [k for row in levels for k in row]
    ver = code_version(("orgchart.py", "graphics.py"))
    orgjson = (ROOT / "config" / "organization.json").read_text(encoding="utf-8")
    port_files = [str(PORTRAITS / mem[k]["portrait"]) for k in keys]
    jobs = []
    out_intro = cache / f"org_intro_{spec_hash(ver, orgjson, *port_files)}.mp4"
    jobs.append(("intro", render_intro, (out_intro,), out_intro, 5.0))
    for i, k in enumerate(keys):
        o = cache / f"org_{i:02d}_{k}_{spec_hash(ver, orgjson, *port_files, i)}.mp4"
        T = CFG["timing"]["portrait_intro_leader" if mem[k].get("leader") else "portrait_intro"]
        jobs.append((k, render_member, (k, i, o), o, T))
    out_fin = cache / f"org_finale_{spec_hash(ver, orgjson, *port_files)}.mp4"
    jobs.append(("finale", render_finale, (out_fin,), out_fin, 5.0))
    return jobs


def _run_job(job):
    label, fn, args, out, dur = job
    if not out.exists():
        fn(*args)
    return out
