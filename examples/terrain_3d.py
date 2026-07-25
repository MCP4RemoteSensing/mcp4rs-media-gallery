#!/usr/bin/env python3
"""
terrain_3d.py — drape open optical imagery over an open DEM as a 3D surface.

Combines two open sources discovered through the same MCP pattern:
  - Copernicus DEM GLO-30 (elevation, ~30 m)   [AWS Open Data]
  - Sentinel-2 L2A RGB (10 m)                    [AWS Open Data]
into a texture-mapped 3D terrain of Hong Kong (Victoria Peak + harbour).

Run:
    pip install pystac-client rasterio numpy matplotlib pillow
    python terrain_3d.py out.png
"""
from __future__ import annotations
import sys, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from pystac_client import Client
import planetary_computer as pc

BBOX = [114.10, 22.19, 114.30, 22.35]   # Hong Kong Island + Kowloon + harbour
N = 220                                   # grid size
EXAG = 3.0                                # vertical exaggeration
OUT = sys.argv[1] if len(sys.argv) > 1 else "terrain_3d.png"
CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"


def read_grid(href, band, shape):
    with rasterio.open(href) as ds:
        l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *BBOX)
        win = from_bounds(l, b, r, t, ds.transform)
        return ds.read(band, window=win, out_shape=shape,
                       resampling=Resampling.bilinear).astype("float32")


def main():
    cat = Client.open(CATALOG)
    dem_it = pc.sign(list(cat.search(collections=["cop-dem-glo-30"], bbox=BBOX, max_items=1).items())[0])
    elev = read_grid(dem_it.assets["data"].href, 1, (N, N))
    # clean nodata / spurious spikes, then smooth for a natural surface
    elev = np.where(np.isfinite(elev), elev, 0.0)
    elev = np.clip(elev, 0, 2000)
    def smooth(a, k=2):
        for _ in range(k):
            a = (a
                 + np.pad(a[1:], ((0, 1), (0, 0)), mode="edge")
                 + np.pad(a[:-1], ((1, 0), (0, 0)), mode="edge")
                 + np.pad(a[:, 1:], ((0, 0), (0, 1)), mode="edge")
                 + np.pad(a[:, :-1], ((0, 0), (1, 0)), mode="edge")) / 5.0
        return a
    elev = smooth(elev, 2)
    print(f"DEM {dem_it.id}: elev {elev.min():.0f}..{elev.max():.0f} m")

    s2 = pc.sign(list(cat.search(collections=["sentinel-2-l2a"], bbox=BBOX,
                         datetime="2023-01-01/2023-12-31",
                         query={"eo:cloud_cover": {"lt": 8}},
                         sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}],
                         max_items=1).items())[0])
    print(f"Sentinel-2 {s2.id}: cloud {s2.properties.get('eo:cloud_cover')}%")
    raw = np.dstack([read_grid(s2.assets[b].href, 1, (N, N)) for b in ("B04", "B03", "B02")])
    nodata = raw.min(axis=2) < 1.0            # pixels outside the S2 tile (any zero band)
    for _ax in (0, 1):                         # dilate 1 px to erase the tile-edge line
        nodata = nodata | np.roll(nodata, 1, _ax) | np.roll(nodata, -1, _ax)
    rgb = np.clip(raw / 3000.0, 0, 1) ** 0.85  # fixed stretch + mild gamma (avoid wash-out)
    sea = np.array([0.52, 0.62, 0.71], dtype="float32")
    rgb[nodata] = sea
    elev[nodata] = 0.0                          # flatten no-data area to sea level

    # geographic grid -> metres, for correct hillshade slope
    lat0 = (BBOX[1] + BBOX[3]) / 2
    x_m = (BBOX[2] - BBOX[0]) * 111320 * math.cos(math.radians(lat0))
    y_m = (BBOX[3] - BBOX[1]) * 110570
    dx, dy = x_m / N, y_m / N

    from matplotlib.colors import LightSource
    ls = LightSource(azdeg=315, altdeg=45)
    shaded = ls.shade_rgb(rgb, elev, vert_exag=EXAG, blend_mode="soft",
                          dx=dx, dy=dy)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(shaded, origin="upper")
    ax.set_axis_off()
    ax.set_title("Hong Kong terrain — Sentinel-2 (10 m) shaded by Copernicus DEM (30 m)\n"
                 f"hillshade relief, vertical exaggeration {EXAG:g}x — both open, one MCP pattern",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print("saved", OUT)


if __name__ == "__main__":
    main()
