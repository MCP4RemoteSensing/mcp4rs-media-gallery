#!/usr/bin/env python3
"""Copy selected generated gallery outputs into commit-ready preview assets.

The normal reproducibility outputs in media/, figures/, and generated/ are
ignored by Git. This script promotes a small, intentional subset into
assets/preview/ so GitHub README and the Hugging Face Space can show examples
before users run the long generation steps.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT / "media"
FIGURES_DIR = ROOT / "figures"
PREVIEW_DIR = ROOT / "assets" / "preview"

PREVIEW_MANIFEST = [
    ("media/nightlights_prd.png", "smoke_nightlights_prd.png"),
    ("media/s2_workflow.gif", "smoke_s2_workflow.gif"),
    ("media/physical_layers.png", "smoke_physical_layers.png"),
    ("media/resolution_compare.png", "smoke_resolution_compare.png"),
    ("media/sar_optical.png", "smoke_sar_optical.png"),
    ("media/terrain_3d.png", "smoke_terrain_3d.png"),
    ("media/terrain_3d_views.png", "smoke_terrain_3d_views.png"),
    ("figures/s2_rgb.png", "intermediate_s2_rgb.png"),
    ("figures/s2_ndwi.png", "intermediate_s2_ndwi.png"),
    ("figures/s2_water.png", "intermediate_s2_water.png"),
    ("media/desert_greening.gif", "full_desert_greening.gif"),
    ("media/lopnur_ponds.gif", "full_lopnur_ponds.gif"),
    ("media/hongjiannao_lake.gif", "full_hongjiannao_lake.gif"),
]


def update_preview_assets(require_full: bool) -> int:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing = []

    for source_name, preview_name in PREVIEW_MANIFEST:
        source = ROOT / source_name
        target = PREVIEW_DIR / preview_name
        if source.exists():
            shutil.copy2(source, target)
            copied += 1
            print(f"copied {source_name} -> assets/preview/{preview_name}")
        else:
            missing.append(source_name)

    if missing:
        print("\nmissing generated outputs:")
        for name in missing:
            print(f"- {name}")

        if require_full:
            print("\nRun the full gallery first:")
            print("python scripts/generate_media_gallery.py --continue-on-error")
            return 1

        print("\nTip: run smoke or full generation before refreshing previews:")
        print("python scripts/generate_media_gallery.py --skip-long --continue-on-error")
        print("python scripts/generate_media_gallery.py --continue-on-error")

    print(f"\nupdated {copied} preview asset(s) in assets/preview/")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="Fail if any full-gallery preview output is missing.",
    )
    args = parser.parse_args()
    raise SystemExit(update_preview_assets(require_full=args.require_full))


if __name__ == "__main__":
    main()
