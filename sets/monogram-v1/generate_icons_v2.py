#!/usr/bin/env python3
"""Gruvbox silhouette icons for the Steam launchers on ~/Desktop.

Takes each game's real Steam logo art (transparent PNG from the local Steam
librarycache), flattens it to a single gruvbox accent colour and centres it on a
dark gruvbox tile with a thin accent ring.

Output: ~/.local/share/icons/gruvbox-games/<slug>.png  (512x512)
Re-run is idempotent; edit ACCENTS below to recolour.
"""
import glob
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ICON_DIR = os.path.expanduser("~/.local/share/icons/gruvbox-games")
STEAM_CACHE = os.path.expanduser("~/.local/share/Steam/appcache/librarycache")
ARCHIVE = os.path.join(ICON_DIR, "monogram-v1")

SIZE = 512
INSET = 8
RADIUS = 100
BORDER = 8
BORDER_ALPHA = 150
BOX_W, BOX_H = 448, 316          # artwork fitting box inside the tile
ALPHA_LO, ALPHA_HI = 50, 150     # alpha levels: kills glow/haze, keeps AA edges
# Logos whose art is dominated by a bloom/glow need a harder cut to stay crisp
# (verified visually: Hades II's neon halo would otherwise read as a blob).
ALPHA_OVERRIDE = {1145350: (170, 235)}

# gruvbox palette
BG_HARD, BG0 = "#1d2021", "#282828"
RED, GREEN, YELLOW, BLUE, PURPLE, AQUA, ORANGE = (
    "#fb4934", "#b8bb26", "#fabd2f", "#83a598", "#d3869b", "#8ec07c", "#fe8019")
FG, FG1, FG4 = "#ebdbb2", "#d5c4a1", "#a89984"

# (desktop basename, slug, steam appid, accent)
GAMES = [
    ("Beyond Citadel",                                            "beyond-citadel",   3371240, GREEN),
    ("Dead Space",                                                "dead-space",       1693980, AQUA),
    ("DOOM 64",                                                   "doom-64",          1148590, ORANGE),
    ("DOOM The Dark Ages",                                        "doom-the-dark-ages", 3017860, RED),
    ("Hades II",                                                  "hades-ii",         1145350, PURPLE),
    ("HELLDIVERS 2",                                              "helldivers-2",     553850,  YELLOW),
    ("METAL GEAR RISING REVENGEANCE",                             "metal-gear-rising-revengeance", 235460, RED),
    ("METAL GEAR SOLID 4 Guns of the Patriots - Master Collection Version",
        "metal-gear-solid-4-guns-of-the-patriots-master-collection-version", 2492670, BLUE),
    ("METAL GEAR SOLID MASTER COLLECTION Vol.2",                   "metal-gear-solid-master-collection-vol-2", 3859630, AQUA),
    ("METAL GEAR SOLID Peace Walker - Master Collection Version",  "metal-gear-solid-peace-walker-master-collection-version", 2492660, GREEN),
    ("Quake",                                                     "quake",            2310,    YELLOW),
    ("Resident Evil Requiem",                                     "resident-evil-requiem", 3764200, GREEN),
    ("Selaco",                                                    "selaco",           1592280, BLUE),
    ("The Blood of Dawnwalker",                                   "the-blood-of-dawnwalker", 3751260, FG1),
    ("Trepang2",                                                  "trepang2",         1164940, FG4),
    ("ULTRAKILL",                                                 "ultrakill",        1229490, FG),
]


def hex2rgb(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def find_logo(appid: int) -> str:
    pats = [f"{STEAM_CACHE}/{appid}/**/logo.png", f"{STEAM_CACHE}/{appid}/logo.png"]
    for pat in pats:
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    raise FileNotFoundError(f"no cached logo.png for appid {appid}")


def logo_mask(appid: int) -> Image.Image:
    """Single-channel mask of the logo artwork, cropped to content."""
    logo = Image.open(find_logo(appid)).convert("RGBA")
    alpha = logo.getchannel("A")
    lo, hi = ALPHA_OVERRIDE.get(appid, (ALPHA_LO, ALPHA_HI))
    span = hi - lo
    alpha = alpha.point(lambda v: 0 if v <= lo else
                        (255 if v >= hi else int((v - lo) * 255 / span)))
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError(f"logo for {appid} is empty after alpha threshold")
    return alpha.crop(bbox)


def stack_split(mask: Image.Image):
    """Stack an ultra-wide two-word wordmark onto two lines.

    A 10:1 wordmark can't be large on a square tile, so 'BEYOND CITADEL' becomes
    two centred lines and roughly quadruples in displayed size. Conservative by
    design: only fires when the widest internal gap splits the art into two
    comparable halves that are each plausibly a word (rejects single words like
    QUAKE, which would otherwise be chopped into 'QUAK' + 'E').
    """
    if mask.width / mask.height < 6:
        return None
    cols = (np.asarray(mask) > 127).any(axis=0)
    gaps, start = [], None
    for i, solid in enumerate(cols):
        if not solid and start is None:
            start = i
        elif solid and start is not None:
            gaps.append((start, i - 1))
            start = None
    if start is not None:
        gaps.append((start, len(cols) - 1))
    inner = [(x, y) for x, y in gaps if x > 0 and y < len(cols) - 1 and y - x >= 2]
    if not inner:
        return None
    x0, x1 = max(inner, key=lambda g: g[1] - g[0])
    parts = [mask.crop((0, 0, x0, mask.height)),
             mask.crop((x1 + 1, 0, mask.width, mask.height))]
    for i, p in enumerate(parts):
        box = p.getbbox()
        if not box:
            return None
        parts[i] = p.crop(box)
    left, right = parts
    if abs(left.width - right.width) / max(left.width, right.width) > 0.35:
        return None
    if max(left.width / left.height, right.width / right.height) > 7:
        return None
    gap = max(6, round(0.38 * max(left.height, right.height)))
    width = max(left.width, right.width)
    out = Image.new("L", (width, left.height + gap + right.height), 0)
    out.paste(left, ((width - left.width) // 2, 0))
    out.paste(right, ((width - right.width) // 2, left.height + gap))
    return out


def thicken(mask: Image.Image) -> Image.Image:
    """Fat bold strokes on wordmarks that are very wide and thin.

    A 10:1 wordmark fitted to a square tile ends up with hairline strokes that
    vanish at desktop icon sizes; dilating the mask restores legibility.
    """
    ratio = mask.width / max(mask.height, 1)
    radius = 3 if ratio >= 8 else 2 if ratio >= 4 else 1 if ratio >= 2.5 else 0
    if not radius:
        return mask
    return mask.filter(ImageFilter.MaxFilter(2 * radius + 1))


def fit(mask: Image.Image) -> Image.Image:
    scale = min(BOX_W / mask.width, BOX_H / mask.height)
    return mask.resize((max(1, round(mask.width * scale)),
                        max(1, round(mask.height * scale))), Image.LANCZOS)


def tile(accent: str) -> Image.Image:
    """Dark gruvbox tile with a vertical gradient and a thin accent ring."""
    base = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    top, bottom = hex2rgb(BG_HARD), hex2rgb(BG0)
    grad = Image.new("RGBA", (SIZE, SIZE))
    for y in range(SIZE):
        t = y / (SIZE - 1)
        grad.paste(tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,),
                   (0, y, SIZE, y + 1))

    shape = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(shape).rounded_rectangle(
        (INSET, INSET, SIZE - INSET, SIZE - INSET), radius=RADIUS, fill=255)
    base.paste(grad, (0, 0), shape)

    ring = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle(
        (INSET + BORDER // 2, INSET + BORDER // 2,
         SIZE - INSET - BORDER // 2, SIZE - INSET - BORDER // 2),
        radius=RADIUS - BORDER // 2, outline=hex2rgb(accent) + (BORDER_ALPHA,), width=BORDER)
    base.alpha_composite(Image.composite(ring, Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)), shape))
    return base


def build(appid: int, accent: str) -> Image.Image:
    mask = logo_mask(appid)
    glyph = fit(thicken(stack_split(mask) or mask))
    art = Image.new("RGBA", glyph.size, hex2rgb(accent) + (255,))
    art.putalpha(glyph)
    canvas = tile(accent)
    canvas.alpha_composite(art, ((SIZE - glyph.width) // 2, (SIZE - glyph.height) // 2))
    return canvas


def main() -> int:
    # keep the previous monogram set around for comparison / rollback
    os.makedirs(ARCHIVE, exist_ok=True)
    for f in glob.glob(os.path.join(ICON_DIR, "*.png")) + glob.glob(os.path.join(ICON_DIR, "*.svg")):
        dest = os.path.join(ARCHIVE, os.path.basename(f))
        if not os.path.exists(dest):
            shutil.move(f, dest)
    old_svg = os.path.join(ICON_DIR, "svg")
    if os.path.isdir(old_svg):
        shutil.move(old_svg, os.path.join(ARCHIVE, "svg"))
    print(f"archived previous set -> {ARCHIVE}")

    done = 0
    for name, slug, appid, accent in GAMES:
        try:
            img = build(appid, accent)
        except Exception as exc:                      # noqa: BLE001 - report and continue
            print(f"  FAIL {name}: {exc}")
            continue
        out = os.path.join(ICON_DIR, f"{slug}.png")
        img.save(out)
        print(f"  ok  {name:<26} {accent}  {appid} -> {os.path.basename(out)}")
        done += 1
    print(f"\n{done}/{len(GAMES)} silhouette icons in {ICON_DIR}")
    return 0 if done == len(GAMES) else 1


if __name__ == "__main__":
    sys.exit(main())
