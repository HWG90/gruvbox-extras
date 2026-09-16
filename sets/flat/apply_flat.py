#!/usr/bin/env python3
"""Point the ~/Desktop launchers at the flat Gruvbox-Plus-style SVG icons.

Matches launcher -> icon by slugifying the .desktop basename, so anything not in
gruvbox-flat/ is simply skipped (that is how DOOM: The Dark Ages, Selaco and
Quake stay as you set them).

Only the Icon= line is rewritten.
Undo:  cp -a ~/Desktop-backup-*/*.desktop ~/Desktop/
       touch ~/Desktop/*.desktop && kbuildsycoca6 --noincremental
"""
import glob
import os

ICON_DIR = os.path.expanduser("~/.local/share/icons/gruvbox-flat")
DESK = os.path.expanduser("~/Desktop")


def slugify(name: str) -> str:
    out = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


icons = {os.path.basename(p)[:-4]: p for p in glob.glob(f"{ICON_DIR}/*.svg")}
applied, skipped = [], []
for df in sorted(glob.glob(f"{DESK}/*.desktop")):
    if os.path.basename(df) == "steam.desktop":
        continue
    slug = slugify(os.path.basename(df)[:-8])
    if slug not in icons:
        skipped.append(slug)
        continue
    lines = open(df, encoding="utf-8").read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("Icon="):
            lines[i] = f"Icon={icons[slug]}\n"
    open(df, "w", encoding="utf-8").write("".join(lines))
    applied.append(slug)

print(f"applied {len(applied)}: {', '.join(applied)}")
print(f"left alone ({len(skipped)}): {', '.join(skipped) or '-'}")
print("then: touch ~/Desktop/*.desktop && kbuildsycoca6 --noincremental")
