"""Hugging Face Space wrapper for the MCP4RS media gallery pipeline.

This app intentionally exposes only the reproducible media workflow:
1. export source URLs and STAC/WMS provenance;
2. generate gallery PNG/GIF outputs from the Python scripts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent
MEDIA_DIR = ROOT / "media"
FIGURES_DIR = ROOT / "figures"
PROVENANCE_DIR = ROOT / "generated" / "provenance"
PREVIEW_DIR = ROOT / "assets" / "preview"

SAMPLE_PROVENANCE = {
    "purpose": "Source URLs and search results used before rendering media gallery outputs.",
    "mcp_tool_records": [
        {
            "key": "nightlights_prd_png_source",
            "tool": "get_nightlights",
            "source": "nightlights",
            "image_url": "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?...",
            "note": "NASA GIBS WMS returns a display-ready PNG URL.",
        },
        {
            "key": "s2_workflow_and_water_fraction",
            "tool": "search_open_data",
            "collection": "sentinel-2-l2a",
            "count": 3,
            "items": [
                {
                    "id": "S2A_..._L2A",
                    "cloud_cover": 1.23,
                    "assets": {
                        "red": "https://.../B04.tif",
                        "green": "https://.../B03.tif",
                        "blue": "https://.../B02.tif",
                        "nir": "https://.../B08.tif",
                    },
                }
            ],
        },
    ],
}

SMOKE_PREVIEW = """
### Preview: Generate Smoke Gallery

Runs:

```bash
python scripts/generate_media_gallery.py --skip-long --continue-on-error
```

| Expected output | What it means |
| --- | --- |
| `media/architecture.mmd` | Mermaid architecture source. |
| `media/nightlights_prd.png` | Display-ready NASA GIBS nightlights image. |
| `media/s2_workflow.gif` | Sentinel-2 RGB -> NDWI -> water-mask workflow. |
| `media/physical_layers.png` | Processed MODIS/GOES/OISST/NASA POWER layers. |
| `media/resolution_compare.png` | Processed NAIP/Sentinel-2/Landsat comparison. |
| `media/sar_optical.png` | Processed Sentinel-2 optical and Sentinel-1 SAR comparison. |
| `media/terrain_3d.png` | Processed Sentinel-2 plus Copernicus DEM terrain view. |
| `figures/*.png` | Intermediate processed frames used by the gallery. |
"""

FULL_PREVIEW = """
### Preview: Generate Full Gallery

Runs:

```bash
python scripts/generate_media_gallery.py --continue-on-error
```

Includes the smoke gallery plus longer time-series GIFs:

| Expected output | What it means |
| --- | --- |
| `media/desert_greening.gif` | Multi-date Sentinel-2 desert-greening animation. |
| `media/lopnur_ponds.gif` | Multi-date Sentinel-2 Lop Nur ponds animation. |
| `media/hongjiannao_lake.gif` | Multi-date Sentinel-2 Hongjiannao lake animation. |
| `figures/desert_a*.png` | Processed frames for `desert_greening.gif`. |
| `figures/lopnur_a*.png` | Processed frames for `lopnur_ponds.gif`. |
| `figures/hongjiannao_a*.png` | Processed frames for `hongjiannao_lake.gif`. |
"""

PREVIEW_ASSET_DESCRIPTIONS = {
    "smoke_nightlights_prd.png": "Smoke: NASA GIBS nightlights image returned from a display-ready source URL.",
    "smoke_s2_workflow.gif": "Smoke: Sentinel-2 RGB, NDWI, and water-mask workflow animation.",
    "smoke_physical_layers.png": "Smoke: processed physical climate/ocean/energy layers.",
    "smoke_resolution_compare.png": "Smoke: NAIP, Sentinel-2, and Landsat resolution comparison.",
    "smoke_sar_optical.png": "Smoke: Sentinel-2 optical and Sentinel-1 SAR comparison.",
    "smoke_terrain_3d.png": "Smoke: Sentinel-2 plus Copernicus DEM terrain rendering.",
    "smoke_terrain_3d_views.png": "Smoke: multi-view Copernicus DEM terrain rendering.",
    "intermediate_s2_rgb.png": "Intermediate: processed Sentinel-2 RGB frame.",
    "intermediate_s2_ndwi.png": "Intermediate: processed NDWI frame.",
    "intermediate_s2_water.png": "Intermediate: processed water-mask frame.",
    "full_desert_greening.gif": "Full: desert-greening multi-date Sentinel-2 animation.",
    "full_lopnur_ponds.gif": "Full: Lop Nur ponds multi-date Sentinel-2 animation.",
    "full_hongjiannao_lake.gif": "Full: Hongjiannao lake multi-date Sentinel-2 animation.",
}


def _run_command(args: list[str]) -> str:
    process = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = []
    if process.stdout:
        output.append(process.stdout.strip())
    if process.stderr:
        output.append("STDERR:\n" + process.stderr.strip())
    output.append(f"exit_code={process.returncode}")
    return "\n\n".join(output)


def _image_outputs() -> list[tuple[str, str]]:
    paths = sorted(MEDIA_DIR.glob("*.png")) + sorted(MEDIA_DIR.glob("*.gif"))
    paths += sorted(FIGURES_DIR.glob("*.png"))
    return [(str(path), path.name) for path in paths]


def _preview_outputs(prefix: str | None = None) -> list[tuple[str, str]]:
    if not PREVIEW_DIR.exists():
        return []

    paths = sorted(PREVIEW_DIR.glob("*.png")) + sorted(PREVIEW_DIR.glob("*.gif"))
    if prefix is not None:
        paths = [path for path in paths if path.name.startswith(prefix)]

    return [
        (str(path), PREVIEW_ASSET_DESCRIPTIONS.get(path.name, path.name))
        for path in paths
    ]


def _file_outputs() -> list[str]:
    paths = sorted(MEDIA_DIR.glob("*.png")) + sorted(MEDIA_DIR.glob("*.gif"))
    paths += sorted(MEDIA_DIR.glob("*.mmd"))
    paths += sorted(FIGURES_DIR.glob("*.png"))
    paths += sorted(PROVENANCE_DIR.glob("*.json"))
    return [str(path) for path in paths]


def _manifest_text() -> str:
    manifest = PROVENANCE_DIR / "media_sources.json"
    if not manifest.exists():
        return "{}"
    try:
        return json.dumps(json.loads(manifest.read_text(encoding="utf-8")), indent=2)
    except json.JSONDecodeError:
        return manifest.read_text(encoding="utf-8")


def _architecture_text() -> str:
    generated = MEDIA_DIR / "architecture.mmd"
    if generated.exists():
        return generated.read_text(encoding="utf-8")

    try:
        from scripts.generate_media_gallery import ARCHITECTURE_MERMAID

        return ARCHITECTURE_MERMAID
    except Exception:
        return "Run Generate Smoke Gallery to write media/architecture.mmd."


def export_sources():
    log = _run_command(["scripts/export_media_sources.py"])
    return log, _manifest_text(), _architecture_text(), _image_outputs(), _file_outputs()


def generate_smoke_gallery():
    log = _run_command(
        ["scripts/generate_media_gallery.py", "--skip-long", "--continue-on-error"]
    )
    return log, _manifest_text(), _architecture_text(), _image_outputs(), _file_outputs()


def generate_full_gallery():
    log = _run_command(["scripts/generate_media_gallery.py", "--continue-on-error"])
    return log, _manifest_text(), _architecture_text(), _image_outputs(), _file_outputs()


def refresh_outputs():
    return (
        "refreshed generated outputs",
        _manifest_text(),
        _architecture_text(),
        _image_outputs(),
        _file_outputs(),
    )


with gr.Blocks(title="MCP4RS Media Gallery") as demo:
    gr.Markdown(
        """
        # MCP4RS Reproducible Media Gallery

        This Space is a web demonstration of the media-gallery extension. The
        main MCP4RS server discovers open remote-sensing source URLs and asset
        links; this standalone pipeline mirrors that source-discovery layer,
        records provenance, and generates PNG/GIF gallery outputs.

        **What you will see:** source provenance JSON from the query layer,
        Mermaid architecture source, generated gallery images/GIFs under
        `media/`, and processed intermediate figures under `figures/`.

        Some source queries return display-ready image URLs, such as NASA GIBS
        nightlights. Most STAC queries return asset URLs and scene IDs first;
        the render scripts then process those assets into visible figures.
        """
    )
    gr.Markdown(
        """
        ## Preview Gallery

        These curated preview assets are intentionally committed under
        `assets/preview/` so GitHub and Hugging Face can show what users should
        expect before they wait for source queries, downloads, and rendering.
        Runtime outputs are still generated under `media/`, `figures/`, and
        `generated/provenance/`.

        After a successful full run, you can also publish those generated
        outputs as a separate Hugging Face Dataset under
        `MCP4RemoteSensing/mcp4rs-media-gallery-outputs` with
        `python scripts/upload_hf_dataset.py`. The upload package includes the
        media outputs plus `metadata.jsonl`, `dataset_manifest.json`, and draft
        Croissant/Responsible-AI metadata for NeurIPS-style hosting.
        """
    )
    with gr.Row():
        smoke_preview_gallery = gr.Gallery(
            value=_preview_outputs("smoke_"),
            label="Embedded Smoke Gallery Preview",
            columns=3,
            height="auto",
        )
        full_preview_gallery = gr.Gallery(
            value=_preview_outputs("full_"),
            label="Embedded Full Gallery Preview",
            columns=3,
            height="auto",
        )
    intermediate_preview_gallery = gr.Gallery(
        value=_preview_outputs("intermediate_"),
        label="Embedded Intermediate Figures Preview",
        columns=3,
        height="auto",
    )

    with gr.Accordion("Sample Source URL Export And Expected Commands", open=True):
        gr.Markdown(
            """
            The buttons below may take time because they query open-data
            catalogs, download remote assets, and render processed outputs.
            These examples explain the source records and command outputs behind
            the embedded preview gallery above.
            """
        )
        gr.Code(
            value=json.dumps(SAMPLE_PROVENANCE, indent=2),
            label="Sample Export Source URLs Output",
            language="json",
        )
        with gr.Row():
            gr.Markdown(SMOKE_PREVIEW)
            gr.Markdown(FULL_PREVIEW)

    with gr.Row():
        export_button = gr.Button("Export Source URLs", variant="secondary")
        smoke_button = gr.Button("Generate Smoke Gallery", variant="primary")
        full_button = gr.Button("Generate Full Gallery")
        refresh_button = gr.Button("Refresh Outputs")

    log_box = gr.Textbox(label="Command Log", lines=12)
    manifest_box = gr.Code(label="Source Provenance", language="json")
    architecture_box = gr.Code(label="Architecture Mermaid", language="markdown")
    gallery = gr.Gallery(
        label="Generated And Processed Media",
        columns=3,
        height="auto",
    )
    downloads = gr.File(label="Generated Files", file_count="multiple")

    outputs = [log_box, manifest_box, architecture_box, gallery, downloads]
    export_button.click(export_sources, outputs=outputs)
    smoke_button.click(generate_smoke_gallery, outputs=outputs)
    full_button.click(generate_full_gallery, outputs=outputs)
    refresh_button.click(refresh_outputs, outputs=outputs)


if __name__ == "__main__":
    demo.launch()
