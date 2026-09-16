#!/usr/bin/env python3
"""Generate gruvbox-themed game icons (SVG -> PNG) for the launchers on ~/Desktop.

Design: solid gruvbox accent tile (slightly gradiented), subtle diagonal stripe
texture for differentiation, thin dark inner border, dark gruvbox monogram.
Output: ~/.local/share/icons/gruvbox-games/<slug>.png  (512x512)
"""
import os
import subprocess
import sys

from PIL import ImageFont

ICON_DIR = os.path.expanduser("~/.local/share/icons/gruvbox-games")
SVG_DIR = os.path.join(ICON_DIR, "svg")
FONT_PATH = subprocess.run(
    ["fc-match", "-f", "%{file}", "DejaVu Sans Condensed:bold"],
    capture_output=True, text=True, check=True).stdout.strip()

# gruvbox palette
BG0 = "#282828"
# bright accents
RED, GREEN, YELLOW, BLUE, PURPLE, AQUA, ORANGE = (
    "#fb4934", "#b8bb26", "#fabd2f", "#83a598", "#d3869b", "#8ec07c", "#fe8019")
# light neutrals
FG, FG1, FG4 = "#ebdbb2", "#d5c4a1", "#a89984"

# desktop-file basename (@ -> _ placeholder), monogram, accent, stripe angle
GAMES = [
    ("Beyond Citadel",                                              "BC",   GREEN,  45),
    ("Dead Space",                                                  "DS",   AQUA,   90),
    ("DOOM 64",                                                     "64",   ORANGE, 45),
    ("DOOM The Dark Ages",                                          "DA",   RED,    45),
    ("Hades II",                                                    "H2",   PURPLE, 45),
    ("HELLDIVERS 2",                                                "HD2",  YELLOW,  0),
    ("METAL GEAR RISING REVENGEANCE",                               "MGR",  RED,     0),
    ("METAL GEAR SOLID 4 Guns of the Patriots - Master Collection Version",
                                                                    "MGS4", BLUE,   45),
    ("METAL GEAR SOLID MASTER COLLECTION Vol.2",                    "MC2",  AQUA,   45),
    ("METAL GEAR SOLID Peace Walker - Master Collection Version",   "PW",   GREEN,  90),
    ("Quake",                                                       "Q",    YELLOW, 45),
    ("Resident Evil Requiem",                                       "RE",   GREEN,   0),
    ("Selaco",                                                      "S",    BLUE,    0),
    ("The Blood of Dawnwalker",                                     "BD",   FG1,     0),
    ("Trepang2",                                                    "T2",   FG4,    90),
    ("ULTRAKILL",                                                   "UK",   FG,     90),
]

MONO_MAX_W, MONO_MAX_H = 396, 250   # room inside the tile for the monogram


def slugify(name: str) -> str:
    out = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def shade(hex_color: str, factor: float) -> str:
    """Darken (factor < 1) a #rrggbb colour."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def mono_font_size(text: str) -> float:
    """Pick a font size so `text` fits the monogram box (TrueType metrics are linear)."""
    ref = 200
    font = ImageFont.truetype(FONT_PATH, ref)
    left, top, right, bottom = font.getbbox(text)
    w, h = right - left, bottom - top
    # getbbox includes ascender/descender space; use advance width for width fit
    advance = font.getlength(text)
    return ref * min(MONO_MAX_W / advance, MONO_MAX_H / max(h, 1))


def build_svg(text: str, accent: str, angle: int) -> str:
    size = round(mono_font_size(text), 2)
    gradient = f"""    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{shade(accent, 1.10)}"/>
      <stop offset="1" stop-color="{shade(accent, 0.86)}"/>
    </linearGradient>"""
    pattern = ""
    overlay = ""
    if angle:
        pattern = f"""    <pattern id="tex" width="24" height="24" patternUnits="userSpaceOnUse"
             patternTransform="rotate({angle} 256 256)">
      <rect width="12" height="24" fill="#000000" opacity="0.08"/>
    </pattern>"""
        overlay = ('    <g clip-path="url(#clip)">\n'
                   '      <rect x="8" y="8" width="496" height="496" fill="url(#tex)"/>\n'
                   '    </g>\n')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <defs>
{gradient}
    <clipPath id="clip">
      <rect x="8" y="8" width="496" height="496" rx="100" ry="100"/>
    </clipPath>
{pattern}  </defs>
  <rect x="8" y="8" width="496" height="496" rx="100" ry="100" fill="url(#tile)"/>
{overlay}  <rect x="14" y="14" width="484" height="484" rx="94" ry="94" fill="none"
        stroke="{BG0}" stroke-opacity="0.22" stroke-width="6"/>
  <text x="256" y="256" text-anchor="middle" dominant-baseline="central"
        font-family="DejaVu Sans Condensed" font-weight="bold"
        font-size="{size}" fill="{BG0}">{text}</text>
</svg>
"""


def main() -> int:
    os.makedirs(SVG_DIR, exist_ok=True)
    print(f"font: {FONT_PATH}")
    made = []
    for name, mono, accent, angle in GAMES:
        slug = slugify(name)
        svg = build_svg(mono, accent, angle)
        svg_path = os.path.join(SVG_DIR, f"{slug}.svg")
        png_path = os.path.join(ICON_DIR, f"{slug}.png")
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        subprocess.run(["rsvg-convert", "-w", "512", "-h", "512",
                        "-o", png_path, svg_path], check=True)
        made.append((name, slug, png_path))
        print(f"  {mono:<5} {accent}  -> {png_path}")
    print(f"\n{len(made)} icons generated in {ICON_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
