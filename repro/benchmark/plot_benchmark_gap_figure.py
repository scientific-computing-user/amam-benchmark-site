#!/usr/bin/env python3
"""Create a main-paper figure that visualizes the benchmark performance gap.

This figure is built directly from the released CSV outputs:
- repro/results/classical/benchmark_macro_over_subsets.csv
- repro/results/deep_survey/deep_macro_over_subsets.csv
- repro/results/foundation_edge/foundation_edge_summary.csv
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.style.use("default")
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "repro" / "results"
OUT_PDF = REPO_ROOT / "repro" / "figures" / "benchmark-gap-overview.pdf"
OUT_PNG = REPO_ROOT / "repro" / "figures" / "benchmark-gap-overview.png"


def load_all_results() -> pd.DataFrame:
    classical = pd.read_csv(RESULTS / "classical" / "benchmark_macro_over_subsets.csv")
    classical_map = {
        "rf_pixel": "RF (pixel features)",
        "gmm_rgb": "GMM-RGB",
        "svm_pixel": "Linear SVM (pixel features)",
        "gabor_kmeans": "Gabor+KMeans",
        "slic_cluster": "SLIC+KMeans",
        "kmeans_rgb": "KMeans-RGB",
        "felzenszwalb_cluster": "Felzenszwalb-GMM",
        "lbp_kmeans": "LBP+KMeans",
        "canny_watershed": "Canny+Watershed",
        "sobel_watershed": "Sobel+Watershed",
    }
    classical = classical.assign(
        model=classical["method"].map(classical_map).fillna(classical["method"]),
        family="Classical",
    )[["model", "family", "miou"]]

    deep = pd.read_csv(RESULTS / "deep_survey" / "deep_macro_over_subsets.csv")
    deep = deep.assign(
        model=deep["display_name"],
        family=np.where(deep["group"] == "general", "Deep-General", "Deep-Metallography"),
    )[["model", "family", "miou"]]

    foundation = pd.read_csv(RESULTS / "foundation_edge" / "foundation_edge_summary.csv")
    foundation_map = {
        "sam_vit_base": "SAM ViT-Base (auto-mask)",
        "slimsam_50": "SlimSAM-50 (auto-mask)",
        "slimsam_77": "SlimSAM-77 (auto-mask)",
        "texturesam_03": "TextureSAM-0.3 (auto-mask)",
        "hed_watershed": "HED + Watershed",
        "pidi_watershed": "PidiNet + Watershed",
    }
    foundation = foundation.assign(
        model=foundation["model_id"].map(foundation_map).fillna(foundation["model_id"]),
        family="Foundation/Edge",
    )[["model", "family", "miou"]]

    df = pd.concat([classical, deep, foundation], ignore_index=True)
    df["miou"] = df["miou"].astype(float)
    return df


def build_figure(df: pd.DataFrame) -> None:
    family_order = ["Classical", "Deep-General", "Deep-Metallography", "Foundation/Edge"]
    palette = {
        "Classical": "#1f77b4",
        "Deep-General": "#2ca02c",
        "Deep-Metallography": "#d62728",
        "Foundation/Edge": "#9467bd",
    }

    fig = plt.figure(figsize=(12.4, 4.9))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.35], wspace=0.28)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    ax_left.set_facecolor("white")
    ax_right.set_facecolor("white")

    # Left panel: per-family distributions with best markers.
    rng = np.random.default_rng(7)
    positions = np.arange(len(family_order))
    family_values = [df.loc[df["family"] == fam, "miou"].to_numpy() for fam in family_order]

    bp = ax_left.boxplot(
        family_values,
        positions=positions,
        widths=0.52,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.4},
        whiskerprops={"color": "#666666", "linewidth": 1.0},
        capprops={"color": "#666666", "linewidth": 1.0},
    )
    for patch, fam in zip(bp["boxes"], family_order):
        patch.set_facecolor(palette[fam])
        patch.set_alpha(0.24)
        patch.set_edgecolor(palette[fam])
        patch.set_linewidth(1.2)

    for idx, fam in enumerate(family_order):
        vals = df.loc[df["family"] == fam, "miou"].to_numpy()
        jitter = rng.normal(0.0, 0.06, size=len(vals))
        ax_left.scatter(
            np.full_like(vals, idx, dtype=float) + jitter,
            vals,
            s=26,
            color=palette[fam],
            alpha=0.82,
            edgecolor="white",
            linewidth=0.35,
            zorder=3,
        )
        best_idx = df.loc[df["family"] == fam, "miou"].idxmax()
        best_row = df.loc[best_idx]
        ax_left.scatter(
            idx,
            best_row["miou"],
            marker="*",
            s=190,
            color="#ffcc00",
            edgecolor="black",
            linewidth=0.7,
            zorder=6,
        )
        ax_left.text(
            idx,
            best_row["miou"] + 0.015,
            f"{best_row['miou']:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
            weight="bold",
        )

    ax_left.axhline(1.0, color="#555555", linestyle="--", linewidth=1.0)
    ax_left.axhline(0.7, color="#9a9a9a", linestyle=":", linewidth=1.0)
    ax_left.text(3.48, 1.0, "Perfect (1.0)", fontsize=8, va="bottom", ha="right", color="#555555")
    ax_left.text(3.48, 0.7, "0.7 reference", fontsize=8, va="bottom", ha="right", color="#666666")
    ax_left.set_ylim(0.30, 1.02)
    ax_left.set_ylabel("Subset-Macro mIoU")
    ax_left.set_xticks(positions)
    ax_left.set_xticklabels(
        ["Classical\n(n=10)", "Deep-General\n(n=14)", "Deep-Metal\n(n=15)", "Foundation/Edge\n(n=6)"],
        fontsize=8,
    )
    ax_left.set_title("Family-Wise Performance Distribution")
    ax_left.grid(axis="y", alpha=0.22, linewidth=0.7)

    # Right panel: global ranking and unresolved gap.
    ranked = df.sort_values("miou", ascending=False).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)

    ax_right.fill_between(
        ranked["rank"].to_numpy(),
        ranked["miou"].to_numpy(),
        np.ones(len(ranked)),
        color="#f6d2d2",
        alpha=0.5,
        label="Unresolved gap to perfect segmentation",
        zorder=1,
    )
    ax_right.plot(
        ranked["rank"],
        ranked["miou"],
        color="#333333",
        linewidth=1.15,
        zorder=2,
    )

    for fam in family_order:
        sub = ranked[ranked["family"] == fam]
        ax_right.scatter(
            sub["rank"],
            sub["miou"],
            s=30,
            color=palette[fam],
            alpha=0.9,
            edgecolor="white",
            linewidth=0.35,
            label=fam,
            zorder=3,
        )

    best = ranked.iloc[0]
    median_val = ranked["miou"].median()
    ax_right.axhline(1.0, color="#555555", linestyle="--", linewidth=1.0)
    ax_right.axhline(median_val, color="#6a6a6a", linestyle=":", linewidth=1.0)
    ax_right.text(45.5, 1.0, "1.0", fontsize=8, va="bottom", ha="right", color="#555555")
    ax_right.text(45.5, median_val, f"Median {median_val:.3f}", fontsize=8, va="bottom", ha="right", color="#666666")
    ax_right.annotate(
        f"Best overall: {best['model']} ({best['miou']:.3f})",
        xy=(best["rank"], best["miou"]),
        xytext=(6.5, 0.965),
        textcoords="data",
        fontsize=8,
        arrowprops={"arrowstyle": "->", "color": "#333333", "lw": 0.9},
    )
    ax_right.set_xlim(0.5, 45.5)
    ax_right.set_ylim(0.30, 1.02)
    ax_right.set_xlabel("Method Rank (45 total; descending mIoU)")
    ax_right.set_ylabel("Subset-Macro mIoU")
    ax_right.set_title("Global Ranking: No Family Closes the Gap")
    ax_right.grid(axis="y", alpha=0.22, linewidth=0.7)

    handles, labels = ax_right.get_legend_handles_labels()
    dedup = {}
    for h, l in zip(handles, labels):
        dedup.setdefault(l, h)
    ax_right.legend(
        [dedup[k] for k in ["Classical", "Deep-General", "Deep-Metallography", "Foundation/Edge"]],
        ["Classical", "Deep-General", "Deep-Metallography", "Foundation/Edge"],
        loc="lower left",
        fontsize=8,
        frameon=True,
    )

    fig.suptitle(
        "AMAM-128 Benchmark Gap Overview: 45 Methods Across Four Model Groups",
        y=0.99,
        fontsize=12,
        weight="bold",
    )
    fig.subplots_adjust(left=0.055, right=0.995, bottom=0.14, top=0.87, wspace=0.28)
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = load_all_results()
    build_figure(df)
    best = df.loc[df["miou"].idxmax()]
    print(f"[ok] wrote {OUT_PDF}")
    print(f"[ok] wrote {OUT_PNG}")
    print(f"[summary] methods={len(df)} best={best['model']} mIoU={best['miou']:.4f}")


if __name__ == "__main__":
    main()
