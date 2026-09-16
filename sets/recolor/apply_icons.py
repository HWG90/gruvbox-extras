#!/usr/bin/env python3
"""Re-point the ~/Desktop game launchers at the gruvbox re-toned icons.

Fully reversible - it only rewrites the Icon= line of each launcher:
    cp -a ~/Desktop-backup-*/*.desktop ~/Desktop/
    touch ~/Desktop/*.desktop && kbuildsycoca6 --noincremental
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "gi", os.path.join(HERE, "generate_icons_v3.py"))
gi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gi)

DESK = os.path.expanduser("~/Desktop")
applied = skipped = 0
for name, slug, appid in gi.GAMES:
    desktop_file = os.path.join(DESK, f"{name}.desktop")
    png = os.path.join(gi.ICON_DIR, f"{slug}.png")
    if not (os.path.isfile(desktop_file) and os.path.isfile(png)):
        print(f"  skip  {name}")
        skipped += 1
        continue
    lines = open(desktop_file, encoding="utf-8").read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("Icon="):
            lines[i] = f"Icon={png}\n"
    open(desktop_file, "w", encoding="utf-8").write("".join(lines))
    applied += 1

print(f"re-themed {applied} launchers from {gi.ICON_DIR}"
      + (f" ({skipped} skipped)" if skipped else ""))
print("then: touch ~/Desktop/*.desktop && kbuildsycoca6 --noincremental")
print("undo: cp -a ~/Desktop-backup-*/*.desktop ~/Desktop/ && "
      "touch ~/Desktop/*.desktop && kbuildsycoca6 --noincremental")
