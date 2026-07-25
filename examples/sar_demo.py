#!/usr/bin/env python3
"""
sar_demo.py — optical vs. radar over the same coast, both open, one MCP pattern.

Renders Sentinel-2 (optical) and Sentinel-1 SAR (radar, VV/VH false colour) over
Haikou Bay, Hainan — the setting of the land-sea SAR programme ("HaiShao").
SAR sees through cloud and at night, complementing optical imagery.

Sources (Microsoft Planetary Computer, anonymous signing, no account):
    sentinel-2-l2a    optical, 10 m
    sentinel-1-rtc    C-band SAR (radiometric terrain corrected), 10 m

Run:
    pip install pystac-client planetary-computer rasterio numpy matplotlib
    python sar_demo.py out.png
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

AOI = [110.10, 19.90, 110.55, 20.12]      # Haikou Bay, Hainan
CAP = 700
OUT = sys.argv[1] if len(sys.argv) > 1 else "sar_demo.png"
CATALOG = "https://planetarycomputer.microsoft.com/api/stac/v1"


def read(href, band, shape=None):
    with rasterio.open(href) as ds:
        l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *AOI)
        win = from_bounds(l, b, r, t, ds.transform)
        if shape is None:
            h, w = int(win.height), int(win.width)
            scale = max(1, int(max(h, w) / CAP))
            shape = (max(1, h // scale), max(1, w // scale))
        return ds.read(band, window=win, out_shape=shape,
                       resampling=Resampling.bilinear).astype("float32")


def norm(a, lo=2, hi=98):
    finite = a[np.isfinite(a)]
    p1, p2 = (np.percentile(finite, [lo, hi]) if finite.size else (0.0, 1.0))
    out = np.clip((a - p1) / (p2 - p1 + 1e-6), 0, 1)
    return np.nan_to_num(out, nan=0.0)


def main():
    cat = Client.open(CATALOG)

    s2 = pc.sign(list(cat.search(collections=["sentinel-2-l2a"], bbox=AOI,
                 datetime="2023-01-01/2023-12-31",
                 query={"eo:cloud_cover": {"lt": 15}},
                 sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}],
                 max_items=1).items())[0])
    print(f"Sentinel-2 {s2.id}: cloud {s2.properties.get('eo:cloud_cover')}%")
    opt = np.dstack([norm(read(s2.assets[b].href, 1)) for b in ("B04", "B03", "B02")])
    shp = opt.shape[:2]

    # Sentinel-1: mosaic same-orbit scenes (max) to cover the whole AOI
    s1_items = [pc.sign(it) for it in cat.search(collections=["sentinel-1-rtc"], bbox=AOI,
                datetime="2023-12-28/2023-12-28", max_items=6).items()
                if "vv" in it.assets and "vh" in it.assets]
    print(f"Sentinel-1: mosaicking {len(s1_items)} scenes")
    vv = np.max([read(it.assets["vv"].href, 1, shp) for it in s1_items], axis=0)
    vh = np.max([read(it.assets["vh"].href, 1, shp) for it in s1_items], axis=0)
    nodata = (vv <= 0) | (vh <= 0) | ~np.isfinite(vv) | ~np.isfinite(vh)
    eps = 1e-6
    vv_db = 10 * np.log10(np.where(nodata, np.nan, vv) + eps)
    vh_db = 10 * np.log10(np.where(nodata, np.nan, vh) + eps)
    ratio = vv_db - vh_db
    sar = np.dstack([norm(vv_db), norm(vh_db), norm(ratio)])  # R=VV G=VH B=VV/VH
    sar[nodata] = 0.0  # residual no-data -> black

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].imshow(opt); axes[0].set_title("Optical — Sentinel-2 (10 m)", fontsize=11)
    axes[1].imshow(sar); axes[1].set_title("Radar — Sentinel-1 SAR VV/VH (10 m, all-weather)", fontsize=11)
    for ax in axes:
        ax.axis("off")
    fig.suptitle("Same coast (Haikou Bay, Hainan), optical + radar — both open, one MCP pattern",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print("saved", OUT)


if __name__ == "__main__":
    main()
