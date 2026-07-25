#!/usr/bin/env python3
"""Regenerate every media/gallery output from source queries and scripts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
MEDIA_DIR = ROOT / "media"
FIGURES_DIR = ROOT / "figures"
PROVENANCE_DIR = ROOT / "generated" / "provenance"

ARCHITECTURE_MERMAID = """flowchart TD
    mcp["Main MCP4RS server tools"]
    mirror["source_queries.py mirror"]
    sources["Open-data APIs and catalogs"]
    provenance["Provenance JSON"]
    renderers["Python render scripts"]
    gallery["Generated media gallery"]
    skill["Future Agent Skill"]

    mcp -.->|same source-discovery contract| mirror
    mirror -->|query URLs, STAC items, WMS images| sources
    sources -->|source asset links and scene IDs| provenance
    provenance -->|auditable inputs| renderers
    renderers -->|processed PNG/GIF outputs| gallery
    skill -.->|later calls MCP tools| mcp
    skill -.->|later orchestrates rendering| renderers
"""


def _run(args: list[str], cwd: Path = ROOT, continue_on_error: bool = False) -> bool:
    print("$", " ".join(args), f"(cwd={cwd})")
    try:
        subprocess.run(args, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        if continue_on_error:
            print(f"warning: command failed with exit code {exc.returncode}: {' '.join(args)}")
            return False
        raise


def _numeric_suffix(path: Path) -> int:
    match = re.search(r"_a(\d+)\.png$", path.name)
    return int(match.group(1)) if match else -1


def _frame_paths(pattern: str) -> list[Path]:
    return sorted(FIGURES_DIR.glob(pattern), key=_numeric_suffix)


def _fit_frames(paths: Iterable[Path]):
    from PIL import Image

    images = [Image.open(path).convert("RGBA") for path in paths]
    if not images:
        raise FileNotFoundError("no frames found")

    width = max(image.width for image in images)
    height = max(image.height for image in images)
    fitted = []
    for image in images:
        canvas = Image.new("RGBA", (width, height), "white")
        canvas.alpha_composite(image, ((width - image.width) // 2, (height - image.height) // 2))
        fitted.append(canvas.convert("P", palette=Image.ADAPTIVE))
    return fitted


def _make_gif(paths: list[Path], out: Path, duration_ms: int) -> None:
    frames = _fit_frames(paths)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print(f"wrote {out} from {len(paths)} frames")


def _download_nightlights() -> None:
    sys.path.insert(0, str(ROOT))
    from source_queries import get_nightlights

    result = get_nightlights(
        bbox=[113.8, 22.1, 114.5, 22.8],
        date="2023-01-01",
        layer="VIIRS_SNPP_DayNightBand_ENCC",
        width=1200,
        height=800,
    )
    url = result["image_url"]
    req = urllib.request.Request(url, headers={"User-Agent": "mcp4rs-open-earth-media/1.0"})
    data = urllib.request.urlopen(req, timeout=90).read()
    out = MEDIA_DIR / "nightlights_prd.png"
    out.write_bytes(data)
    (PROVENANCE_DIR / "nightlights_prd_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"wrote {out} from get_nightlights image_url")


def _write_architecture_mermaid() -> None:
    """Write the architecture as Mermaid source instead of a fragile image."""

    out = MEDIA_DIR / "architecture.mmd"
    out.write_text(ARCHITECTURE_MERMAID, encoding="utf-8")
    print(f"wrote {out}")


def _clean_generated_pngs() -> None:
    for directory in (MEDIA_DIR, FIGURES_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    for directory in (MEDIA_DIR, FIGURES_DIR):
        for pattern in ("*.png", "*.gif", "*.mmd", "*.svg"):
            for path in directory.glob(pattern):
                path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep generating independent outputs if one remote endpoint fails.",
    )
    parser.add_argument(
        "--skip-long",
        action="store_true",
        help="Skip long multi-frame lake/desert time-series renders.",
    )
    args = parser.parse_args()

    _clean_generated_pngs()

    _run([sys.executable, "export_media_sources.py"], cwd=SCRIPTS_DIR, continue_on_error=args.continue_on_error)
    try:
        _download_nightlights()
    except Exception as exc:
        if not args.continue_on_error:
            raise
        print(f"warning: nightlights download failed: {type(exc).__name__}: {exc}")
    _write_architecture_mermaid()

    example_outputs = [
        ("examples/physical_layers.py", MEDIA_DIR / "physical_layers.png"),
        ("examples/resolution_compare.py", MEDIA_DIR / "resolution_compare.png"),
        ("examples/sar_demo.py", MEDIA_DIR / "sar_optical.png"),
        ("examples/terrain_3d.py", MEDIA_DIR / "terrain_3d.png"),
        ("examples/terrain_3d_views.py", MEDIA_DIR / "terrain_3d_views.png"),
    ]
    for script, out in example_outputs:
        _run([sys.executable, script, str(out)], continue_on_error=args.continue_on_error)

    _run([sys.executable, "../render_scene.py"], cwd=SCRIPTS_DIR, continue_on_error=args.continue_on_error)
    s2_frames = [
        FIGURES_DIR / "s2_rgb.png",
        FIGURES_DIR / "s2_ndwi.png",
        FIGURES_DIR / "s2_water.png",
    ]
    if all(path.exists() for path in s2_frames):
        _make_gif(s2_frames, MEDIA_DIR / "s2_workflow.gif", duration_ms=1100)

    if not args.skip_long:
        _run([sys.executable, "../render_desert.py"], cwd=SCRIPTS_DIR, continue_on_error=args.continue_on_error)
        desert_frames = _frame_paths("desert_a*.png")
        if desert_frames:
            _make_gif(desert_frames, MEDIA_DIR / "desert_greening.gif", duration_ms=850)

        for key, media_name in (
            ("lopnur", "lopnur_ponds.gif"),
            ("hongjiannao", "hongjiannao_lake.gif"),
        ):
            _run(
                [sys.executable, "../render_lake.py", "full", key],
                cwd=SCRIPTS_DIR,
                continue_on_error=args.continue_on_error,
            )
            frames = _frame_paths(f"{key}_a*.png")
            if frames:
                _make_gif(frames, MEDIA_DIR / media_name, duration_ms=500)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "media": sorted(path.name for path in MEDIA_DIR.glob("*") if path.suffix in {".png", ".gif"}),
        "diagrams": sorted(path.name for path in MEDIA_DIR.glob("*.mmd")),
        "figures": sorted(path.name for path in FIGURES_DIR.glob("*.png")),
    }
    summary_path = PROVENANCE_DIR / "generated_media_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
