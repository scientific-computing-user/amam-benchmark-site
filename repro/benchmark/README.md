# AMAM-128 Benchmark Execution (Model Runs + Inference)

This directory contains the exact scripts used to run the AMAM-128 model experiments.

## What Is Executed Here

All model testing is executed locally from these scripts (not via a hosted inference service):

- `run_benchmark.py`: 10 classical methods.
- `run_deep_survey.py`: 29 supervised deep methods.
- `run_foundation_edge_addons.py`: 6 foundation/edge add-ons (including TextureSAM if available).
- `plot_benchmark_gap_figure.py`: main benchmark-gap figure.
- `build_appendix_representative_assets.py`: appendix visual audit assets.
- `publish_results_to_site.py`: syncs reproducibility outputs into website CSV artifacts.
- `build_model_provenance_manifest.py`: writes a 45-row per-model checkpoint/source manifest.
- `verify_45_model_repro.py`: hard verification that all 45 model ids/checkpoint rows/results are consistent.

## One-Command Full Reproduction

```bash
# from repository root
bash repro/benchmark/run_all_repro.sh
```

Pipeline order:

1. Classical benchmark (`run_benchmark.py`)
2. Deep benchmark (`run_deep_survey.py`)
3. Foundation/edge benchmark (`run_foundation_edge_addons.py`)
4. Gap figure generation
5. Representative appendix assets generation
6. Publish CSVs to `assets/data/results/`
7. Build `repro/results/model_provenance_manifest.csv` and `.md`
8. Build `repro/results/reproducibility_audit_45_models.json` and `.md`

## Run Families Separately

```bash
# 10 classical
python3 repro/benchmark/run_benchmark.py

# 29 supervised deep (14 general + 15 metallography-oriented)
python3 repro/benchmark/run_deep_survey.py --img-size 192 --epochs 5 --batch-size 4 --device auto

# 6 foundation/edge add-ons (SAM/SlimSAM/TextureSAM/HED/PidiNet)
python3 repro/benchmark/run_foundation_edge_addons.py --img-size 192 --device auto
```

## Determinism / Protocol

- Pair-only inclusion from `assets/data/amam-dataset.json`.
- Deterministic split seed: `17` (see script constants/protocol JSON outputs).
- Subset-aware macro metrics: mIoU, Dice, Pixel Accuracy.
- Output protocol manifests:
  - `repro/results/classical/benchmark_protocol.json`
  - `repro/results/deep_survey/deep_protocol.json`
  - `repro/results/foundation_edge/foundation_edge_protocol.json`

## Where Outputs Are Written

### Classical (10)

- `repro/results/classical/benchmark_summary.csv`
- `repro/results/classical/benchmark_macro_over_subsets.csv`
- `repro/results/classical/benchmark_micro_over_images.csv`
- `repro/results/classical/benchmark_per_subset.csv`
- `repro/results/classical/benchmark_raw_per_image.csv`

`benchmark_summary.csv` is the canonical subset-macro summary used by the paper and website.

### Supervised Deep (29)

- `repro/results/deep_survey/deep_general_summary.csv`
- `repro/results/deep_survey/deep_metallography_summary.csv`
- `repro/results/deep_survey/deep_macro_over_subsets.csv`
- `repro/results/deep_survey/deep_per_subset.csv`
- `repro/results/deep_survey/deep_per_image.csv`

### Foundation / Edge (6)

- `repro/results/foundation_edge/foundation_edge_summary.csv`
- `repro/results/foundation_edge/foundation_edge_per_subset.csv`
- `repro/results/foundation_edge/foundation_edge_per_image.csv`

### Published Website CSVs

- `assets/data/results/benchmark_summary.csv`
- `assets/data/results/deep_macro_over_subsets.csv`
- `assets/data/results/foundation_edge_summary.csv`

### Checkpoint / Source Manifest (All 45 Models)

- `repro/results/model_provenance_manifest.csv`
- `repro/results/model_provenance_manifest.md`

## Hard Proof Command (45 Models)

```bash
python3 repro/benchmark/verify_45_model_repro.py
```

This command fails if any model id is missing/misaligned across result files, or if the provenance manifest is incomplete. On success, it writes:

- `repro/results/reproducibility_audit_45_models.json`
- `repro/results/reproducibility_audit_45_models.md`

## Optional TextureSAM Dependency

`run_foundation_edge_addons.py` supports TextureSAM when these are present:

- `repro/external/TextureSAM`
- `repro/external/TextureSAM_Datasets/checkpoints/sam2.1_hiera_small_0.3.pt`

Exact sources used in this benchmark:

- TextureSAM repository: `https://github.com/Scientific-Computing-Lab/TextureSAM`
- TextureSAM checkpoints drive: `https://drive.google.com/drive/folders/1pUJLa898WYEcb4Y_sOaXsSVe-CsPkwRv`

Example setup:

```bash
mkdir -p repro/external
git clone https://github.com/Scientific-Computing-Lab/TextureSAM repro/external/TextureSAM
mkdir -p repro/external/TextureSAM_Datasets/checkpoints
# then place sam2.1_hiera_small_0.3.pt at:
# repro/external/TextureSAM_Datasets/checkpoints/sam2.1_hiera_small_0.3.pt
```
