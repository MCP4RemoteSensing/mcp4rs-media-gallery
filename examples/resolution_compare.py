#!/usr/bin/env python3
"""
resolution_compare.py — show what "resolution" means, with real open imagery.

Renders the SAME small area (San Francisco International Airport) from three
open sources at their native ground sampling distance (GSD), side by side:
    NAIP        ~0.6 m   (runways, taxiways, individual aircraft)
    Sentinel-2   10 m    (airport shape, major structures)
    Landsat     30 m     (coarse blocks)

All three via Microsoft Planetary Computer (anonymous signing, no account).

Run:
    pip install pystac-client planetary-computer rasterio numpy matplotlib
    python resolution_compare.py
"""
from __future__ import annotations
import sys
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

AOI = [-122.397, 37.605, -122.355, 37.632]  # San Francisco Int'l Airport (SFO)
CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"
OUT = sys.argv[1] if len(sys.argv) > 1 else "resolution_compare.png"


def best(cat, collection, dt, cloud=True):
    kw = dict(collections=[collection], bbox=AOI, datetime=dt, max_items=15)
    if cloud:
        kw["query"] = {"eo:cloud_cover": {"lt": 10}}
        kw["sortby"] = [{"field": "properties.eo:cloud_cover", "direction": "asc"}]
    items = list(cat.search(**kw).items())
    return pc.sign(items[0]) if items else None


def read_band(href, band, cap):
    with rasterio.open(href) as ds:
        l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *AOI)
        win = from_bounds(l, b, r, t, ds.transform)
        h, w = int(win.height), int(win.width)
        scale = max(1, int(max(h, w) / cap))
        out = (max(1, h // scale), max(1, w // scale))
        return ds.read(band, window=win, out_shape=out,
                       resampling=Resampling.bilinear).astype("float32")


def stretch(rgb):
    out = np.zeros_like(rgb)
    for i in range(3):
        ch = rgb[..., i]
        valid = ch[ch > 0]
        lo, hi = np.percentile(valid if valid.size else ch, [2, 98])
        out[..., i] = np.clip((ch - lo) / (hi - lo + 1e-6), 0, 1)
    return out


def rgb_for(item, bands, cap):
    chans = [read_band(item.assets[a].href, bnd, cap) for a, bnd in bands]
    hmin = min(c.shape[0] for c in chans); wmin = min(c.shape[1] for c in chans)
    chans = [c[:hmin, :wmin] for c in chans]
    return stretch(np.dstack(chans))


def main():
    cat = Client.open(CATALOG)
    plan = [
        ("NAIP — 0.6 m", "naip", "2018-01-01/2024-12-31", False,
         lambda it: [("image", 1), ("image", 2), ("image", 3)], 1400),
        ("Sentinel-2 — 10 m", "sentinel-2-l2a", "2022-06-01/2022-09-30", True,
         lambda it: [("B04", 1), ("B03", 1), ("B02", 1)], 1400),
        ("Landsat — 30 m", "landsat-c2-l2", "2022-06-01/2022-09-30", True,
         lambda it: [("red", 1), ("green", 1), ("blue", 1)], 1400),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4))
    for ax, (title, coll, dt, cloud, bandfn, cap) in zip(axes, plan):
        try:
            it = best(cat, coll, dt, cloud)
            if it is None:
                ax.text(0.5, 0.5, "no scene", ha="center"); ax.set_title(title)
                ax.axis("off"); print(f"{title}: no scene"); continue
            img = rgb_for(it, bandfn(it), cap)
            ax.imshow(img, interpolation="nearest")
            ax.set_title(f"{title}\n{it.id[:28]}", fontsize=9)
            ax.axis("off")
            print(f"{title}: {it.id}  -> {img.shape[1]}x{img.shape[0]} px")
        except Exception as e:
            ax.text(0.5, 0.5, f"ERR\n{type(e).__name__}", ha="center"); ax.axis("off")
            print(f"{title}: ERR {type(e).__name__}: {e}")
    fig.suptitle("Same area (San Francisco Int'l Airport), three open sources at native resolution",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print("saved", OUT)


if __name__ == "__main__":
    main()
