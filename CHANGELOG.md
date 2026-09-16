# Changelog

Recorded from the session that produced the set (2026-09-15 → 2026-09-16).
Every entry is a decision that was tried and either kept or reverted, so a later
reader does not repeat a rejected approach.

## Style direction

1. **Monogram tiles** (`sets/monogram-v1/`) — first attempt. Rejected: *"I wanted
   them to more closely resemble their actual icons... but stylized / silhouetted."*
2. **Steam logo silhouettes** — closer. Rejected: *"use their actual desktop
   icons, not the logos."*
3. **Gruvbox duotone of the installed icons** (`sets/recolor/`) — hue-aware recolor,
   not a luminance ramp (a pure ramp rendered DOOM 64's red demon face near-black).
   Liked, but superseded by the flat tile style below. Kept here for reference.
4. **Flat glyphs on the reference tile** (`sets/flat/`) — the live direction,
   matching the user's own updated `quake.svg`.

## Corrections along the way

- **Top corners were not transparent.** Root cause: a 4px inset, sub-pixel at 96px.
  Fixed by reusing the reference icon's inset path verbatim.
- **Too much top sheen.** The reference's "bevel" is a thin rim ring with
  `fill-rule="evenodd"`, not a wash over the tile. Row-by-row match against the
  reference after the fix.
- **DOOM 64 and Hades II looked wrong as wordmarks.** Switched to their icon art
  (their wordmarks cannot be flattened legibly at 96px).
- **Space Marine 2's grungy wordmark** reads as noise when flattened — replaced
  with the Ultramarines chapter badge, with source-scale cleaning.
- **Blood of Dawnwalker**: a boldened variant was rejected as *worse* and reverted;
  the real complaint was a **giant square outline** that is not in the artwork —
  the mask was capturing the icon's own light margin around the dark mark.
- **DOOM: The Dark Ages cannot be flattened.** At every threshold the crest reduces
  to a solid disc or a gear ring. It now uses the crest artwork composited on the
  tile, not a flat glyph.

## Final smoothing pass (2026-09-16)

- **SM2**: `length_threshold` 3.5 → 20. The default made the traced path follow
  every pixel of mask wobble, which rasterised as jaggedness on the U's curves.
- **DOOM 64**: added a 3.0px blur at the 128px **source** resolution before the 8x
  upscale. Edge deviation at the desktop's real 256px fell from 10.22% to 1.15% of
  glyph area (a hand-drawn vector measures 0.10% — that is the anti-aliasing floor).
  2.2 left visible jaggies; 5.0 muddled the face's features.

## Reverted: DOOM 64 source smoothing (2026-09-16)

A 3.0px blur at the source resolution fixed the edge (10.22% → 1.15% wobble) but
**destroyed the mark** — the horns, eyes and mouth melted into a blob. This mark is
detail-rich artwork (a horned face inside a pentagram), not a bold geometric glyph,
so it does not tolerate the treatment that worked for the low-res-but-simple case.

Reverted to no source smoothing, keeping `length_threshold=16`. The residual edge
wobble is accepted in exchange for a readable mark: with a blur strong enough to
calm the edge, the mark is not recognisable at all, which is worse than a rough edge.

Also tested and rejected: compositing the real artwork on the tile (the approach
used for DOOM: The Dark Ages). At 256px it is too dark and low-contrast against the
tile, and would muddle further at small sizes. Flat single-tone wins for this mark.

## Verification standards used

- The desktop renders at 256px (`iconSize=6`); all smoothness measurements are at
  that size.
- Edge smoothness is judged against a hand-drawn vector rendered identically, at
  equal magnification — earlier comparisons that mixed sizes gave false answers.
- Every change: 15/15 SVGs rasterise, all icon paths resolve, and a `diff -r`
  against the launcher backup shows **only `Icon=` lines differ**.
- 13 of 15 icons were byte-identical across the final smoothing pass; only SM2 and
  DOOM 64 changed.
