# Media Reproducibility

This repo should not rely on pre-shipped gallery images as evidence. Every media
asset is generated from a recorded query and a script.

`media/`, `figures/`, and `generated/provenance/` are output locations. In Git
they contain only `.gitkeep` files.

`assets/preview/` is different: it is a small curated preview folder for
GitHub README and Hugging Face Space embeds. Preview assets are copied from a
successful local smoke/full run so users can see examples before waiting for
the long-running generation buttons.

The original source layer is not `figures/`. It is the provenance metadata
recorded under `generated/provenance/`, especially `media_sources.json`.
That metadata points to the remote STAC items, asset URLs, WMS image URLs, and
other open-data endpoints. The `figures/` directory contains processed
intermediate figures and frames produced by the render scripts.

## Step 1: Export Source URLs

```bash
python scripts/export_media_sources.py
```

This writes:

```text
generated/provenance/media_sources.json
```

The source export uses `source_queries.py`, an app-independent mirror of the
source-discovery behavior in the main MCP4RS server.

| Source-query function | URL field to inspect |
| --- | --- |
| `search_open_data` | `items[].assets.red`, `items[].assets.green`, `items[].assets.blue`, `items[].assets.nir` |
| `search_catalog` | `items[].assets.*` |
| `get_nightlights` | `image_url` |

## Step 2: Generate The Gallery

Fast smoke test:

```bash
python scripts/generate_media_gallery.py --skip-long --continue-on-error
```

Full generation:

```bash
python scripts/generate_media_gallery.py --continue-on-error
```

The full run writes generated media under `media/` and provenance files under
`generated/provenance/`.

It also writes intermediate static figures and GIF frames under `figures/`.
Those files are useful for inspection, but they are still processed outputs,
not original-source figures.

## Step 3: Refresh Embedded Preview Assets

After a successful local run, promote selected generated outputs into the
committed preview folder:

```bash
python scripts/update_preview_assets.py
```

For a complete smoke plus full preview set:

```bash
python scripts/export_media_sources.py
python scripts/generate_media_gallery.py --continue-on-error
python scripts/update_preview_assets.py --require-full
```

This copies selected files into `assets/preview/`, including:

| Preview asset | Source generated output |
| --- | --- |
| `assets/preview/smoke_s2_workflow.gif` | `media/s2_workflow.gif` |
| `assets/preview/smoke_physical_layers.png` | `media/physical_layers.png` |
| `assets/preview/intermediate_s2_rgb.png` | `figures/s2_rgb.png` |
| `assets/preview/full_desert_greening.gif` | `media/desert_greening.gif` |
| `assets/preview/full_lopnur_ponds.gif` | `media/lopnur_ponds.gif` |
| `assets/preview/full_hongjiannao_lake.gif` | `media/hongjiannao_lake.gif` |

Commit `assets/preview/` when you want GitHub and Hugging Face to show the
latest visual previews. Do not commit the runtime `media/`, `figures/`, or
`generated/provenance/` outputs.

## Generated Media Mapping

| Output | Source discovery | Processing pipeline |
| --- | --- | --- |
| `media/architecture.mmd` | No remote data source; generated as Mermaid source in `scripts/generate_media_gallery.py`. | Rendered by GitHub when embedded in Markdown; shown as Mermaid source in the Hugging Face Space. |
| `media/nightlights_prd.png` | `get_nightlights(...).image_url` from NASA GIBS WMS. | Download URL returned by source-query function. |
| `media/s2_workflow.gif` | `search_open_data` returns Sentinel-2 red/green/blue/NIR asset URLs. | `render_scene.py` -> `figures/s2_rgb.png`, `figures/s2_ndwi.png`, `figures/s2_water.png` -> GIF. |
| `media/desert_greening.gif` | Sentinel-2 STAC search in `render_desert.py`, recorded in `generated/provenance/desert_greening_sources.json`. | `render_desert.py` -> `figures/desert_a*.png` -> GIF. |
| `media/lopnur_ponds.gif` | Sentinel-2 STAC search in `render_lake.py full lopnur`, recorded in `generated/provenance/lopnur_sources.json`. | `render_lake.py` -> `figures/lopnur_a*.png` -> GIF. |
| `media/hongjiannao_lake.gif` | Sentinel-2 STAC search in `render_lake.py full hongjiannao`, recorded in `generated/provenance/hongjiannao_sources.json`. | `render_lake.py` -> `figures/hongjiannao_a*.png` -> GIF. |
| `media/physical_layers.png` | `search_catalog` for MODIS LST, GOES, OISST; NASA POWER URL for solar. | `examples/physical_layers.py`. |
| `media/resolution_compare.png` | `search_catalog` for NAIP, Sentinel-2, Landsat. | `examples/resolution_compare.py`. |
| `media/sar_optical.png` | Sentinel-2 and Sentinel-1 RTC STAC searches. | `examples/sar_demo.py`. |
| `media/terrain_3d.png` | Planetary Computer STAC search for Sentinel-2 and Copernicus DEM. | `examples/terrain_3d.py`. |
| `media/terrain_3d_views.png` | Planetary Computer STAC search for Copernicus DEM. | `examples/terrain_3d_views.py`. |

## Future Agent Skill Integration

This workflow can later become an Agent Skill:

```text
Skill receives a gallery request
  -> calls MCP4RS source-discovery tools
  -> records returned URLs and scene IDs
  -> runs selected render scripts
  -> validates generated files
  -> returns media outputs plus provenance JSON
```

That skill can then be used alongside the MCP server: the MCP provides data
access, while the skill performs the longer multi-step rendering workflow.

## Debug Session

Some outputs can show partial failure even when the overall script still writes
an image. This is expected when `--continue-on-error` is enabled, or when a
single remote endpoint is temporarily unavailable.

For example, `media/resolution_compare.png` can contain an `ERR` panel if one
of NAIP, Sentinel-2, or Landsat fails during that run. The script catches
per-panel exceptions and continues to save the final figure.

Use this quick debug loop:

```bash
python examples/resolution_compare.py media/resolution_compare.png
```

Capture logs for issue reports:

```bash
python examples/resolution_compare.py media/resolution_compare.png 2>&1 | tee generated/provenance/resolution_compare_debug.log
```

Then inspect these artifacts together:

- `media/resolution_compare.png`
- `generated/provenance/resolution_compare_debug.log`
- `generated/provenance/media_sources.json`

If the same command later succeeds without code changes, the most likely cause
is transient remote-service behavior (timeouts, rate limits, temporary catalog
or asset read failures) rather than a deterministic local bug.

## Notes

- Public STAC catalogs can grow over time. The scripts pin bbox, date range,
  cloud filters, and source collections; provenance records the exact scene IDs
  and asset URLs selected in a given run.
- Microsoft Planetary Computer asset URLs may be signed at runtime. Signed URLs
  can expire, so rerun the source export script when reproducing.
- `architecture.mmd` is explanatory, not a remote-sensing result. It is generated
  as Mermaid source, not as a Matplotlib or screenshot-style image.
- `--continue-on-error` is useful in Colab because one public service can be
  temporarily slow while the other outputs still succeed.
