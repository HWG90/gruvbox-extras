#!/usr/bin/env python3
"""Flat Gruvbox-Plus-style SVG icons: dark gradient tile + flat single-colour glyph.

Geometry is copied from the reference theme icon the user pointed at
(~/.local/share/icons/Gruvbox-Plus-Dark/apps/scalable/quake.svg) rather than
approximated:

  * tile path spans x 5.43..250.078, y 11.577..239.915 with corner radius ~84.5,
    i.e. INSET from the canvas so transparency shows as a margin all round
    (a flush tile reads as square-cornered once rasterised to desktop size)
  * tile fill is a vertical #504945 -> #3c3836 gradient
  * a second pass with the same path, group opacity .4, carries the bevel:
    #ebdbb2 fading to 9.8% by 12.5%, then #282828 rising to 49.8% at the bottom
  * glyph is flat, single colour, clipped to the tile

The glyph is each game's own Steam logo (transparent PNG in the librarycache),
reduced to an alpha mask and vectorised with vtracer. HELLDIVERS 2 reuses the
user's own hd2.svg artwork.

Output: ~/.local/share/icons/gruvbox-flat/<slug>.svg  (256x256)
"""
import glob
import os
from collections import deque
import re
import subprocess
import sys
import tempfile

import numpy as np
import vtracer
from PIL import Image, ImageFilter

OUT = os.path.expanduser("~/.local/share/icons/gruvbox-flat")
CACHE = os.path.expanduser("~/.local/share/Steam/appcache/librarycache")
HD2 = os.path.expanduser("~/.local/share/icons/gruvbox-recolor/hd2.svg")
HICOLOR = os.path.expanduser("~/.local/share/icons/hicolor")
ICON_SIZES = [256, 128, 96, 64, 48, 32, 24, 16]
# Icon art carrying grunge/noise texture needs a morphological close or the glyph
# reads as speckle rather than a flat shape (a 5-radius close at 1024 scale).
CLOSE_ICON = {}          # SM2 now comes from SOURCE_ICON, which cleans itself
# Thin-line icon art blurs at 96px; dilating bolds the strokes so the emblem reads.
DILATE_ICON = {}
# Emblems that are a bright ring around a darker core: glyph = the ring's FILLED
# interior, i.e. the shield silhouette. Tracing the ring alone yields a generic
# gear (all the core detail is darker than the ring). appid -> ring threshold.
SHIELD = {3017860: 135}
# optionally knock the crest's dark ornament back out of the filled disc
SHIELD_DETAIL = {3017860: 100}
SIZE = 256
BOX = 0.74              # glyph guard box, as a fraction of the canvas
SUPERSAMPLE = 4
ALPHA_LO, ALPHA_HI = 50, 150

# A harder cut strips the semi-transparent/textured edge pixels that a logo's
# alpha carries. Too low and the glyph comes out ragged and torn; too high and
# thin or glowing artwork is erased. 170..235 is the sweet spot for textured,
# neon or FX-heavy logos.
ALPHA_OVERRIDE = {
    1148590: (170, 235),     # DOOM 64 - textured gold fill -> ragged edges at 50..150
    1145350: (170, 235),     # Hades II - neon halo bridges the letterforms
    235460: (170, 235),      # MGR - electric FX bridges the letterforms
}
CLOSE = {1148590: 0, 1145350: 0, 235460: 0}

# the reference tile, verbatim from Gruvbox-Plus-Dark/apps/scalable/quake.svg
TILE_PATH = ("M 165.439 11.577 C 239.495 11.577 250.078 22.134 250.078 96.12 "
             "L 250.078 155.371 C 250.078 229.358 239.495 239.915 165.439 239.915 "
             "L 90.069 239.915 C 16.014 239.915 5.43 229.358 5.43 155.371 "
             "L 5.43 96.12 C 5.43 22.134 16.014 11.577 90.069 11.577 L 165.439 11.577 Z")

# The reference's bevel is a thin rim RING (fill-rule evenodd), not a wash over
# the whole tile - filling the tile with it is what made the top sheen too strong.
RIM_PATH = ("M 165.068 11.951 C 169.396 11.941 173.724 11.991 178.052 12.089 C 181.927 12.167 185.803 12.315 189.678 12.541 C 193.131 12.737 196.583 13.022 200.026 13.395 C 203.085 13.73 206.144 14.181 209.174 14.741 C 211.889 15.243 214.574 15.881 217.22 16.657 C 219.62 17.355 221.971 18.219 224.243 19.241 C 226.358 20.184 228.384 21.304 230.302 22.591 C 232.142 23.829 233.863 25.244 235.437 26.806 C 237.001 28.378 238.417 30.088 239.656 31.925 C 240.945 33.841 242.066 35.865 243.02 37.967 C 244.043 40.247 244.909 42.585 245.617 44.972 C 246.394 47.615 247.034 50.297 247.535 53.009 C 248.096 56.035 248.548 59.081 248.883 62.136 C 249.257 65.575 249.542 69.014 249.739 72.462 C 249.965 76.323 250.112 80.194 250.201 84.055 C 250.289 88.378 250.339 92.701 250.329 97.014 L 250.329 155.226 C 250.339 159.549 250.289 163.862 250.201 168.185 C 250.112 172.056 249.965 175.917 249.739 179.778 C 249.542 183.226 249.257 186.675 248.883 190.104 C 248.548 193.159 248.096 196.215 247.535 199.241 C 247.034 201.943 246.394 204.625 245.617 207.268 C 244.909 209.655 244.043 212.003 243.02 214.273 C 242.066 216.385 240.945 218.399 239.656 220.315 C 238.417 222.152 237.001 223.872 235.437 225.434 C 233.863 226.996 232.142 228.411 230.302 229.649 C 228.384 230.936 226.358 232.056 224.243 232.999 C 221.971 234.021 219.62 234.885 217.22 235.593 C 214.574 236.369 211.889 237.007 209.174 237.499 C 206.144 238.068 203.085 238.51 200.026 238.845 C 196.583 239.218 193.131 239.503 189.678 239.699 C 185.803 239.925 181.927 240.073 178.052 240.161 C 173.724 240.249 169.396 240.299 165.068 240.289 L 90.942 240.289 C 86.614 240.299 82.286 240.249 77.958 240.161 C 74.083 240.073 70.207 239.925 66.332 239.699 C 62.879 239.503 59.427 239.218 55.984 238.845 C 52.925 238.51 49.866 238.068 46.836 237.499 C 44.121 237.007 41.436 236.369 38.79 235.593 C 36.39 234.885 34.039 234.021 31.767 232.999 C 29.652 232.056 27.626 230.936 25.708 229.649 C 23.868 228.411 22.147 226.996 20.573 225.434 C 19.009 223.872 17.593 222.152 16.354 220.315 C 15.065 218.399 13.944 216.385 12.99 214.273 C 11.967 212.003 11.101 209.655 10.393 207.268 C 9.616 204.625 8.976 201.943 8.475 199.241 C 7.914 196.215 7.462 193.159 7.127 190.104 C 6.753 186.675 6.468 183.226 6.271 179.778 C 6.045 175.917 5.898 172.056 5.809 168.185 C 5.721 163.862 5.671 159.549 5.681 155.226 L 5.681 97.014 C 5.671 92.701 5.721 88.378 5.809 84.055 C 5.898 80.194 6.045 76.323 6.271 72.462 C 6.468 69.014 6.753 65.575 7.127 62.136 C 7.462 59.081 7.914 56.035 8.475 53.009 C 8.976 50.297 9.616 47.615 10.393 44.972 C 11.101 42.585 11.967 40.247 12.99 37.967 C 13.944 35.865 15.065 33.841 16.354 31.925 C 17.593 30.088 19.009 28.378 20.573 26.806 C 22.147 25.244 23.868 23.829 25.708 22.591 C 27.626 21.304 29.652 20.184 31.767 19.241 C 34.039 18.219 36.39 17.355 38.79 16.657 C 41.436 15.881 44.121 15.243 46.836 14.741 C 49.866 14.181 52.925 13.73 55.984 13.395 C 59.427 13.022 62.879 12.737 66.332 12.541 C 70.207 12.315 74.083 12.167 77.958 12.089 C 82.286 11.991 86.614 11.941 90.942 11.951 L 165.068 11.951 Z M 165.078 15.96 C 169.376 15.95 173.675 15.999 177.973 16.087 C 181.8 16.176 185.626 16.323 189.452 16.539 C 192.836 16.736 196.219 17.011 199.583 17.384 C 202.554 17.699 205.515 18.131 208.446 18.681 C 211.023 19.153 213.58 19.762 216.099 20.499 C 218.322 21.147 220.495 21.953 222.6 22.896 C 224.509 23.751 226.338 24.763 228.069 25.922 C 229.692 27.013 231.207 28.26 232.594 29.646 C 233.981 31.031 235.23 32.544 236.332 34.165 C 237.492 35.894 238.506 37.712 239.361 39.608 C 240.306 41.72 241.112 43.892 241.761 46.102 C 242.509 48.617 243.109 51.162 243.591 53.736 C 244.132 56.664 244.565 59.611 244.889 62.578 C 245.263 65.938 245.539 69.308 245.735 72.688 C 245.952 76.51 246.109 80.322 246.188 84.144 C 246.276 88.437 246.325 92.721 246.325 97.014 C 246.325 97.014 246.325 97.014 246.325 97.014 L 246.325 155.226 C 246.325 155.226 246.325 155.226 246.325 155.226 C 246.325 159.519 246.276 163.803 246.188 168.096 C 246.109 171.918 245.952 175.74 245.735 179.552 C 245.539 182.932 245.263 186.302 244.889 189.672 C 244.565 192.629 244.132 195.576 243.591 198.504 C 243.109 201.078 242.509 203.623 241.761 206.138 C 241.112 208.358 240.306 210.52 239.361 212.632 C 238.506 214.528 237.492 216.356 236.332 218.075 C 235.23 219.706 233.981 221.219 232.594 222.604 C 231.207 223.98 229.692 225.227 228.069 226.318 C 226.338 227.477 224.509 228.489 222.6 229.344 C 220.495 230.297 218.322 231.093 216.099 231.741 C 213.58 232.478 211.023 233.087 208.446 233.559 C 205.515 234.109 202.554 234.541 199.583 234.865 C 196.219 235.229 192.836 235.514 189.452 235.701 C 185.626 235.917 181.8 236.074 177.973 236.153 C 173.675 236.251 169.376 236.29 165.078 236.29 C 165.078 236.29 165.078 236.29 165.068 236.29 L 90.942 236.29 C 90.932 236.29 90.932 236.29 90.932 236.29 C 86.634 236.29 82.335 236.251 78.037 236.153 C 74.21 236.074 70.384 235.917 66.558 235.701 C 63.174 235.514 59.791 235.229 56.427 234.865 C 53.456 234.541 50.495 234.109 47.564 233.559 C 44.987 233.087 42.43 232.478 39.911 231.741 C 37.688 231.093 35.515 230.297 33.41 229.344 C 31.501 228.489 29.672 227.477 27.941 226.318 C 26.318 225.227 24.803 223.98 23.416 222.604 C 22.029 221.219 20.78 219.706 19.678 218.075 C 18.518 216.356 17.504 214.528 16.649 212.632 C 15.704 210.52 14.898 208.358 14.249 206.138 C 13.501 203.623 12.901 201.078 12.419 198.504 C 11.878 195.576 11.445 192.629 11.121 189.672 C 10.747 186.302 10.472 182.932 10.275 179.552 C 10.058 175.74 9.901 171.918 9.822 168.096 C 9.734 163.803 9.685 159.519 9.685 155.226 C 9.685 155.226 9.685 155.226 9.685 155.226 L 9.685 97.014 C 9.685 97.014 9.685 97.014 9.685 97.014 C 9.685 92.721 9.734 88.437 9.822 84.144 C 9.901 80.322 10.058 76.51 10.275 72.688 C 10.472 69.308 10.747 65.938 11.121 62.578 C 11.445 59.611 11.878 56.664 12.419 53.736 C 12.901 51.162 13.501 48.617 14.249 46.102 C 14.898 43.892 15.704 41.72 16.649 39.608 C 17.504 37.712 18.518 35.894 19.678 34.165 C 20.78 32.544 22.029 31.031 23.416 29.646 C 24.803 28.26 26.318 27.013 27.941 25.922 C 29.672 24.763 31.501 23.751 33.41 22.896 C 35.515 21.953 37.688 21.147 39.911 20.499 C 42.43 19.762 44.987 19.153 47.564 18.681 C 50.495 18.131 53.456 17.699 56.427 17.384 C 59.791 17.011 63.174 16.736 66.558 16.539 C 70.384 16.323 74.21 16.176 78.037 16.087 C 82.335 15.999 86.634 15.95 90.932 15.96 C 90.932 15.96 90.932 15.96 90.942 15.96 L 165.068 15.96 C 165.078 15.96 165.078 15.96 165.078 15.96 Z")

GAMES = [
    ("beyond-citadel", 3371240, "#b8bb26", "logo"),
    ("dead-space",     1693980, "#8ec07c", "logo"),
    ("doom-64",        1148590, "#fe8019", "icon"),
    ("hades-ii",       1145350, "#d3869b", "icon"),
    ("helldivers-2",   553850,  "#fabd2f", "hd2"),
    ("metal-gear-rising-revengeance", 235460, "#fb4934", "logo"),
    ("metal-gear-solid-4-guns-of-the-patriots-master-collection-version", 2492670, "#83a598", "logo"),
    ("metal-gear-solid-master-collection-vol-2", 3859630, "#fabd2f", "logo"),
    ("metal-gear-solid-peace-walker-master-collection-version", 2492660, "#d5c4a1", "logo"),
    ("resident-evil-requiem", 3764200, "#b8bb26", "logo"),
    ("trepang2",       1164940, "#a89984", "icon"),
    ("ultrakill",      1229490, "#ebdbb2", "logo"),
    ("the-blood-of-dawnwalker", 3751260, "#d3869b", "icon"),
    ("selaco",         1592280, "#83a598", "logo"),
    ("warhammer-40-000-space-marine-2", 2183900, "#fabd2f", "icon"),
]


def logo_alpha(appid: int) -> Image.Image:
    hits = (glob.glob(f"{CACHE}/{appid}/**/logo.png", recursive=True)
            + glob.glob(f"{CACHE}/{appid}/logo.png"))
    if not hits:
        raise FileNotFoundError(f"no cached logo.png for {appid}")
    return Image.open(hits[0]).convert("RGBA").getchannel("A")


def otsu_v(v: np.ndarray) -> int:
    """Otsu threshold over the value channel - separates a lit subject from black."""
    hist = np.bincount(v.astype(np.uint8).ravel(), minlength=256).astype(float)
    tot = hist.sum()
    s_all = float((np.arange(256) * hist).sum())
    wB = sB = 0.0
    best_t, best_val = 0, -1.0
    for t in range(256):
        wB += hist[t]
        if wB == 0:
            continue
        wF = tot - wB
        if wF == 0:
            break
        sB += t * hist[t]
        mB, mF = sB / wB, (s_all - sB) / wF
        var = wB * wF * (mB - mF) ** 2
        if var > best_val:
            best_val, best_t = var, t
    return best_t


# NOTE: icon art only works when the emblem is a single bright subject on a dark
# field. DOOM: The Dark Ages' crest is a bright olive ring around a much darker
# inner disc + crest, so Otsu keeps just the ring - a generic cog with no DOOM
# identity. Its wordmark reads far better, so it uses "logo".


def trim_solid_border(binary: np.ndarray, max_px: int = 20, thresh: float = 0.95) -> np.ndarray:
    """Remove the icon's OWN border frame.

    Many Steam icons carry a frame/edge band right at the canvas edge - the outer
    few pixels read as fully "subject" in both colour directions. It is invisible
    at icon size, but scaled up to fill a tile it becomes a thick square outline
    that is not part of the game's mark. The emblem is always inset, so trimming
    the solid outer rows/columns removes the frame and nothing else.
    """
    a = binary
    top = 0
    while top < max_px and a.shape[0] > top + 8 and a[top].mean() >= thresh:
        top += 1
    bottom = 0
    while bottom < max_px and a.shape[0] - bottom - 1 > top + 4 and a[a.shape[0] - bottom - 1].mean() >= thresh:
        bottom += 1
    left = 0
    while left < max_px and a.shape[1] > left + 8 and a[:, left].mean() >= thresh:
        left += 1
    right = 0
    while right < max_px and a.shape[1] - right - 1 > left + 4 and a[:, a.shape[1] - right - 1].mean() >= thresh:
        right += 1
    if not (top or bottom or left or right):
        return binary
    return a[top:a.shape[0] - bottom, left:a.shape[1] - right]


def drop_small_border_blobs(binary: np.ndarray, keep_frac: float = 0.20) -> np.ndarray:
    """After the margin trim, drop components that touch the edge AND are small.

    When an icon is a dark mark inset in a light margin, trimming the margin can
    leave its four corners behind as little tabs on a diagonal. They are not part
    of the artwork (the original has no frame at all), so remove them - but only
    if they are small, which protects full-bleed artwork.
    """
    h, w = binary.shape
    total = binary.sum()
    if not total:
        return binary
    seen = np.zeros_like(binary)
    keep = np.zeros_like(binary)
    for sy in range(h):
        for sx in range(w):
            if not binary[sy, sx] or seen[sy, sx]:
                continue
            q = deque([(sy, sx)])
            seen[sy, sx] = True
            comp, touches = [], False
            while q:
                y, x = q.popleft()
                comp.append((y, x))
                if y in (0, h - 1) or x in (0, w - 1):
                    touches = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if not (touches and len(comp) < keep_frac * total):
                for y, x in comp:
                    keep[y, x] = True
    return keep


def fill_holes(binary: np.ndarray) -> np.ndarray:
    """Fill enclosed regions: outside = non-subject reachable from the border."""
    h, w = binary.shape
    comp = ~binary
    seen = np.zeros_like(comp)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if comp[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if comp[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    steps = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    while q:
        y, x = q.popleft()
        for dy, dx in steps:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and comp[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return ~seen


def shield_mask(appid: int) -> Image.Image:
    """Filled silhouette of a bright-ring emblem (steam_icon art)."""
    path = None
    for s in ICON_SIZES:
        p = f"{HICOLOR}/{s}x{s}/apps/steam_icon_{appid}.png"
        if os.path.isfile(p):
            path = p
            break
    if not path:
        raise FileNotFoundError(f"no installed icon for {appid}")
    v = np.asarray(Image.open(path).convert("RGB")).astype(np.float32).max(axis=2)
    thr = SHIELD.get(appid, 135)
    ring = v > thr
    if ring.mean() > 0.5:
        ring = ~ring
    m = Image.fromarray((ring * 255).astype(np.uint8), "L")
    m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))   # bridge ring gaps
    filled = fill_holes(np.asarray(m) > 127)
    # punch out the crest's bold dark ornament (open first, so only large shapes
    # survive and the fine engraving does not turn to speckle at 96px)
    dark_thr = SHIELD_DETAIL.get(appid)
    if dark_thr is not None:
        dk = Image.fromarray(((v < dark_thr) * 255).astype(np.uint8), "L")
        dk = dk.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))
        filled = filled & ~(np.asarray(dk) > 127)
    out = Image.fromarray((filled * 255).astype(np.uint8), "L")
    print(f"       (shield: ring V>{thr}, filled to {filled.mean() * 100:.0f}% of frame)")
    return out.crop(out.getbbox())


def morph_bin(mask: np.ndarray, close: int = 0, open_: int = 0) -> np.ndarray:
    """Binary morphological close then open."""
    im = Image.fromarray((mask * 255).astype(np.uint8), "L")
    if close:
        im = im.filter(ImageFilter.MaxFilter(2 * close + 1)).filter(ImageFilter.MinFilter(2 * close + 1))
    if open_:
        im = im.filter(ImageFilter.MinFilter(2 * open_ + 1)).filter(ImageFilter.MaxFilter(2 * open_ + 1))
    return np.asarray(im) > 127


def drop_speckles(mask: np.ndarray, min_frac: float = 0.02) -> np.ndarray:
    """Drop connected components smaller than min_frac of the total subject area."""
    h, w = mask.shape
    total = mask.sum()
    if not total:
        return mask
    seen = np.zeros_like(mask)
    keep = np.zeros_like(mask)
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            q = deque([(sy, sx)])
            seen[sy, sx] = True
            comp = []
            while q:
                y, x = q.popleft()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(comp) >= min_frac * total:
                for y, x in comp:
                    keep[y, x] = True
    return keep


# Some games' marks are not in the installed icon art at all, or that art is a
# grungy wordmark that reads badly flattened. Point the glyph at an explicit
# source image instead: appid -> (path relative to this file, value threshold).
# Icons whose installed art is a dark mark with only thin bright details: a colour
# threshold keeps just the detail fragments, which turn to mud at 96px. These icons
# carry the mark's real shape in ALPHA, so take the silhouette from there instead.
ALPHA_ART = {1148590: 0.005}     # DOOM 64: alpha silhouette, eye sockets cut out
                                 # (value = min blob size kept as a hole)

# Edge smoothing, per app. A traced edge is only as smooth as the mask it came from.
#   ("src", r)  = blur at SOURCE resolution, before the upscale: removes the
#                 pixel-grid stair-steps of a low-res source (DOOM 64 is 128px and
#                 gets upscaled 8x, so its edge was visibly blocky).
#   ("fine", r) = blur at 4096 then re-threshold: rounds the residual wobble of a
#                 worn outline WITHOUT moving the edge, so corners stay put.
# Spline simplification, per app. vtracer's length_threshold controls the minimum
# curve segment: the default 3.5 makes the path follow every pixel-level wobble of
# the mask, which reads as jaggedness on a curve. A higher value fits fewer, longer
# segments, so the edge rasterises as a clean curve. Only raise it for glyphs whose
# detail survives it - small features are what gets lost.
TRACE_LT = {
    2183900: 20,     # Space Marine 2 (bold geometric U - nothing small to lose)
    1148590: 16,     # DOOM 64 (eye sockets are ~80px at 256, safely above this)
}
TRACE_LT_DEFAULT = 3.5

SMOOTH = {
    # DOOM 64 is deliberately NOT smoothed at the source: this mark is detailed
    # artwork (a horned face inside a pentagram), and any source-scale blur strong
    # enough to calm its edge destroys the horns, eyes and mouth. Its residual edge
    # wobble is accepted in exchange for keeping the mark readable.

    2183900: ("fine", 12),     # Space Marine 2
}


def fine_smooth(mask_img: Image.Image, radius: int, hi: int = 4096) -> Image.Image:
    """Smooth an edge at higher resolution than the wobble, then re-threshold."""
    big = mask_img.resize((hi, hi), Image.LANCZOS).filter(ImageFilter.GaussianBlur(radius))
    small = big.resize(mask_img.size, Image.LANCZOS)
    out = Image.fromarray((np.asarray(small) > 127).astype(np.uint8) * 255, "L")
    return out.crop(out.getbbox())


SOURCE_ICON = {
    2183900: ("sources/ultramarines-badge.png", 180),
}


def icon_art_mask(appid: int) -> Image.Image:
    """Flat subject mask taken from the installed ICON art (not the wordmark logo).

    These icons are opaque artwork on a dark background, so there is no alpha to
    use: threshold on HSV value (max channel), which keeps saturated art that
    luminance would drop (a pure-red demon face has luminance only 76/255).

    An entry in SOURCE_ICON short-circuits all of that with an explicit artwork
    file, for marks that are not in the installed icon art (or whose icon art is
    a grungy wordmark that reads badly when flattened).
    """
    ov = SOURCE_ICON.get(appid)
    if ov:
        rel, thr = ov
        src = rel if os.path.isabs(rel) else os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)
        v = np.asarray(Image.open(src).convert("RGB")).astype(np.float32).max(axis=2)
        subj = v > thr                            # the light mark; the plate is far darker
        subj = morph_bin(subj, close=2)           # bridge the art's grunge pinholes
        subj = fill_holes(subj)
        subj = drop_speckles(subj)
        subj = morph_bin(subj, close=2, open_=2)  # even out the worn outline
        m = Image.fromarray((subj * 255).astype(np.uint8), "L")
        m = m.resize((1024, 1024), Image.LANCZOS)
        # The badge's outline is battle-worn, so the traced edge carries nicks and
        # nubs that read as grain at 256px. Smoothing at 1024 is too coarse to fix
        # it without moving the edge (a big blur there rounds the U's squared ends);
        # smoothing at 4096 lets the boundary settle sub-pixel, so the edge comes out
        # clean and the geometry stays exactly where it was.
        sm = SMOOTH.get(appid)
        if sm and sm[0] == "fine":
            m = fine_smooth(m, sm[1])
        print(f"       (source override: {os.path.basename(src)}, subject {subj.mean() * 100:.0f}% of frame)")
        return m.crop(m.getbbox())
    path = None
    for s in ICON_SIZES:
        p = f"{HICOLOR}/{s}x{s}/apps/steam_icon_{appid}.png"
        if os.path.isfile(p):
            path = p
            break
    if not path:
        raise FileNotFoundError(f"no installed icon for {appid}")
    v = np.asarray(Image.open(path).convert("RGB")).astype(np.float32).max(axis=2)
    if appid in ALPHA_ART:
        hole_frac = ALPHA_ART[appid]
        rgba = Image.open(path).convert("RGBA")
        arr = np.asarray(rgba)
        al = arr[:, :, 3]
        if (al < 128).mean() > 0.03:                 # the art really does carry a silhouette
            subj = morph_bin(al > 128, close=1)
            holes = 0
            if hole_frac:
                # Knock the LARGEST bright features back out as negative space (DOOM 64's
                # eye sockets). Small holes do not survive 96px and just read as speckle,
                # so only blobs above hole_frac of the mark survive as holes.
                av = arr[:, :, :3].astype(np.float32).max(axis=2)
                bright = av > otsu_v(av)
                if bright.mean() > 0.5:
                    bright = ~bright
                big = drop_speckles(subj & bright, hole_frac)
                subj = subj & ~big
                holes = big.sum()
            m = Image.fromarray((subj * 255).astype(np.uint8), "L")
            sm = SMOOTH.get(appid)
            if sm and sm[0] == "src":
                m = m.filter(ImageFilter.GaussianBlur(sm[1]))
            m = m.resize((1024, 1024), Image.LANCZOS)   # smooth off the source pixel grid
            m = Image.fromarray((np.asarray(m) >= 128).astype(np.uint8) * 255, "L")
            if sm and sm[0] == "fine":
                m = fine_smooth(m, sm[1])
            print(f"       (alpha art: {os.path.basename(path)}, subject {subj.mean() * 100:.0f}% "
                  f"of frame, {holes} px of detail as holes)")
            return m.crop(m.getbbox())
    # Otsu, not the midpoint: these icons are mostly black, so a midpoint cut
    # (0..194 here) keeps only the highlights and the glyph comes out fragmentary.
    thr = otsu_v(v)
    subj = v > thr
    if subj.mean() > 0.5:                 # subject is the minority side
        subj = ~subj
    subj = trim_solid_border(subj)           # remove the icon's own border frame
    subj = drop_small_border_blobs(subj)     # and any leftover frame corners
    m = Image.fromarray((subj * 255).astype(np.uint8), "L")
    # dilate at SOURCE scale - doing it after the upscale makes the radius 4x weaker
    dv = DILATE_ICON.get(appid, 0)
    if dv:
        m = m.filter(ImageFilter.MaxFilter(2 * dv + 1))
    m = m.resize((1024, 1024), Image.LANCZOS)      # smooth off the source pixel grid
    m = Image.fromarray((np.asarray(m) >= 128).astype(np.uint8) * 255, "L")
    r = CLOSE_ICON.get(appid, 0)
    if r:
        m = m.filter(ImageFilter.MaxFilter(2 * r + 1)).filter(ImageFilter.MinFilter(2 * r + 1))
    box = m.getbbox()
    if not box:
        raise ValueError(f"empty icon-art mask for {appid}")
    print(f"       (icon art: {os.path.basename(path)}, subject {subj.mean() * 100:.0f}% of frame)")
    return m.crop(box)


def svg_alpha(path: str) -> Image.Image:
    png = tempfile.mktemp(suffix=".png")
    subprocess.run(["rsvg-convert", "-w", "1024", "-b", "none", "-o", png, path], check=True)
    im = Image.open(png).convert("RGBA")
    box = im.getchannel("A").getbbox()
    return im.crop(box).getchannel("A") if box else im.getchannel("A")


def cut_mask(appid: int, alpha: Image.Image) -> Image.Image:
    lo, hi = ALPHA_OVERRIDE.get(appid, (ALPHA_LO, ALPHA_HI))
    span = hi - lo
    m = alpha.point(lambda v: 0 if v <= lo else (255 if v >= hi else int((v - lo) * 255 / span)))
    r = CLOSE.get(appid, 0)
    if r:
        m = m.filter(ImageFilter.MaxFilter(2 * r + 1)).filter(ImageFilter.MinFilter(2 * r + 1))
    box = m.getbbox()
    if not box:
        raise ValueError(f"empty mask for {appid} at cut {lo}..{hi}")
    return m.crop(box)


def stack_two(mask: Image.Image):
    """Stack an ultra-wide two-word wordmark onto two centred lines."""
    if mask.width / max(mask.height, 1) < 6:
        return None
    cols = (np.asarray(mask) > 127).any(axis=0)
    gaps, s = [], None
    for i, solid in enumerate(cols):
        if not solid and s is None:
            s = i
        elif solid and s is not None:
            gaps.append((s, i - 1)); s = None
    inner = [(x, y) for x, y in gaps if x > 0 and y < len(cols) - 1 and y - x >= 2]
    if not inner:
        return None
    x0, x1 = max(inner, key=lambda g: g[1] - g[0])
    parts = []
    for seg in (mask.crop((0, 0, x0, mask.height)), mask.crop((x1 + 1, 0, mask.width, mask.height))):
        b = seg.getbbox()
        if not b:
            return None
        parts.append(seg.crop(b))
    left, right = parts
    if abs(left.width - right.width) / max(left.width, right.width) > 0.35:
        return None
    if max(left.width / left.height, right.width / right.height) > 7:
        return None
    gap = max(6, round(0.38 * max(left.height, right.height)))
    w = max(left.width, right.width)
    out = Image.new("L", (w, left.height + gap + right.height), 0)
    out.paste(left, ((w - left.width) // 2, 0))
    out.paste(right, ((w - right.width) // 2, left.height + gap))
    return out


def glyph_paths(mask: Image.Image, accent: str, length_thr: float = None) -> str:
    box = SIZE * BOX
    sc = min(box / mask.width, box / mask.height)
    tw, th = max(2, round(mask.width * sc)), max(2, round(mask.height * sc))
    big = mask.resize((tw * SUPERSAMPLE, th * SUPERSAMPLE), Image.LANCZOS)
    bw = np.full((big.height, big.width), 255, np.uint8)
    bw[np.asarray(big) > 127] = 0
    src = tempfile.mktemp(suffix=".png")
    Image.fromarray(bw, "L").convert("RGB").save(src)
    svg = tempfile.mktemp(suffix=".svg")
    vtracer.convert_image_to_svg_py(
        src, svg, colormode="binary", hierarchical="cutout", mode="spline",
        filter_speckle=2, color_precision=8, layer_difference=6,
        corner_threshold=60,
        length_threshold=(TRACE_LT_DEFAULT if length_thr is None else length_thr),
        max_iterations=10,
        splice_threshold=45, path_precision=3)
    body = open(svg, encoding="utf-8").read()
    body = body[body.find(">", body.find("<svg")) + 1: body.rfind("</svg>")]
    body = re.sub(r'fill="[^"]*"', f'fill="{accent}"', body)
    tx, ty = (SIZE - tw) / 2.0, (SIZE - th) / 2.0
    return (f'  <g clip-path="url(#tileClip)">\n'
            f'    <g transform="translate({tx:.2f},{ty:.2f}) scale({1.0 / SUPERSAMPLE})">\n'
            f'{body}\n    </g>\n  </g>')


def wrap(mask: Image.Image, accent: str, length_thr: float = None) -> str:
    """Render a glyph mask into the reference-matched tile as a standalone SVG."""
    glyph = glyph_paths(mask, accent, length_thr)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#504945"/>
      <stop offset="1" stop-color="#3c3836"/>
    </linearGradient>
    <linearGradient id="bevel" x1=".517" y1="0" x2=".517" y2="1">
      <stop offset="0" stop-color="#ebdbb2"/>
      <stop offset="0.125" stop-color="#ebdbb2" stop-opacity="0.098"/>
      <stop offset="0.925" stop-color="#282828" stop-opacity="0.098"/>
      <stop offset="1" stop-color="#282828" stop-opacity="0.498"/>
    </linearGradient>
    <clipPath id="tileClip"><path d="{TILE_PATH}"/></clipPath>
  </defs>
  <path d="{TILE_PATH}" fill="url(#tile)"/>
  <g opacity="0.4"><path d="{RIM_PATH}" fill-rule="evenodd" fill="url(#bevel)"/></g>
{glyph}
</svg>
'''


def build(slug: str, appid: int, accent: str, kind: str) -> str:
    if kind == "hd2":
        mask = svg_alpha(HD2)
    elif kind == "shield":
        mask = shield_mask(appid)
    elif kind == "icon":
        mask = icon_art_mask(appid)
    else:
        mask = cut_mask(appid, logo_alpha(appid))
    st = stack_two(mask)
    if st is not None:
        mask = st
    return wrap(mask, accent, TRACE_LT.get(appid))


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for slug, appid, accent, kind in GAMES:
        try:
            svg = build(slug, appid, accent, kind)
        except Exception as exc:                    # noqa: BLE001
            print(f"  FAIL {slug}: {exc}")
            continue
        with open(os.path.join(OUT, f"{slug}.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg)
        lo, hi = ALPHA_OVERRIDE.get(appid, (ALPHA_LO, ALPHA_HI))
        print(f"  ok   {slug:<58} {accent}  cut {lo}..{hi}")
        ok += 1
    print(f"\n{ok}/{len(GAMES)} flat SVG icons in {OUT}")
    return 0 if ok == len(GAMES) else 1


if __name__ == "__main__":
    sys.exit(main())
