# GitHub And Hugging Face Setup

This folder is ready to become an independent GitHub repo.

Suggested GitHub repository:

```text
MCP4RemoteSensing/mcp4rs-media-gallery
```

Suggested Hugging Face Space:

```text
zlysunshine/mcp4rs-media-gallery
```

## Create And Push With GitHub CLI

From this folder:

```bash
git init
git add .
git commit -m "Add reproducible MCP4RS media gallery"
gh repo create MCP4RemoteSensing/mcp4rs-media-gallery \
  --public \
  --source=. \
  --remote=origin \
  --push
```

If you prefer a personal repo first:

```bash
gh repo create YOUR_GITHUB_USERNAME/mcp4rs-media-gallery \
  --public \
  --source=. \
  --remote=origin \
  --push
```

## Run In Codespaces

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python scripts/export_media_sources.py
python scripts/generate_media_gallery.py --skip-long --continue-on-error
```

The core workflow is app-independent. `source_queries.py` mirrors the
source-discovery behavior of the main MCP4RS MCP server, while
`scripts/generate_media_gallery.py` renders the media outputs.

## Refresh README And Space Preview Assets

To embed the fancy smoke and full gallery previews in GitHub README and the
Hugging Face Space, first generate outputs locally, then copy selected files
into `assets/preview/`:

```bash
python scripts/export_media_sources.py
python scripts/generate_media_gallery.py --continue-on-error
python scripts/update_preview_assets.py --require-full
```

Commit `assets/preview/`. Do not commit runtime outputs from `media/`,
`figures/`, or `generated/provenance/`.

## Open In Colab

After pushing to GitHub, open:

```text
https://colab.research.google.com/github/MCP4RemoteSensing/mcp4rs-media-gallery/blob/main/notebooks/MCP4RS_Reproducible_Media_Gallery_Demo.ipynb
```

## Deploy To Hugging Face Space

Create a new Gradio Space named:

```text
mcp4rs-media-gallery
```

Add a Hugging Face write token to the GitHub repo:

```text
GitHub repo -> Settings -> Secrets and variables -> Actions
New repository secret:
Name: HF_TOKEN
Value: your Hugging Face write token
```

Then push to GitHub. The workflow at
`.github/workflows/sync-to-hugging-face.yml` copies only the selected Space
runtime files into a temporary folder and force-pushes that folder to Hugging
Face. It does not sync local Python environments, caches, runtime-generated
media, or provenance JSON.

The included `app.py` is only a small Space wrapper around the same two commands:

```bash
python scripts/export_media_sources.py
python scripts/generate_media_gallery.py --skip-long --continue-on-error
```
