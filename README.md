## Mask for drone orthomosaic over Saugatuck Harbor Natural Area (SHNA)

Masks the surfaces the 3-class surface-composition model (dead / grass / sand) has no training
data for, so they can be excluded from the analysis. Used by the Krebsbach et al. paper — see
`byurk/krebsbach-et-al`.

**→ Work in progress lives in [`review/`](review/).** The hand mask here is incomplete; an
automatic detector was written to propose the rest, validated on 2026-07-25, and found wanting.
`review/mask_review.qgs` is a QGIS project for adjudicating its 52 open candidate patches.
**Read `review/README.md` before touching the mask.**

To get started add a sim link to the orthomosaic or make a new copy inside the repository (make sure to add it to .gitignore).

## Classes

ID Class

- 0 lake_michigan
- 1 wetland
- 2 vegetation
- 3 lake
- 4 shoreline
- 5 sand
- 6 human_structure

Note: `mask_grass_paper.shp` is stored in **EPSG:4326**; `review/hand_mask_utm.gpkg` is the same
140 polygons reprojected to the ortho's **EPSG:6345** with 4 self-intersecting polygons repaired.
Digitise against the UTM copy so areas and distances are metric.

<img src="/mask.png" width="400px" height="600px"/>
