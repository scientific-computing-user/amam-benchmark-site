#!/usr/bin/env python3
"""
AMAM foundation/edge add-on survey.

Models:
- SAM ViT-Base (automatic mask generation)
- SlimSAM-50
- SlimSAM-77
- TextureSAM (SAM2.1 small, eta<=0.3 checkpoint)
- HED + watershed
- PidiNet + watershed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from skimage import segmentation
from sklearn.cluster import KMeans
from transformers import pipeline
from controlnet_aux import HEDdetector, PidiNetDetector

SEED = 17
TRAIN_FRACTION = 0.8
MAX_PIXELS_PER_MASK = 20_000

REPO_ROOT = Path(__file__).resolve().parents[2]
REPRO_ROOT = REPO_ROOT / "repro"
DATA_JSON = REPO_ROOT / "assets/data/amam-dataset.json"
OUT_DIR = REPRO_ROOT / "results/foundation_edge"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TEXTURESAM_REPO = REPRO_ROOT / "external/TextureSAM"
TEXTURESAM_CKPT = REPRO_ROOT / "external/TextureSAM_Datasets/checkpoints/sam2.1_hiera_small_0.3.pt"

warnings.filterwarnings("ignore", message=r".*urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"sklearn\.utils\.extmath")
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"sklearn\.cluster\._kmeans")


@dataclass
class PairSample:
    subset_id: str
    subset_name: str
    family: str
    phase_count: int
    original_path: Path
    mask_path: Path


@dataclass
class SplitData:
    train: List[PairSample]
    test: List[PairSample]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def load_dataset_pairs() -> Tuple[List[PairSample], Dict[str, int], Dict[str, dict]]:
    data = json.loads(DATA_JSON.read_text())
    pairs: List[PairSample] = []
    subset_phase_count: Dict[str, int] = {}
    subset_meta: Dict[str, dict] = {}

    for subset in data["subsets"]:
        subset_id = subset["id"]
        phase_count = len(subset.get("phases", []))
        if phase_count < 2:
            continue

        masks = {
            m["id"]: Path(REPO_ROOT / m["path"])
            for m in subset.get("gallery", {}).get("masks", [])
            if m.get("id") and m.get("path")
        }
        subset_meta[subset_id] = subset
        subset_phase_count[subset_id] = phase_count

        for orig in subset.get("gallery", {}).get("originals", []):
            mask_id = orig.get("maskId")
            orig_rel = orig.get("path")
            if not mask_id or not orig_rel or mask_id not in masks:
                continue
            orig_path = Path(REPO_ROOT / orig_rel)
            mask_path = masks[mask_id]
            if not orig_path.exists() or not mask_path.exists():
                continue
            pairs.append(
                PairSample(
                    subset_id=subset_id,
                    subset_name=subset["material"],
                    family=subset["family"],
                    phase_count=phase_count,
                    original_path=orig_path,
                    mask_path=mask_path,
                )
            )
    return pairs, subset_phase_count, subset_meta


def deterministic_split(pairs: List[PairSample]) -> Dict[str, SplitData]:
    by_subset: Dict[str, List[PairSample]] = {}
    for p in pairs:
        by_subset.setdefault(p.subset_id, []).append(p)

    split: Dict[str, SplitData] = {}
    for subset_id, items in by_subset.items():
        items = sorted(items, key=lambda x: x.original_path.name)
        stable = int(hashlib.sha1(subset_id.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(SEED + stable % 10_000)
        rng.shuffle(items)
        n = len(items)
        n_train = max(1, int(round(TRAIN_FRACTION * n)))
        n_train = min(n - 1, n_train)
        split[subset_id] = SplitData(train=items[:n_train], test=items[n_train:])
    return split


def read_image(path: Path, img_size: int, mode: str = "RGB", nearest: bool = False) -> np.ndarray:
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.BILINEAR
    arr = Image.open(path).convert(mode).resize((img_size, img_size), resample)
    return np.array(arr)


def estimate_mask_centroids(split: Dict[str, SplitData], k_by_subset: Dict[str, int], img_size: int) -> Dict[str, np.ndarray]:
    centers = {}
    for subset_id, sdata in split.items():
        k = k_by_subset[subset_id]
        px = []
        for sample in sdata.train:
            m = read_image(sample.mask_path, img_size, mode="RGB").reshape(-1, 3).astype(np.float64)
            if len(m) > MAX_PIXELS_PER_MASK:
                idx = np.random.choice(len(m), MAX_PIXELS_PER_MASK, replace=False)
                m = m[idx]
            px.append(m)
        all_px = np.concatenate(px, axis=0)
        all_px = np.nan_to_num(all_px, nan=0.0, posinf=0.0, neginf=0.0)
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED)
        km.fit(all_px)
        centers[subset_id] = km.cluster_centers_
    return centers


def mask_to_labels(mask_rgb: np.ndarray, centers: np.ndarray) -> np.ndarray:
    flat = mask_rgb.reshape(-1, 3).astype(np.float32)
    d = cdist(flat, centers.astype(np.float32))
    labels = np.argmin(d, axis=1)
    return labels.reshape(mask_rgb.shape[:2]).astype(np.int64)


def hu_map(pred: np.ndarray, gt: np.ndarray, k: int) -> np.ndarray:
    conf = np.zeros((k, k), dtype=np.int64)
    for i in range(k):
        for j in range(k):
            conf[i, j] = np.sum((pred == i) & (gt == j))
    row, col = linear_sum_assignment(conf.max() - conf)
    mapped = np.zeros_like(pred)
    for r, c in zip(row, col):
        mapped[pred == r] = c
    return mapped


def metrics(pred: np.ndarray, gt: np.ndarray, k: int) -> Dict[str, float]:
    ious, dices = [], []
    for c in range(k):
        p = pred == c
        g = gt == c
        inter = np.logical_and(p, g).sum()
        union = np.logical_or(p, g).sum()
        iou = inter / union if union else 1.0
        denom = p.sum() + g.sum()
        dice = (2 * inter) / denom if denom else 1.0
        ious.append(iou)
        dices.append(dice)
    return {
        "miou": float(np.mean(ious)),
        "dice": float(np.mean(dices)),
        "pixel_acc": float((pred == gt).mean()),
    }


def kmeans_rgb(img_rgb: np.ndarray, k: int) -> np.ndarray:
    x = img_rgb.reshape(-1, 3).astype(np.float32)
    km = KMeans(n_clusters=k, n_init=5, random_state=SEED)
    y = km.fit_predict(x)
    return y.reshape(img_rgb.shape[:2]).astype(np.int64)


def region_cluster_from_masks(
    masks: List[np.ndarray],
    scores: np.ndarray,
    img_rgb: np.ndarray,
    k: int,
) -> np.ndarray:
    h, w = img_rgb.shape[:2]
    if len(masks) == 0:
        return kmeans_rgb(img_rgb, k)

    order = np.argsort(scores)[::-1]
    region = np.full((h, w), -1, dtype=np.int32)
    rid = 0
    for i in order[:120]:
        m = masks[int(i)]
        if m.shape != (h, w):
            m = np.array(Image.fromarray(m.astype(np.uint8) * 255).resize((w, h), Image.Resampling.NEAREST)) > 0
        new = m & (region < 0)
        if new.sum() < 16:
            continue
        region[new] = rid
        rid += 1

    if rid == 0:
        return kmeans_rgb(img_rgb, k)

    if np.any(region < 0):
        region[region < 0] = rid
        rid += 1

    means = np.zeros((rid, 3), dtype=np.float32)
    for r in range(rid):
        px = img_rgb[region == r]
        means[r] = px.mean(axis=0) if len(px) else np.zeros((3,), dtype=np.float32)

    if rid < k:
        return kmeans_rgb(img_rgb, k)

    km = KMeans(n_clusters=k, n_init=10, random_state=SEED)
    reg_labels = km.fit_predict(means)
    pred = reg_labels[region]
    return pred.astype(np.int64)


def edge_to_watershed(edge_gray: np.ndarray, k: int) -> np.ndarray:
    edge = edge_gray.astype(np.float32)
    if edge.max() > 1.0:
        edge /= 255.0
    non_edge = 1.0 - edge
    dist = distance_transform_edt(non_edge > np.quantile(non_edge, 0.45))
    qs = np.quantile(dist, np.linspace(0.2, 0.9, k))
    markers = np.zeros_like(dist, dtype=np.int32)
    for i, q in enumerate(qs, start=1):
        markers[dist >= q] = i
    if markers.max() < 2:
        markers[dist > dist.mean()] = 1
        markers[dist <= dist.mean()] = 2
    ws = segmentation.watershed(edge, markers=markers, compactness=0.001)
    return ((ws - 1) % k).astype(np.int64)


def run_model_sam(pipe, img_rgb: np.ndarray, k: int) -> np.ndarray:
    out = pipe(Image.fromarray(img_rgb), points_per_batch=16)
    masks = out["masks"]
    scores = np.array([float(s) for s in out["scores"]], dtype=np.float32)
    return region_cluster_from_masks(masks=masks, scores=scores, img_rgb=img_rgb, k=k)


def run_model_hed(detector, img_rgb: np.ndarray, k: int) -> np.ndarray:
    out = detector(Image.fromarray(img_rgb))
    edge = np.array(out.convert("L").resize((img_rgb.shape[1], img_rgb.shape[0]), Image.Resampling.BILINEAR))
    return edge_to_watershed(edge_gray=edge, k=k)


def load_texturesam_generator(repo_dir: Path, checkpoint_path: Path):
    sam2_root = repo_dir / "sam2"
    if not sam2_root.exists():
        raise FileNotFoundError(f"TextureSAM repo not found: {sam2_root}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"TextureSAM checkpoint missing: {checkpoint_path}")

    sam2_root_str = str(sam2_root)
    if sam2_root_str not in sys.path:
        sys.path.insert(0, sam2_root_str)

    from sam2.build_sam import build_sam2
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    import torch

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cfg = "configs/sam2.1/sam2.1_hiera_s.yaml"
    model = build_sam2(
        config_file=cfg,
        ckpt_path=str(checkpoint_path),
        device=device,
        apply_postprocessing=False,
    )
    # Follow TextureSAM inference defaults while keeping runtime practical.
    return SAM2AutomaticMaskGenerator(
        model=model,
        points_per_side=32,
        pred_iou_thresh=0.8,
        stability_score_thresh=0.2,
        mask_threshold=0.0,
        min_mask_region_area=0,
        output_mode="binary_mask",
        multimask_output=False,
    )


def run_model_texturesam(mask_generator, img_rgb: np.ndarray, k: int) -> np.ndarray:
    out = mask_generator.generate(img_rgb)
    masks = [o["segmentation"] for o in out]
    scores = np.array([float(o.get("predicted_iou", o.get("area", 0.0))) for o in out], dtype=np.float32)
    return region_cluster_from_masks(masks=masks, scores=scores, img_rgb=img_rgb, k=k)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--img-size", type=int, default=192)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--models", type=str, default="", help="Comma-separated model_ids to run.")
    p.add_argument("--texturesam-repo", type=str, default=str(TEXTURESAM_REPO))
    p.add_argument("--texturesam-ckpt", type=str, default=str(TEXTURESAM_CKPT))
    p.add_argument("--no-resume", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(SEED)

    pairs, k_by_subset, subset_meta = load_dataset_pairs()
    split = deterministic_split(pairs)
    centers = estimate_mask_centroids(split, k_by_subset, img_size=args.img_size)

    test_samples = [s for sp in split.values() for s in sp.test]
    print(f"[info] test samples: {len(test_samples)}")

    print("[load] foundation/edge models")
    sam_base = pipeline("mask-generation", model="facebook/sam-vit-base", device=args.device)
    slim_50 = pipeline("mask-generation", model="nielsr/slimsam-50-uniform", device=args.device)
    slim_77 = pipeline("mask-generation", model="nielsr/slimsam-77-uniform", device=args.device)
    hed = HEDdetector.from_pretrained("lllyasviel/Annotators")
    pidi = PidiNetDetector.from_pretrained("lllyasviel/Annotators")
    texturesam = load_texturesam_generator(
        repo_dir=Path(args.texturesam_repo),
        checkpoint_path=Path(args.texturesam_ckpt),
    )

    models = [
        ("sam_vit_base", "foundation_sam", lambda img, k: run_model_sam(sam_base, img, k)),
        ("slimsam_50", "foundation_sam", lambda img, k: run_model_sam(slim_50, img, k)),
        ("slimsam_77", "foundation_sam", lambda img, k: run_model_sam(slim_77, img, k)),
        ("texturesam_03", "foundation_texture", lambda img, k: run_model_texturesam(texturesam, img, k)),
        ("hed_watershed", "deep_edge", lambda img, k: run_model_hed(hed, img, k)),
        ("pidi_watershed", "deep_edge", lambda img, k: run_model_hed(pidi, img, k)),
    ]

    if args.models.strip():
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        models = [m for m in models if m[0] in wanted]
        if not models:
            raise ValueError("No matching model_ids in --models.")

    per_image_csv = OUT_DIR / "foundation_edge_per_image.csv"
    meta_json = OUT_DIR / "foundation_edge_model_meta.json"

    rows = []
    model_runtime: Dict[str, float] = {}
    done_models = set()
    if per_image_csv.exists() and meta_json.exists() and not args.no_resume:
        prev = pd.read_csv(per_image_csv)
        rows.extend(prev.to_dict("records"))
        done_models = set(prev["model_id"].unique())
        meta_prev = json.loads(meta_json.read_text())
        model_runtime = {k: float(v["runtime_sec"]) for k, v in meta_prev.items() if "runtime_sec" in v}
        print(f"[info] resume enabled, skipping {len(done_models)} completed models")

    for model_id, category, fn in models:
        if model_id in done_models:
            print(f"[skip] {model_id}")
            continue
        t0 = time.time()
        print(f"[run] {model_id}")
        for idx, sample in enumerate(test_samples, start=1):
            img = read_image(sample.original_path, img_size=args.img_size, mode="RGB")
            mask = read_image(sample.mask_path, img_size=args.img_size, mode="RGB")
            gt = mask_to_labels(mask, centers[sample.subset_id])
            k = sample.phase_count
            pred = fn(img, k)
            pred = hu_map(pred, gt, k)
            m = metrics(pred, gt, k)
            rows.append(
                {
                    "model_id": model_id,
                    "category": category,
                    "subset": sample.subset_id,
                    "subset_name": sample.subset_name,
                    "family": sample.family,
                    "image": sample.original_path.name,
                    "miou": m["miou"],
                    "dice": m["dice"],
                    "pixel_acc": m["pixel_acc"],
                }
            )
            if idx % 5 == 0:
                print(f"  [progress] {model_id}: {idx}/{len(test_samples)}")
        model_runtime[model_id] = time.time() - t0

        # Incremental checkpoint.
        df_now = pd.DataFrame(rows)
        df_now.to_csv(per_image_csv, index=False)
        meta_payload = {k: {"runtime_sec": v} for k, v in model_runtime.items()}
        meta_json.write_text(json.dumps(meta_payload, indent=2))

    df = pd.DataFrame(rows)
    df.to_csv(per_image_csv, index=False)

    per_subset = (
        df.groupby(["model_id", "category", "subset"], as_index=False)[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values(["category", "miou"], ascending=[True, False])
    )
    per_subset.to_csv(OUT_DIR / "foundation_edge_per_subset.csv", index=False)

    macro = (
        per_subset.groupby(["model_id", "category"], as_index=False)[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values("miou", ascending=False)
    )
    macro["runtime_min"] = macro["model_id"].map(lambda m: model_runtime.get(m, np.nan) / 60.0)
    macro.to_csv(OUT_DIR / "foundation_edge_summary.csv", index=False)

    lines = [
        "| Rank | Model | Category | mIoU | Dice | Pixel Acc | Runtime (min) |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for i, r in macro.reset_index(drop=True).iterrows():
        lines.append(
            f"| {i+1} | {r['model_id']} | {r['category']} | {r['miou']:.4f} | {r['dice']:.4f} | {r['pixel_acc']:.4f} | {r['runtime_min']:.1f} |"
        )
    (OUT_DIR / "foundation_edge_table.md").write_text("\n".join(lines))

    protocol = {
        "seed": SEED,
        "img_size": args.img_size,
        "train_fraction": TRAIN_FRACTION,
        "n_pairs": len(pairs),
        "test_images": len(test_samples),
        "models": [m for m, _, _ in models],
    }
    (OUT_DIR / "foundation_edge_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\n[done] saved", OUT_DIR)
    print(macro.to_string(index=False))


if __name__ == "__main__":
    main()
