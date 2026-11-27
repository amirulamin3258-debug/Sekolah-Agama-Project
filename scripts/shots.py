"""Shot renderer: turns one shot spec (photo / video / split / card / ...) into a cached 1080p30 clip."""
from __future__ import annotations

import subprocess
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

import graphics as G
from common import CFG, FPS, H, W, FrameWriter, code_version, ease, ease_out, lerp, path, rgb, spec_hash

MEDIA = path("media")
KB_SCALE = 1.12  # canvas headroom for Ken Burns moves


# --------------------------------------------------------------------------- sources
def media_file(code: str) -> Path:
    for ext in (".jpg", ".jpeg", ".png", ".mp4", ".mov"):
        p = MEDIA / f"{code}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"Bahan {code} tiada dalam {MEDIA} (jalankan scripts/import_assets.py)")


def load_photo(code: str, crop=None, rotate=0.0) -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(media_file(code))).convert("RGB")
    if crop:
        x0, y0, x1, y1 = crop
        im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
    if rotate:
        im = im.rotate(rotate, resample=Image.BICUBIC, expand=False)
        m = int(min(im.size) * abs(np.sin(np.radians(rotate))) * 1.1) + 2
        im = im.crop((m, m, im.width - m, im.height - m))
    return im


def cover(im: Image.Image, w: int, h: int, focus_y=0.45, focus_x=0.5) -> Image.Image:
    s = max(w / im.width, h / im.height)
    nw, nh = int(im.width * s + 0.5), int(im.height * s + 0.5)
    r = im.resize((nw, nh), Image.LANCZOS)
    x = int((nw - w) * focus_x)
    y = int((nh - h) * focus_y)
    return r.crop((x, y, x + w, y + h))


def blurred_bg(im: Image.Image, w: int, h: int) -> Image.Image:
    small = cover(im, w // 8, h // 8)
    small = small.filter(ImageFilter.GaussianBlur(6))
    bg = small.resize((w, h), Image.BICUBIC)
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    tint = Image.new("RGB", (w, h), rgb("dark_green"))
    return Image.blend(bg, tint, 0.25)


def photo_canvas(spec: dict, w=None, h=None) -> Image.Image:
    w = w or int(W * KB_SCALE)
    h = h or int(H * KB_SCALE)
    im = load_photo(spec["src"], spec.get("crop"), spec.get("rotate", 0))
    fit = spec.get("fit", "auto")
    aspect = im.width / im.height
    if fit == "cover" or (fit == "auto" and aspect >= 1.25):
        can = cover(im, w, h, spec.get("focus_y", 0.42), spec.get("focus_x", 0.5))
    else:
        can = blurred_bg(im, w, h)
        fh = int(h * 0.94)
        fw = int(im.width * fh / im.height)
        if fw > w * 0.94:
            fw = int(w * 0.94)
            fh = int(im.height * fw / im.width)
        fg = im.resize((fw, fh), Image.LANCZOS)
        x, y = (w - fw) // 2, (h - fh) // 2
        sh = Image.new("L", (w, h), 0)
        sh.paste(170, (x + 10, y + 14, x + fw + 10, y + fh + 14))
        sh = sh.filter(ImageFilter.GaussianBlur(18))
        can.paste(Image.new("RGB", (w, h), (0, 0, 0)), (0, 0), sh)
        can.paste(fg, (x, y))
        gold = Image.new("RGB", (fw + 6, fh + 6), rgb("gold"))
        can.paste(gold, (x - 3, y - 3))
        can.paste(fg, (x, y))
    if spec.get("desat"):
        can = ImageEnhance.Color(can).enhance(0.45)
    return can


def kb_frames(canvas: Image.Image, n: int, motion: str):
    cw, ch = canvas.size
    # (z0, z1, cx0, cx1): z=1 shows the whole canvas; cx is the horizontal centre (fraction of width)
    moves = {
        "in": (1.0, 1.09, 0.5, 0.5),
        "out": (1.09, 1.0, 0.5, 0.5),
        "left": (1.10, 1.10, 0.545, 0.455),
        "right": (1.10, 1.10, 0.455, 0.545),
        "still": (1.0, 1.015, 0.5, 0.5),
    }
    z0, z1, c0, c1 = moves[motion]
    for i in range(n):
        u = i / max(1, n - 1)
        t = ease(u) * 0.6 + u * 0.4
        z = lerp(z0, z1, t)
        vw = cw / z
        vh = vw * H / W
        cx = lerp(c0, c1, t) * cw
        cy = 0.5 * ch
        x0 = min(max(cx - vw / 2, 0), cw - vw)
        y0 = min(max(cy - vh / 2, 0), ch - vh)
        yield canvas.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)


def auto_motion(code: str, idx: int = 0) -> str:
    return ["in", "out", "left", "in", "right", "out"][(zlib.crc32(code.encode()) + idx) % 6]


def video_frames(spec: dict, n: int, w=W, h=H, fill="auto"):
    """Decode a (trimmed) clip to exactly n frames of w x h via ffmpeg; vertical clips get a blurred backdrop."""
    src = media_file(spec["src"])
    t_in = float(spec.get("in", 0))
    speed = float(spec.get("speed", 1.0))
    dur = n / FPS * speed + 0.1
    crop = spec.get("crop")
    pre = []
    if crop:
        x0, y0, x1, y1 = crop
        pre.append(f"crop=iw*{x1 - x0}:ih*{y1 - y0}:iw*{x0}:ih*{y0}")
    pre.append(f"setpts=PTS/{speed}" if speed != 1.0 else "setpts=PTS")
    pre.append(f"fps={FPS}")
    pre = ",".join(pre)
    sharpen = "unsharp=5:5:0.7:5:5:0.0"
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(src)], capture_output=True, text=True)
    sw, sh = map(int, probe.stdout.strip().split(",")[:2])
    if crop:
        sw, sh = int(sw * (crop[2] - crop[0])), int(sh * (crop[3] - crop[1]))
    src_aspect = sw / sh
    if fill == "cover" or (fill == "auto" and abs(src_aspect - w / h) < 0.25):
        fc = (f"[0:v]{pre},scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={w}:{h},{sharpen},format=rgb24[o]")
    else:
        fc = (f"[0:v]{pre},split[a][b];"
              f"[a]scale={w // 4}:{h // 4}:force_original_aspect_ratio=increase,crop={w // 4}:{h // 4},"
              f"boxblur=8:2,scale={w}:{h},eq=brightness=-0.12:saturation=0.8[bg];"
              f"[b]scale=-2:{int(h * 0.96) if h > w else h}:flags=lanczos,{sharpen}[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=rgb24[o]")
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t_in:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
           "-filter_complex", fc, "-map", "[o]", "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    fsz = w * h * 3
    last = None
    for _ in range(n):
        buf = p.stdout.read(fsz)
        if len(buf) == fsz:
            last = Image.frombytes("RGB", (w, h), buf)
        if last is None:
            last = Image.new("RGB", (w, h), rgb("dark_green"))
        yield last
    p.stdout.close()
    p.wait()


# --------------------------------------------------------------------------- shot types
def shot_duration(spec: dict) -> float:
    if "dur" in spec:
        return float(spec["dur"])
    if spec["type"] == "video":
        return (float(spec["out"]) - float(spec.get("in", 0))) / float(spec.get("speed", 1.0))
    return CFG["timing"]["photo_default"]


def _overlays(img: Image.Image, spec: dict, t: float) -> Image.Image:
    ovs = spec.get("overlays", [])
    if not ovs:
        return img
    base = img.convert("RGBA")
    for ov in ovs:
        lt = t - ov.get("start", 0.0)
        if ov["kind"] == "lower_third":
            lay = G.lower_third_layer(ov["title"], ov.get("sub", ""), lt, ov.get("dur", CFG["timing"]["lower_third"]))
        elif ov["kind"] == "badge":
            lay = G.big_badge_layer(lt, ov.get("dur", shot_duration(spec)), ov["text"], ov.get("sub", ""))
        elif ov["kind"] == "label":
            lay = _corner_label(ov["text"], lt, ov.get("dur", 99), ov.get("pos", "tl"))
        else:
            lay = None
        if lay is not None:
            base.alpha_composite(lay)
    return base


def _corner_label(text, t, dur, pos):
    if t < 0 or t > dur:
        return None
    from PIL import ImageDraw
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a = ease(t / 0.4) * (1 - ease((t - dur + 0.3) / 0.3))
    f = G.font("title", 40, "Bold")
    tw, th = G.text_size(d, text, f)
    x = 70 if pos == "tl" else W - tw - 110
    d.rectangle([x - 20, 60, x + tw + 20, 60 + th + 34], fill=rgb("dark_green", int(220 * a)))
    d.line([(x - 20, 60 + th + 34), (x + tw + 20, 60 + th + 34)], fill=rgb("gold", int(255 * a)), width=4)
    d.text((x, 72), text, font=f, fill=rgb("gold", int(255 * a)))
    return lay


def gen_frames(spec: dict, n: int):
    ty = spec["type"]
    dur = n / FPS
    if ty == "photo":
        can = photo_canvas(spec)
        yield from kb_frames(can, n, spec.get("motion") or auto_motion(spec["src"]))
    elif ty == "video":
        yield from video_frames(spec, n)
    elif ty == "split":
        yield from split_frames(spec, n)
    elif ty == "card":
        for i in range(n):
            yield G.chapter_card(i / FPS, dur, spec.get("number", ""), spec["title"], spec.get("subtitle", ""))
    elif ty == "opening_title":
        for i in range(n):
            yield G.opening_title(i / FPS, dur, CFG)
    elif ty == "main_title":
        for i in range(n):
            yield G.main_title(i / FPS, dur, CFG)
    elif ty == "text_card":
        bg = photo_canvas({"src": spec["bg"], "fit": "cover"}, W, H).filter(ImageFilter.GaussianBlur(8)) if spec.get("bg") else None
        for i in range(n):
            yield G.text_card(i / FPS, dur, spec["heading"], spec["items"], spec.get("sub", ""), bg)
    elif ty == "compare":
        yield from compare_frames(spec, n)
    elif ty == "collage":
        yield from collage_frames(spec, n)
    elif ty == "credits":
        for i in range(n):
            yield G.credits_frame(i / FPS, dur, [tuple(b) for b in spec["blocks"]])
    else:
        raise ValueError(f"Jenis shot tidak dikenali: {ty}")


def split_frames(spec, n):
    srcs = spec["srcs"]
    k = len(srcs)
    gap = 8
    pw = (W - gap * (k + 1)) // k // 2 * 2
    ph = H - 2 * gap - 120
    gap = (W - pw * k) // (k + 1)
    iters = []
    for s in srcs:
        s = dict(s) if isinstance(s, dict) else {"src": s}
        if s["src"].startswith("V"):
            iters.append(video_frames(s, n, pw, ph, fill="cover"))
        else:
            can = cover(load_photo(s["src"], s.get("crop")), int(pw * 1.08), int(ph * 1.08), s.get("focus_y", 0.4))

            def ph_iter(can=can):
                for i in range(n):
                    z = 1 + 0.06 * (i / n)
                    vw, vh = can.width / 1.08 / z * 1.0, can.height / 1.08 / z
                    x0, y0 = (can.width - vw) / 2, (can.height - vh) / 2
                    yield can.transform((pw, ph), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)
            iters.append(ph_iter())
    bg = G.green_background().convert("RGB")
    for i in range(n):
        fr = bg.copy()
        for j, it in enumerate(iters):
            p = next(it)
            x = gap + j * (pw + gap)
            fr.paste(p, (x, gap + 60))
        from PIL import ImageDraw
        d = ImageDraw.Draw(fr)
        for j in range(1, k):
            x = gap + j * (pw + gap) - gap // 2
            d.line([(x, 60), (x, H - 60)], fill=rgb("gold"), width=3)
        yield fr


def compare_frames(spec, n):
    b = photo_canvas({"src": spec["before"], "fit": "cover", "desat": True, "crop": spec.get("before_crop")}, W, H)
    a = photo_canvas({"src": spec["after"], "fit": "cover", "crop": spec.get("after_crop")}, W, H)
    from PIL import ImageDraw
    dur = n / FPS
    for i in range(n):
        t = i / FPS
        p = ease((t - 1.2) / 1.2)
        x = int(W * p)
        fr = b.copy()
        if x > 0:
            fr.paste(a.crop((0, 0, x, H)), (0, 0))
        d = ImageDraw.Draw(fr)
        if 0 < x < W:
            d.line([(x, 0), (x, H)], fill=rgb("gold"), width=6)
        fr = _overlays(fr, {"overlays": [{"kind": "label", "text": "SEBELUM", "start": 0, "dur": 2.0, "pos": "tl"},
                                         {"kind": "label", "text": "SELEPAS", "start": 2.2, "dur": dur - 2.2, "pos": "tr"}]}, t)
        yield fr


def collage_frames(spec, n):
    from PIL import ImageDraw
    srcs = spec["srcs"]
    k = len(srcs)
    pw, ph = 520, 390
    tiles = []
    for s in srcs:
        im = cover(load_photo(s), pw, ph)
        t = Image.new("RGB", (pw + 12, ph + 12), rgb("gold"))
        t.paste(im, (6, 6))
        tiles.append(t)
    bg = G.green_background().convert("RGB")
    total_w = k * (pw + 12) + (k - 1) * 50
    x0 = (W - total_w) // 2
    dur = n / FPS
    for i in range(n):
        t = i / FPS
        fr = bg.copy().convert("RGBA")
        for j, tile in enumerate(tiles):
            p = ease_out((t - 0.2 - j * 0.35) / 0.9)
            if p <= 0:
                continue
            y = int(H / 2 - ph / 2 - 50 + (1 - p) * 160)
            lay = Image.new("RGBA", fr.size, (0, 0, 0, 0))
            lay.paste(tile, (x0 + j * (pw + 62), y))
            fr.alpha_composite(G.with_alpha(lay, p))
        if spec.get("caption"):
            d = ImageDraw.Draw(fr)
            a = ease((t - 1.4) / 0.8)
            G.draw_center(d, W / 2, H - 230, spec["caption"], G.font("title", 54, "Bold"), rgb("gold", int(255 * a)))
        yield fr.convert("RGB")


# --------------------------------------------------------------------------- render + cache
def source_files(spec: dict) -> list[str]:
    out = []
    for k in ("src", "before", "after", "bg"):
        if spec.get(k):
            out.append(str(media_file(spec[k])))
    for s in spec.get("srcs", []):
        out.append(str(media_file(s["src"] if isinstance(s, dict) else s)))
    return out


def render_shot(spec: dict, cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir or path("cache")
    n = max(1, int(round(shot_duration(spec) * FPS)))
    key = spec_hash(spec, n, code_version(), CFG["colors"], *source_files(spec))
    out = cache_dir / f"{spec.get('id', spec['type'])}_{key}.mp4"
    if out.exists():
        return out
    fw = FrameWriter(out)
    for i, fr in enumerate(gen_frames(spec, n)):
        fw.write(_overlays(fr, spec, i / FPS))
    fw.close()
    return out


def _render_worker(args):
    spec, cache_dir = args
    return render_shot(spec, Path(cache_dir))
