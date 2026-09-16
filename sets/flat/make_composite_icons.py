#!/usr/bin/env python3
"""Composite icons: marks whose artwork cannot survive flattening to one tone.

Two games need this. Both are composites of the game's OWN artwork, re-toned to
gruvbox, keyed out with its alpha, and centred on the standard generated tile -
the tile geometry is imported from generate_flat_icons.py so it matches the flat
set exactly.

  DOOM: The Dark Ages - the crest reduces to a solid disc or a gear ring at every
      threshold, so no flat silhouette is recognisable.
  DOOM 64 - the wordmark's letters are FUSED (the silhouette is 76% solid ink) and
      are distinguished by colour and texture; flattened to one tone they merge
      into an unreadable mass.

Run:  ../gruvbox-recolor/.venv312/bin/python make_composite_icons.py
"""
import glob
import importlib.util
import os
import subprocess

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
gf = importlib.util.module_from_spec(
    importlib.util.spec_from_file_location("gf", os.path.join(HERE, "generate_flat_icons.py")))
gf.__spec__.loader.exec_module(gf)
gi = importlib.util.module_from_spec(
    importlib.util.spec_from_file_location(
        "gi", os.path.join(HERE, "..", "gruvbox-recolor", "generate_icons_v3.py")))
gi.__spec__.loader.exec_module(gi)
if not os.path.isfile(gi.__file__):
    raise SystemExit("recolour generator not found")


def installed_icon(appid):
    for s in gf.ICON_SIZES:
        p = f"{gf.HICOLOR}/{s}x{s}/apps/steam_icon_{appid}.png"
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(appid)


def tile(size=512):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#504945"/><stop offset="1" stop-color="#3c3836"/>
    </linearGradient>
    <linearGradient id="bevel" x1=".517" y1="0" x2=".517" y2="1">
      <stop offset="0" stop-color="#ebdbb2"/>
      <stop offset="0.125" stop-color="#ebdbb2" stop-opacity="0.098"/>
      <stop offset="0.925" stop-color="#282828" stop-opacity="0.098"/>
      <stop offset="1" stop-color="#282828" stop-opacity="0.498"/>
    </linearGradient>
  </defs>
  <path d="{gf.TILE_PATH}" fill="url(#tile)"/>
  <g opacity="0.4"><path d="{gf.RIM_PATH}" fill-rule="evenodd" fill="url(#bevel)"/></g>
</svg>
'''
    open("/tmp/_comp_tile.svg", "w").write(svg)
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-b", "none",
                    "-o", "/tmp/_comp_tile.png", "/tmp/_comp_tile.svg"], check=True)
    return Image.open("/tmp/_comp_tile.png").convert("RGBA")


def composite(src_rgba, box, out, upscale=3, alpha_cut=128):
    arr = np.asarray(src_rgba)
    sil = arr[:, :, 3] >= alpha_cut
    bb = Image.fromarray((sil * 255).astype(np.uint8), "L").getbbox()
    crop = src_rgba.convert("RGB").crop(bb)
    mask = sil[bb[1]:bb[3], bb[0]:bb[2]]
    up = crop.resize((crop.width * upscale, crop.height * upscale), Image.LANCZOS)
    toned = gi.map_image(up).resize((mask.shape[1] * upscale, mask.shape[0] * upscale), Image.LANCZOS)
    art = toned.convert("RGBA")
    art.putalpha(Image.fromarray((mask * 255).astype(np.uint8), "L").resize(
        (mask.shape[1] * upscale, mask.shape[0] * upscale), Image.LANCZOS))
    canvas = tile(512)
    sc = (512 * box) / max(art.size)
    a2 = art.resize((round(art.width * sc), round(art.height * sc)), Image.LANCZOS)
    canvas.alpha_composite(a2, ((512 - a2.width) // 2, (512 - a2.height) // 2))
    canvas.save(out)
    print(f"  wrote {out}  (source {crop.size}, ink {100*mask.mean():.1f}%, box {box})")


# DOOM: The Dark Ages - crest artwork
composite(Image.open(installed_icon(3017860)).convert("RGBA"), 0.78,
          os.path.join(HERE, "doom-the-dark-ages-shield.png"))

# DOOM 64 - the official wordmark artwork
logo = Image.open(glob.glob(
    "/home/goose/.local/share/Steam/appcache/librarycache/1148590/logo.png")[0]).convert("RGBA")
composite(logo, 0.90, os.path.join(HERE, "doom-64-wordmark.png"))
