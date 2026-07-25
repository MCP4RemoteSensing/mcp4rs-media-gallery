#!/usr/bin/env python3
"""
terrain_3d_views.py — one open DEM, four perspective angles on a single figure.

Renders the Copernicus DEM (GLO-30) of Hong Kong as a shaded 3D surface
(elevation-coloured, hillshaded) from four camera azimuths — a multi-angle
"3D terrain" panel. Uses Planetary Computer (anonymous signing, no account).

Run:
    pip install pystac-client planetary-computer rasterio numpy matplotlib
    python terrain_3d_views.py out.png
"""
from __future__ import annotations
import sys, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
import planetary_computer as pc
from pystac_client import Client

BBOX = [114.10, 22.19, 114.30, 22.35]     # Hong Kong
N = 200
EXAG = 4.0
OUT = sys.argv[1] if len(sys.argv) > 1 else "terrain_3d_views.png"
CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"


def read_dem():
    cat = Client.open(CATALOG)
    it = pc.sign(list(cat.search(collections=["cop-dem-glo-30"], bbox=BBOX, max_items=1).items())[0])
    with rasterio.open(it.assets["data"].href) as ds:
        l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *BBOX)
        win = from_bounds(l, b, r, t, ds.transform)
        elev = ds.read(1, window=win, out_shape=(N, N),
                       resampling=Resampling.bilinear).astype("float32")
    elev = np.clip(np.where(np.isfinite(elev), elev, 0.0), 0, 2000)
    for _ in range(2):  # smooth
        elev = (elev
                + np.pad(elev[1:], ((0, 1), (0, 0)), mode="edge")
                + np.pad(elev[:-1], ((1, 0), (0, 0)), mode="edge")
                + np.pad(elev[:, 1:], ((0, 0), (0, 1)), mode="edge")
                + np.pad(elev[:, :-1], ((0, 0), (1, 0)), mode="edge")) / 5.0
    return elev, it.id


def main():
    elev, dem_id = read_dem()
    print(f"DEM {dem_id}: {elev.min():.0f}..{elev.max():.0f} m")
    lat0 = (BBOX[1] + BBOX[3]) / 2
    xkm = (BBOX[2] - BBOX[0]) * 111.32 * math.cos(math.radians(lat0))
    ykm = (BBOX[3] - BBOX[1]) * 110.57
    X, Y = np.meshgrid(np.linspace(0, xkm, N), np.linspace(0, ykm, N))
    Z = (elev / 1000.0) * EXAG

    ls = LightSource(azdeg=315, altdeg=45)
    azims = [-120, -60, 0, 60]
    fig = plt.figure(figsize=(20, 5.2))
    for i, az in enumerate(azims):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d")
        ax.plot_surface(X, Y, Z, cmap="terrain", lightsource=ls,
                        rstride=1, cstride=1, linewidth=0, antialiased=False,
                        shade=True, vmin=0, vmax=max(Z.max(), 0.1))
        ax.set_box_aspect((xkm, ykm, max(Z.max(), 0.1) * 3.0))
        ax.view_init(elev=40, azim=az)
        ax.set_axis_off()
        ax.set_title(f"azimuth {az}\N{DEGREE SIGN}", fontsize=10)
    fig.suptitle("Hong Kong terrain in 3D from four angles — Copernicus DEM (30 m), "
                 f"vertical exaggeration {EXAG:g}x (open data, one MCP pattern)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print("saved", OUT)


if __name__ == "__main__":
    main()
