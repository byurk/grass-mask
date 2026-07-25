#!/usr/bin/env python3
"""Generate mask_review.qgs — a QGIS project for adjudicating the mask candidates.

Written as XML rather than through PyQGIS because the QGIS.app bundle on this Mac has no
usable Python framework for headless use. Idiom matches what QGIS 3.44 writes (<Option> maps,
not the deprecated <prop k=/v=> form). Stretch min/max are baked in deliberately: the ortho
encodes nodata as 65535, and letting QGIS compute a default stretch over that value is what
made every earlier render come out nearly black.
"""
import uuid, html

CRS = """<spatialrefsys nativeFormat="Wkt">
      <proj4>+proj=utm +zone=16 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs</proj4>
      <srsid>3230</srsid><srid>6345</srid><authid>EPSG:6345</authid>
      <description>NAD83(2011) / UTM zone 16N</description>
      <projectionacronym>utm</projectionacronym>
      <ellipsoidacronym>EPSG:7019</ellipsoidacronym>
      <geographicflag>false</geographicflag>
    </spatialrefsys>"""

EXT = (564263.22, 4724081.93, 565026.47, 4725176.68)


def lid(name):
    return f"{name}_{uuid.uuid5(uuid.NAMESPACE_DNS, name).hex}"


def fill(color, outline, width=0.4, style="solid"):
    return f"""<layer enabled="1" locked="0" class="SimpleFill" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="{color}"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="offset" type="QString" value="0,0"/>
            <Option name="offset_unit" type="QString" value="MM"/>
            <Option name="outline_color" type="QString" value="{outline}"/>
            <Option name="outline_style" type="QString" value="{style}"/>
            <Option name="outline_width" type="QString" value="{width}"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>"""


def symbol(name, color, outline, width=0.4, style="solid"):
    return (f'<symbol is_animated="0" clip_to_extent="1" alpha="1" frame_rate="10" '
            f'name="{name}" force_rhr="0" type="fill">{fill(color, outline, width, style)}</symbol>')


def raster_layer(fname, title, checked, renderer, nodata_bands=0, opacity="1"):
    nd = ""
    if nodata_bands:
        items = "".join(
            f'<noDataList bandNo="{b}" useSrcNoData="0">'
            f'<noDataRange min="-1" max="0.5"/><noDataRange min="65500" max="70000"/>'
            f'</noDataList>' for b in range(1, nodata_bands + 1))
        nd = f"<noData>{items}</noData>"
    return f"""<maplayer type="raster" hasScaleBasedVisibilityFlag="0" autoRefreshTime="0" refreshOnNotifyEnabled="0">
      <id>{lid(fname)}</id>
      <datasource>./{fname}</datasource>
      <layername>{html.escape(title)}</layername>
      <srs>{CRS}</srs>
      <provider>gdal</provider>
      {nd}
      <pipe>
        <provider>
          <resampling enabled="true" maxOversampling="2"
            zoomedInResamplingMethod="nearestNeighbour" zoomedOutResamplingMethod="average"/>
        </provider>
        {renderer}
        <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
        <huesaturation colorizeOn="0" saturation="0" grayscaleMode="0"/>
        <rasterresampler maxOversampling="2"/>
      </pipe>
      <blendMode>0</blendMode>
    </maplayer>"""


def multiband(r, g, b, opacity="1"):
    def ce(tag, lo, hi):
        return (f"<{tag}ContrastEnhancement><minValue>{lo}</minValue><maxValue>{hi}</maxValue>"
                f"<algorithm>StretchToMinimumMaximum</algorithm></{tag}ContrastEnhancement>")
    return (f'<rasterrenderer type="multibandcolor" redBand="1" greenBand="2" blueBand="3" '
            f'opacity="{opacity}" alphaBand="-1" nodataColor="">'
            + ce("red", *r) + ce("green", *g) + ce("blue", *b) + "</rasterrenderer>")


def paletted(entries, opacity="0.55"):
    items = "".join(f'<paletteEntry value="{v}" color="{c}" label="{l}" alpha="255"/>'
                    for v, c, l in entries)
    return (f'<rasterrenderer type="paletted" band="1" opacity="{opacity}" alphaBand="-1" '
            f'nodataColor=""><colorPalette>{items}</colorPalette></rasterrenderer>')


def pseudocolor(lo, hi, stops, opacity="1"):
    items = "".join(f'<item value="{v}" color="{c}" label="{v}" alpha="255"/>' for v, c in stops)
    return (f'<rasterrenderer type="singlebandpseudocolor" band="1" opacity="{opacity}" '
            f'alphaBand="-1" classificationMin="{lo}" classificationMax="{hi}" nodataColor="">'
            f'<rastershader><colorrampshader colorRampType="INTERPOLATED" classificationMode="1" '
            f'clip="0" minimumValue="{lo}" maximumValue="{hi}">{items}</colorrampshader>'
            f'</rastershader></rasterrenderer>')


def vector_layer(gpkg, sublayer, title, renderer, extra="", labeling=""):
    return f"""<maplayer type="vector" geometry="Polygon" hasScaleBasedVisibilityFlag="0" refreshOnNotifyEnabled="0">
      <id>{lid(gpkg + sublayer)}</id>
      <datasource>./{gpkg}|layername={sublayer}</datasource>
      <layername>{html.escape(title)}</layername>
      <srs>{CRS}</srs>
      <provider encoding="UTF-8">ogr</provider>
      {renderer}
      {labeling}
      {extra}
      <blendMode>0</blendMode>
      <featureBlendMode>0</featureBlendMode>
      <layerOpacity>1</layerOpacity>
    </maplayer>"""


def categorized(attr, cats):
    """cats: list of (value, label, color, outline, width, style)"""
    c = "".join(f'<category render="true" value="{html.escape(str(v))}" symbol="{i}" '
                f'label="{html.escape(l)}"/>' for i, (v, l, *_rest) in enumerate(cats))
    s = "".join(symbol(str(i), col, out, w, st)
                for i, (_v, _l, col, out, w, st) in enumerate(cats))
    return (f'<renderer-v2 forceraster="0" symbollevels="0" enableorderby="0" '
            f'attr="{attr}" referencescale="-1" type="categorizedSymbol">'
            f'<categories>{c}</categories><symbols>{s}</symbols></renderer-v2>')


def single(color, outline, width=0.4, style="solid"):
    return (f'<renderer-v2 forceraster="0" symbollevels="0" enableorderby="0" '
            f'referencescale="-1" type="singleSymbol">{symbol("0", color, outline, width, style)}'
            f'</renderer-v2>')


VERDICTS = ["grass", "woodland", "wetland", "water", "other", "unsure"]

verdict_widget = """<fieldConfiguration>
        <field name="verdict" configurationFlags="NoFlag">
          <editWidget type="ValueMap">
            <config><Option type="Map"><Option name="map" type="List">
              %s
            </Option></Option></config>
          </editWidget>
        </field>
      </fieldConfiguration>""" % "".join(
    f'<Option type="Map"><Option name="{v}" type="QString" value="{v}"/></Option>'
    for v in [""] + VERDICTS)

patch_labels = """<labeling type="simple">
        <settings><text-style fieldName="patch_id" fontSize="9" textColor="255,255,255,255"
            fontWeight="75" isExpression="0">
          <text-buffer bufferDraw="1" bufferSize="1" bufferColor="0,0,0,255"/>
        </text-style>
        <placement placement="0" centroidInside="1"/>
        <rendering scaleVisibility="0" drawLabels="1"/></settings>
      </labeling>"""

# ---- layer tree, top of the list = top of the QGIS panel -------------------------------------
LAYERS = [
    # (file, sublayer|None, title, checked, maplayer-xml)
    ("my_edits.gpkg", "my_edits", "✏ my_edits — draw here", True,
     vector_layer("my_edits.gpkg", "my_edits", "✏ my_edits — draw here",
                  single("255,0,0,0", "255,0,0,255", 0.8))),
    ("review_patches.gpkg", "review_patches", "① review_patches — set 'verdict'", True,
     vector_layer("review_patches.gpkg", "review_patches", "① review_patches — set 'verdict'",
                  categorized("verdict", [
                      ("", "unreviewed", "247,225,26,80", "247,225,26,255", 0.8, "solid"),
                      ("grass", "grass — KEEP in analysis", "0,200,0,90", "0,140,0,255", 0.6, "solid"),
                      ("woodland", "woodland — mask out", "27,120,55,120", "27,120,55,255", 0.6, "solid"),
                      ("wetland", "wetland — mask out", "44,127,184,120", "44,127,184,255", 0.6, "solid"),
                      ("water", "water — mask out", "0,80,255,120", "0,60,200,255", 0.6, "solid"),
                      ("other", "other", "160,160,160,110", "90,90,90,255", 0.6, "solid"),
                      ("unsure", "unsure", "255,140,0,110", "255,140,0,255", 0.8, "solid"),
                  ]), extra=verdict_widget, labeling=patch_labels)),
    ("water_candidates.gpkg", "water_candidates", "② water candidates (5)", True,
     vector_layer("water_candidates.gpkg", "water_candidates", "② water candidates (5)",
                  single("0,80,255,90", "0,60,200,255", 0.6))),
    ("woodland_small_candidates.gpkg", "woodland_small", "③ woodland candidates, small (12)", True,
     vector_layer("woodland_small_candidates.gpkg", "woodland_small",
                  "③ woodland candidates, small (12)",
                  single("255,255,255,0", "255,160,0,255", 0.7))),
    ("woodland_big_candidate.gpkg", "woodland_big", "④ THE 160,377 m² candidate", True,
     vector_layer("woodland_big_candidate.gpkg", "woodland_big", "④ THE 160,377 m² candidate",
                  single("255,255,255,0", "255,255,0,255", 1.0))),
    ("hand_mask_utm.gpkg", "hand_mask", "⑤ Krebsbach hand mask (UTM)", True,
     vector_layer("hand_mask_utm.gpkg", "hand_mask", "⑤ Krebsbach hand mask (UTM)",
                  categorized("class", [
                      ("vegetation", "vegetation", "0,255,255,50", "0,255,255,255", 0.5, "solid"),
                      ("wetland", "wetland", "255,0,255,50", "255,0,255,255", 0.7, "solid"),
                      ("lake", "lake", "0,102,255,60", "0,102,255,255", 0.7, "solid"),
                      ("lake_michigan", "lake_michigan", "0,102,255,60", "0,102,255,255", 0.7, "solid"),
                      ("human_structure", "human_structure", "255,128,0,80", "255,128,0,255", 0.7, "solid"),
                      ("unlabeled", "unlabeled", "255,255,255,60", "255,255,255,255", 0.7, "solid"),
                  ]))),
    ("block_segmentation.tif", None, "⑥ split: brightness + texture", True,
     raster_layer("block_segmentation.tif", "⑥ split: brightness + texture", True,
                  paletted([(1, "#1b7837", "woodland"), (2, "#f7e11a", "grass_like"),
                            (3, "#2c7fb8", "wetland"), (4, "#7a7a7a", "canopy_shadow")]))),
    ("block_segmentation_raw.tif", None, "⑦ same split, unsmoothed", False,
     raster_layer("block_segmentation_raw.tif", "⑦ same split, unsmoothed", False,
                  paletted([(1, "#1b7837", "woodland"), (2, "#f7e11a", "grass_like"),
                            (3, "#2c7fb8", "wetland"), (4, "#7a7a7a", "canopy_shadow")]))),
    ("texture_05m.tif", None, "⑧ texture (NIR sd, 3.5 m) — crowns are rough", False,
     raster_layer("texture_05m.tif", "⑧ texture (NIR sd, 3.5 m) — crowns are rough", False,
                  pseudocolor(0, 2500, [(0, "#000000"), (314, "#2c3e70"),
                                        (900, "#e07b39"), (1512, "#ffe680"), (2500, "#ffffff")]))),
    ("ndvi_05m.tif", None, "⑨ NDVI", False,
     raster_layer("ndvi_05m.tif", "⑨ NDVI", False,
                  pseudocolor(-0.2, 0.9, [(-0.2, "#8c510a"), (0.0, "#d8b365"), (0.3, "#f6e8c3"),
                                          (0.45, "#c7eae5"), (0.6, "#5ab4ac"), (0.9, "#01665e")]))),
    ("cir_025m.tif", None, "⑩ FALSE COLOUR (NIR-R-G) 25 cm", True,
     raster_layer("cir_025m.tif", "⑩ FALSE COLOUR (NIR-R-G) 25 cm", True,
                  multiband((200, 13000), (150, 7000), (400, 5500)), nodata_bands=3)),
    ("rgb_025m.tif", None, "⑪ TRUE COLOUR 25 cm", False,
     raster_layer("rgb_025m.tif", "⑪ TRUE COLOUR 25 cm", False,
                  multiband((150, 7000), (400, 5500), (200, 4000)), nodata_bands=3)),
]

tree = "".join(
    f'<layer-tree-layer expanded="0" name="{html.escape(t)}" patch_size="-1,-1" '
    f'legend_split_behavior="0" id="{lid(f + (s or ""))}" legend_exp="" '
    f'source="./{f}{"|layername=" + s if s else ""}" '
    f'checked="{"Qt::Checked" if c else "Qt::Unchecked"}" '
    f'providerKey="{"ogr" if s else "gdal"}"/>'
    for f, s, t, c, _x in LAYERS)

doc = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis projectname="SHNA mask review" version="3.44.10-Solothurn">
  <homePath path=""/>
  <title>SHNA mask review</title>
  <projectCrs>{CRS}</projectCrs>
  <layer-tree-group>
    {tree}
    <custom-order enabled="0"/>
  </layer-tree-group>
  <mapcanvas name="theMapCanvas" annotationsVisible="1">
    <units>meters</units>
    <extent><xmin>{EXT[0]}</xmin><ymin>{EXT[1]}</ymin><xmax>{EXT[2]}</xmax><ymax>{EXT[3]}</ymax></extent>
    <rotation>0</rotation>
    <destinationsrs>{CRS}</destinationsrs>
    <rendermaptile>0</rendermaptile>
  </mapcanvas>
  <projectlayers>
    {"".join(x for *_h, x in LAYERS)}
  </projectlayers>
  <layerorder/>
  <properties>
    <Measure><Ellipsoid type="QString">EPSG:7019</Ellipsoid></Measure>
    <Gui><CanvasColour type="QString">#ffffff</CanvasColour></Gui>
    <PositionPrecision><Automatic type="bool">true</Automatic></PositionPrecision>
  </properties>
</qgis>
"""

with open("mask_review.qgs", "w") as fh:
    fh.write(doc)
print(f"wrote mask_review.qgs with {len(LAYERS)} layers")
