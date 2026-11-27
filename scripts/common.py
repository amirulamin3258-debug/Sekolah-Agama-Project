"""Shared helpers: config loading, paths, fonts, colours, ffmpeg pipes, caching."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent


def load_json(name: str) -> dict:
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


CFG = load_json("video_config.json")
W, H, FPS = CFG["width"], CFG["height"], CFG["fps"]
COL = CFG["colors"]


def rgb(name_or_hex: str, alpha: int | None = None):
    h = COL.get(name_or_hex, name_or_hex).lstrip("#")
    c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return c + (alpha,) if alpha is not None else c


def path(key: str) -> Path:
    p = ROOT / CFG["paths"][key]
    if key in ("cache", "chapters", "output"):
        p.mkdir(parents=True, exist_ok=True)
    return p


@lru_cache(maxsize=64)
def font(kind: str, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(ROOT / CFG["fonts"][kind]), size)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
    return f


def spec_hash(*parts) -> str:
    """Stable hash of a render spec + the source files' mtimes/sizes (cache key)."""
    h = hashlib.sha1()
    for p in parts:
        if isinstance(p, (str, Path)) and len(str(p)) < 1024 and "\n" not in str(p) and Path(p).is_file():
            st = Path(p).stat()
            h.update(f"{p}:{st.st_size}:{int(st.st_mtime)}".encode())
        else:
            h.update(json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def code_version(files=("shots.py", "graphics.py")) -> str:
    """Hash of the renderer modules that affect pixels, so cached clips refresh when they change."""
    h = hashlib.sha1()
    for f in [ROOT / "scripts" / n for n in files]:
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


def encoder_args(crf=None, preset=None):
    e = CFG["encode"]
    return ["-c:v", "libx264", "-preset", preset or e["intermediate_preset"],
            "-crf", str(crf if crf is not None else e["intermediate_crf"]),
            "-pix_fmt", "yuv420p", "-r", str(FPS)]


class FrameWriter:
    """Pipe raw RGB frames (PIL images) into ffmpeg -> H.264 file."""

    def __init__(self, out: Path, w=W, h=H):
        self.out = Path(out)
        self.tmp = self.out.with_suffix(".part.mp4")
        self.p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", *encoder_args(), "-an", str(self.tmp)],
            stdin=subprocess.PIPE)
        self.n = 0

    def write(self, img):
        if img.mode != "RGB":
            img = img.convert("RGB")
        self.p.stdin.write(img.tobytes())
        self.n += 1

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise RuntimeError(f"ffmpeg failed for {self.out}")
        os.replace(self.tmp, self.out)
        return self.out


def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Command failed: " + " ".join(map(str, cmd)) + "\n" + r.stderr[-3000:])
    return r


def probe_duration(p: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)])
    return float(r.stdout.strip())


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return a + (b - a) * t
