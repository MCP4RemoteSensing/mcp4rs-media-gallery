#!/usr/bin/env python3
"""
Seasonal water/colour time-series over a desert target, from Sentinel-2 L2A on AWS.

Usage:
    python render_lake.py test               # render ONE recent clear frame per target to /tmp
    python render_lake.py full <key>         # full time-series for one target (writes ../figures)

Targets are defined in TARGETS. "full" mode:
  - searches the AOI for 2025-01-01 .. 2026-06-30, eo:cloud_cover < CLOUD
  - locks onto the single dominant MGRS tile (so frames are co-registered, no edge smear)
  - windowed native-10m read of R/G/B over a fixed AOI window
  - global 2-98 percentile stretch across ALL frames (no brightness flicker)
  - writes figures/<prefix>_a0..aN.png  (sequential, for GIF assembly)
"""
from __future__ import annotations
import json
import sys, collections
from pathlib import Path
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform
from pystac_client import Client

STAC = "https://earth-search.aws.element84.com/v1/"
CLOUD = 15
START, END = "2025-01-01", "2026-06-30"
OUT_DIR = Path(__file__).resolve().parent / "figures"
PROVENANCE_DIR = Path(__file__).resolve().parent / "generated" / "provenance"

# key -> (name, lon, lat, half_px@10m, search_pad_deg, force_tile)
TARGETS = {
    "lopnur":  ("Lop Nur potash evaporation ponds, Xinjiang", 90.85, 40.45, 700, 0.18, "46TCK"),
    "hongjiannao": ("Hongjiannao Lake, Mu Us desert",        109.88, 39.07, 520, 0.14, "49SDD"),
}

def search(client, lon, lat, pad, dt):
    bbox = [lon-pad, lat-pad, lon+pad, lat+pad]
    return list(client.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=dt,
                query={"eo:cloud_cover": {"lt": CLOUD}}, max_items=400).items())

def read_win(href, lon, lat, half):
    with rasterio.open(href) as ds:
        xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
        row, col = ds.index(xs[0], ys[0])
        win = rasterio.windows.Window(col-half, row-half, 2*half, 2*half)
        return ds.read(1, window=win, out_shape=(2*half, 2*half),
                       resampling=Resampling.bilinear).astype("float32")

def render(rgb, title, path, dpi=150):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.figure(figsize=(6,6)); plt.imshow(rgb); plt.axis("off")
    plt.title(title, fontsize=12); plt.tight_layout()
    plt.savefig(path, dpi=dpi, bbox_inches="tight"); plt.close()

def test():
    client = Client.open(STAC)
    for key,(name,lon,lat,half,pad,ftile) in TARGETS.items():
        items = search(client, lon, lat, pad, START+"/"+END)
        if ftile:
            items = [it for it in items if it.id.split("_")[1]==ftile]
        items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 99))
        if not items:
            print(f"{key}: NO scene"); continue
        it = items[0]
        r = read_win(it.assets["red"].href, lon, lat, half)
        g = read_win(it.assets["green"].href, lon, lat, half)
        b = read_win(it.assets["blue"].href, lon, lat, half)
        def st(a): p=np.percentile(a,[2,98]); return np.clip((a-p[0])/(p[1]-p[0]+1e-6),0,1)
        render(np.dstack([st(r),st(g),st(b)]), f"{name}\n{it.id}",
               f"/tmp/test_{key}.png")
        print(f"{key}: {it.id} cloud={it.properties.get('eo:cloud_cover'):.2f}% -> /tmp/test_{key}.png")

def full(key):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    name, lon, lat, half, pad, ftile = TARGETS[key]
    client = Client.open(STAC)
    items = search(client, lon, lat, pad, START+"/"+END)
    def tile(it): return it.id.split("_")[1]
    dom = ftile or collections.Counter(tile(it) for it in items).most_common(1)[0][0]
    items = [it for it in items if tile(it)==dom]
    # one scene per date (lowest cloud that day), sorted chronologically
    by_day = {}
    for it in items:
        d = it.properties["datetime"][:10]
        if d not in by_day or it.properties.get("eo:cloud_cover",99) < by_day[d].properties.get("eo:cloud_cover",99):
            by_day[d] = it
    chosen = [by_day[d] for d in sorted(by_day)]
    # thin to <= MAXF evenly-spaced frames (smooth but not absurdly long)
    MAXF = 30
    if len(chosen) > MAXF:
        idx = np.linspace(0, len(chosen)-1, MAXF).round().astype(int)
        chosen = [chosen[i] for i in sorted(set(idx))]
    print(f"{key}: tile={dom}  candidate days={len(by_day)} -> using {len(chosen)} frames")

    bands = []
    wseries = []   # (day, water_fraction%) -- Server B segment_water tracked over time
    provenance = []
    for it in chosen:
        try:
            r = read_win(it.assets["red"].href, lon, lat, half)
            g = read_win(it.assets["green"].href, lon, lat, half)
            b = read_win(it.assets["blue"].href, lon, lat, half)
            nir = read_win(it.assets["nir"].href, lon, lat, half)
        except Exception as e:
            print("  skip", it.id, e); continue
        day = it.properties["datetime"][:10]
        ndwi = (g - nir) / (g + nir + 1e-6)
        wf = float(np.mean(ndwi > 0)) * 100.0
        bands.append((day, it.id, it.properties.get("eo:cloud_cover"), r, g, b))
        wseries.append((day, wf))
        provenance.append({
            "day": day,
            "id": it.id,
            "datetime": str(it.datetime),
            "cloud_cover": it.properties.get("eo:cloud_cover"),
            "water_fraction_percent": wf,
            "assets": {
                band: it.assets[band].href
                for band in ("red", "green", "blue", "nir")
                if band in it.assets
            },
        })
        print(f"  {day} {it.id} cloud={bands[-1][2]:.2f}% water={wf:.1f}%")
    if not bands:
        print("no frames"); return
    source_record = {
        "endpoint": STAC,
        "collection": "sentinel-2-l2a",
        "target_key": key,
        "target_name": name,
        "target_lon_lat": [lon, lat],
        "search_pad_deg": pad,
        "tile": dom,
        "datetime_range": f"{START}/{END}",
        "cloud_threshold": CLOUD,
        "items": provenance,
    }
    (PROVENANCE_DIR / f"{key}_sources.json").write_text(
        json.dumps(source_record, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    def gp(i): v=np.concatenate([d[3+i].ravel() for d in bands]); return np.percentile(v,[2,98])
    (rl,rh),(gl,gh),(bl,bh)=gp(0),gp(1),gp(2)
    def st(a,lo,hi): return np.clip((a-lo)/(hi-lo+1e-6),0,1)
    import matplotlib.pyplot as plt
    for i,(day,sid,cc,r,g,b) in enumerate(bands):
        rgb=np.dstack([st(r,rl,rh),st(g,gl,gh),st(b,bl,bh)])
        render(rgb, f"{name}\n{day}", OUT_DIR / f"{key}_a{i}.png")
    print(f"NFRAMES={len(bands)}  ({key}_a0..a{len(bands)-1})")

    # Server B water-segmentation tracked over seasons -> water-area trend
    days = [d for d,_ in wseries]; wf = [w for _,w in wseries]
    import datetime as _dt
    x = [_dt.date.fromisoformat(d) for d in days]
    plt.figure(figsize=(5,3))
    plt.plot(x, wf, "o-", color="#1f5fa8", lw=2, ms=4)
    plt.fill_between(x, wf, min(wf)-2, color="#1f5fa8", alpha=0.15)
    plt.ylabel("water area (% of AOI)"); plt.title("Server B segment_water -- seasonal water", fontsize=10)
    plt.grid(alpha=0.3); plt.xticks(rotation=30, fontsize=7); plt.tight_layout()
    plt.savefig(OUT_DIR / f"{key}_water.png", dpi=150, bbox_inches="tight"); plt.close()
    print(f"water trend: min={min(wf):.1f}% max={max(wf):.1f}%  -> {OUT_DIR / f'{key}_water.png'}")
    print(f"wrote {PROVENANCE_DIR / f'{key}_sources.json'}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv)>1 else "test"
    if mode=="test": test()
    elif mode=="full": full(sys.argv[2])
