#!/usr/bin/env python3
"""
Acquire a REAL Sentinel-2 scene from AWS Open Data and render the workflow:
  true-color RGB  ->  NDWI  ->  water mask

Outputs (into figures/): s2_rgb.png, s2_ndwi.png, s2_water.png
Also prints the STAC "before -> after" context.

Run (inside the project venv):
    python render_scene.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
from pystac_client import Client

STAC = "https://earth-search.aws.element84.com/v1/"
# Haikou-bay search box: picks tile 49QDC (north Hainan coast), a real
# land/sea mix -- the SAME scene the live demo (client_demo.py) targets.
SEARCH_BBOX = [110.10, 19.90, 110.55, 20.12]
BBOX = [110.10, 19.90, 110.55, 20.12]
SIZE = 640
OUT_DIR = Path(__file__).resolve().parent / "figures"
PROVENANCE_DIR = Path(__file__).resolve().parent / "generated" / "provenance"

def read_window(href, aoi, size=SIZE):
    """Windowed read cropped to the AOI (avoids scene-edge no-data wedges)."""
    from rasterio.warp import transform_bounds
    with rasterio.open(href) as ds:
        l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *aoi)
        win = ds.window(l, b, r, t)
        return ds.read(1, window=win, out_shape=(size, size),
                       resampling=Resampling.bilinear).astype("float32")

def stretch(a, lo=2, hi=98):
    p2, p98 = np.percentile(a, [lo, hi])
    return np.clip((a - p2) / (p98 - p2 + 1e-6), 0, 1)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    print("== search Sentinel-2 L2A on AWS (STAC) ==")
    c = Client.open(STAC)
    s = c.search(collections=["sentinel-2-l2a"], bbox=SEARCH_BBOX,
                 datetime="2025-01-01/2025-06-30",
                 query={"eo:cloud_cover": {"lt": 10}},
                 max_items=1,
                 sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}])
    item = next(s.items())
    print(f"picked {item.id}  cloud={item.properties.get('eo:cloud_cover')}%")
    print(f"item bbox = {[round(x,3) for x in item.bbox]}")
    # Render the whole scene footprint (same extent the demo's segment_water
    # reads), so the water_fraction here matches the live-demo / appendix value
    # and the SAME scene (49QDC, Haikou) is shown throughout the deck.
    BBOX[:] = list(item.bbox)
    print(f"render AOI = {[round(x,3) for x in BBOX]}")
    source_record = {
        "tool_equivalent": "search_open_data",
        "endpoint": STAC,
        "collection": "sentinel-2-l2a",
        "search_bbox": SEARCH_BBOX,
        "render_bbox": list(BBOX),
        "datetime_range": "2025-01-01/2025-06-30",
        "max_cloud_cover": 10,
        "item": {
            "id": item.id,
            "datetime": str(item.datetime),
            "cloud_cover": item.properties.get("eo:cloud_cover"),
            "assets": {
                band: item.assets[band].href
                for band in ("red", "green", "blue", "nir")
                if band in item.assets
            },
        },
    }
    (PROVENANCE_DIR / "s2_workflow_sources.json").write_text(
        json.dumps(source_record, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("\n-- STAC BEFORE (what AWS hosts: a STAC Item) --")
    print(json.dumps({
        "id": item.id, "collection": item.collection_id,
        "datetime": str(item.datetime), "bbox": [round(x,3) for x in item.bbox],
        "assets(sample)": ["red(B04)", "green(B03)", "blue(B02)", "nir(B08)"],
    }, indent=2))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    red  = read_window(item.assets["red"].href, BBOX)
    green= read_window(item.assets["green"].href, BBOX)
    blue = read_window(item.assets["blue"].href, BBOX)
    nir  = read_window(item.assets["nir"].href, BBOX)

    valid = (red + green + blue) > 0    # mask scene-edge no-data

    # 1) true-color RGB
    rgb = np.dstack([stretch(red), stretch(green), stretch(blue)])
    plt.figure(figsize=(5,5)); plt.imshow(rgb); plt.axis("off")
    plt.title(f"Sentinel-2 true color\n{item.id}", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT_DIR / "s2_rgb.png", dpi=140, bbox_inches="tight"); plt.close()

    # 2) NDWI
    ndwi = (green - nir) / (green + nir + 1e-6)
    ndwi_disp = np.where(valid, ndwi, np.nan)
    plt.figure(figsize=(5,5)); im=plt.imshow(ndwi_disp, cmap="RdYlBu", vmin=-0.6, vmax=0.6)
    plt.axis("off"); plt.title("NDWI = (Green - NIR)/(Green + NIR)", fontsize=9)
    plt.colorbar(im, fraction=0.046, pad=0.04)
    plt.tight_layout(); plt.savefig(OUT_DIR / "s2_ndwi.png", dpi=140, bbox_inches="tight"); plt.close()

    # 3) water mask over RGB (only over valid pixels)
    water = valid & (ndwi > 0.0)
    overlay = rgb.copy()
    overlay[water] = [0.0, 0.55, 1.0]    # highlight water in blue
    frac = float(water.sum() / max(valid.sum(), 1))
    plt.figure(figsize=(5,5)); plt.imshow(overlay); plt.axis("off")
    plt.title(f"Water mask  (water_fraction = {frac:.3f})", fontsize=9)
    plt.tight_layout(); plt.savefig(OUT_DIR / "s2_water.png", dpi=140, bbox_inches="tight"); plt.close()

    # 4) single triptych (acquire -> transform -> present) on one canvas
    fig, ax = plt.subplots(1, 3, figsize=(12, 4.2))
    ax[0].imshow(rgb); ax[0].set_title("1 - Acquire (true color)", fontsize=11)
    ax[1].imshow(ndwi_disp, cmap="RdYlBu", vmin=-0.6, vmax=0.6)
    ax[1].set_title("2 - Transform (NDWI)", fontsize=11)
    ax[2].imshow(overlay); ax[2].set_title(f"3 - Present (water_fraction = {frac:.2f})", fontsize=11)
    for a in ax: a.axis("off")
    fig.suptitle(f"Sentinel-2 L2A on AWS  -  {item.id}  (cloud {item.properties.get('eo:cloud_cover')}%)",
                 fontsize=12, y=1.02)
    plt.tight_layout(); plt.savefig(OUT_DIR / "s2_triptych.png", dpi=130, bbox_inches="tight"); plt.close()

    print(f"\n-- AFTER (agent result): water_fraction = {frac:.4f} --")
    print(f"wrote {OUT_DIR}/s2_rgb.png, s2_ndwi.png, s2_water.png, s2_triptych.png")
    print(f"wrote {PROVENANCE_DIR / 's2_workflow_sources.json'}")

if __name__ == "__main__":
    main()
