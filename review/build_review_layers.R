# Build the layers for the mask-review QGIS project.
#
# Purpose: the auto-generated woodland candidate is one 158,599 m2 polygon that merges genuine
# woodland with a grass-like fringe and some wet ground. NDVI alone cannot split them (woodland
# 0.85 vs fringe 0.57, both over the 0.45 threshold); NIR brightness + image texture can, because
# tree crowns are optically rough (Krebsbach's own woodland polygons run sd~1500 vs open dune ~314).
# This writes those diagnostic layers plus an EDITABLE patch layer so the verdict can be recorded
# per patch rather than as one global yes/no.
suppressMessages({library(terra); library(sf)})
setwd("/Users/yurk/Documents/Projects/grass-mask/review")
ORTHO_CRS <- "EPSG:6345"          # NAD83(2011) / UTM 16N — the ortho's CRS

cir <- rast("cir_025m.tif")       # bands: NIR, Red, Green
cir[cir == 0] <- NA; cir[cir >= 65500] <- NA
nir <- aggregate(cir[[1]], fact = 2, fun = "mean", na.rm = TRUE)   # 0.5 m working grid
red <- aggregate(cir[[2]], fact = 2, fun = "mean", na.rm = TRUE)

ndvi <- (nir - red)/(nir + red); names(ndvi) <- "ndvi"
tex  <- focal(nir, w = 7, fun = "sd", na.rm = TRUE); names(tex) <- "texture"
writeRaster(ndvi, "ndvi_05m.tif", overwrite = TRUE, gdal = c("COMPRESS=DEFLATE","TILED=YES"))
writeRaster(tex,  "texture_05m.tif", overwrite = TRUE, gdal = c("COMPRESS=DEFLATE","TILED=YES"))

# --- Krebsbach's hand mask, reprojected to the ortho CRS so digitising is metric ---
msf <- st_read("../mask_grass_paper.shp", quiet = TRUE)
msf$class[is.na(msf$class)] <- "unlabeled"
bad <- !st_is_valid(msf); msf <- st_make_valid(msf)
msf <- st_transform(msf, 6345)
msf$area_m2 <- round(as.numeric(st_area(msf)), 1)
st_write(msf, "hand_mask_utm.gpkg", "hand_mask", delete_dsn = TRUE, quiet = TRUE)
cat(sprintf("hand mask: %d polygons reprojected 4326 -> 6345 (%d had invalid geometry, repaired)\n",
            nrow(msf), sum(bad)))

# --- reproduce the woodland candidate on this grid, then split it by brightness + texture ---
mrast <- rasterize(vect(msf), ndvi, field = 1, background = 0)
wood_raw <- (focal(ndvi, w = 9, fun = "mean", na.rm = TRUE) > 0.45) & (mrast == 0)   # ~5 m smoothing
wood_raw[wood_raw == 0] <- NA
wp <- disagg(as.polygons(wood_raw, dissolve = TRUE)); wp <- wp[expanse(wp) >= 200]
cat(sprintf("woodland candidate: %d patches >= 200 m2, largest %.0f m2\n", nrow(wp), max(expanse(wp))))

wmask <- rasterize(wp, ndvi, field = 1)
seg <- ndvi * 0
seg[!is.na(wmask) & nir >= 4000 & tex >= 900] <- 1   # woodland  : bright + crown texture
seg[!is.na(wmask) & nir >= 4000 & tex <  900] <- 2   # GRASS-LIKE: bright + smooth
seg[!is.na(wmask) & nir <  4000 & tex <  900] <- 3   # wetland   : dark + smooth
seg[!is.na(wmask) & nir <  4000 & tex >= 900] <- 4   # canopy shadow (ambiguous: could be wet woodland)
seg[is.na(wmask)] <- NA; seg[seg == 0] <- NA
lut <- data.frame(value = 1:4, class = c("woodland","grass_like","wetland","canopy_shadow"))
# Write BOTH the raw split and a lightly despeckled one. How much the grass-like class shrinks
# under smoothing is itself the diagnostic: a coherent fringe survives, an interdigitated one
# does not. Don't pre-decide that with an aggressive filter.
seg_raw <- seg; levels(seg_raw) <- lut
writeRaster(seg_raw, "block_segmentation_raw.tif", overwrite = TRUE,
            gdal = c("COMPRESS=DEFLATE","TILED=YES"), datatype = "INT1U")
seg <- focal(seg, w = 3, fun = "modal", na.rm = TRUE) |> mask(wmask)   # gentle, 1.5 m
levels(seg) <- lut
writeRaster(seg, "block_segmentation.tif", overwrite = TRUE,
            gdal = c("COMPRESS=DEFLATE","TILED=YES"), datatype = "INT1U")
a5 <- prod(res(seg))
cat(sprintf("grass_like: %.0f m2 raw -> %.0f m2 after 1.5 m despeckle (%.0f%% retained)\n",
            sum(values(seg_raw) == 2, na.rm = TRUE) * a5, sum(values(seg) == 2, na.rm = TRUE) * a5,
            100 * sum(values(seg) == 2, na.rm = TRUE) / sum(values(seg_raw) == 2, na.rm = TRUE)))

# --- the reviewable patch layer: everything the split says is NOT woodland ---
nonwood <- seg %in% c(2, 3); nonwood[nonwood == 0] <- NA
pp <- disagg(as.polygons(nonwood, dissolve = TRUE))
pp$area_m2 <- round(expanse(pp), 1)
pp <- pp[pp$area_m2 >= 50]
# modal over the whole patch, not the centroid: concave patches put their centroid outside themselves
pp$class_auto <- ifelse(extract(seg, pp, fun = "modal", na.rm = TRUE, ID = FALSE)[, 1] == 3,
                        "wetland", "grass_like")
pp$patch_id <- seq_len(nrow(pp))
pp$verdict  <- ""      # <- fill in QGIS: grass | woodland | wetland | other | unsure
pp$notes    <- ""
pp <- pp[, c("patch_id","area_m2","class_auto","verdict","notes")]
st_write(st_as_sf(pp), "review_patches.gpkg", "review_patches", delete_dsn = TRUE, quiet = TRUE)
cat(sprintf("review patches: %d polygons >= 50 m2, %.0f m2 total (median %.0f m2)\n",
            nrow(pp), sum(pp$area_m2), median(pp$area_m2)))

# --- water candidates: never written by the original script (its own mask suppressed them) ---
wet <- (ndvi < 0) & (mrast == 0); wet[wet == 0] <- NA
wv <- disagg(as.polygons(wet, dissolve = TRUE)); wv$area_m2 <- round(expanse(wv), 1)
wv <- wv[wv$area_m2 >= 10]
st_write(st_as_sf(wv), "water_candidates.gpkg", "water_candidates", delete_dsn = TRUE, quiet = TRUE)
cat(sprintf("water candidates: %d patches >= 10 m2, %.0f m2 total\n", nrow(wv), sum(wv$area_m2)))

# --- the 12 smaller woodland candidates, kept separate from the big one ---
wp$area_m2 <- round(expanse(wp), 1)
small <- wp[wp$area_m2 < 100000]; small$verdict <- ""
st_write(st_as_sf(small[, c("area_m2","verdict")]), "woodland_small_candidates.gpkg",
         "woodland_small", delete_dsn = TRUE, quiet = TRUE)
big <- wp[which.max(wp$area_m2)]
st_write(st_as_sf(big[, "area_m2"]), "woodland_big_candidate.gpkg",
         "woodland_big", delete_dsn = TRUE, quiet = TRUE)
cat(sprintf("small woodland candidates: %d (%.0f m2); big candidate %.0f m2\n",
            nrow(small), sum(small$area_m2), max(wp$area_m2)))
# --- empty free-hand layer: for drawing boundaries the automatic split got wrong ---
# Class list follows ../README.md (ids 0-6); 4=shoreline and 5=sand were defined but never used.
edits <- st_sf(class = character(), note = character(),
               geometry = st_sfc(crs = st_crs(6345), dim = "XY"))
if (!file.exists("my_edits.gpkg"))
  st_write(edits, "my_edits.gpkg", "my_edits", driver = "GPKG", quiet = TRUE) else
  cat("my_edits.gpkg already exists — left alone so edits are not overwritten\n")

cat("\nlayers written to", getwd(), "\n")
