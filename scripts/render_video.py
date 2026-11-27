"""Final assembly: chapters → master MP4 with music, original audio, optional voice-over and subtitles."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

import music
from common import CFG, ROOT, path, run
from shots import media_file

SR = music.SR


def load_timelines() -> list[dict]:
    from build_chapters import chapters
    tls = []
    for ch in chapters():
        p = path("chapters") / ch["id"] / "timeline.json"
        if not p.exists():
            raise SystemExit(f"Bab {ch['id']} belum dibina. Jalankan: python main.py build")
        tls.append(json.loads(p.read_text(encoding="utf-8")))
    return tls


def fmt_srt(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def fmt_ass(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_subtitles(cues: list[dict], out_dir: Path) -> tuple[Path, Path]:
    srt = out_dir / "subtitles_ms.srt"
    srt.write_text("\n".join(f"{i + 1}\n{fmt_srt(c['start'])} --> {fmt_srt(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues)), encoding="utf-8")
    fs = CFG["subtitles"]["font_size"]
    gold = CFG["colors"]["gold"].lstrip("#")
    ass_gold = f"&H00{gold[4:6]}{gold[2:4]}{gold[0:2]}"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Narasi,Inter Medium,{fs},&H00FFFFFF,{ass_gold},&H00202020,&H8C000000,0,0,0,0,100,100,0.5,0,1,2.2,1.5,2,260,260,58,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{fmt_ass(c['start'])},{fmt_ass(c['end'])},Narasi,,0,0,0,,{{\\fad(350,350)}}{c['text']}" for c in cues]
    ass = out_dir / "subtitles_ms.ass"
    ass.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return srt, ass


def read_audio(src: Path, t_in: float, dur: float) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_in}", "-t", f"{dur}", "-i", str(src), "-vn", "-ac", "2", "-ar", str(SR),
                        "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()


def db(x):
    return 10 ** (x / 20)


def build_audio(tls: list[dict], total: float, out: Path, cues: list[dict]) -> Path:
    a = CFG["audio"]
    n = int(total * SR)
    if a.get("music_file_override"):
        mus = read_audio(ROOT / a["music_file_override"], 0, total)
        mus = np.pad(mus, ((0, max(0, n - len(mus))), (0, 0)))[:n]
    else:
        mcues, t = [], 0.0
        for tl in tls:
            mcues.append((t, tl["duration"], tl["music"]))
            t += tl["duration"]
        mus = music.score(mcues, total)[:n]
        mus = np.pad(mus, ((0, n - len(mus)), (0, 0)))
    duck = np.ones(n, dtype=np.float32)
    orig = np.zeros((n, 2), dtype=np.float32)
    t0 = 0.0
    for tl in tls:
        for oa in tl.get("original_audio", []):
            seg = read_audio(media_file(oa["src"]), oa["in"], oa["dur"])
            i = int((t0 + oa["start"]) * SR)
            seg = seg[: n - i]
            fade = min(len(seg) // 4, int(0.4 * SR))
            if fade:
                seg[:fade] *= np.linspace(0, 1, fade)[:, None]
                seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
            orig[i:i + len(seg)] += seg * db(a["original_audio_gain_db"])
            duck[i:i + len(seg)] = np.minimum(duck[i:i + len(seg)], db(a["duck_music_db"]))
        t0 += tl["duration"]
    # optional recorded voice-over: assets/audio/voiceover/cue_###.wav (see output/voiceover_script.txt)
    vo_dir = ROOT / a["voiceover_dir"]
    vo = np.zeros((n, 2), dtype=np.float32)
    for k, c in enumerate(cues):
        f = vo_dir / f"cue_{k + 1:03d}.wav"
        if f.exists():
            seg = read_audio(f, 0, 60)
            i = int(c["start"] * SR)
            seg = seg[: n - i]
            vo[i:i + len(seg)] += seg
            duck[i:i + len(seg)] = np.minimum(duck[i:i + len(seg)], db(a["duck_music_db"]))
    # smooth the ducking envelope (≈300 ms)
    k = int(0.3 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same").astype(np.float32)
    mix = mus * db(a["music_gain_db"] + 6) * duck[:, None] + orig + vo
    fi, fo = int(a["fade_in"] * SR), int(a["fade_out"] * SR)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = np.max(np.abs(mix)) + 1e-9
    if peak > 0.95:
        mix *= 0.95 / peak
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    return out


def render(preview: bool = False) -> Path:
    tls = load_timelines()
    outd = path("output")
    cues, t = [], 0.0
    for tl in tls:
        for c in tl["subtitles"]:
            cues.append({"start": round(t + c["start"], 3), "end": round(t + c["end"], 3), "text": c["text"], "chapter": tl["id"]})
        t += tl["duration"]
    total = t
    srt, ass = write_subtitles(cues, outd)
    (outd / "voiceover_script.txt").write_text(
        "Skrip suara latar (rakam setiap baris sebagai assets/audio/voiceover/cue_###.wav, kemudian render semula)\n\n" +
        "\n".join(f"cue_{i + 1:03d}  [{fmt_srt(c['start'])}]  {c['text']}" for i, c in enumerate(cues)), encoding="utf-8")
    wav = build_audio(tls, total, outd / "master_audio.wav", cues)
    lst = outd / "chapters.txt"
    lst.write_text("".join(f"file '{(ROOT / tl['file']).as_posix()}'\n" for tl in tls))
    e = CFG["encode"]
    final = outd / (("PREVIEW_540p_" if preview else "") + CFG["paths"]["final_name"])
    vf = []
    if CFG["subtitles"]["burn_in"]:
        vf.append(f"subtitles={ass.as_posix()}:fontsdir={(ROOT / 'assets/fonts').as_posix()}")
    if preview:
        vf.append("scale=960:540")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
           "-map", "0:v", "-map", "1:a"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast" if preview else e["final_preset"], "-crf", str(26 if preview else e["final_crf"]),
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(CFG["fps"]), "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "128k" if preview else e["audio_bitrate"], "-ar", str(SR), "-shortest", str(final)]
    run(cmd)
    lst.unlink()
    meta = {"file": final.name, "duration_s": round(total, 2),
            "chapters": [{"id": tl["id"], "name": tl["name"], "duration_s": round(tl["duration"], 2)} for tl in tls],
            "subtitle_cues": len(cues)}
    (outd / "render_report.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[siap] {final.relative_to(ROOT)}  ({total / 60:.1f} min)")
    return final


if __name__ == "__main__":
    import sys
    render(preview="--preview" in sys.argv)
