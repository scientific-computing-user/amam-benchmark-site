#!/usr/bin/env python3
"""
Build a per-model provenance manifest for the AMAM-128 benchmark runs.

Outputs:
  - repro/results/model_provenance_manifest.csv
  - repro/results/model_provenance_manifest.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = REPO_ROOT / "repro/results"

CLASSICAL_CSV = RESULT_ROOT / "classical/benchmark_summary.csv"
DEEP_GENERAL_CSV = RESULT_ROOT / "deep_survey/deep_general_summary.csv"
DEEP_METAL_CSV = RESULT_ROOT / "deep_survey/deep_metallography_summary.csv"
FOUNDATION_CSV = RESULT_ROOT / "foundation_edge/foundation_edge_summary.csv"

OUT_CSV = RESULT_ROOT / "model_provenance_manifest.csv"
OUT_MD = RESULT_ROOT / "model_provenance_manifest.md"


CLASSICAL_NAMES = {
    "svm_pixel": "Linear SVM (pixel features)",
    "rf_pixel": "RF (pixel features)",
    "gmm_rgb": "GMM-RGB",
    "gabor_kmeans": "Gabor+KMeans",
    "slic_cluster": "SLIC+KMeans",
    "kmeans_rgb": "KMeans-RGB",
    "felzenszwalb_cluster": "Felzenszwalb+GMM",
    "lbp_kmeans": "LBP+KMeans",
    "canny_watershed": "Canny+Watershed",
    "sobel_watershed": "Sobel+Watershed",
}


FOUNDATION_META = {
    "sam_vit_base": {
        "display_name": "SAM ViT-Base (auto-mask)",
        "checkpoint_kind": "pretrained_full_model",
        "checkpoint_identifier": "facebook/sam-vit-base",
        "checkpoint_loader": "transformers.pipeline('mask-generation', model='facebook/sam-vit-base')",
        "checkpoint_source_location": "Hugging Face model id: facebook/sam-vit-base",
        "repro_script": "repro/benchmark/run_foundation_edge_addons.py",
    },
    "slimsam_50": {
        "display_name": "SlimSAM-50 (auto-mask)",
        "checkpoint_kind": "pretrained_full_model",
        "checkpoint_identifier": "nielsr/slimsam-50-uniform",
        "checkpoint_loader": "transformers.pipeline('mask-generation', model='nielsr/slimsam-50-uniform')",
        "checkpoint_source_location": "Hugging Face model id: nielsr/slimsam-50-uniform",
        "repro_script": "repro/benchmark/run_foundation_edge_addons.py",
    },
    "slimsam_77": {
        "display_name": "SlimSAM-77 (auto-mask)",
        "checkpoint_kind": "pretrained_full_model",
        "checkpoint_identifier": "nielsr/slimsam-77-uniform",
        "checkpoint_loader": "transformers.pipeline('mask-generation', model='nielsr/slimsam-77-uniform')",
        "checkpoint_source_location": "Hugging Face model id: nielsr/slimsam-77-uniform",
        "repro_script": "repro/benchmark/run_foundation_edge_addons.py",
    },
    "texturesam_03": {
        "display_name": "TextureSAM-0.3 (auto-mask)",
        "checkpoint_kind": "external_local_checkpoint",
        "checkpoint_identifier": "sam2.1_hiera_small_0.3.pt",
        "checkpoint_loader": "build_sam2(..., checkpoint='.../sam2.1_hiera_small_0.3.pt')",
        "checkpoint_source_location": (
            "Local optional dependency: repro/external/TextureSAM "
            "+ repro/external/TextureSAM_Datasets/checkpoints/sam2.1_hiera_small_0.3.pt"
        ),
        "repro_script": "repro/benchmark/run_foundation_edge_addons.py",
    },
    "hed_watershed": {
        "display_name": "HED + Watershed",
        "checkpoint_kind": "pretrained_detector",
        "checkpoint_identifier": "lllyasviel/Annotators (HED)",
        "checkpoint_loader": "controlnet_aux.HEDdetector.from_pretrained('lllyasviel/Annotators')",
        "checkpoint_source_location": "ControlNet Aux pretrained annotator package",
        "repro_script": "repro/benchmark/run_foundation_edge_addons.py",
    },
    "pidi_watershed": {
        "display_name": "PidiNet + Watershed",
        "checkpoint_kind": "pretrained_detector",
        "checkpoint_identifier": "lllyasviel/Annotators (PidiNet)",
        "checkpoint_loader": "controlnet_aux.PidiNetDetector.from_pretrained('lllyasviel/Annotators')",
        "checkpoint_source_location": "ControlNet Aux pretrained annotator package",
        "repro_script": "repro/benchmark/run_foundation_edge_addons.py",
    },
}


def build_classical_rows(df: pd.DataFrame) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    ranked = df.sort_values("miou", ascending=False).reset_index(drop=True)
    for i, r in ranked.iterrows():
        model_id = str(r["method"])
        rows.append(
            {
                "model_group": "classical",
                "paper_table_group": "Appendix classical table",
                "rank_within_group": i + 1,
                "model_id": model_id,
                "display_name": CLASSICAL_NAMES.get(model_id, model_id),
                "category": str(r["category"]),
                "miou": f"{float(r['miou']):.4f}",
                "checkpoint_kind": "none",
                "checkpoint_identifier": "none",
                "checkpoint_loader": "No pretrained checkpoint (classical algorithm fit on AMAM train split)",
                "checkpoint_source_location": (
                    "scikit-learn / scikit-image classical methods executed in "
                    "repro/benchmark/run_benchmark.py"
                ),
                "repro_script": "repro/benchmark/run_benchmark.py",
                "result_source_csv": "repro/results/classical/benchmark_summary.csv",
            }
        )
    return rows


def build_deep_rows(df: pd.DataFrame, group_name: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    ranked = df.sort_values("miou", ascending=False).reset_index(drop=True)
    for i, r in ranked.iterrows():
        model_id = str(r["model_id"])
        encoder = str(r["encoder"])
        no_external_ckpt = model_id == "metal_mlography_unet_vgg16_gray"
        if no_external_ckpt:
            ckpt_kind = "random_init"
            ckpt_id = f"{encoder}; encoder_weights=None"
            ckpt_loader = (
                f"smp.create_model('{r['architecture']}', encoder_name='{encoder}', "
                "encoder_weights=None)"
            )
            ckpt_source = "No external checkpoint; model initialized from scratch and trained on AMAM."
        else:
            ckpt_kind = "pretrained_encoder"
            ckpt_id = f"{encoder}; encoder_weights='imagenet'"
            ckpt_loader = (
                f"smp.create_model('{r['architecture']}', encoder_name='{encoder}', "
                "encoder_weights='imagenet')"
            )
            ckpt_source = (
                "ImageNet encoder checkpoint loaded through segmentation_models_pytorch "
                "and timm encoder registry."
            )

        rows.append(
            {
                "model_group": group_name,
                "paper_table_group": (
                    "Appendix deep-general table"
                    if group_name == "deep_general"
                    else "Appendix deep-metallography table"
                ),
                "rank_within_group": i + 1,
                "model_id": model_id,
                "display_name": str(r["display_name"]),
                "category": str(r["category"]),
                "miou": f"{float(r['miou']):.4f}",
                "checkpoint_kind": ckpt_kind,
                "checkpoint_identifier": ckpt_id,
                "checkpoint_loader": ckpt_loader,
                "checkpoint_source_location": ckpt_source,
                "repro_script": "repro/benchmark/run_deep_survey.py",
                "result_source_csv": (
                    "repro/results/deep_survey/deep_general_summary.csv"
                    if group_name == "deep_general"
                    else "repro/results/deep_survey/deep_metallography_summary.csv"
                ),
            }
        )
    return rows


def build_foundation_rows(df: pd.DataFrame) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    ranked = df.sort_values("miou", ascending=False).reset_index(drop=True)
    for i, r in ranked.iterrows():
        model_id = str(r["model_id"])
        meta = FOUNDATION_META[model_id]
        rows.append(
            {
                "model_group": "foundation_edge",
                "paper_table_group": "Appendix foundation/edge table",
                "rank_within_group": i + 1,
                "model_id": model_id,
                "display_name": meta["display_name"],
                "category": str(r["category"]),
                "miou": f"{float(r['miou']):.4f}",
                "checkpoint_kind": meta["checkpoint_kind"],
                "checkpoint_identifier": meta["checkpoint_identifier"],
                "checkpoint_loader": meta["checkpoint_loader"],
                "checkpoint_source_location": meta["checkpoint_source_location"],
                "repro_script": meta["repro_script"],
                "result_source_csv": "repro/results/foundation_edge/foundation_edge_summary.csv",
            }
        )
    return rows


def write_markdown(df: pd.DataFrame, out_path: Path) -> None:
    lines = [
        "# AMAM-128 Model Provenance Manifest",
        "",
        "This manifest maps every benchmarked model row to its checkpoint provenance and execution script.",
        "",
        f"- Total rows: {len(df)}",
        f"- Classical: {(df['model_group'] == 'classical').sum()}",
        f"- Deep general: {(df['model_group'] == 'deep_general').sum()}",
        f"- Deep metallography: {(df['model_group'] == 'deep_metallography').sum()}",
        f"- Foundation/edge: {(df['model_group'] == 'foundation_edge').sum()}",
        "",
        "| Group | Rank | Model | Category | mIoU | Checkpoint kind | Checkpoint identifier | Checkpoint source | Script |",
        "|---|---:|---|---|---:|---|---|---|---|",
    ]

    for _, r in df.iterrows():
        lines.append(
            "| "
            + f"{r['model_group']} | {r['rank_within_group']} | {r['display_name']} | {r['category']} | {r['miou']} | "
            + f"{r['checkpoint_kind']} | {r['checkpoint_identifier']} | {r['checkpoint_source_location']} | {r['repro_script']} |"
        )

    out_path.write_text("\n".join(lines))


def main() -> None:
    classical = pd.read_csv(CLASSICAL_CSV)
    deep_general = pd.read_csv(DEEP_GENERAL_CSV)
    deep_metal = pd.read_csv(DEEP_METAL_CSV)
    foundation = pd.read_csv(FOUNDATION_CSV)

    rows: List[Dict[str, str]] = []
    rows.extend(build_classical_rows(classical))
    rows.extend(build_deep_rows(deep_general, "deep_general"))
    rows.extend(build_deep_rows(deep_metal, "deep_metallography"))
    rows.extend(build_foundation_rows(foundation))

    manifest = pd.DataFrame(rows)

    expected = 10 + 14 + 15 + 6
    if len(manifest) != expected:
        raise RuntimeError(f"Unexpected model count in manifest: {len(manifest)} != {expected}")

    group_order = {
        "classical": 0,
        "deep_general": 1,
        "deep_metallography": 2,
        "foundation_edge": 3,
    }
    manifest["group_order"] = manifest["model_group"].map(group_order)
    manifest = manifest.sort_values(["group_order", "rank_within_group"], kind="stable").drop(columns=["group_order"]).reset_index(drop=True)
    manifest.to_csv(OUT_CSV, index=False)
    write_markdown(manifest, OUT_MD)

    print("[done] wrote")
    print(" -", OUT_CSV)
    print(" -", OUT_MD)
    print(manifest.groupby("model_group").size().to_string())


if __name__ == "__main__":
    main()
