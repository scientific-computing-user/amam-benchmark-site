# AMAM Benchmark Website

Interactive dataset website for the **Annotated Metallic Alloys Microstructures (AMAM)** benchmark.

## Features

- Dataset overview, creation workflow, and statistics
- Section-by-section explorer for all AMAM subsets
- Responsive image gallery with zoom/lightbox navigation
- Per-image metadata and quick property view
- Category-level and global download controls
- Metadata export (`amam-dataset-manifest.json`)

## Local preview

```bash
# from repository root
python3 -m http.server 4177
# open http://127.0.0.1:4177
```

## Files

- `index.html`: page structure
- `assets/css/styles.css`: design and responsive layout
- `assets/js/app.js`: rendering, filters, lightbox, downloads
- `assets/data/amam-dataset.json`: dataset metadata + links
- `assets/images/*`: representative microstructure samples
- `repro/*`: full reproducibility package (all benchmark code, outputs, and paper assets)

## Reproduce benchmark results

```bash
# from repository root
bash repro/benchmark/run_all_repro.sh
```

Detailed instructions are in `repro/README.md`.
Execution details for every model family are in `repro/benchmark/README.md`.

## Deployment notes

- A `.nojekyll` file is included so GitHub Pages serves static assets directly.
- For private-only GitHub Pages publication, GitHub requires enterprise access-control support.
- On personal `GitHub Free`, GitHub Pages is not private-access controlled.
