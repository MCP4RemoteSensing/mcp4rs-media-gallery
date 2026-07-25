"""Upload generated MCP4RS media-gallery outputs to a Hugging Face Dataset.

Run this after `scripts/generate_media_gallery.py` has produced local outputs.
The script does not modify the source repo; it stages selected generated files
in a temporary folder and uploads that folder to a Hugging Face dataset repo.

The staged dataset includes generated media, intermediate figures, provenance
JSON, a structured `metadata.jsonl` index, a dataset card, and a draft
Croissant JSON-LD file with core and minimal Responsible AI fields.
"""

from __future__ import annotations
import csv
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from mimetypes import guess_type
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ID = "MCP4RemoteSensing/mcp4rs-media-gallery-outputs"
DATASET_NAME = "MCP4RS Reproducible Media Gallery Outputs"
DATASET_URL_TEMPLATE = "https://huggingface.co/datasets/{repo_id}"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
TOKEN_ENV_VAR = "HF_DATASET_TOKEN"
FALLBACK_TOKEN_ENV_VAR = "HF_TOKEN"

INCLUDE_DIRS = {
    "media": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.mmd"],
    "figures": ["*.png", "*.jpg", "*.jpeg", "*.gif"],
    "generated/provenance": ["*.json"],
    "assets/preview": ["*.png", "*.jpg", "*.jpeg", "*.gif"],
}

CREATORS = [
    {"name": "Dongping Liu", "role": "creator and MCP4RS co-owner"},
    {"name": "Luyao Zhang", "role": "creator and MCP4RS co-owner"},
]

OPEN_DATA_ACKNOWLEDGEMENTS = [
    "ESA/Copernicus Sentinel-1 and Sentinel-2 data accessed through open STAC-style catalogs where available.",
    "USGS/NASA Landsat open data accessed through open catalog assets where available.",
    "USDA NAIP imagery accessed through open catalog assets where available.",
    "Copernicus DEM terrain data accessed through open catalog assets where available.",
    "NASA GIBS/VIIRS nightlights WMS imagery.",
    "NASA MODIS land-surface temperature products used by the physical-layers example.",
    "NOAA GOES and NOAA OISST open datasets used by the physical-layers example.",
    "NASA POWER open meteorological and solar-resource data used by the physical-layers example.",
]

OPEN_SOURCE_TOOL_ACKNOWLEDGEMENTS = [
    "Python",
    "Gradio",
    "Hugging Face Hub",
    "pystac-client",
    "Microsoft Planetary Computer Python tooling",
    "Rasterio",
    "NumPy",
    "Matplotlib",
    "Pillow",
    "Requests",
]

CROISSANT_CITATION = (
    "Akhtar, M. et al. (2024). Croissant: A Metadata Format for ML-Ready "
    "Datasets. NeurIPS 2024 Datasets and Benchmarks Track. "
    "https://proceedings.neurips.cc/paper_files/paper/2024/hash/"
    "9547b09b722f2948ff3ddb5d86002bc0-Abstract-Datasets_and_Benchmarks_Track.html"
)


def iter_files(base: Path, patterns: Iterable[str]) -> Iterable[Path]:
    for pattern in patterns:
        yield from sorted(base.glob(pattern))


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def artifact_role(relative_path: str) -> str:
    if relative_path.startswith("media/"):
        return "final_gallery_media"
    if relative_path.startswith("figures/"):
        return "processed_intermediate_figure"
    if relative_path.startswith("generated/provenance/"):
        return "source_and_processing_provenance"
    if relative_path.startswith("assets/preview/"):
        return "curated_preview_asset"
    return "dataset_artifact"


def media_type(path: Path) -> str:
    guessed, _ = guess_type(path.name)
    if guessed:
        return guessed
    if path.suffix.lower() == ".mmd":
        return "text/vnd.mermaid"
    if path.suffix.lower() == ".jsonl":
        return "application/jsonl"
    return "application/octet-stream"


def copy_outputs(staging: Path) -> list[dict[str, object]]:
    manifest: list[dict[str, object]] = []
    for relative_dir, patterns in INCLUDE_DIRS.items():
        source_dir = ROOT / relative_dir
        if not source_dir.exists():
            continue
        for source_file in iter_files(source_dir, patterns):
            if source_file.name == ".gitkeep":
                continue
            target_file = staging / relative_dir / source_file.name
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            relative_path = str(target_file.relative_to(staging))
            manifest.append(
                {
                    "path": relative_path,
                    "source_folder": relative_dir,
                    "bytes": source_file.stat().st_size,
                    "kind": source_file.suffix.lower().lstrip("."),
                    "media_type": media_type(source_file),
                    "role": artifact_role(relative_path),
                }
            )
    return manifest

def write_metadata_csv(staging: Path, manifest: list[dict[str, object]]) -> None:
    """Write a viewer-friendly artifact index for Hugging Face Datasets."""
    descriptions = {
        "final_gallery_media": "Final PNG/GIF gallery output generated by the MCP4RS rendering workflow.",
        "processed_intermediate_figure": "Intermediate processed frame or diagnostic figure used to inspect or assemble final gallery media.",
        "source_and_processing_provenance": "JSON record of source URLs, catalog records, selected scenes, and processing context.",
        "curated_preview_asset": "Small selected preview asset embedded in the GitHub README and Hugging Face Space.",
    }
    fieldnames = [
        "path",
        "source_folder",
        "role",
        "file_format",
        "media_type",
        "bytes",
        "description",
    ]
    with (staging / "metadata.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in manifest:
            writer.writerow(
                {
                    "path": item["path"],
                    "source_folder": item["source_folder"],
                    "role": item["role"],
                    "file_format": item["kind"],
                    "media_type": item["media_type"],
                    "bytes": item["bytes"],
                    "description": descriptions.get(str(item["role"]), "Dataset artifact."),
                }
            )
def write_metadata_jsonl(staging: Path, manifest: list[dict[str, object]]) -> None:
    descriptions = {
        "final_gallery_media": "Final PNG/GIF gallery output generated by the MCP4RS rendering workflow.",
        "processed_intermediate_figure": "Intermediate processed frame or diagnostic figure used to inspect or assemble final gallery media.",
        "source_and_processing_provenance": "JSON record of source URLs, catalog records, selected scenes, and processing context.",
        "curated_preview_asset": "Small selected preview asset embedded in the GitHub README and Hugging Face Space.",
    }
    with (staging / "metadata.jsonl").open("w", encoding="utf-8") as handle:
        for item in manifest:
            row = {
                "path": item["path"],
                "source_folder": item["source_folder"],
                "role": item["role"],
                "file_format": item["kind"],
                "media_type": item["media_type"],
                "bytes": item["bytes"],
                "description": descriptions.get(str(item["role"]), "Dataset artifact."),
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def croissant_field(field_id: str, name: str, data_type: str) -> dict[str, object]:
    return {
        "@type": "cr:Field",
        "@id": f"artifact_index/{field_id}",
        "name": name,
        "dataType": data_type,
        "source": {
            "fileObject": {"@id": "metadata_jsonl"},
            "extract": {"column": name},
        },
    }


def write_croissant_metadata(
    staging: Path, repo_id: str, manifest: list[dict[str, object]]
) -> None:
    dataset_url = DATASET_URL_TEMPLATE.format(repo_id=repo_id)
    now = datetime.now(timezone.utc).isoformat()
    croissant = {
        "@context": {
            "@language": "en",
            "sc": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "rai": "http://mlcommons.org/croissant/RAI/",
            "prov": "http://www.w3.org/ns/prov#",
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
        },
        "@type": "sc:Dataset",
        "name": DATASET_NAME,
        "description": (
            "Generated sample outputs from the MCP4RS media-gallery workflow, "
            "including final gallery media, processed intermediate figures, "
            "curated previews, and source provenance JSON."
        ),
        "url": dataset_url,
        "license": LICENSE_URL,
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "datePublished": now,
        "creator": [
            {"@type": "sc:Person", "name": creator["name"]} for creator in CREATORS
        ],
        "citation": CROISSANT_CITATION,
        "keywords": [
            "remote sensing",
            "earth observation",
            "MCP",
            "geospatial",
            "open data",
            "Croissant",
            "Responsible AI metadata",
        ],
        "distribution": [
            {
                "@type": "cr:FileSet",
                "@id": "media_files",
                "name": "Final gallery media",
                "containedIn": {"@id": "dataset_repo"},
                "includes": "media/*",
                "encodingFormat": "image/*",
            },
            {
                "@type": "cr:FileSet",
                "@id": "figure_files",
                "name": "Processed intermediate figures",
                "containedIn": {"@id": "dataset_repo"},
                "includes": "figures/*",
                "encodingFormat": "image/*",
            },
            {
                "@type": "cr:FileSet",
                "@id": "provenance_files",
                "name": "Source and processing provenance",
                "containedIn": {"@id": "dataset_repo"},
                "includes": "generated/provenance/*.json",
                "encodingFormat": "application/json",
            },
            {
                "@type": "cr:FileObject",
                "@id": "metadata_jsonl",
                "name": "Structured artifact index",
                "contentUrl": "metadata.jsonl",
                "encodingFormat": "application/jsonl",
            },
        ],
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "artifact_index",
                "name": "Artifact index",
                "description": "One row per uploaded generated artifact.",
                "field": [
                    croissant_field("path", "path", "sc:Text"),
                    croissant_field("role", "role", "sc:Text"),
                    croissant_field("source_folder", "source_folder", "sc:Text"),
                    croissant_field("media_type", "media_type", "sc:Text"),
                    croissant_field("bytes", "bytes", "sc:Integer"),
                    croissant_field("description", "description", "sc:Text"),
                ],
            }
        ],
        "rai:dataLimitations": (
            "This dataset contains generated visualization outputs and provenance "
            "records for demonstration, documentation, teaching, and reproducibility. "
            "It is not a calibrated benchmark dataset, not a substitute for the "
            "underlying satellite products, and should not be used for operational "
            "environmental, emergency, legal, or safety-critical decisions."
        ),
        "rai:dataBiases": (
            "Spatial and temporal coverage reflects the small set of demonstration "
            "queries selected by the MCP4RS media-gallery workflow. Outputs may "
            "over-represent visually interesting scenes and under-represent other "
            "regions, seasons, sensors, cloud conditions, and land-cover types."
        ),
        "rai:personalSensitiveInformation": (
            "The dataset is built from open remote-sensing and environmental data "
            "products and generated visualizations. It is not intended to contain "
            "personal or sensitive information. Very high-resolution imagery, where "
            "present via upstream open data, should still be used responsibly."
        ),
        "rai:dataUseCases": (
            "Established use cases include reproducing the MCP4RS media-gallery "
            "demo, inspecting source provenance, teaching remote-sensing workflows, "
            "and documenting an MCP-style open-data rendering pipeline. Validity is "
            "not established for model training benchmarks, scientific measurement, "
            "policy evaluation, or operational monitoring without independent checks."
        ),
        "rai:dataSocialImpact": (
            "Positive impacts include more transparent remote-sensing demos, reusable "
            "educational examples, and lower recomputation cost. Risks include "
            "over-interpreting rendered samples as authoritative measurements or "
            "forgetting upstream data-provider constraints. Mitigations include "
            "provenance JSON, explicit limitations, and upstream acknowledgements."
        ),
        "rai:hasSyntheticData": False,
        "prov:wasDerivedFrom": OPEN_DATA_ACKNOWLEDGEMENTS,
        "prov:wasGeneratedBy": [
            "MCP4RS media-gallery scripts: export_media_sources.py, generate_media_gallery.py, and update_preview_assets.py.",
            "Open-source tools: " + ", ".join(OPEN_SOURCE_TOOL_ACKNOWLEDGEMENTS) + ".",
            f"Source repository commit: {git_commit()}.",
            f"Packaged artifact count: {len(manifest)}.",
        ],
        "sc:measurementTechnique": (
            "Open-data catalog and WMS source discovery followed by Python-based "
            "raster rendering, figure generation, GIF assembly, and provenance export."
        ),
        "sc:variableMeasured": [
            "artifact path",
            "artifact role",
            "media type",
            "file size",
            "source provenance",
        ],
    }
    (staging / "croissant_metadata.json").write_text(
        json.dumps(croissant, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_dataset_card(staging: Path, repo_id: str, manifest: list[dict[str, object]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    counts: dict[str, int] = {}
    for item in manifest:
        counts[item["source_folder"]] = counts.get(item["source_folder"], 0) + 1

    lines = [
        "---",
        "license: cc-by-4.0",
        "task_categories:",
        "- image-to-image",
        "- visual-question-answering",
        "pretty_name: MCP4RS Reproducible Media Gallery Outputs",
        "tags:",
        "- remote-sensing",
        "- earth-observation",
        "- mcp",
        "- geospatial",
        "- open-data",
        "- croissant",
        "- responsible-ai",
        "---",
        "",
        "# MCP4RS Reproducible Media Gallery Outputs",
        "",
        "This dataset contains generated sample outputs from the MCP4RS media-gallery workflow.",
        "It is intended to make the expensive or slow generated figures reusable for demos, documentation, teaching, and downstream analysis.",
        "",
        "The original open-data source evidence is recorded in `generated/provenance/*.json`.",
        "`figures/` contains processed intermediate frames, and `media/` contains final gallery PNG/GIF outputs.",
        "`assets/preview/` contains curated README and Hugging Face Space preview assets.",
        "",
        "## Creators",
        "",
        "| Name | Credit |",
        "| --- | --- |",
    ]
    for creator in CREATORS:
        lines.append(f"| {creator['name']} | {creator['role']} |")

    lines.extend(
        [
            "",
            "## NeurIPS 2026 Dataset Hosting Notes",
            "",
            "This package is prepared to align with the NeurIPS 2026 Evaluations & Datasets hosting guide:",
            "",
            "- The dataset is hosted on Hugging Face Datasets.",
            "- `metadata.jsonl` provides a structured artifact index.",
            "- `croissant_metadata.json` provides draft Croissant core metadata plus minimal Responsible AI fields.",
            "- Before OpenReview submission, download or verify the Hugging Face-generated Croissant file and validate the completed Croissant metadata with the NeurIPS-recommended validator.",
            "- If this dataset is part of a NeurIPS submission, include the dataset URL and the validated Croissant metadata file in OpenReview.",
            "",
            "Croissant reference: " + CROISSANT_CITATION,
            "",
            "## Responsible AI Summary",
            "",
            "- **Limitations:** generated visualization outputs for demo/reproducibility; not an operational monitoring or calibrated benchmark dataset.",
            "- **Biases:** selected demonstration scenes may over-represent visually interesting regions, sensors, dates, and conditions.",
            "- **Personal/sensitive information:** not intended to contain personal data; use high-resolution upstream imagery responsibly where applicable.",
            "- **Use cases:** demo reproduction, teaching, provenance inspection, and open-data workflow documentation.",
            "- **Social impact:** lowers recomputation cost and improves transparency, but users should not over-interpret rendered previews as authoritative measurements.",
            "- **Synthetic data:** `false`; outputs are rendered/processed from open remote-sensing and environmental source data, not synthetically generated scenes.",
            "",
            "## Open Data And Tool Acknowledgements",
            "",
            "Open data sources include:",
            "",
        ]
    )
    for acknowledgement in OPEN_DATA_ACKNOWLEDGEMENTS:
        lines.append(f"- {acknowledgement}")

    lines.extend(["", "Open-source tools include:", ""])
    for acknowledgement in OPEN_SOURCE_TOOL_ACKNOWLEDGEMENTS:
        lines.append(f"- {acknowledgement}")

    lines.extend(
        [
            "",
            "## Contents",
            "",
            "| Folder | Meaning | File count |",
            "| --- | --- | ---: |",
        ]
    )
    for folder in INCLUDE_DIRS:
        lines.append(f"| `{folder}/` | Generated workflow artifacts | {counts.get(folder, 0)} |")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            f"- Source repository commit: `{git_commit()}`",
            f"- Dataset upload time: `{now}`",
            f"- Dataset repo: `{repo_id}`",
            "",
            "To regenerate locally:",
            "",
            "```bash",
            "python scripts/export_media_sources.py",
            "python scripts/generate_media_gallery.py --continue-on-error",
            "python scripts/update_preview_assets.py --require-full",
            "```",
            "",
            "Then upload a refreshed dataset:",
            "",
            "```bash",
            f"python scripts/upload_hf_dataset.py --repo-id {repo_id}",
            "```",
            "",
            "The upload script creates:",
            "",
            "```text",
            "README.md",
            "metadata.jsonl",
            "dataset_manifest.json",
            "croissant_metadata.json",
            "```",
            "",
            "## Notes",
            "",
            "This is a generated-output dataset, not a replacement for the underlying satellite data providers.",
            "Please cite or acknowledge the original data providers listed in the provenance JSON files where appropriate.",
            "",
        ]
    )
    (staging / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_manifest(staging: Path, manifest: list[dict[str, object]], repo_id: str) -> None:
    payload = {
        "repo_id": repo_id,
        "source_repo_commit": git_commit(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(manifest),
        "creators": CREATORS,
        "open_data_acknowledgements": OPEN_DATA_ACKNOWLEDGEMENTS,
        "open_source_tool_acknowledgements": OPEN_SOURCE_TOOL_ACKNOWLEDGEMENTS,
        "croissant_reference": CROISSANT_CITATION,
        "files": manifest,
    }
    (staging / "dataset_manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload generated MCP4RS media-gallery outputs to a Hugging Face Dataset."
    )
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help=f"Hugging Face dataset repo ID. Defaults to {DEFAULT_REPO_ID}.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get(TOKEN_ENV_VAR)
        or os.environ.get(FALLBACK_TOKEN_ENV_VAR),
        help=(
            "Hugging Face dataset write token. Defaults to "
            f"{TOKEN_ENV_VAR}, then {FALLBACK_TOKEN_ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create the dataset as private if it does not exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Stage files and print the manifest without uploading.",
    )
    args = parser.parse_args()

    if not args.token and not args.dry_run:
        raise SystemExit(
            "Missing token. Set HF_DATASET_TOKEN, set HF_TOKEN, or pass --token."
        )

    with tempfile.TemporaryDirectory(prefix="mcp4rs_hf_dataset_") as tmp:
        staging = Path(tmp)
        manifest = copy_outputs(staging)
        if not manifest:
            raise SystemExit(
                "No generated outputs found. Run:\n"
                "  python scripts/export_media_sources.py\n"
                "  python scripts/generate_media_gallery.py --continue-on-error\n"
                "  python scripts/update_preview_assets.py --require-full"
            )

        write_manifest(staging, manifest, args.repo_id)
        
        write_metadata_jsonl(staging, manifest)
        write_metadata_csv(staging, manifest)
        write_croissant_metadata(staging, args.repo_id, manifest)
        write_dataset_card(staging, args.repo_id, manifest)

        print(f"Staged {len(manifest)} generated files for dataset upload:")
        for item in manifest:
            print(f"  {item['path']} ({item['bytes']} bytes)")
        print("\nGenerated dataset metadata:")
        print("  README.md")
        print("  metadata.jsonl")
        print("  dataset_manifest.json")
        print("  croissant_metadata.json")
        print("  metadata.csv")

        if args.dry_run:
            print(f"\nDry run only. Staged folder: {staging}")
            print("No upload performed.")
            return 0

        try:
            from huggingface_hub import HfApi, upload_folder
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "Missing dependency: huggingface_hub. Run:\n"
                "  python -m pip install -r requirements.txt"
            ) from exc

        api = HfApi(token=args.token)
        api.create_repo(
            repo_id=args.repo_id,
            repo_type="dataset",
            private=args.private,
            exist_ok=True,
        )
        upload_folder(
            repo_id=args.repo_id,
            repo_type="dataset",
            folder_path=str(staging),
            token=args.token,
            commit_message="Upload MCP4RS generated media gallery outputs",
        )
        print(f"\nUploaded dataset: {DATASET_URL_TEMPLATE.format(repo_id=args.repo_id)}")
        print("Next: open the dataset page, inspect the Croissant tab, and validate croissant_metadata.json.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
