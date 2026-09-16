# gruvbox-extras

Gruvbox-themed desktop launcher icons for the Steam games on this machine's
desktop, plus the generators that produced them and the earlier sets they
superseded.

The goal throughout: each game's **own mark**, restyled to sit natively in the
`Gruvbox-Plus-Dark` icon theme — recognisable as the original artwork, not
redesigned.

---

## Current live set — `sets/flat/`

Flat single-tone glyphs on a shared dark tile. The tile geometry (inset path,
corner radius, gradient, hairline rim ring) is copied verbatim from the user's own
reference icon, `Gruvbox-Plus-Dark/apps/scalable/quake.svg` — not eyeballed.

16 launchers on the desktop; 14 come from this generator, plus two composites
(built by `make_composite_icons.py` for marks whose artwork cannot survive
flattening to a single tone):

| Launcher | appid | Accent | Glyph source |
|---|---|---|---|
| beyond-citadel | 3371240 | `#b8bb26` | wordmark |
| dead-space | 1693980 | `#8ec07c` | wordmark |
| doom-64 | 1148590 | — | **not a flat glyph**: the official wordmark artwork composited on the tile |
| hades-ii | 1145350 | `#d3869b` | icon art |
| helldivers-2 | 553850 | `#fabd2f` | user's own `hd2.svg` |
| metal-gear-rising-revengeance | 235460 | `#fb4934` | wordmark |
| metal-gear-solid-4 (MC) | 2492670 | `#83a598` | wordmark |
| metal-gear-solid MC Vol.2 | 3859630 | `#fabd2f` | wordmark |
| metal-gear-solid-peace-walker | 2492660 | `#d5c4a1` | wordmark |
| resident-evil-requiem | 3764200 | `#b8bb26` | wordmark |
| trepang2 | 1164940 | `#a89984` | icon art |
| ultrakill | 1229490 | `#ebdbb2` | wordmark |
| the-blood-of-dawnwalker | 3751260 | `#d3869b` | icon art |
| selaco | 1592280 | `#83a598` | wordmark |
| warhammer-40-000-space-marine-2 | 2183900 | `#fabd2f` | **external source**: the Ultramarines chapter badge |
| doom-the-dark-ages | 3017860 | — | **not a flat glyph**: the crest artwork composited on the tile |

`quake.svg` and `steam.desktop` are the user's own and were never modified.

### Pipeline (`sets/flat/generate_flat_icons.py`)

1. Get the glyph mask — wordmark alpha, icon art, icon art via **alpha silhouette**,
   an **external source override**, or a **composite** for marks that cannot be
   flattened without losing their identity.
2. Clean it: trim the icon's own border band, drop leftover frame corners, punch
   negative-space detail, smooth.
3. Upscale to 1024 and re-threshold to shed the source's pixel grid.
4. Trace with vtracer (spline, binary, 4x supersample) and wrap in the reference tile.

Requires the Python 3.12 venv at `sets/recolor/.venv312` (vtracer segfaults on
kwargs under Python 3.14):

```bash
sets/recolor/.venv312/bin/python sets/flat/generate_flat_icons.py   # writes the SVGs
python3 sets/flat/apply_flat.py                                     # rewrites Icon= lines
```

### Layout

```
sets/flat/          the live flat set: generator, apply script, 14 SVGs, and the two
                    composite PNGs (DOOM: TDA crest, DOOM 64 wordmark)
sets/recolor/       earlier duotone re-tone of the installed icons (PNG), superseded
sets/monogram-v1/   first attempt: gruvbox monogram tiles, superseded
desktop/            the .desktop launchers as applied, for the record
```

## Applying and rolling back

`apply_flat.py` rewrites **only** the `Icon=` line of each launcher, matched by
basename. Everything else in the launchers is untouched.

```bash
touch ~/Desktop/*.desktop
kbuildsycoca6 --noincremental
```

The original launchers are in `~/Desktop-backup-<timestamp>/` on the machine.
Rollback: copy them back and re-run the two commands above.

## Hard-won details worth keeping

- **Use the alpha channel when the icon has one.** DOOM: TDA's colour mask found
  only 19% of the shield — the entire outer rim was silently cut off.
- **An icon's own border band is not part of the mark.** It is invisible at icon
  size but becomes a huge square outline once a mask is scaled to fill a tile.
- **Do not decide mask polarity by area.** "Invert if the subject exceeds 50%"
  flipped DOOM: TDA's mask onto the icon's black margin, producing a black square
  with a hollow centre.
- **A low-res source can be smoothed at the SOURCE scale before any upscale — but
  only when the mark is bold and simple.** DOOM 64's 128px art is upscaled 8x, so
  its edge follows the source's pixel grid (~10% of glyph area wobbles). A 3.0px
  source blur fixed that (1.15%) yet **destroyed the mark**: it is detail-rich
  artwork (a horned face inside a pentagram), and the horns, eyes and mouth melted
  away. That smoothing was reverted and the wobble accepted — an unreadable mark is
  worse than a rough edge. See `CHANGELOG.md`.
- **vtracer's `length_threshold` defaults to 3.5**, which makes the path follow
  every pixel-level wobble of the mask — that rasterises as jaggedness on a curve.
- **At the desktop's 256px icon size, ~0.10% edge deviation is just
  anti-aliasing** (measured from a hand-drawn vector at the same size). Judge
  smoothness against that floor, at the real size, at equal magnification.

## Provenance

See `NOTICE.md`. Gruvbox itself is MIT, by morhetz / gruvbox-contrib.
