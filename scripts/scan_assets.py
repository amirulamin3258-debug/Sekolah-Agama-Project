"""Scan local assets and write config/asset_manifest.json.

For every storyboard code: Drive source, local working copy, resolution/orientation/duration,
which chapter/segment uses it, applied fixes (watermark crop etc.) and status. Results are cached
by file size + mtime so re-scans are instant.
"""
from __future__ import annotations

import json
import subprocess

from PIL import Image

from common import ROOT, load_json, path


def probe(f):
    if f.suffix.lower() in (".mp4", ".mov"):
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                            "-of", "json", str(f)], capture_output=True, text=True)
        j = json.loads(r.stdout)
        s = j["streams"][0]
        return {"width": s["width"], "height": s["height"], "duration_s": round(float(j["format"]["duration"]), 2)}
    with Image.open(f) as im:
        return {"width": im.width, "height": im.height}


def usage_map():
    act = load_json("activities.json")
    use = {}
    for ch in act["chapters"]:
        for si, seg in enumerate(ch.get("segments", [])):
            for s in seg["shots"]:
                s = {"src": s} if isinstance(s, str) else s
                codes = [s.get(k) for k in ("src", "before", "after", "bg")] + \
                        [x["src"] if isinstance(x, dict) else x for x in s.get("srcs", [])]
                for c in filter(None, codes):
                    use.setdefault(c, []).append({"chapter": ch["id"], "segment": seg.get("label") or seg.get("narration", "")[:50]})
    return use


def scan() -> dict:
    sb = load_json("storyboard_assets.json")
    fixes = load_json("activities.json").get("asset_fixes", {})
    cache_f = path("cache") / "scan_cache.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    use = usage_map()
    media = path("media")
    items = []
    for a in sb["assets"]:
        local = next((p for p in media.glob(f"{a['code']}.*")), None)
        info = {}
        if local:
            k = f"{local.name}:{local.stat().st_size}:{int(local.stat().st_mtime)}"
            info = cache.get(k) or probe(local)
            cache[k] = info
        w, h = info.get("width"), info.get("height")
        items.append({
            "code": a["code"], "type": "video" if a["code"].startswith("V") else "image",
            "drive_id": a["drive_id"], "drive_url": f"https://drive.google.com/file/d/{a['drive_id']}/view",
            "drive_folder": a["drive_folder"], "drive_subfolder": a["subfolder"], "original_name": a["drive_title"],
            "local_file": str(local.relative_to(ROOT)) if local else None,
            **info, "orientation": (None if not w else "portrait" if h > w else "landscape"),
            "content": a["content"], "storyboard_chapter": a["chapter"], "storyboard_status": a["status"], "note": a["note"],
            "fix": fixes.get(a["code"]), "used_in": use.get(a["code"], []),
        })
    cache_f.write_text(json.dumps(cache))
    portraits = []
    org = load_json("organization.json")["committee"]["members"]
    for key, m in org.items():
        p = path("portraits") / m["portrait"]
        portraits.append({"key": key, "name": m["name"], "role": m["role"], "file": str(p.relative_to(ROOT)),
                          "present": p.exists(), "verified": m.get("verified", False), "flag": m.get("flag")})
    man = {
        "generated_by": "scripts/scan_assets.py",
        "source": sb["source"],
        "summary": {
            "total": len(items), "images": sum(i["type"] == "image" for i in items), "videos": sum(i["type"] == "video" for i in items),
            "local_present": sum(bool(i["local_file"]) for i in items),
            "used_in_video": sum(bool(i["used_in"]) for i in items),
            "storyboard_guna": sum(i["storyboard_status"] == "Guna" for i in items),
            "storyboard_simpanan": sum(i["storyboard_status"] == "Simpanan" for i in items),
            "storyboard_gugur": sum(i["storyboard_status"] == "Gugur" for i in items),
        },
        "drive_folders": sb["drive_folders"],
        "portraits": portraits,
        "assets": items,
    }
    (ROOT / "config" / "asset_manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    s = man["summary"]
    print(f"[manifest] {s['total']} bahan ({s['images']} gambar, {s['videos']} video); {s['local_present']} ada secara tempatan; "
          f"{s['used_in_video']} digunakan dalam video.")
    return man


if __name__ == "__main__":
    scan()
