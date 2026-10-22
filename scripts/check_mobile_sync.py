#!/usr/bin/env python3
"""Fail if the native shells' bundled web assets drift from frontend/web.

frontend/web is the single source of truth (mobile/capacitor.config.json sets
webDir to it). The copies under mobile/*/public are produced by `cap sync`.

  python scripts/check_mobile_sync.py          # report drift, exit 1 if any
  python scripts/check_mobile_sync.py --fix    # copy web files over the shells

Files that only exist in the shells (cordova.js, cordova_plugins.js, generated
by Capacitor) are ignored. Empty files in web are always an error.
"""
import filecmp, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "frontend" / "web"
SHELLS = [
    ROOT / "mobile" / "android" / "app" / "src" / "main" / "assets" / "public",
    ROOT / "mobile" / "ios" / "App" / "App" / "public",
]
GENERATED = {"cordova.js", "cordova_plugins.js"}

def main(fix: bool) -> int:
    problems = 0
    for f in WEB.rglob("*"):
        if f.is_file() and f.stat().st_size == 0 and f.name != "__init__.py":
            print(f"EMPTY source file: {f.relative_to(ROOT)}")
            problems += 1
    for shell in SHELLS:
        if not shell.exists():
            continue
        for f in WEB.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(WEB)
            dst = shell / rel
            if not dst.exists() or not filecmp.cmp(f, dst, shallow=False):
                if fix:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
                else:
                    print(f"DRIFT: {dst.relative_to(ROOT)}")
                    problems += 1
        for f in shell.rglob("*"):
            if f.is_file() and f.name not in GENERATED and not (WEB / f.relative_to(shell)).exists():
                print(f"ORPHAN (not in web): {f.relative_to(ROOT)}")
                problems += 1
    print("OK" if not problems else f"{problems} problem(s)")
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main("--fix" in sys.argv))
