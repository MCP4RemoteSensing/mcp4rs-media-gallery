#!/usr/bin/env python3
"""Export source-query provenance for the reproducible media gallery.

This script answers: "Which URL did the MCP/search layer return before the
media renderer processed it?" It writes a JSON manifest under
generated/provenance/media_sources.json by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _compact_items(result: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    compact = []
    for item in result.get("items", [])[:limit]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "id": item.get("id"),
                "datetime": item.get("datetime"),
                "cloud_cover": item.get("cloud_cover"),
                "gsd_m": item.get("gsd_m"),
                "assets": item.get("assets", {}),
            }
        )
    return compact


def _call_tool(
    key: str,
    tool_name: str,
    fn: Callable[..., dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = fn(**args)
    except Exception as exc:  # keep the manifest useful during endpoint outages
        return {
            "key": key,
            "tool": tool_name,
            "arguments": args,
            "error": f"{type(exc).__name__}: {exc}",
        }

    record: dict[str, Any] = {
        "key": key,
        "tool": tool_name,
        "arguments": args,
        "endpoint": result.get("endpoint"),
        "collection": result.get("collection"),
        "source": result.get("source"),
        "title": result.get("title"),
        "count": result.get("count"),
        "signing": result.get("signing"),
    }
    if "image_url" in result:
        record["image_url"] = result["image_url"]
    if "items" in result:
        record["items"] = _compact_items(result)
    if "hint" in result:
        record["hint"] = result["hint"]
    if "reference" in result:
        record["reference"] = result["reference"]
    return record


def _nasa_power_url(bbox: list[float]) -> str:
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN",
        "community": "RE",
        "longitude-min": bbox[0],
        "longitude-max": bbox[2],
        "latitude-min": bbox[1],
        "latitude-max": bbox[3],
        "format": "JSON",
    }
    return (
        "https://power.larc.nasa.gov/api/temporal/climatology/regional?"
        + urllib.parse.urlencode(params)
    )


def build_manifest() -> dict[str, Any]:
    """Run source searches and return a provenance manifest."""

    from source_queries import get_nightlights, search_catalog, search_open_data

    records = [
        _call_tool(
            "s2_workflow_and_water_fraction",
            "search_open_data",
            search_open_data,
            {
                "bbox": [110.10, 19.90, 110.55, 20.12],
                "datetime_range": "2025-01-01/2025-06-30",
                "max_items": 3,
                "max_cloud_cover": 10.0,
            },
        ),
        _call_tool(
            "nightlights_prd_png_source",
            "get_nightlights",
            get_nightlights,
            {
                "bbox": [113.8, 22.1, 114.5, 22.8],
                "date": "2023-01-01",
                "layer": "VIIRS_SNPP_DayNightBand_ENCC",
                "width": 1200,
                "height": 800,
            },
        ),
        _call_tool(
            "resolution_compare_naip",
            "search_catalog",
            search_catalog,
            {
                "source": "naip",
                "bbox": [-122.397, 37.605, -122.355, 37.632],
                "datetime_range": "2018-01-01/2024-12-31",
                "max_items": 3,
                "max_cloud_cover": 30.0,
            },
        ),
        _call_tool(
            "resolution_compare_sentinel2",
            "search_catalog",
            search_catalog,
            {
                "source": "sentinel-2",
                "bbox": [-122.397, 37.605, -122.355, 37.632],
                "datetime_range": "2022-06-01/2022-09-30",
                "max_items": 3,
                "max_cloud_cover": 10.0,
            },
        ),
        _call_tool(
            "resolution_compare_landsat",
            "search_catalog",
            search_catalog,
            {
                "source": "landsat",
                "bbox": [-122.397, 37.605, -122.355, 37.632],
                "datetime_range": "2022-06-01/2022-09-30",
                "max_items": 3,
                "max_cloud_cover": 10.0,
            },
        ),
        _call_tool(
            "sar_source_search",
            "search_catalog",
            search_catalog,
            {
                "source": "sentinel-1",
                "bbox": [110.10, 19.90, 110.55, 20.12],
                "datetime_range": "2023-12-28/2023-12-28",
                "max_items": 6,
                "max_cloud_cover": 30.0,
            },
        ),
        _call_tool(
            "thermal_lst_source_search",
            "search_catalog",
            search_catalog,
            {
                "source": "thermal-lst",
                "bbox": [112, 32, 120, 40],
                "datetime_range": "2023-07-01/2023-08-31",
                "max_items": 5,
                "max_cloud_cover": 30.0,
            },
        ),
        _call_tool(
            "weather_goes_source_search",
            "search_catalog",
            search_catalog,
            {
                "source": "weather-goes",
                "bbox": [-98, 20, -80, 32],
                "datetime_range": "2023-08-29/2023-08-31",
                "max_items": 5,
                "max_cloud_cover": 30.0,
            },
        ),
        _call_tool(
            "sst_source_search",
            "search_catalog",
            search_catalog,
            {
                "source": "sst",
                "bbox": [118, 18, 145, 40],
                "datetime_range": "2023-08-01/2023-08-05",
                "max_items": 5,
                "max_cloud_cover": 30.0,
            },
        ),
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Source URLs and search results used before rendering media gallery outputs.",
        "mcp_tool_records": records,
        "script_internal_open_data_queries": {
            "terrain_3d_copernicus_dem": {
                "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1",
                "collection": "cop-dem-glo-30",
                "bbox": [114.10, 22.19, 114.30, 22.35],
                "note": "Used by examples/terrain_3d.py and examples/terrain_3d_views.py.",
            },
            "physical_layers_nasa_power": {
                "url": _nasa_power_url([106.0, 16.0, 116.0, 26.0]),
                "note": "Used by examples/physical_layers.py.",
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(ROOT / "generated" / "provenance" / "media_sources.json"),
        help="Path for the generated JSON manifest.",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
