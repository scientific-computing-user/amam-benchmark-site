#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[1/6] Classical benchmark (10 methods)"
python3 repro/benchmark/run_benchmark.py

if [[ "${SKIP_DEEP:-0}" != "1" ]]; then
  echo "[2/6] Deep supervised survey (29 models)"
  python3 repro/benchmark/run_deep_survey.py --img-size 192 --epochs 5 --batch-size 4 --device auto
else
  echo "[2/6] SKIP_DEEP=1 -> skipping deep survey"
fi

if [[ "${SKIP_FOUNDATION:-0}" != "1" ]]; then
  echo "[3/6] Foundation/edge survey (6 models incl. TextureSAM)"
  python3 repro/benchmark/run_foundation_edge_addons.py --img-size 192 --device auto
else
  echo "[3/6] SKIP_FOUNDATION=1 -> skipping foundation/edge survey"
fi

echo "[4/6] Benchmark gap figure"
python3 repro/benchmark/plot_benchmark_gap_figure.py

echo "[5/6] Representative appendix prediction assets"
python3 repro/benchmark/build_appendix_representative_assets.py

echo "[6/7] Publish results to website assets"
python3 repro/benchmark/publish_results_to_site.py

echo "[7/7] Build per-model provenance manifest"
python3 repro/benchmark/build_model_provenance_manifest.py

echo "[done] Repro pipeline complete."
