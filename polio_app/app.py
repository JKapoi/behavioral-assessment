"""
===============================================================================
SHINY APP (PYTHON): POLIO VIRUS HEATMAP & CLUSTER MAP WITH FILTERS + PNG EXPORT
===============================================================================

Python / Shiny-for-Python port of app.R (R Shiny + mapgl).

Run locally:
    pip install -r requirements.txt
    playwright install chromium        # only needed for the PNG download
    shiny run --reload app.py
Then open http://127.0.0.1:8000

Configuration (environment variables, all optional):
    POLIO_DATA_PATH    path to the Excel file (default: the path used in app.R,
                       or AllPolioviruses_20230406_V2.xlsx next to this file)
    POLIO_DATA_SHEET   sheet name (default: AllPolioviruses_20230303)
    MAPTILER_API_KEY   MapTiler key for the "openstreetmap" basemap style.
                       Without a key the app falls back to plain OSM raster tiles.
"""

from __future__ import annotations

import html
import json
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from shiny import App, reactive, render, ui

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent

_DEFAULT_DATA_PATHS = [
    APP_DIR / "AllPolioviruses_20230406_V2.xlsx",
    Path("C:/Users/ADMIN/Documents/AAAPEPVirus/AScript/AllPolioviruses_20230406_V2.xlsx"),
]
DATA_PATH = os.environ.get("POLIO_DATA_PATH") or next(
    (str(p) for p in _DEFAULT_DATA_PATHS if p.exists()), str(_DEFAULT_DATA_PATHS[-1])
)
DATA_SHEET = os.environ.get("POLIO_DATA_SHEET", "AllPolioviruses_20230303")

MAPTILER_API_KEY = os.environ.get("MAPTILER_API_KEY", "hxrAw46qpobL63GesyZb")

MAPLIBRE_JS = os.environ.get("MAPLIBRE_JS_URL", "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js")
MAPLIBRE_CSS = os.environ.get("MAPLIBRE_CSS_URL", "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css")

# West, South, East, North (same as africa_bbox in app.R)
AFRICA_BBOX = [-20, -35, 55, 38]
JITTER_FACTOR = 0.01  # equivalent of st_jitter(factor = 0.01)

KNOWN_COLORS = {
    "cVDPV1": "#F067A6",
    "cVDPV2": "#3ABB9C",
    "cVDPV3": "#8ED8F8",
    "WPV1": "#FF0000",
    "VDPV1": "#305cde",
    "VDPV2": "#F254F0",
    "VDPV3": "orange",
}
OTHER_COLOR = "grey"

LEGEND_HTML = (
    '<div style="background: white; padding: 10px; border-radius: 5px; font-size: 13px; '
    'line-height: 1.5; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">'
    "<strong>Polio Virus Type</strong><br>"
    + "".join(f'<span style="color:{c};">&#9632;</span> {v}<br>' for v, c in KNOWN_COLORS.items())
    + f'<span style="color:{OTHER_COLOR};">&#9632;</span> Other</div>'
)

FILTERS = {  # input id -> data column
    "year": "Year",
    "country": "Country",
    "virus": "AllViruses",
    "emergence": "Emergence",
}

POPUP_FIELDS = [
    ("Country", "Country"),
    ("DONSET", "DONSET"),
    ("Virus Type", "VirusType"),
    ("Emergence", "Emergence"),
    ("EPID", "EPID"),
    ("Province", "Province"),
    ("District", "District"),
]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_data() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, sheet_name=DATA_SHEET)
    df = df.rename(columns={"Lat": "latitude", "Long": "longitude"})
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["latitude"].between(-35, 38) & df["longitude"].between(-20, 55)].copy()

    # Make sure every column the app uses exists
    for col in set(FILTERS.values()) | {c for _, c in POPUP_FIELDS}:
        if col not in df.columns:
            df[col] = pd.NA

    # Year is compared as text so "2020" from the dropdown matches 2020 / 2020.0
    df["Year"] = df["Year"].map(_year_to_str)

    # Popup text (same content as popup_content in app.R), HTML-escaped
    donset = pd.to_datetime(df["DONSET"], errors="coerce").dt.strftime("%d-%b-%Y")
    parts = []
    for label, col in POPUP_FIELDS:
        values = donset if col == "DONSET" else df[col]
        values = values.map(lambda v: "" if pd.isna(v) else html.escape(str(v)))
        parts.append(f"<b>{label}:</b> " + values)
    df["popup_content"] = parts[0]
    for p in parts[1:]:
        df["popup_content"] = df["popup_content"] + "<br>" + p

    return df.reset_index(drop=True)


def _year_to_str(v) -> str | None:
    if pd.isna(v):
        return None
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else str(v)
    except (TypeError, ValueError):
        return str(v)


def _choices(series: pd.Series) -> list[str]:
    values = series.dropna().astype(str).unique().tolist()
    try:
        values.sort(key=float)
    except ValueError:
        values.sort()
    return ["All"] + values


def jitter(df: pd.DataFrame, factor: float = JITTER_FACTOR, seed: int | None = None) -> pd.DataFrame:
    """Rough equivalent of sf::st_jitter(): uniform noise scaled by the data extent."""
    if df.empty:
        return df
    rng = np.random.default_rng(seed)
    extent = np.mean([np.ptp(df["longitude"]), np.ptp(df["latitude"])])
    amount = factor * extent
    out = df.copy()
    out["longitude"] = out["longitude"] + rng.uniform(-amount, amount, len(out))
    out["latitude"] = out["latitude"] + rng.uniform(-amount, amount, len(out))
    return out


def to_geojson(df: pd.DataFrame, props: list[str]) -> dict:
    features = []
    for row in df[["longitude", "latitude", *props]].itertuples(index=False):
        lon, lat, *vals = row
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": {k: (None if pd.isna(v) else str(v)) for k, v in zip(props, vals)},
        })
    return {"type": "FeatureCollection", "features": features}


def color_match(prop: str, extra_types) -> list:
    """MapLibre 'match' expression: known colours, grey for anything else."""
    expr = ["match", ["to-string", ["get", prop]]]
    for v, c in KNOWN_COLORS.items():
        expr += [v, c]
    for v in sorted(set(extra_types) - set(KNOWN_COLORS)):
        expr += [v, OTHER_COLOR]
    return expr + [OTHER_COLOR]


try:
    RAW_DATA = load_data()
    LOAD_ERROR = None
except Exception as e:  # show the problem in the UI instead of crashing
    RAW_DATA = pd.DataFrame(columns=["latitude", "longitude", *FILTERS.values(), "popup_content"])
    LOAD_ERROR = f"Could not load data from {DATA_PATH!r} (sheet {DATA_SHEET!r}): {e}"


# ---------------------------------------------------------------------------
# Map HTML (MapLibre GL JS; replaces mapgl::maplibre)
# ---------------------------------------------------------------------------
def basemap_style() -> str | dict:
    if MAPTILER_API_KEY:
        return f"https://api.maptiler.com/maps/openstreetmap/style.json?key={MAPTILER_API_KEY}"
    return {
        "version": 8,
        "glyphs": "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",  # cluster count labels
        "sources": {"osm": {
            "type": "raster", "tileSize": 256,
            "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            "attribution": "&copy; OpenStreetMap contributors",
        }},
        "layers": [{"id": "osm", "type": "raster", "source": "osm"}],
    }


def heatmap_layers(df: pd.DataFrame) -> tuple[dict, list]:
    sources = {"polio": {"type": "geojson", "data": to_geojson(df, ["VirusType", "popup_content"])}}
    layers = [
        {
            "id": "polio_heatmap", "type": "heatmap", "source": "polio",
            "paint": {
                "heatmap-radius": 12,
                "heatmap-color": [
                    "interpolate", ["linear"], ["heatmap-density"],
                    0, "rgba(0,0,0,0)", 0.25, "palegreen", 0.5, "yellow", 0.75, "orange", 1, "red",
                ],
                "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 6, 0],
            },
        },
        {
            # One layer coloured by VirusType (app.R added one layer per type)
            "id": "polio_points", "type": "circle", "source": "polio", "minzoom": 5,
            "paint": {
                "circle-color": color_match("VirusType", df["VirusType"].dropna().astype(str).unique()),
                "circle-radius": 6,
                "circle-stroke-color": "black",
                "circle-stroke-width": 1,
            },
        },
    ]
    return sources, layers


def cluster_layers(df: pd.DataFrame) -> tuple[dict, list]:
    sources = {"polio": {
        "type": "geojson", "data": to_geojson(df, ["AllViruses"]),
        "cluster": True, "clusterRadius": 40,
    }}
    layers = [
        {
            "id": "polio_clusters", "type": "circle", "source": "polio", "filter": ["has", "point_count"],
            "paint": {
                "circle-color": ["step", ["get", "point_count"], "#2b83ba", 50, "#abdda4", 200, "#fdae61"],
                "circle-radius": ["step", ["get", "point_count"], 20, 50, 30, 200, 40],
                "circle-blur": 0.2,
                "circle-stroke-color": "white",
                "circle-stroke-width": 3,
            },
        },
        {
            "id": "polio_cluster_count", "type": "symbol", "source": "polio", "filter": ["has", "point_count"],
            "layout": {"text-field": ["get", "point_count_abbreviated"], "text-size": 12},
        },
        {
            "id": "polio_unclustered", "type": "circle", "source": "polio", "minzoom": 4,
            "filter": ["!", ["has", "point_count"]],
            "paint": {
                "circle-color": color_match("AllViruses", df["AllViruses"].dropna().astype(str).unique()),
                "circle-radius": 6,
                "circle-stroke-color": "black",
                "circle-stroke-width": 1,
            },
        },
    ]
    return sources, layers


def map_html(sources: dict, layers: list, popup_layer: str | None = None, for_export: bool = False) -> str:
    config = {
        "style": basemap_style(),
        "bounds": AFRICA_BBOX,
        "sources": sources,
        "layers": layers,
        "popupLayer": popup_layer,
        "legend": LEGEND_HTML,
        "export": for_export,
    }
    # Escape "</" so data can never close the <script> tag
    config_json = json.dumps(config).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="{MAPLIBRE_CSS}">
<script src="{MAPLIBRE_JS}"></script>
<style>
  html, body, #map {{ margin: 0; padding: 0; width: 100%; height: 100%; }}
  .legend-ctrl {{ margin: 0 0 10px 10px; }}
</style></head>
<body><div id="map"></div>
<script>
const cfg = {config_json};
const map = new maplibregl.Map({{
  container: "map", style: cfg.style, bounds: cfg.bounds,
  fitBoundsOptions: {{ padding: 10 }}, preserveDrawingBuffer: cfg.export,
  attributionControl: {{ compact: true }}
}});
map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl({{
  onAdd() {{
    const el = document.createElement("div");
    el.className = "maplibregl-ctrl legend-ctrl";
    el.innerHTML = cfg.legend;
    return el;
  }},
  onRemove() {{}}
}}, "bottom-left");
map.on("load", () => {{
  for (const [id, src] of Object.entries(cfg.sources)) map.addSource(id, src);
  for (const layer of cfg.layers) map.addLayer(layer);
  if (cfg.popupLayer) {{
    map.on("click", cfg.popupLayer, (e) => {{
      new maplibregl.Popup().setLngLat(e.lngLat)
        .setHTML(e.features[0].properties.popup_content).addTo(map);
    }});
    map.on("mouseenter", cfg.popupLayer, () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", cfg.popupLayer, () => map.getCanvas().style.cursor = "");
  }}
  if (map.getLayer("polio_clusters")) {{
    // Click a cluster to zoom into it
    map.on("click", "polio_clusters", async (e) => {{
      const f = map.queryRenderedFeatures(e.point, {{ layers: ["polio_clusters"] }})[0];
      const zoom = await map.getSource("polio").getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({{ center: f.geometry.coordinates, zoom }});
    }});
    map.on("mouseenter", "polio_clusters", () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", "polio_clusters", () => map.getCanvas().style.cursor = "");
  }}
  map.once("idle", () => {{ window.mapReady = true; }});
}});
</script></body></html>"""


def map_frame(doc: str) -> ui.Tag:
    return ui.tags.iframe(
        srcdoc=doc,
        style="width: 100%; height: 650px; border: 0;",
    )


# ---------------------------------------------------------------------------
# PNG export (replaces saveWidget + webshot)
# ---------------------------------------------------------------------------
async def screenshot_html(doc: str, width: int = 1200, height: int = 800) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader"])
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.set_content(doc, wait_until="load")
            try:
                await page.wait_for_function("window.mapReady === true", timeout=30_000)
            except Exception:
                pass  # take the picture anyway (e.g. slow basemap tiles)
            return await page.screenshot(type="png")
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
app_ui = ui.page_fluid(
    ui.panel_title("\U0001F4CD Polio Virus Heatmap & Clustering", window_title="Polio Virus Heatmap"),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select("year", "Select Year:", choices=_choices(RAW_DATA["Year"]), selected="All"),
            ui.input_select("country", "Select Country:", choices=_choices(RAW_DATA["Country"]), selected="All"),
            ui.input_select("virus", "Select Virus Type:", choices=_choices(RAW_DATA["AllViruses"]), selected="All"),
            ui.input_select("emergence", "Select Emergence Group:", choices=_choices(RAW_DATA["Emergence"]), selected="All"),
            ui.download_button("download_heatmap", "Download Heatmap (PNG)"),
            ui.output_text("n_points"),
            width=300,
        ),
        ui.div(LOAD_ERROR, class_="alert alert-danger") if LOAD_ERROR else None,
        ui.navset_tab(
            ui.nav_panel("Heatmap", ui.output_ui("heatmap")),
            ui.nav_panel("Cluster Map", ui.output_ui("clustermap")),
        ),
    ),
)


# render.download_button is the newer name (Shiny >= 1.8); older versions use render.download
_download_renderer = getattr(render, "download_button", render.download)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
def server(input, output, session):

    @reactive.calc
    def filtered_data() -> pd.DataFrame:
        df = RAW_DATA
        for input_id, col in FILTERS.items():
            value = input[input_id]()
            if value and value != "All":
                df = df[df[col].astype(str) == value]
        return jitter(df)

    @render.text
    def n_points():
        return f"{len(filtered_data()):,} viruses shown"

    def heatmap_doc(for_export: bool = False) -> str:
        sources, layers = heatmap_layers(filtered_data())
        return map_html(sources, layers, popup_layer="polio_points", for_export=for_export)

    @render.ui
    def heatmap():
        return map_frame(heatmap_doc())

    @render.ui
    def clustermap():
        sources, layers = cluster_layers(filtered_data())
        return map_frame(map_html(sources, layers))

    @_download_renderer(filename=lambda: f"polio_heatmap_{date.today()}.png", media_type="image/png")
    async def download_heatmap():
        try:
            png = await screenshot_html(heatmap_doc(for_export=True))
        except Exception as e:
            ui.notification_show(
                f"PNG export failed ({e}). Install it with: pip install playwright && playwright install chromium",
                type="error", duration=10,
            )
            raise
        yield png


app = App(app_ui, server)
