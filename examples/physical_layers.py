#!/usr/bin/env python3
"""
physical_layers.py — beyond RGB: four open geophysical layers, no registration.

One MCP-style discovery pattern reaches many *physical* variables of the Earth,
each from an open, no-registration source:
    Thermal infrared  — MODIS Land Surface Temperature (Planetary Computer)
    Solar energy      — NASA POWER all-sky surface irradiance (open API)
    Weather           — GOES ABI band 13 (thermal IR clouds, Planetary Computer)
    Ocean             — NOAA OISST sea-surface temperature (Planetary Computer)

Run:
    pip install pystac-client planetary-computer rasterio numpy matplotlib
    python physical_layers.py out.png
"""
from __future__ import annotations
import sys, json, urllib.request
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
import planetary_computer as pc
from pystac_client import Client

OUT = sys.argv[1] if len(sys.argv) > 1 else "physical_layers.png"
CAT = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")


def read_win(href, bbox, cap=400, band=1, shape=None):
    with rasterio.open(href) as ds:
        l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *bbox)
        win = from_bounds(l, b, r, t, ds.transform)
        if shape is None:
            h, w = int(win.height), int(win.width)
            s = max(1, int(max(h, w) / cap))
            shape = (max(1, h // s), max(1, w // s))
        return ds.read(band, window=win, out_shape=shape,
                       resampling=Resampling.bilinear).astype("float32")


def best(coll, bbox, dt):
    its = list(CAT.search(collections=[coll], bbox=bbox, datetime=dt, max_items=5).items())
    return pc.sign(its[0]) if its else None


def solar_grid(bbox):
    url = ("https://power.larc.nasa.gov/api/temporal/climatology/regional?"
           "parameters=ALLSKY_SFC_SW_DWN&community=RE"
           f"&longitude-min={bbox[0]}&longitude-max={bbox[2]}"
           f"&latitude-min={bbox[1]}&latitude-max={bbox[3]}&format=JSON")
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mcp"}), timeout=60))
    lons, lats, vals = [], [], []
    for f in d["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        p = f["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
        ann = p.get("ANN") or np.mean([v for k, v in p.items() if k != "ANN"])
        lons.append(lon); lats.append(lat); vals.append(ann)
    ux, uy = np.unique(lons), np.unique(lats)
    grid = np.full((len(uy), len(ux)), np.nan)
    xi = {v: i for i, v in enumerate(ux)}; yi = {v: i for i, v in enumerate(uy)}
    for lo, la, v in zip(lons, lats, vals):
        grid[yi[la], xi[lo]] = v
    return grid[::-1], [ux.min(), ux.max(), uy.min(), uy.max()]


def main():
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))

    # (1) Thermal IR — MODIS LST over the North China Plain (mosaic tiles)
    bl = [112, 32, 120, 40]
    shp = (360, 360)
    its = [pc.sign(it) for it in CAT.search(collections=["modis-11A2-061"], bbox=bl,
           datetime="2023-07-01/2023-08-31", max_items=8).items()]
    acc = np.zeros(shp)
    for it in its:
        try:
            a = read_win(it.assets["LST_Day_1km"].href, bl, shape=shp)
        except Exception:
            continue
        acc = np.maximum(acc, np.where(np.isfinite(a) & (a > 0), a, 0))
    lst = np.where(acc > 0, acc * 0.02 - 273.15, np.nan)
    im = axes[0, 0].imshow(lst, cmap="inferno")
    axes[0, 0].set_title("Thermal IR — land surface temp (MODIS)\nNorth China, summer", fontsize=10)
    fig.colorbar(im, ax=axes[0, 0], shrink=0.7, label="\N{DEGREE SIGN}C")

    # (2) Solar — NASA POWER GHI over South China / Hainan
    grid, ext = solar_grid([106, 16, 116, 26])
    im = axes[0, 1].imshow(grid, cmap="plasma", extent=ext, aspect="auto")
    axes[0, 1].set_title("Solar energy — all-sky irradiance (NASA POWER)\nSouth China Sea region", fontsize=10)
    fig.colorbar(im, ax=axes[0, 1], shrink=0.7, label="kWh/m$^2$/day")

    # (3) Weather — GOES ABI band 13 thermal IR (Gulf of Mexico)
    bg = [-98, 20, -80, 32]
    it = best("goes-cmi", bg, "2023-08-29/2023-08-31")
    c13 = read_win(it.assets["C13_2km"].href, bg)
    axes[1, 0].imshow(c13, cmap="Greys")  # cold cloud tops -> bright
    axes[1, 0].set_title("Weather — GOES thermal IR (band 13)\nGulf of Mexico (storm clouds)", fontsize=10)

    # (4) Ocean — NOAA OISST sea-surface temperature (NW Pacific / Kuroshio)
    bo = [118, 18, 145, 40]
    it = best("noaa-cdr-sea-surface-temperature-optimum-interpolation", bo, "2023-08-01/2023-08-05")
    sst = read_win(it.assets["sst"].href, bo)
    sst = np.where(np.abs(sst) > 100, sst * 0.01, sst)  # scale if stored as int*100
    sst = np.where(sst < -5, np.nan, sst)
    im = axes[1, 1].imshow(sst, cmap="turbo")
    axes[1, 1].set_title("Ocean — sea-surface temperature (NOAA OISST)\nNW Pacific / Kuroshio", fontsize=10)
    fig.colorbar(im, ax=axes[1, 1], shrink=0.7, label="\N{DEGREE SIGN}C")

    for ax in axes.flat:
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Beyond RGB: four open geophysical layers, no registration — one MCP pattern",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print("saved", OUT)


if __name__ == "__main__":
    main()
