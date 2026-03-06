#!/usr/bin/env python3
"""Publish reproduced CSV results into website assets/data/results.

This keeps the GitHub Pages report table synchronized with benchmark reruns.
"""

from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REPRO_RESULTS = REPO_ROOT / "repro" / "results"
SITE_RESULTS = REPO_ROOT / "assets" / "data" / "results"

COPY_MAP = {
    REPRO_RESULTS / "classical" / "benchmark_summary.csv": SITE_RESULTS / "benchmark_summary.csv",
    REPRO_RESULTS / "deep_survey" / "deep_macro_over_subsets.csv": SITE_RESULTS / "deep_macro_over_subsets.csv",
    REPRO_RESULTS / "foundation_edge" / "foundation_edge_summary.csv": SITE_RESULTS / "foundation_edge_summary.csv",
}


def main() -> None:
    SITE_RESULTS.mkdir(parents=True, exist_ok=True)
    missing = [src for src in COPY_MAP if not src.exists()]
    if missing:
        missing_str = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(
            "Cannot publish website results; missing source files:\n" + missing_str
        )

    for src, dst in COPY_MAP.items():
        shutil.copy2(src, dst)
        print(f"[copied] {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")

    print("[done] Website CSV assets refreshed.")


if __name__ == "__main__":
    main()
