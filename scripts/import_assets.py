"""Import school media from a local folder or ZIP (e.g. a Google Drive download) into assets/.

Files are matched to storyboard codes (I01…I87, V01…V56) by, in order:
  1. exact code filename (I24.jpg)      2. original Drive file name      3. exact file size
Portraits are matched by the person's name tokens in the file name (e.g. "Bendahari - Ustazah Noor sadina…jpg").
Originals are never modified; working copies are written to assets/media and assets/portraits.

Usage:
  python scripts/import_assets.py /path/to/folder_or_zip [--portraits /path/to/portrait_folder_or_zip]
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from common import ROOT, load_json, path

MEDIA_EXT = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".heic"}


def unpack(src: Path) -> Path:
    if src.is_dir():
        return src
    if zipfile.is_zipfile(src):
        d = Path(tempfile.mkdtemp(prefix="srar_import_"))
        with zipfile.ZipFile(src) as z:
            z.extractall(d)
        return d
    raise SystemExit(f"Bukan folder/ZIP: {src}")


def import_media(src: Path) -> dict:
    sb = load_json("storyboard_assets.json")["assets"]
    by_title = {a["drive_title"].lower(): a for a in sb}
    by_size = {}
    for a in sb:
        by_size.setdefault(a["size"], []).append(a)
    dest = path("media")
    dest.mkdir(parents=True, exist_ok=True)
    found, unknown = {}, []
    for f in sorted(unpack(src).rglob("*")):
        if not f.is_file() or f.suffix.lower() not in MEDIA_EXT:
            continue
        a = None
        m = re.fullmatch(r"([IV]\d\d)", f.stem.upper())
        if m:
            a = next((x for x in sb if x["code"] == m.group(1)), None)
        a = a or by_title.get(f.name.lower())
        if a is None and len(by_size.get(f.stat().st_size, [])) == 1:
            a = by_size[f.stat().st_size][0]
        if a is None:
            unknown.append(str(f))
            continue
        out = dest / f"{a['code']}{f.suffix.lower()}"
        if not out.exists() or out.stat().st_size != f.stat().st_size:
            shutil.copy2(f, out)
        found[a["code"]] = str(f)
    print(f"[import] {len(found)} bahan dipadankan → {dest.relative_to(ROOT)}")
    if unknown:
        print(f"[import] {len(unknown)} fail tidak dipadankan (disimpan dalam output/unmatched_import.txt)")
        (path("output") / "unmatched_import.txt").write_text("\n".join(unknown), encoding="utf-8")
    return found


def _tokens(s: str) -> set[str]:
    stop = {"bin", "binti", "pn", "en", "tn", "hj", "ustaz", "ustazah", "mohd", "abd", "abdul", "jpg", "png", "mp4"}
    return {t for t in re.findall(r"[a-z]+", s.lower()) if len(t) > 2 and t not in stop}


def import_portraits(src: Path) -> None:
    org = load_json("organization.json")["committee"]["members"]
    dest = path("portraits")
    dest.mkdir(parents=True, exist_ok=True)
    unmatched = []
    for f in sorted(unpack(src).rglob("*")):
        if not f.is_file() or f.suffix.lower() not in MEDIA_EXT:
            continue
        ft = _tokens(f.stem)
        best, score = None, 0
        for key, m in org.items():
            sc = len(ft & _tokens(m["name"]))
            if sc > score:
                best, score = key, sc
        if best and score >= 2:
            target = dest / org[best]["portrait"]
            target = target.with_suffix(f.suffix.lower())
            shutil.copy2(f, target)
            print(f"[potret] {f.name}  →  {org[best]['name']} ({target.name})")
        else:
            unmatched.append(f.name)
    for u in unmatched:
        print(f"[potret] TIDAK DIPADANKAN: {u}  (tambah ke senarai pengesahan)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if "--portraits" in args:
        i = args.index("--portraits")
        import_portraits(Path(args[i + 1]))
        args = args[:i] + args[i + 2:]
    for a in args:
        import_media(Path(a))
