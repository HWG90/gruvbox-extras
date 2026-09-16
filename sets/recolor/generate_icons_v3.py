#!/usr/bin/env python3
"""Re-tone the ACTUAL desktop icons into gruvbox, keeping them recognisable.

Source = the real icon files installed under
~/.local/share/icons/hicolor/<size>/apps/steam_icon_<appid>.png (falling back to
the small square client icon in Steam's librarycache, which is how Selaco is
covered).

Method: a hue-aware gruvbox duotone.
  * Each pixel keeps its own hue, snapped to the nearest gruvbox colour family
    (red / orange / yellow / green / aqua / blue / purple).
  * Its brightness (HSV value) drives position along that family's gruvbox
    gradient, so shading and gradients survive.
  * Low-saturation pixels (black/white/grey line art) ride the neutral gruvbox
    brown-to-cream ramp instead.

A plain luminance ramp would destroy saturated art - DOOM 64's red demon face
has luminance 14/255, so it would come out nearly black.

Per-icon handling:
  * SMOOTH_MASK - tiny (32-48px) flat emblems. The binary mask is upscaled
    smoothly and re-thresholded, which removes the 32px pixel grid without
    losing holes or thin features. Tracing these with vtracer was tried and is
    WORSE: binary tracing faithfully reproduces the 32px stair-steps (angular
    outlines, lost holes), because the geometry is quantised at source.
  * POSTERIZE - Selaco's only source is a 32px portrait. Blurring just smears
    it, so its tone is quantised to a few flat gruvbox bands instead, which
    reads as deliberate rather than muddy.
  * BG_REPLACE - The Blood of Dawnwalker is dark artwork on a WHITE background.
    Inverting its tone (as a flat logo would be) turns photographic shading into
    a negative, so instead the light background is flood-filled and swapped for
    gruvbox dark, leaving the artwork's own lighting polarity intact.

Output: ~/.local/share/icons/gruvbox-recolor/<slug>.png (512x512, square like
the originals).

Run with any python that has numpy+pillow. vtracer is only needed if VECTORIZE
is non-empty, and then it must be a venv on python < 3.14 (it segfaults on
kwargs under 3.14):
    .venv312/bin/python generate_icons_v3.py
"""
import glob
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

ICON_DIR = os.path.expanduser("~/.local/share/icons/gruvbox-recolor")
HICOLOR = os.path.expanduser("~/.local/share/icons/hicolor")
STEAM_CACHE = os.path.expanduser("~/.local/share/Steam/appcache/librarycache")
SIZE = 512
SOURCE_SIZES = [256, 128, 96, 64, 48, 32, 24, 16]
SAT_MIN = 0.30           # below this a pixel is treated as neutral line art
AUTO_LEVELS = True       # stretch each icon's tone range to the full gradient
SMALL_PX = 64            # sources at/below this get the flat-art treatment
BIG = 1024               # working resolution for mask reconstruction

# gruvbox families: (name, faded/dark, bright)
FAMILIES = [
    ("red",    "#cc241d", "#fb4934"),
    ("orange", "#d65d0e", "#fe8019"),
    ("yellow", "#d79921", "#fabd2f"),
    ("green",  "#98971a", "#b8bb26"),
    ("aqua",   "#689d6a", "#8ec07c"),
    ("blue",   "#458588", "#83a598"),
    ("purple", "#b16286", "#d3869b"),
]

# tiny flat emblems: rebuild the mask instead of interpolating the 32px grid
SMOOTH_MASK = {"helldivers-2"}
# tone quantisation levels (flat gruvbox bands) for un-fixable low-res art
POSTERIZE = {}
# light-background artwork: swap the background, don't invert the tone
BG_REPLACE = {"the-blood-of-dawnwalker": 0.30}
# optional: slugs to trace with vtracer instead of rebuilding the mask
VECTORIZE = set()
# Official Steam grid art (600x900 in sources/), centre-cropped to square. Same
# artwork as the desktop icon, just large enough to re-tone cleanly - used where
# the installed icon is only 32-48px. (appid, vertical crop bias 0=top 1=bottom)
HIGH_RES = {
    "quake": (2310, 0.50),
    "beyond-citadel": (3371240, 0.50),
    "selaco": (1592280, 0.50),
    "ultrakill": (1229490, 0.50),
}
SOURCES_DIR = os.path.join(ICON_DIR, "sources")


def hex2rgb(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(c1: str, c2: str, t: float) -> str:
    a, b = hex2rgb(c1), hex2rgb(c2)
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def ramp(stops) -> np.ndarray:
    xs = np.array([s[0] for s in stops]) * 255.0
    cols = np.array([hex2rgb(s[1]) for s in stops], dtype=float)
    lut = np.zeros((256, 3), dtype=float)
    for ch in range(3):
        lut[:, ch] = np.interp(np.arange(256), xs, cols[:, ch])
    return lut.round().clip(0, 255).astype(np.uint8)


# neutral gruvbox browns -> cream, for grey/white/black artwork
NEUTRAL = ramp([(0.00, "#1d2021"), (0.25, "#282828"), (0.45, "#3c3836"),
                (0.62, "#504945"), (0.78, "#7c6f64"), (0.90, "#a89984"),
                (1.00, "#ebdbb2")])

# one gradient per colour family: gruvbox-dark base -> faded -> bright -> cream
FAMILY_RAMPS = np.stack([
    ramp([(0.00, "#1d2021"), (0.25, "#282828"), (0.45, "#3c3836"),
          (0.62, mix(faded, "#1d2021", 0.30)), (0.80, faded), (0.92, bright),
          (1.00, mix(bright, "#fbf1c7", 0.50))])
    for _, faded, bright in FAMILIES])

FAMILY_HUES = np.array([
    __import__("colorsys").rgb_to_hsv(*[c / 255 for c in hex2rgb(b)])[0] * 360
    for _, _, b in FAMILIES])


def build_hue_lut() -> np.ndarray:
    lut = np.zeros(360, dtype=np.intp)
    for h in range(360):
        d = np.abs(((FAMILY_HUES - h + 180) % 360) - 180)
        lut[h] = int(np.argmin(d))
    return lut


HUE_LUT = build_hue_lut()


def high_res(slug: str):
    """Square crop of the downloaded Steam grid art, or None."""
    spec = HIGH_RES.get(slug)
    if not spec:
        return None
    appid, bias = spec
    path = os.path.join(SOURCES_DIR, f"{appid}_grid.jpg")
    if not os.path.isfile(path):
        return None
    im = Image.open(path).convert("RGB")
    w, h = im.size
    side = min(w, h)
    top = max(0, min(h - side, int((h - side) * bias)))
    left = max(0, (w - side) // 2)
    return im.crop((left, top, left + side, top + side))


def find_source(appid: int):
    """Real installed icon first, else the square client icon in Steam's cache."""
    for s in SOURCE_SIZES:
        p = f"{HICOLOR}/{s}x{s}/apps/steam_icon_{appid}.png"
        if os.path.isfile(p):
            return p, f"hicolor {s}px"
    for p in sorted(glob.glob(f"{STEAM_CACHE}/{appid}/*")):
        try:
            im = Image.open(p)
        except Exception:                                   # noqa: BLE001
            continue
        w, h = im.size
        if abs(w - h) <= max(2, 0.1 * w) and max(w, h) <= 64:
            return p, f"steam cache {w}x{h}"
    return None, None


# ---------------------------------------------------------------- mask rebuild
def subject_mask(path: str) -> np.ndarray:
    """True where the artwork is (minority side of a midpoint split)."""
    g = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    thr = (g.min() + g.max()) / 2.0
    bright = g > thr
    return bright if bright.mean() < 0.5 else ~bright


def clean_mask(path: str) -> Image.Image:
    """Smoothly upscale the binary mask, re-threshold, come back down.

    Removes the source pixel grid while keeping holes and thin strokes, which
    tracing at source resolution destroys.
    """
    m = Image.fromarray((subject_mask(path) * 255).astype(np.uint8), "L")
    m = m.resize((BIG, BIG), Image.LANCZOS)
    m = Image.fromarray((np.asarray(m) >= 128).astype(np.uint8) * 255, "L")
    m = m.resize((SIZE, SIZE), Image.LANCZOS)
    return m.convert("RGB")


def vectorize(path: str) -> Image.Image:
    """Optional: binary vtracer trace -> crisp raster, polarity normalised."""
    import subprocess
    import tempfile
    import vtracer

    bw = tempfile.mktemp(suffix=".png")
    (Image.fromarray((subject_mask(path) * 255).astype(np.uint8), "L")
     .convert("RGB").save(bw))
    svg = tempfile.mktemp(suffix=".svg")
    vtracer.convert_image_to_svg_py(
        bw, svg, colormode="binary", hierarchical="cutout", mode="spline",
        filter_speckle=0, color_precision=8, layer_difference=6,
        corner_threshold=60, length_threshold=3.5, max_iterations=10,
        splice_threshold=45, path_precision=3)
    png = tempfile.mktemp(suffix=".png")
    subprocess.run(["rsvg-convert", "-w", str(BIG), "-h", str(BIG), "-b", "white",
                    "-o", png, svg], check=True)
    im = Image.fromarray(255 - np.asarray(Image.open(png).convert("RGB")), "RGB")
    return im.resize((SIZE, SIZE), Image.LANCZOS)


# ------------------------------------------------------- light-background swap
def flood_bg(im: Image.Image) -> np.ndarray:
    """Light, low-saturation region connected to the border = background."""
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    v = a.max(2)
    sat = np.where(v > 1e-6, (v - a.min(2)) / np.maximum(v, 1e-6), 0.0)
    cand = (v > 0.72) & (sat < 0.25)
    h, w = cand.shape
    seen = np.zeros_like(cand)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if cand[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if cand[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and cand[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return seen


# ------------------------------------------------------------------- mapping
def decompose(a: np.ndarray):
    v = a.max(axis=2)
    mn = a.min(axis=2)
    d = v - mn
    sat = np.where(v > 1e-6, d / np.maximum(v, 1e-6), 0.0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    safe = np.where(d == 0, 1, d)
    hue = np.zeros_like(v)
    nz = d > 1e-6
    m = nz & (v == r)
    hue[m] = (60.0 * ((g - b) / safe) % 360.0)[m]
    m = nz & (v == g)
    hue[m] = (60.0 * ((b - r) / safe) + 120.0)[m]
    m = nz & (v == b)
    hue[m] = (60.0 * ((r - g) / safe) + 240.0)[m]
    return v, sat, hue


def tone_map(v: np.ndarray, sat: np.ndarray, hue: np.ndarray,
             levels: int = 0) -> Image.Image:
    if AUTO_LEVELS:
        lo, hi = np.percentile(v, 2), np.percentile(v, 98)
        if hi - lo > 0.15:
            v = np.clip((v - lo) / (hi - lo), 0.0, 1.0)
    if levels > 1:
        v = np.round(v * (levels - 1)) / (levels - 1)
    fam = HUE_LUT[np.clip(hue, 0, 359.999).astype(np.intp)]
    tone = np.clip((v * 255.0).round(), 0, 255).astype(np.uint8)
    out = np.where((sat < SAT_MIN)[..., None], NEUTRAL[tone], FAMILY_RAMPS[fam, tone])
    return Image.fromarray(out.astype(np.uint8), "RGB")


def map_image(im: Image.Image, levels: int = 0) -> Image.Image:
    src = im.size
    if im.size != (SIZE, SIZE):
        im = im.resize((SIZE, SIZE), Image.LANCZOS)
    if SMOOTH_SMALL and max(src) < SMALL_PX:
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    a = np.asarray(im).astype(np.float32) / 255.0
    return tone_map(*decompose(a), levels=levels)


SMOOTH_SMALL = False     # superseded by clean_mask / posterise below


def gruvboxify(path: str, levels: int = 0) -> tuple:
    im = Image.open(path).convert("RGB")
    return map_image(im, levels=levels), im.size


def bg_replace(path: str, lift: float = 0.30) -> Image.Image:
    """Swap a light background for gruvbox dark, keeping the art's own shading."""
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255.0
    v, sat, hue = decompose(a)
    bg = flood_bg(im)
    subj = ~bg
    if subj.sum() < 0.02 * subj.size:      # flood fill failed: treat all as art
        subj = np.ones_like(subj)
    lo, hi = np.percentile(v[subj], 2), np.percentile(v[subj], 98)
    s = np.clip((v - lo) / max(hi - lo, 1e-6), 0, 1)
    v_out = np.where(bg, 0.0, lift + (1.0 - lift) * s)
    fam = HUE_LUT[np.clip(hue, 0, 359.999).astype(np.intp)]
    tone = np.clip((v_out * 255.0).round(), 0, 255).astype(np.uint8)
    out = np.where((sat < SAT_MIN)[..., None], NEUTRAL[tone], FAMILY_RAMPS[fam, tone])
    return Image.fromarray(out.astype(np.uint8), "RGB")


GAMES = [
    ("Beyond Citadel",                    "beyond-citadel",   3371240),
    ("Dead Space",                        "dead-space",        1693980),
    ("DOOM 64",                           "doom-64",           1148590),
    ("DOOM The Dark Ages",                "doom-the-dark-ages", 3017860),
    ("Hades II",                          "hades-ii",          1145350),
    ("HELLDIVERS 2",                      "helldivers-2",      553850),
    ("METAL GEAR RISING REVENGEANCE",     "metal-gear-rising-revengeance", 235460),
    ("METAL GEAR SOLID 4 Guns of the Patriots - Master Collection Version",
        "metal-gear-solid-4-guns-of-the-patriots-master-collection-version", 2492670),
    ("METAL GEAR SOLID MASTER COLLECTION Vol.2",
        "metal-gear-solid-master-collection-vol-2", 3859630),
    ("METAL GEAR SOLID Peace Walker - Master Collection Version",
        "metal-gear-solid-peace-walker-master-collection-version", 2492660),
    ("Quake",                             "quake",             2310),
    ("Resident Evil Requiem",             "resident-evil-requiem", 3764200),
    ("Selaco",                            "selaco",            1592280),
    ("The Blood of Dawnwalker",           "the-blood-of-dawnwalker", 3751260),
    ("Trepang2",                          "trepang2",          1164940),
    ("ULTRAKILL",                         "ultrakill",         1229490),
]


def main() -> int:
    os.makedirs(ICON_DIR, exist_ok=True)
    ok = 0
    for name, slug, appid in GAMES:
        path, how = find_source(appid)
        if not path:
            print(f"  SKIP {name:<26} no icon source (appid {appid})")
            continue
        hi = high_res(slug)
        if hi is not None:
            img = map_image(hi)
            how = "steam grid art 600x900 -> square"
        elif slug in SMOOTH_MASK:
            img = map_image(clean_mask(path))
            how += " +mask-rebuild"
        elif slug in VECTORIZE:
            img = map_image(vectorize(path))
            how += " +vtracer"
        elif slug in BG_REPLACE:
            img = bg_replace(path, BG_REPLACE[slug])
            how += " +bg-replace"
        else:
            img = gruvboxify(path, levels=POSTERIZE.get(slug, 0))[0]
            if slug in POSTERIZE:
                how += f" +posterise{POSTERIZE[slug]}"
        img.save(os.path.join(ICON_DIR, f"{slug}.png"))
        print(f"  ok   {name:<26} src={how}")
        ok += 1
    print(f"\n{ok}/{len(GAMES)} recoloured icons in {ICON_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
