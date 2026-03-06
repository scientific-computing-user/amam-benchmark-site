# Reproducibility Package (AMAM-128)

This folder contains the full code and outputs used to build the benchmark results and figures.

## What Is Included

- `benchmark/`: all benchmark execution scripts (classical, deep, foundation/edge, plotting, appendix assets, site publishing).
- `results/`: generated CSV summaries and per-image/per-subset outputs.
- `figures/`: generated benchmark figures and appendix visual assets.
- `requirements.txt`: Python dependencies for reruns.

## Quick Start

```bash
# from repository root
python3 -m venv .venv
source .venv/bin/activate
pip install -r repro/requirements.txt
```

## Run Full Reproduction

```bash
# from repository root
bash repro/benchmark/run_all_repro.sh
```

For a script-by-script execution map (exact model families, outputs, and protocol files), see:

- `repro/benchmark/README.md`

This executes:

1. `run_benchmark.py` (10 classical methods)
2. `run_deep_survey.py` (general + metallography-oriented supervised deep models)
3. `run_foundation_edge_addons.py` (SAM/SlimSAM + edge add-ons)
4. `plot_benchmark_gap_figure.py`
5. `build_appendix_representative_assets.py`
6. `publish_results_to_site.py` (syncs report CSVs into `assets/data/results/`)
7. `build_model_provenance_manifest.py` (writes per-model checkpoint/source manifest)
8. `verify_45_model_repro.py` (hard consistency audit for all 45 model rows)

## Optional Fast Modes

Skip expensive stages:

```bash
SKIP_DEEP=1 bash repro/benchmark/run_all_repro.sh
SKIP_FOUNDATION=1 bash repro/benchmark/run_all_repro.sh
```

## External Optional Dependency (TextureSAM)

`run_foundation_edge_addons.py` can use TextureSAM if checkpoints/repos are available under:

- `repro/external/TextureSAM`
- `repro/external/TextureSAM_Datasets/checkpoints/sam2.1_hiera_small_0.3.pt`

If missing, the script still runs the other foundation/edge models.

Exact sources used:

- `https://github.com/Scientific-Computing-Lab/TextureSAM`
- `https://drive.google.com/drive/folders/1pUJLa898WYEcb4Y_sOaXsSVe-CsPkwRv`

## Per-Model Checkpoint Provenance

The full 45-row model checkpoint/source manifest is generated at:

- `repro/results/model_provenance_manifest.csv`
- `repro/results/model_provenance_manifest.md`

Hard reproducibility audit outputs:

- `repro/results/reproducibility_audit_45_models.json`
- `repro/results/reproducibility_audit_45_models.md`
