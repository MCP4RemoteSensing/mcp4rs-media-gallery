# Upload Generated Gallery Outputs To Hugging Face Datasets

The Hugging Face Space should stay lightweight. A completed full run can produce
useful generated sample outputs under:

```text
media/
figures/
generated/provenance/
assets/preview/
```

Publish those files as a separate Hugging Face Dataset so the compute spent
rendering them is reusable. The recommended dataset location is:

```text
https://huggingface.co/datasets/MCP4RemoteSensing/mcp4rs-media-gallery-outputs
```

## NeurIPS 2026 Hosting Requirements To Acknowledge

The NeurIPS 2026 Evaluations & Datasets hosting guide says that dataset
contributions should be hosted on a supported platform such as Hugging Face,
Kaggle, Harvard Dataverse, or OpenML. Dataset submissions must include Croissant
machine-readable metadata with core fields and minimal Responsible AI metadata.
For OpenReview, authors should provide both the dataset URL and a validated
Croissant metadata file.

This repo supports that workflow by generating:

```text
metadata.jsonl
dataset_manifest.json
croissant_metadata.json
README.md
```

inside the Hugging Face Dataset upload package.

Important: Hugging Face can also generate Croissant metadata from supported
dataset formats. Before NeurIPS submission, download or inspect the Hugging Face
Croissant metadata, merge/confirm the Responsible AI fields from
`croissant_metadata.json`, and validate the final Croissant file with the
NeurIPS-recommended validator.

Croissant reference to cite:

```text
Akhtar, M. et al. (2024). Croissant: A Metadata Format for ML-Ready Datasets.
NeurIPS 2024 Datasets and Benchmarks Track.
https://proceedings.neurips.cc/paper_files/paper/2024/hash/9547b09b722f2948ff3ddb5d86002bc0-Abstract-Datasets_and_Benchmarks_Track.html
```

## Creator Credits

The generated dataset card and metadata credit:

| Name | Credit |
| --- | --- |
| Dongping Liu | Creator and MCP4RS co-owner |
| Luyao Zhang | Creator and MCP4RS co-owner |

The generated dataset also acknowledges the open data providers and open-source
tools used by the workflow.

## 1. Generate The Full Local Outputs

```bash
python -m pip install -r requirements.txt
python scripts/export_media_sources.py
python scripts/generate_media_gallery.py --continue-on-error
python scripts/update_preview_assets.py --require-full
```

If the internet is interrupted, rerun the full gallery command. Existing
successful outputs can remain in place, and the script will continue where it
can.

## 2. Create A Hugging Face Token For The Organization Dataset

Create a token at:

```text
https://huggingface.co/settings/tokens
```

Recommended setup:

1. Create a fine-grained token.
2. Give it write access to the target organization or dataset repo:

```text
MCP4RemoteSensing/mcp4rs-media-gallery-outputs
```

3. Confirm that your Hugging Face account is a member of:

```text
https://huggingface.co/MCP4RemoteSensing
```

4. For local manual uploads, keep the token in a local env file (not tracked by
  git) and load it into your shell only when needed. Recommended secret name:

```text
HF_DATASET_TOKEN
```

5. Create a local env file in the repo root. You can use either `.local.env`
  or `.env.local` (pick one and keep it out of git):

```bash
cat > .local.env << 'EOF'
HF_DATASET_TOKEN=hf_your_token_here
EOF
```

6. Load the env file into your current shell session:

```bash
set -a
source .local.env
set +a
```

If you use `.env.local`, load that file instead:

```bash
set -a
source .env.local
set +a
```

7. Confirm the token is available before dry run or upload:

```bash
test -n "$HF_DATASET_TOKEN" && echo "HF_DATASET_TOKEN is set" || echo "HF_DATASET_TOKEN is missing"
```

Do not commit the token. Do not paste it into README files, notebooks, or issue
comments.

## 3. Dry Run The Dataset Package

```bash
python scripts/upload_hf_dataset.py --dry-run
```

This uses the default organization dataset repo:

```text
MCP4RemoteSensing/mcp4rs-media-gallery-outputs
```

You can override it:

```bash
python scripts/upload_hf_dataset.py \
  --repo-id MCP4RemoteSensing/your-dataset-name \
  --dry-run
```

The dry run prints the files that would be uploaded and stages:

```text
README.md
metadata.jsonl
dataset_manifest.json
croissant_metadata.json
```

Recommended command order before upload:

1. Load `.local.env` (or `.env.local`) into the shell.
2. Verify `HF_DATASET_TOKEN` is set.
3. Run `python scripts/upload_hf_dataset.py --dry-run`.
4. Run the real upload command.

## 4. Upload The Dataset

```bash
python scripts/upload_hf_dataset.py
```

For a private dataset:

```bash
python scripts/upload_hf_dataset.py --private
```

For an explicit repo ID:

```bash
python scripts/upload_hf_dataset.py \
  --repo-id MCP4RemoteSensing/mcp4rs-media-gallery-outputs
```

The script creates or updates:

```text
https://huggingface.co/datasets/MCP4RemoteSensing/mcp4rs-media-gallery-outputs
```

The upload script reads tokens in this order:

```text
1. --token
2. HF_DATASET_TOKEN
3. HF_TOKEN
```

Use `HF_DATASET_TOKEN` for dataset uploads so it remains separate from any
token used by the Hugging Face Space deployment.

## Future GitHub Action Token

For automated dataset uploads, add this GitHub Actions secret:

```text
Repository Settings -> Secrets and variables -> Actions -> New repository secret
Name: HF_DATASET_TOKEN
Value: your Hugging Face dataset write token
```

A future dataset-only workflow can expose it to the script as:

```yaml
env:
  HF_DATASET_TOKEN: ${{ secrets.HF_DATASET_TOKEN }}
```

Then call:

```bash
python scripts/upload_hf_dataset.py \
  --repo-id MCP4RemoteSensing/mcp4rs-media-gallery-outputs
```

## What Gets Uploaded

| Folder or file | Meaning |
| --- | --- |
| `media/` | Final gallery PNG/GIF outputs. |
| `figures/` | Processed intermediate figures and animation frames. |
| `generated/provenance/` | Source URL, STAC item, and WMS provenance JSON. |
| `assets/preview/` | Curated preview images/GIFs embedded by README and Space. |
| `metadata.jsonl` | One structured row per uploaded artifact. |
| `dataset_manifest.json` | Upload manifest with creators, source commit, acknowledgements, and file list. |
| `croissant_metadata.json` | Draft Croissant JSON-LD with core and minimal Responsible AI fields. |
| `README.md` | Hugging Face Dataset card. |

## Open Data And Tool Acknowledgement Scope

The generated dataset card acknowledges:

- ESA/Copernicus Sentinel-1 and Sentinel-2.
- USGS/NASA Landsat.
- USDA NAIP.
- Copernicus DEM.
- NASA GIBS/VIIRS nightlights WMS.
- NASA MODIS.
- NOAA GOES and NOAA OISST.
- NASA POWER.
- Python, Gradio, Hugging Face Hub, pystac-client, Microsoft Planetary Computer
  tooling, Rasterio, NumPy, Matplotlib, Pillow, and Requests.

When preparing a formal paper or NeurIPS submission, also cite the specific
upstream datasets or services used by each generated output. The source
provenance JSON files are the best place to audit those references.

## Final NeurIPS Checklist

Before submission:

1. Confirm the dataset URL is accessible to reviewers.
2. Confirm the dataset card includes creators, limitations, biases, use cases,
   social impact, sensitive-data statement, synthetic-data statement, and source
   provenance.
3. Inspect Hugging Face's Croissant tab once the dataset is uploaded.
4. Validate the final Croissant metadata using the NeurIPS-recommended
   validator.
5. Upload the validated Croissant metadata file to OpenReview.
6. Include the dataset URL in the paper and submission form.
