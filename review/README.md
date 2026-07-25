# Mask review — adjudicating the auto-generated candidates

Open **`mask_review.qgs`**.

## The question

The 3-class surface-composition model (dead / grass / sand) has no training data for water,
wetland, woodland or trees, so those areas have to be masked out of the analysis. Krebsbach's
hand mask (140 polygons, 157,882 m²) does not cover all of them, and an automatic detector was
written to propose the rest.

That detector produced **one 160,377 m² polygon** — 97% of everything it proposed, and about
**23% of the whole unmasked study area**. It is layer ④.

It is not homogeneous. Splitting it by NIR brightness and image texture gives:

| | area | share | NDVI | texture |
|---|---|---|---|---|
| woodland (bright, crown texture) | ~110,000 m² | 70% | 0.85 | 1654 |
| **grass-like (bright, smooth)** | **~20,000 m²** | **13%** | **0.57** | **554** |
| wetland (dark, smooth) | ~2,700 m² | 2% | — | — |
| canopy shadow (dark, rough) | ~16,600 m² | 10% | — | — |

**The question is which of the grass-like patches are really grass** — i.e. target surface that
must stay *in* the analysis — and which are woodland, wetland or something else. It is unlikely
to be a single answer for all of them, which is why the verdict is recorded per patch.

## How to answer it

Layer ① `review_patches` holds the **52 non-woodland patches ≥ 50 m²** (17,072 m² total,
median 160 m²), each labelled with its `patch_id` and drawn yellow while unreviewed.

1. Toggle ⑩ **false colour** (vegetation = red, sand = cyan-white, water = dark) against
   ⑪ **true colour**. False colour separates cover types far better.
2. Turn ⑧ **texture** on to see why the split fell where it did — tree crowns are optically
   rough, marram is smooth. Krebsbach's own woodland polygons average 1512 on this layer,
   open dune 314, his wetlands 557.
3. Toggle ① on and off. Ask of each yellow patch: is this dune surface the quadrat model
   should be predicting, or is it something the model was never trained on?
4. Edit ① (pencil icon), click a patch, set **`verdict`** from the dropdown:
   `grass` · `woodland` · `wetland` · `water` · `other` · `unsure`.
   Colour updates as you go, so remaining yellow = still to do. `notes` is free text.
5. Where the automatic boundary is simply in the wrong place, draw the correct one in
   **`✏ my_edits`** instead (fields: `class`, `note`). Use the class names from `../README.md`.

Also worth a verdict while you are in there: ③ the **12 small woodland candidates** (4,735 m²,
each has a `verdict` field), and ② the **5 water candidates** (1,995 m²) — these were never
written by the original script, because it suppressed its own detector inside the existing mask
and the two lakes are already masked.

## Layers

| | layer | notes |
|---|---|---|
| ✏ | `my_edits` | empty, editable — draw corrected boundaries here |
| ① | `review_patches` | **the 52 patches to adjudicate**; set `verdict` |
| ② | `water_candidates` | 5 patches ≥ 10 m², 1,995 m² |
| ③ | `woodland_small` | the 12 smaller woodland candidates, 4,735 m² |
| ④ | `woodland_big` | the 160,377 m² candidate |
| ⑤ | `hand_mask` | Krebsbach's mask, **reprojected 4326 → 6345** so digitising is metric; 4 self-intersecting polygons repaired |
| ⑥ | `block_segmentation` | the brightness+texture split, 1.5 m despeckle |
| ⑦ | `block_segmentation_raw` | same split, unsmoothed — the difference shows how interdigitated the classes are (97% of grass-like survives, so the fringe is fairly coherent) |
| ⑧ | `texture_05m` | focal sd of NIR over 3.5 m |
| ⑨ | `ndvi_05m` | |
| ⑩ | `cir_025m` | false colour NIR-Red-Green, 25 cm |
| ⑪ | `rgb_025m` | true colour, 25 cm |

## What in here is durable, and what is scaffolding

Two different kinds of file live in this directory, and they should be treated differently.

**Regenerable** — deterministic functions of the ortho plus the two build scripts:
`cir_025m.tif`, `rgb_025m.tif`, `ndvi_05m.tif`, `texture_05m.tif`, `block_segmentation*.tif`,
all three candidate `.gpkg`s, and `mask_review.qgs`. The segmentation in particular is *meant*
to be thrown away — it is superseded the moment a fitted classifier replaces the thresholds.
Losing any of this costs only the minutes it takes to re-run the two scripts.

**Irreplaceable** — `review_patches.gpkg` (once `verdict` is filled in) and `my_edits.gpkg`.
These are human judgement from the only person who can supply it, and they are the **training
labels** for the classifier that replaces the hand thresholds. Nothing can recompute them.
Commit after every editing session.

Because the verdicts carry geometry, they stay valid even after the segmentation underneath them
is replaced — they can be spatially re-joined to whatever comes next. But `patch_id` will *not*
survive a re-segmentation, so never treat a verdict as an annotation keyed to that id; the
polygon is the label.

## Caveats

- The thresholds behind ⑥ (NIR 4000, texture 900) are **calibrated against Krebsbach's labelled
  classes but not fitted**. They are a better-anchored guess than the NDVI > 0.45 they replace,
  not a validated model. The verdicts recorded here are intended to become training data for a
  fitted classifier, which is what the paper should actually report.
- `canopy_shadow` (dark + rough) is genuinely ambiguous — wet woodland looks the same. It is
  currently treated as woodland and is **not** in the review layer.
- The DEM is **bare earth**, confirmed: surface roughness inside the densest vegetation
  (0.044 m) is lower than over open sand (0.064 m), NDVI correlates −0.17 with roughness and
  0.003 with height, and a 373 m² building shows a 0.00 m top-hat. So canopy height is not
  available as a discriminator, and the old `tallveg` detector was measuring dune topography.

## Regenerating

`cir_025m.tif` and `rgb_025m.tif` are gitignored (146 MB). Rebuild them on euler from
`model-dune/raw_data/drone_sitched/ortho.tif`:

```bash
gdalwarp -tr 0.25 0.25 -r average -b 5 -b 3 -b 2 -co COMPRESS=DEFLATE -co TILED=YES ortho.tif cir_025m.tif
gdalwarp -tr 0.25 0.25 -r average -b 3 -b 2 -b 1 -co COMPRESS=DEFLATE -co TILED=YES ortho.tif rgb_025m.tif
```

Then `Rscript build_review_layers.R` (rebuilds everything except `my_edits.gpkg`, which is
never overwritten) and `python3 make_qgis_project.py`.

Note: on euler, use **`/opt/R/4.3.2/bin/Rscript`** — plain `Rscript` now resolves to R 4.6.1,
where renv cannot bootstrap and no packages load.
