# Data Sources and Update Cadence

This document inventories the open-data sources used by the MCP4RS media-gallery
workflow and records whether each source updates regularly. It also clarifies
the difference between:

- upstream open-data catalogs, which may continue to receive new observations;
- the current gallery generation scripts, which use fixed demonstration AOIs and
  date ranges; and
- the Hugging Face Dataset upload, which is a reproducible snapshot of one
  generation run.

The bbox format used throughout the codebase is:

```text
[min_lon, min_lat, max_lon, max_lat]
```

## Short Answer

The generated dataset is not bounded by one global study area. It is assembled
from several fixed sample regions that demonstrate different remote-sensing
modalities: optical, SAR, nightlights, thermal, weather, ocean, solar, and DEM
terrain.

Most upstream sources are dynamic or catalog-maintained. The uploaded generated
dataset is static until the workflow is rerun and a new version is uploaded.

Future users can generate new dataset snapshots by changing bbox, date range,
source, cloud threshold, and output mode. The lower-level query functions already
accept `bbox` and `datetime_range`; the current Gradio UI does not yet expose all
of those controls for every renderer.

## Source Inventory

| Source key | Provider / platform | Collection or API | Used for | Current demo AOI / target | Current demo time range | Updates regularly? | Notes |
|---|---|---|---|---|---|---|---|
| `sentinel-2` | AWS Open Data / Element84 Earth Search; Microsoft Planetary Computer in some examples | `sentinel-2-l2a` | RGB, NDWI, water mask, desert greening, lake/pond time series, SAR optical comparison, terrain texture | Haikou Bay; Talatan Solar Park; Lop Nur; Hongjiannao; SFO; Hong Kong | 2017-2025 summer windows; 2025-01-01/2026-06-30 for lake targets; 2025-01-01/2025-06-30 for water workflow; 2022 or 2023 windows in examples | Yes | Sentinel-2 is an ongoing mission; AWS notes that new Sentinel data are added regularly. The generated output is a snapshot of selected scenes. |
| `sentinel-1` / `sentinel-1-rtc` | AWS Earth Search and Microsoft Planetary Computer | `sentinel-1-grd` or `sentinel-1-rtc` depending on script | SAR / optical comparison | Haikou Bay, Hainan: `[110.10, 19.90, 110.55, 20.12]` | `2023-12-28/2023-12-28` for SAR mosaic in current script | Yes, catalog-maintained | SAR can support all-weather and night observation. Availability depends on orbit, processing collection, and catalog platform. |
| `naip` | Microsoft Planetary Computer / USDA | `naip` | Very-high-resolution comparison | San Francisco International Airport: `[-122.397, 37.605, -122.355, 37.632]` | `2018-01-01/2024-12-31` | Periodic, not continuous | NAIP is US-only and updated by acquisition campaigns, not as a daily global satellite feed. |
| `landsat` | Microsoft Planetary Computer / USGS | `landsat-c2-l2` | 30 m resolution comparison | San Francisco International Airport: `[-122.397, 37.605, -122.355, 37.632]` | `2022-06-01/2022-09-30` | Yes | Landsat is a long-running satellite archive and ongoing observation program; selected demo scenes are fixed by the script's query window. |
| `nightlights` | NASA GIBS / VIIRS DNB / Black Marble | WMS layer `VIIRS_SNPP_DayNightBand_ENCC` | Pearl River Delta nightlights PNG | Pearl River Delta: `[113.8, 22.1, 114.5, 22.8]` | `2023-01-01` | Yes, product-dependent | The script builds a WMS `GetMap` URL with a `TIME` parameter. NASA Black Marble / VIIRS products are designed for repeated nighttime-light observation, but exact layer latency depends on the served product. |
| `thermal-lst` | Microsoft Planetary Computer / NASA MODIS | `modis-11A2-061` | Land surface temperature panel | North China Plain: `[112, 32, 120, 40]` | `2023-07-01/2023-08-31` | Yes, catalog-maintained | MODIS LST is a recurring thermal product. The demo uses a historical summer window. |
| `weather-goes` | Microsoft Planetary Computer / NOAA GOES | `goes-cmi` | Weather / cloud-top thermal IR panel | Gulf of Mexico: `[-98, 20, -80, 32]` | `2023-08-29/2023-08-31` | Yes | GOES is a geostationary weather source with frequent observations; the demo uses a short historical storm/cloud window. |
| `sst` | Microsoft Planetary Computer / NOAA | `noaa-cdr-sea-surface-temperature-optimum-interpolation` | Sea-surface temperature panel | NW Pacific / Kuroshio: `[118, 18, 145, 40]` | `2023-08-01/2023-08-05` | Yes, product-dependent | OISST is a recurring ocean temperature product. The generated figure is a fixed historical snapshot. |
| `cop-dem-glo-30` | Microsoft Planetary Computer / Copernicus DEM | `cop-dem-glo-30` | Hong Kong terrain and 3D views | Hong Kong: `[114.10, 22.19, 114.30, 22.35]` | Static terrain source; no observation date range in current query | No regular scene update expected | DEM is a relatively static elevation product, unlike daily or repeat-pass satellite imagery. |
| `nasa-power` | NASA POWER API | `temporal/climatology/regional` with `ALLSKY_SFC_SW_DWN` | Solar irradiance panel | South China / Hainan: `[106, 16, 116, 26]` | Climatology endpoint, no single observation date in current query | Product/API maintained; climatology itself is not a live scene feed | The current script uses climatology rather than daily or monthly POWER endpoints. |
| Generated architecture | Local script | `media/architecture.mmd` | Workflow diagram | Not geospatial | Generated at run time | Not applicable | This is documentation output, not remote-sensing data. |

## Current Generated Snapshot Range

The current gallery generation scripts cover approximately:

```text
2017-06-01 through 2026-06-30
```

This is the union of all configured time windows, not a guarantee that every
source covers the whole period.

| Output | Source data | Current spatial input | Current temporal input |
|---|---|---|---|
| `media/s2_workflow.gif` | Sentinel-2 L2A | Search bbox `[110.10, 19.90, 110.55, 20.12]`; render bbox becomes the selected STAC item footprint | `2025-01-01/2025-06-30` |
| `media/desert_greening.gif` | Sentinel-2 L2A | Search bbox `[100.44, 36.08, 100.74, 36.34]`; target `(100.575, 36.200)`; tile `47SPA` | Annual summer windows, `2017-06-01` to `2025-09-30` |
| `media/lopnur_ponds.gif` | Sentinel-2 L2A | Target `(90.85, 40.45)`; search pad `0.18`; tile `46TCK` | `2025-01-01/2026-06-30` |
| `media/hongjiannao_lake.gif` | Sentinel-2 L2A | Target `(109.88, 39.07)`; search pad `0.14`; tile `49SDD` | `2025-01-01/2026-06-30` |
| `media/nightlights_prd.png` | NASA GIBS VIIRS DNB | `[113.8, 22.1, 114.5, 22.8]` | `2023-01-01` |
| `media/physical_layers.png` | MODIS LST, NASA POWER, GOES, OISST | North China, South China/Hainan, Gulf of Mexico, NW Pacific | Mostly 2023 historical windows; NASA POWER climatology for solar |
| `media/resolution_compare.png` | NAIP, Sentinel-2, Landsat | SFO: `[-122.397, 37.605, -122.355, 37.632]` | NAIP `2018-01-01/2024-12-31`; Sentinel-2 and Landsat `2022-06-01/2022-09-30` |
| `media/sar_optical.png` | Sentinel-2 and Sentinel-1 RTC | Haikou Bay: `[110.10, 19.90, 110.55, 20.12]` | Sentinel-2 `2023-01-01/2023-12-31`; Sentinel-1 `2023-12-28/2023-12-28` |
| `media/terrain_3d.png` | Copernicus DEM plus Sentinel-2 | Hong Kong: `[114.10, 22.19, 114.30, 22.35]` | DEM static; Sentinel-2 `2023-01-01/2023-12-31` |
| `media/terrain_3d_views.png` | Copernicus DEM | Hong Kong: `[114.10, 22.19, 114.30, 22.35]` | DEM static |

## Can Users Generate New Dataset Ranges?

Yes. The source-discovery layer is already parameterized:

```python
search_open_data(
    bbox=[min_lon, min_lat, max_lon, max_lat],
    datetime_range="YYYY-MM-DD/YYYY-MM-DD",
    max_items=5,
    max_cloud_cover=20.0,
)
```

```python
search_catalog(
    source="sentinel-2",
    bbox=[min_lon, min_lat, max_lon, max_lat],
    datetime_range="YYYY-MM-DD/YYYY-MM-DD",
    max_items=5,
    max_cloud_cover=30.0,
)
```

```python
get_nightlights(
    bbox=[min_lon, min_lat, max_lon, max_lat],
    date="YYYY-MM-DD",
    layer="VIIRS_SNPP_DayNightBand_ENCC",
)
```

The current render scripts still hard-code showcase AOIs so the demo can run
reliably and produce stable visuals. A future version can expose these controls
in the UI:

| Future control | Why it matters |
|---|---|
| Region name | Records human-readable context in provenance and dataset cards. |
| Bbox | Defines the geospatial extent of the generated dataset. |
| Start and end date | Defines temporal coverage for STAC or WMS queries. |
| Source collection | Lets users choose Sentinel-2, Sentinel-1, Landsat, NAIP, MODIS, GOES, OISST, etc. |
| Cloud-cover threshold | Controls optical-scene quality and scene availability. |
| Max items / max frames | Controls compute time and output size. |
| Output mode | Supports smoke tests, full time series, or dataset-publication runs. |

## Dynamic Source vs Static Dataset Snapshot

| Layer | Does it update? | What changes over time? |
|---|---|---|
| Upstream open-data source | Usually yes, except static products such as DEM | New catalog items, revised metadata, reprocessed products, or newly available imagery. |
| Source-query result | Yes, if rerun against a dynamic catalog | The selected scene IDs can change if new lower-cloud or newer items enter the query window. |
| Generated local outputs | No | PNG/GIF/provenance files remain fixed until scripts are rerun. |
| Hugging Face Dataset upload | No, per uploaded revision | It is a versioned snapshot. New versions require regeneration and upload. |

For reproducibility, each upload should preserve:

- `generated/provenance/media_sources.json`
- source-specific provenance files such as `s2_workflow_sources.json`,
  `desert_greening_sources.json`, `lopnur_sources.json`, and
  `hongjiannao_sources.json`
- `dataset_manifest.json`
- `metadata.jsonl`
- `croissant_metadata.json`

## Provider References

- AWS Open Data Sentinel-2 L2A COGs: https://registry.opendata.aws/sentinel-2-l2a-cogs/
- Element84 Earth Search: https://earth-search.aws.element84.com/v1/
- Element84 Earth Search overview: https://github.com/Element84/earth-search
- Microsoft Planetary Computer Data Catalog: https://planetarycomputer.microsoft.com/catalog
- NASA GIBS WMS: https://gibs.earthdata.nasa.gov/
- NASA Black Marble / VIIRS: https://www.earthdata.nasa.gov/data/projects/black-marble
- NASA POWER API: https://power.larc.nasa.gov/docs/services/api/
- NASA POWER Climatology API: https://power.larc.nasa.gov/docs/services/api/temporal/climatology/
- Copernicus DEM on Planetary Computer: https://planetarycomputer.microsoft.com/dataset/group/copernicus-dem

## Recommended Next Implementation

For the next dataset-oriented release, add one user-configurable generation entry
point that writes a region-specific output folder:

```text
generated/runs/<region_slug>/
```

Each run should include:

```text
config.json
source_provenance.json
metadata.jsonl
figures/
media/
```

This would make it clear which geospatial range, time range, source collection,
and cloud/filter settings created each dataset snapshot.
