#!/usr/bin/env python3
"""SRAR Iskandariah 2026 — documentary video pipeline.

  python main.py scan                       # build config/asset_manifest.json
  python main.py import <folder|zip> [--portraits <folder|zip>]
  python main.py build [01 02 ...]          # render chapters (cached; only changed shots re-render)
  python main.py preview                    # fast 540p preview of the full video
  python main.py render                     # final 1080p30 H.264/AAC MP4 → output/
  python main.py all                        # scan + build + render
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "scan":
        import scan_assets
        scan_assets.scan()
    elif cmd == "import":
        import import_assets
        sys.argv = ["import_assets.py", *rest]
        exec(compile(Path(import_assets.__file__).read_text(), import_assets.__file__, "exec"), {"__name__": "__main__"})
    elif cmd == "build":
        import build_chapters
        for ch in build_chapters.chapters():
            if not rest or any(r in ch["id"] for r in rest):
                build_chapters.build_chapter(ch)
    elif cmd in ("render", "preview"):
        import render_video
        render_video.render(preview=cmd == "preview")
    elif cmd == "all":
        main(["scan"])
        main(["build"])
        main(["render"])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
