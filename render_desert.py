#!/usr/bin/env python3
"""
Multi-year greening time-series over the Talatan Solar Park (Gonghe, Qinghai) ---
the world's largest PV park, where panels shaded the ground and grassland returned.

For each year: query Sentinel-2 L2A on AWS (STAC), pick the lowest-cloud summer scene,
windowed-read Red+NIR over a fixed AOI, compute NDVI, render an annotated frame.
Then assemble an MP4 + GIF. Also prints mean NDVI per year (the greening trend).

Run inside the project venv:
    python render_desert.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, rasterio
from rasterio.enums import Resampling
from pystac_client import Client

STAC = "https://earth-search.aws.element84.com/v1/"
# Talatan PV park, Gonghe County, Qinghai (Qinghai-Tibet Plateau).
TILE = "47SPA"                       # MGRS tile that actually covers the park
TARGET = (100.575, 36.200)           # lon, lat inside the panel cluster
HALF = 300                           # half-window in px (10 m) -> ~6.0 km, tighter & sharper
AOI = [100.44, 36.08, 100.74, 36.34] # used only for the STAC search bbox
YEARS = list(range(2017, 2026))      # 2017..2025 = 9 frames -> smoother animation
SIZE = 2 * HALF                      # read at NATIVE 10 m (no down-sampling => crisp)
OUT_DIR = Path(__file__).resolve().parent / "figures"
PROVENANCE_DIR = Path(__file__).resolve().parent / "generated" / "provenance"

def best_scene(client, year):
    s = client.search(collections=["sentinel-2-l2a"], bbox=AOI,
                      datetime=f"{year}-06-01/{year}-09-30",
                      query={"eo:cloud_cover": {"lt": 20}},
                      max_items=30,
                      sortby=[{"field":"properties.eo:cloud_cover","direction":"asc"}])
    for it in s.items():
        if TILE in it.id:            # same tile every year -> aligned, no edge smear
            return it
    return None

def read_win(href):
    from rasterio.warp import transform
    with rasterio.open(href) as ds:
        xs, ys = transform("EPSG:4326", ds.crs, [TARGET[0]], [TARGET[1]])
        row, col = ds.index(xs[0], ys[0])
        win = rasterio.windows.Window(col - HALF, row - HALF, 2*HALF, 2*HALF)
        return ds.read(1, window=win, out_shape=(SIZE, SIZE),
                       resampling=Resampling.bilinear).astype("float32")

def main():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    client = Client.open(STAC)
    # ---- pass 1: gather every year's bands so we can stretch GLOBALLY (no flicker) ----
    data = []   # list of (year, id, cloud, red, green, blue, ndvi_mean)
    provenance = []
    for y in YEARS:
        it = best_scene(client, y)
        if it is None:
            print(f"{y}: no scene"); continue
        red   = read_win(it.assets["red"].href)
        green = read_win(it.assets["green"].href)
        blue  = read_win(it.assets["blue"].href)
        nir   = read_win(it.assets["nir"].href)
        ndvi  = (nir - red) / (nir + red + 1e-6)
        provenance.append({
            "year": y,
            "id": it.id,
            "datetime": str(it.datetime),
            "cloud_cover": it.properties.get("eo:cloud_cover"),
            "assets": {
                band: it.assets[band].href
                for band in ("red", "green", "blue", "nir")
                if band in it.assets
            },
        })
        data.append((y, it.id, it.properties.get("eo:cloud_cover"),
                     red, green, blue, float(np.nanmean(ndvi))))
        print(f"{y}: {it.id} cloud={it.properties.get('eo:cloud_cover'):.2f}% "
              f"meanNDVI={float(np.nanmean(ndvi)):.3f}")
    if not data:
        print("no frames"); return
    source_record = {
        "endpoint": STAC,
        "collection": "sentinel-2-l2a",
        "bbox": AOI,
        "target": TARGET,
        "tile": TILE,
        "years": YEARS,
        "items": provenance,
    }
    (PROVENANCE_DIR / "desert_greening_sources.json").write_text(
        json.dumps(source_record, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # global per-channel 2-98 percentile from all years stacked together
    def gp(ch_idx):
        allv = np.concatenate([d[3+ch_idx].ravel() for d in data])
        return np.percentile(allv, [2, 98])
    (r_lo,r_hi),(g_lo,g_hi),(b_lo,b_hi) = gp(0), gp(1), gp(2)
    def st(a, lo, hi): return np.clip((a-lo)/(hi-lo+1e-6), 0, 1)

    # ---- pass 2: render contiguous frames desert_a0..a(N-1) with the fixed stretch ----
    means = []
    for i,(y,sid,cloud,red,green,blue,nm) in enumerate(data):
        means.append((y, nm))
        rgb = np.dstack([st(red,r_lo,r_hi), st(green,g_lo,g_hi), st(blue,b_lo,b_hi)])
        plt.figure(figsize=(6,6)); plt.imshow(rgb); plt.axis("off")
        plt.title(f"Talatan Solar Park, Qinghai - {y}", fontsize=13)
        plt.tight_layout()
        plt.savefig(OUT_DIR / f"desert_{y}.png", dpi=170, bbox_inches="tight")
        plt.savefig(OUT_DIR / f"desert_a{i}.png", dpi=170, bbox_inches="tight")
        plt.close()
    nframes = len(data)
    print(f"NFRAMES={nframes}  (desert_a0..a{nframes-1})")

    # trend plot
    ys=[a for a,_ in means]; ms=[b for _,b in means]
    plt.figure(figsize=(5,3))
    plt.plot(ys, ms, "o-", color="#2e8b40", lw=2)
    plt.fill_between(ys, ms, min(ms)-0.02, color="#2e8b40", alpha=0.15)
    plt.xlabel("year"); plt.ylabel("mean NDVI"); plt.title("Greening trend (AOI mean NDVI)", fontsize=11)
    plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(OUT_DIR / "desert_trend.png", dpi=140, bbox_inches="tight"); plt.close()
    print("trend:", means)
    print(f"wrote {PROVENANCE_DIR / 'desert_greening_sources.json'}")

if __name__ == "__main__":
    main()
