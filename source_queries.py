#!/usr/bin/env python3
"""App-independent source discovery for the MCP4RS media gallery.

This module intentionally is not an MCP server. It mirrors the source-discovery
behavior of the MCP tools in the main MCP4RS repository so the media-gallery
pipeline can be demonstrated independently in Colab, Codespaces, or a small
Hugging Face Space wrapper.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/"
COLLECTION = "sentinel-2-l2a"

SOURCES: dict[str, dict[str, Any]] = {
    "sentinel-2": {
        "title": "Sentinel-2 L2A (optical, 10 m)",
        "endpoint": "https://earth-search.aws.element84.com/v1/",
        "collection": "sentinel-2-l2a",
        "gsd_m": 10,
        "provider": "AWS Open Data / Element84",
        "cloud_field": "eo:cloud_cover",
        "requires_signing": False,
        "preview_assets": ["red", "green", "blue", "nir"],
    },
    "naip": {
        "title": "NAIP aerial imagery (very high-res, ~0.6-1 m)",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "naip",
        "gsd_m": 0.6,
        "provider": "Microsoft Planetary Computer / USDA",
        "cloud_field": None,
        "requires_signing": True,
        "preview_assets": ["image"],
        "note": "US coverage only; pick a US bbox for this source.",
    },
    "landsat": {
        "title": "Landsat Collection 2 L2 (30 m, archive since 1982)",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "landsat-c2-l2",
        "gsd_m": 30,
        "provider": "Microsoft Planetary Computer / USGS",
        "cloud_field": "eo:cloud_cover",
        "requires_signing": True,
        "preview_assets": ["red", "green", "blue", "nir08"],
    },
    "sentinel-1": {
        "title": "Sentinel-1 GRD (SAR, all-weather, 10 m)",
        "endpoint": "https://earth-search.aws.element84.com/v1/",
        "collection": "sentinel-1-grd",
        "gsd_m": 10,
        "provider": "AWS Open Data / Element84",
        "cloud_field": None,
        "requires_signing": False,
        "preview_assets": ["vv", "vh"],
        "note": "Synthetic-aperture radar complements optical imagery.",
    },
    "nightlights": {
        "title": "VIIRS nighttime lights (low-light EO, ~500 m)",
        "endpoint": "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi",
        "collection": "VIIRS_SNPP_DayNightBand_ENCC",
        "gsd_m": 500,
        "provider": "NASA GIBS (VIIRS DNB / Black Marble)",
        "cloud_field": None,
        "requires_signing": False,
        "requires_auth": False,
        "access": "wms",
        "layers": ["VIIRS_SNPP_DayNightBand_ENCC", "VIIRS_Black_Marble"],
        "note": "Nighttime / low-light EO via NASA GIBS WMS.",
        "reference": "https://blackmarble.gsfc.nasa.gov/",
    },
    "thermal-lst": {
        "title": "MODIS land surface temperature (thermal IR, 1 km)",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "modis-11A2-061",
        "gsd_m": 1000,
        "provider": "Microsoft Planetary Computer / NASA MODIS",
        "cloud_field": None,
        "requires_signing": True,
        "preview_assets": ["LST_Day_1km"],
        "note": "Thermal infrared surface temperature. Scale 0.02 K.",
    },
    "weather-goes": {
        "title": "GOES ABI weather imagery (thermal IR clouds, ~2 km)",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "goes-cmi",
        "gsd_m": 2000,
        "provider": "Microsoft Planetary Computer / NOAA GOES",
        "cloud_field": None,
        "requires_signing": True,
        "preview_assets": ["C13_2km"],
        "note": "Geostationary weather imagery. Band 13 is clean IR window.",
    },
    "sst": {
        "title": "NOAA OISST sea-surface temperature (~25 km)",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1",
        "collection": "noaa-cdr-sea-surface-temperature-optimum-interpolation",
        "gsd_m": 25000,
        "provider": "Microsoft Planetary Computer / NOAA",
        "cloud_field": None,
        "requires_signing": True,
        "preview_assets": ["sst"],
        "note": "Ocean temperature proxy for fronts and warm currents.",
    },
}


def list_sources() -> dict[str, Any]:
    """List source catalogs the media-gallery pipeline can query."""

    return {
        "sources": {
            key: {
                "title": source["title"],
                "gsd_m": source["gsd_m"],
                "provider": source["provider"],
                "collection": source["collection"],
                "requires_signing": source.get("requires_signing", False),
                "requires_auth": source.get("requires_auth", False),
            }
            for key, source in SOURCES.items()
        },
        "note": "These entries mirror the source-discovery surface of MCP4RS.",
    }


def search_open_data(
    bbox: list[float],
    datetime_range: str | None = None,
    max_items: int = 5,
    max_cloud_cover: float = 20.0,
) -> dict[str, Any]:
    """Search Sentinel-2 L2A through AWS Earth Search and return asset URLs."""

    try:
        from pystac_client import Client
    except ImportError:
        return {
            "error": "pystac-client not installed. Run: pip install pystac-client",
            "hint": "Install requirements.txt before running source export.",
        }

    client = Client.open(STAC_ENDPOINT)
    search = client.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=datetime_range,
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        max_items=max_items,
        sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    )

    items = []
    for item in search.items():
        items.append(
            {
                "id": item.id,
                "datetime": str(item.datetime),
                "cloud_cover": round(item.properties.get("eo:cloud_cover", -1), 2),
                "assets": {
                    band: item.assets[band].href
                    for band in ("red", "green", "blue", "nir", "swir16", "swir22")
                    if band in item.assets
                },
            }
        )

    return {
        "endpoint": STAC_ENDPOINT,
        "collection": COLLECTION,
        "count": len(items),
        "items": items,
        "note": "Open Sentinel-2 data discovered through AWS Earth Search.",
    }


def search_catalog(
    source: str,
    bbox: list[float],
    datetime_range: str | None = None,
    max_items: int = 5,
    max_cloud_cover: float = 30.0,
) -> dict[str, Any]:
    """Search one configured open catalog by source name."""

    if source not in SOURCES:
        return {"error": f"unknown source '{source}'", "available": list(SOURCES)}
    src = SOURCES[source]

    if src.get("access") == "wms":
        return {
            "source": source,
            "title": src["title"],
            "native_gsd_m": src["gsd_m"],
            "provider": src["provider"],
            "access": "wms (imagery, not STAC items)",
            "hint": "call get_nightlights(bbox, date) for a ready-to-render image URL",
            "reference": src.get("reference"),
        }

    if src.get("requires_auth"):
        return {
            "source": source,
            "title": src["title"],
            "native_gsd_m": src["gsd_m"],
            "provider": src["provider"],
            "note": src.get("auth_note", "requires provider login"),
            "reference": src.get("reference"),
        }

    try:
        from pystac_client import Client
    except ImportError:
        return {"error": "pip install pystac-client"}

    kwargs: dict[str, Any] = {
        "collections": [src["collection"]],
        "bbox": bbox,
        "datetime": datetime_range,
        "max_items": max_items,
    }
    if src.get("cloud_field"):
        kwargs["query"] = {src["cloud_field"]: {"lt": max_cloud_cover}}
        kwargs["sortby"] = [
            {"field": f"properties.{src['cloud_field']}", "direction": "asc"}
        ]

    client = Client.open(src["endpoint"])
    search = client.search(**kwargs)

    signer = None
    if src.get("requires_signing"):
        try:
            import planetary_computer as pc

            signer = pc.sign
        except ImportError:
            signer = None

    items = []
    for item in search.items():
        assets = {}
        for asset_name in src["preview_assets"]:
            if asset_name in item.assets:
                href = item.assets[asset_name].href
                assets[asset_name] = signer(href) if signer else href
        cloud = item.properties.get(src["cloud_field"]) if src.get("cloud_field") else None
        items.append(
            {
                "id": item.id,
                "datetime": str(item.datetime),
                "gsd_m": item.properties.get("gsd", src["gsd_m"]),
                "cloud_cover": round(cloud, 2) if isinstance(cloud, (int, float)) else None,
                "assets": assets,
            }
        )

    return {
        "source": source,
        "title": src["title"],
        "endpoint": src["endpoint"],
        "collection": src["collection"],
        "native_gsd_m": src["gsd_m"],
        "count": len(items),
        "items": items,
        "signing": (
            "applied"
            if signer
            else ("needed: pip install planetary-computer" if src.get("requires_signing") else "n/a")
        ),
    }


def get_nightlights(
    bbox: list[float],
    date: str = "2023-01-01",
    layer: str = "VIIRS_SNPP_DayNightBand_ENCC",
    width: int = 512,
    height: int = 512,
) -> dict[str, Any]:
    """Build a NASA GIBS WMS URL for a nighttime-lights PNG."""

    if layer not in SOURCES["nightlights"]["layers"]:
        return {"error": f"unknown layer '{layer}'", "available": SOURCES["nightlights"]["layers"]}

    min_lon, min_lat, max_lon, max_lat = bbox
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "SRS": "EPSG:4326",
        "BBOX": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "WIDTH": width,
        "HEIGHT": height,
        "FORMAT": "image/png",
        "TIME": date,
    }
    url = SOURCES["nightlights"]["endpoint"] + "?" + urllib.parse.urlencode(params)
    return {
        "source": "nightlights",
        "layer": layer,
        "date": date,
        "bbox": bbox,
        "native_gsd_m": 500,
        "provider": "NASA GIBS (VIIRS DNB / Black Marble)",
        "image_url": url,
        "format": "image/png",
        "auth": "none (open)",
        "note": "Nighttime / low-light EO; render or download the URL directly.",
    }
