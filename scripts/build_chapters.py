"""Build each chapter: expand the edit list, render shots (parallel + cached), join with transitions."""
from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

import orgchart
import shots as S
from common import CFG, FPS, ROOT, load_json, path, run, spec_hash, code_version

TRANS = {"dissolve": 0.5, "dissolve_long": 1.0, "cut": 1.0 / FPS}
GREEN = CFG["colors"]["dark_green"].replace("#", "0x")


def norm_shot(s, fixes: dict) -> dict:
    if isinstance(s, str):
        s = {"src": s}
    s = dict(s)
    s.setdefault("type", "video" if s.get("src", "").startswith("V") else "photo")
    if s.get("src") in fixes:
        for k, v in fixes[s["src"]].items():
            s.setdefault(k, v)
    if s["type"] == "video" and "out" not in s and "dur" not in s:
        s["dur"] = 4.0
    if s["type"] == "split":
        s["srcs"] = [dict(fixes.get(x["src"] if isinstance(x, dict) else x, {}), **(x if isinstance(x, dict) else {"src": x})) for x in s["srcs"]]
    return s


def credits_blocks() -> list:
    org = load_json("organization.json")["committee"]
    mem = [m for m in org["members"].values() if m.get("verified")]
    lead = [f"{m['role']} — {m['name']}" for m in mem[:5]]
    ajk = [m["name"] for m in mem if m["role"] == "Ahli Jawatankuasa"]
    aud = [m["name"] for m in mem if m["role"].startswith("Pemeriksa")]
    return [
        ["JAWATANKUASA SRAR ISKANDARIAH 2026", lead],
        ["AHLI JAWATANKUASA", ajk],
        ["PEMERIKSA KIRA-KIRA", aud],
        ["FOTO & VIDEO", ["Warga SRAR Iskandariah"]],
        ["MUZIK", ["Gubahan instrumental asal (dijana khas untuk video ini)"]],
        ["TERIMA KASIH", ["Guru, kakitangan, ibu bapa & komuniti", "SRAR Iskandariah · Batu Gajah, Perak · 2026"]],
    ]


def expand(ch: dict, fixes: dict) -> list[dict]:
    """Flatten segments → shots with transition, overlays (lower third) and narration cue markers."""
    out = []
    for si, seg in enumerate(ch.get("segments", [])):
        tr = seg.get("trans", "dissolve")
        for j, raw in enumerate(seg["shots"]):
            s = norm_shot(raw, fixes)
            s["id"] = f"{ch['id']}_{si:02d}_{j:02d}"
            s["trans_in"] = TRANS["dissolve"] if j == 0 else TRANS[tr]
            if s["type"] == "credits":
                s["blocks"] = credits_blocks()
            if j == 0 and seg.get("label"):
                s.setdefault("overlays", [])
                s["overlays"] = [{"kind": "lower_third", "title": seg["label"], "sub": seg.get("sub", ""),
                                  "start": 0.5, "dur": CFG["timing"]["lower_third"]}] + list(s["overlays"])
            if j == 0 and seg.get("narration"):
                s["_narration"] = seg["narration"]
                s["_seg_shots"] = len(seg["shots"])
            out.append(s)
    if out:
        out[0]["trans_in"] = 0
    return out


def render_parallel(specs, cache: Path, procs: int):
    jobs = [(s, str(cache)) for s in specs]
    with Pool(procs) as p:
        return p.map(S._render_worker, jobs, chunksize=1)


def join(clips: list[Path], durs: list[float], trans: list[float], out: Path) -> float:
    """xfade-chain clips; trans[i] is the overlap between clip i-1 and clip i (trans[0] ignored)."""
    total = sum(durs) - sum(trans[1:])
    args = ["ffmpeg", "-v", "error", "-y"]
    for c in clips:
        args += ["-i", str(c)]
    fc, last, cur = [], "[0:v]", durs[0]
    for i in range(len(clips)):
        fc.append(f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p[v{i}]")
    last = "[v0]"
    for i in range(1, len(clips)):
        off = cur - trans[i]
        fc.append(f"{last}[v{i}]xfade=transition=fade:duration={trans[i]:.4f}:offset={off:.4f}[x{i}]")
        last = f"[x{i}]"
        cur = off + durs[i]
    fc.append(f"{last}fade=t=in:st=0:d=0.5:color={GREEN},fade=t=out:st={total - 0.8:.3f}:d=0.8:color={GREEN}[out]")
    script = out.with_suffix(".filter.txt")
    script.write_text(";\n".join(fc))
    e = CFG["encode"]
    run(args + ["-filter_complex_script", str(script), "-map", "[out]", "-c:v", "libx264", "-preset", e["intermediate_preset"],
                "-crf", str(e["intermediate_crf"]), "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(out)])
    script.unlink()
    return total


def build_chapter(ch: dict, procs: int = 4) -> dict:
    act = load_json("activities.json")
    fixes = {k: v for k, v in act.get("asset_fixes", {}).items() if not k.startswith("_")}
    cache = path("cache")
    cdir = path("chapters") / ch["id"]
    cdir.mkdir(parents=True, exist_ok=True)
    cues, audio = [], []

    if ch.get("type") == "orgchart":
        card = {"type": "card", "id": f"{ch['id']}_card", "dur": CFG["timing"]["chapter_card"], **ch["card"]}
        card_clip = S.render_shot(card, cache)
        jobs = orgchart.build_parts(cache)
        with Pool(procs) as p:
            clips = p.map(orgchart._run_job, jobs, chunksize=1)
        clips = [card_clip] + clips
        durs = [round(card["dur"] * FPS) / FPS] + [round(j[4] * FPS) / FPS for j in jobs]
        trans = [0, TRANS["dissolve"]] + [TRANS["cut"]] * (len(jobs) - 1)
        starts = _starts(durs, trans)
        cues.append({"start": 0.4, "end": durs[0] - 0.3, "text": ch["narration_intro"]})
        cues.append({"start": starts[1] + 0.3, "end": starts[1] + durs[1] - 0.2, "text": ch["narration_chart"]})
        cues.append({"start": starts[-1] + 0.5, "end": starts[-1] + durs[-1] - 0.6, "text": ch["narration_finale"]})
        labels = ["card"] + [j[0] for j in jobs]
    else:
        specs = expand(ch, fixes)
        clips = render_parallel(specs, cache, procs)
        durs = [round(S.shot_duration(s) * FPS) / FPS for s in specs]
        trans = [s["trans_in"] for s in specs]
        starts = _starts(durs, trans)
        labels = [s["id"] for s in specs]
        for i, s in enumerate(specs):
            if s.get("_narration"):
                k = s["_seg_shots"]
                seg_end = starts[i + k - 1] + durs[i + k - 1]
                txt = s["_narration"]
                show = max(3.2, min(7.5, 1.2 + 0.075 * len(txt)))
                cues.append({"start": starts[i] + 0.35, "end": min(seg_end - 0.3, starts[i] + 0.35 + show), "text": txt})
            if s.get("audio"):
                audio.append({"src": s["src"], "start": starts[i], "in": float(s.get("in", 0)), "dur": durs[i]})

    out = cdir / f"{ch['id']}.mp4"
    key = spec_hash([str(c) for c in clips], trans, code_version())
    stamp = cdir / ".build_key"
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        total = sum(durs) - sum(trans[1:])
    else:
        total = join(clips, durs, trans, out)
        stamp.write_text(key)
    timeline = {"id": ch["id"], "name": ch["name"], "music": ch.get("music", "warm"), "duration": total, "file": str(out.relative_to(ROOT)),
                "shots": [{"label": l, "start": round(st, 3), "dur": round(d, 3), "clip": Path(c).name} for l, st, d, c in zip(labels, starts, durs, clips)],
                "subtitles": cues, "original_audio": audio}
    (cdir / "timeline.json").write_text(json.dumps(timeline, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[bab] {ch['id']}: {len(clips)} shot, {total:.1f} s → {out.relative_to(ROOT)}")
    return timeline


def _starts(durs, trans):
    st, cur = [0.0], durs[0]
    for i in range(1, len(durs)):
        s = cur - trans[i]
        st.append(s)
        cur = s + durs[i]
    return st


def chapters() -> list[dict]:
    return load_json("activities.json")["chapters"]


if __name__ == "__main__":
    want = sys.argv[1:]
    for ch in chapters():
        if not want or any(w in ch["id"] for w in want):
            build_chapter(ch)
