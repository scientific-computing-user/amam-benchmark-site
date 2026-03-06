#!/usr/bin/env python3
"""
AMAM benchmark sweep over 10 segmentation methods.

Methods are grouped as:
- baseline: kmeans_rgb, gmm_rgb
- edge: canny_watershed, sobel_watershed
- contour_region: felzenszwalb_cluster, slic_cluster
- texture: lbp_kmeans, gabor_kmeans
- metallography_learned: rf_pixel, svm_pixel
"""

from __future__ import annotations

import json
import math
import random
import hashlib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from PIL import Image
from scipy.optimize import linear_sum_assignment
from scipy.ndimage import distance_transform_edt
from scipy.spatial.distance import cdist
from skimage import color, filters, feature, segmentation
from skimage.filters import gabor
from skimage.morphology import binary_opening, disk
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

SEED = 17
RNG = np.random.default_rng(SEED)
random.seed(SEED)
np.random.seed(SEED)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_JSON = REPO_ROOT / "assets/data/amam-dataset.json"
RESULT_DIR = REPO_ROOT / "repro/results/classical"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

IMG_SIZE = (256, 256)
TRAIN_FRACTION = 0.8
MAX_TRAIN_PIXELS_PER_SUBSET = 80_000

warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    module=r"sklearn\.utils\.extmath",
)
warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    module=r"sklearn\.cluster\._kmeans",
)
warnings.filterwarnings(
    "ignore",
    message=r"Applying `local_binary_pattern` to floating-point images",
    category=UserWarning,
)


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
            orig_path_rel = orig.get("path")
            if not mask_id or not orig_path_rel or mask_id not in masks:
                continue
            orig_path = Path(REPO_ROOT / orig_path_rel)
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


def read_image(path: Path, mode: str = "RGB") -> np.ndarray:
    img = Image.open(path).convert(mode).resize(IMG_SIZE, Image.Resampling.BILINEAR)
    return np.array(img)


def sanitize_features(features: np.ndarray, clip: float = 8.0) -> np.ndarray:
    x = np.asarray(features, dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    if x.ndim != 2 or x.shape[0] == 0:
        return x
    mean = x.mean(axis=0, keepdims=True)
    std = x.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    x = (x - mean) / std
    x = np.clip(x, -clip, clip)
    return x.astype(np.float64, copy=False)


def estimate_mask_centroids(split: Dict[str, SplitData], k_by_subset: Dict[str, int]) -> Dict[str, np.ndarray]:
    centroids = {}
    for subset_id, sdata in split.items():
        k = k_by_subset[subset_id]
        px = []
        for sample in sdata.train:
            m = read_image(sample.mask_path, mode="RGB").reshape(-1, 3)
            if len(m) > 15000:
                idx = RNG.choice(len(m), 15000, replace=False)
                m = m[idx]
            px.append(m)
        all_px = np.concatenate(px, axis=0).astype(np.float64, copy=False)
        km = KMeans(n_clusters=k, n_init=5, random_state=SEED)
        km.fit(all_px)
        centroids[subset_id] = km.cluster_centers_
    return centroids


def mask_to_labels(mask_rgb: np.ndarray, centers: np.ndarray) -> np.ndarray:
    flat = mask_rgb.reshape(-1, 3).astype(np.float32)
    d = cdist(flat, centers.astype(np.float32))
    labels = np.argmin(d, axis=1)
    return labels.reshape(mask_rgb.shape[:2])


def hu_map(pred: np.ndarray, gt: np.ndarray, k: int) -> np.ndarray:
    conf = np.zeros((k, k), dtype=np.int64)
    for i in range(k):
        for j in range(k):
            conf[i, j] = np.sum((pred == i) & (gt == j))
    row_ind, col_ind = linear_sum_assignment(conf.max() - conf)
    mapped = np.zeros_like(pred)
    for r, c in zip(row_ind, col_ind):
        mapped[pred == r] = c
    return mapped


def metrics(pred: np.ndarray, gt: np.ndarray, k: int) -> Dict[str, float]:
    ious = []
    dices = []
    for c in range(k):
        p = pred == c
        g = gt == c
        inter = np.logical_and(p, g).sum()
        union = np.logical_or(p, g).sum()
        iou = inter / union if union else 1.0
        dice = (2 * inter) / (p.sum() + g.sum()) if (p.sum() + g.sum()) else 1.0
        ious.append(iou)
        dices.append(dice)
    acc = (pred == gt).mean()
    return {"miou": float(np.mean(ious)), "dice": float(np.mean(dices)), "pixel_acc": float(acc)}


def feat_rgb(img_rgb: np.ndarray) -> np.ndarray:
    return img_rgb.reshape(-1, 3).astype(np.float32)


def feat_rgb_grad(img_rgb: np.ndarray) -> np.ndarray:
    gray = color.rgb2gray(img_rgb)
    gx = filters.sobel_h(gray)
    gy = filters.sobel_v(gray)
    gmag = np.sqrt(gx**2 + gy**2)
    f = np.concatenate([img_rgb.astype(np.float32), gmag[..., None] * 255.0], axis=-1)
    return f.reshape(-1, 4)


def feat_texture_lbp(img_rgb: np.ndarray) -> np.ndarray:
    gray = color.rgb2gray(img_rgb)
    gray_u8 = np.clip(gray * 255.0, 0, 255).astype(np.uint8)
    lbp = feature.local_binary_pattern(gray_u8, P=8, R=1, method="uniform")
    lbp_max = float(np.max(lbp))
    lbp_norm = lbp / lbp_max if lbp_max > 0 else np.zeros_like(lbp, dtype=np.float32)
    f = np.concatenate([gray[..., None], lbp_norm[..., None]], axis=-1)
    return f.reshape(-1, 2).astype(np.float32)


def feat_texture_gabor(img_rgb: np.ndarray) -> np.ndarray:
    gray = color.rgb2gray(img_rgb)
    feats = [gray]
    for theta in [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]:
        real, imag = gabor(gray, frequency=0.2, theta=theta)
        feats.append(real)
        feats.append(imag)
    stack = np.stack(feats, axis=-1)
    return stack.reshape(-1, stack.shape[-1]).astype(np.float32)


def model_cluster(features: np.ndarray, k: int, mode: str) -> np.ndarray:
    features = sanitize_features(features)
    if mode == "kmeans":
        model = KMeans(n_clusters=k, n_init=5, random_state=SEED)
        labels = model.fit_predict(features)
    elif mode == "gmm":
        model = GaussianMixture(n_components=k, random_state=SEED, covariance_type="diag")
        labels = model.fit_predict(features)
    else:
        raise ValueError(mode)
    return labels


def canny_watershed(img_rgb: np.ndarray, k: int) -> np.ndarray:
    gray = color.rgb2gray(img_rgb)
    edges = feature.canny(gray, sigma=1.4)
    dist = distance_transform_edt(~edges)
    # k marker levels from distance quantiles
    qs = np.quantile(dist, np.linspace(0.15, 0.9, k))
    markers = np.zeros_like(dist, dtype=np.int32)
    for i, q in enumerate(qs, start=1):
        markers[dist >= q] = i
    grad = filters.sobel(gray)
    ws = segmentation.watershed(grad, markers=markers, compactness=0.001)
    # compress to k labels
    return (ws - 1) % k


def sobel_watershed(img_rgb: np.ndarray, k: int) -> np.ndarray:
    gray = color.rgb2gray(img_rgb)
    grad = filters.sobel(gray)
    markers = np.zeros_like(gray, dtype=np.int32)
    q = np.quantile(grad, np.linspace(0.2, 0.8, k + 1))
    for i in range(k):
        band = (grad >= q[i]) & (grad < q[i + 1])
        markers[band] = i + 1
    ws = segmentation.watershed(grad, markers=markers, compactness=0.003)
    return (ws - 1) % k


def slic_cluster(img_rgb: np.ndarray, k: int) -> np.ndarray:
    seg = segmentation.slic(img_rgb, n_segments=250, compactness=10, start_label=0)
    n = seg.max() + 1
    means = np.zeros((n, 3), dtype=np.float32)
    for i in range(n):
        px = img_rgb[seg == i]
        means[i] = px.mean(axis=0)
    means = sanitize_features(means)
    km = KMeans(n_clusters=k, random_state=SEED, n_init=5)
    seg_labels = km.fit_predict(means)
    return seg_labels[seg]


def felzenszwalb_cluster(img_rgb: np.ndarray, k: int) -> np.ndarray:
    seg = segmentation.felzenszwalb(img_rgb, scale=120, sigma=0.8, min_size=40)
    n = seg.max() + 1
    means = np.zeros((n, 3), dtype=np.float32)
    for i in range(n):
        px = img_rgb[seg == i]
        means[i] = px.mean(axis=0)
    means = sanitize_features(means)
    gm = GaussianMixture(n_components=k, random_state=SEED, covariance_type="diag")
    seg_labels = gm.fit_predict(means)
    return seg_labels[seg]


def train_pixel_model(split: Dict[str, SplitData], centers: Dict[str, np.ndarray], mode: str):
    models = {}
    for subset_id, sdata in split.items():
        Xs = []
        ys = []
        for sample in sdata.train:
            img = read_image(sample.original_path, mode="RGB")
            mask = read_image(sample.mask_path, mode="RGB")
            y = mask_to_labels(mask, centers[subset_id]).reshape(-1)
            f = feat_rgb_grad(img)
            # sample pixels
            n = len(y)
            take = min(12000, n)
            idx = RNG.choice(n, take, replace=False)
            Xs.append(f[idx])
            ys.append(y[idx])
        X = np.concatenate(Xs, axis=0)
        X = sanitize_features(X)
        y = np.concatenate(ys, axis=0)
        if len(y) > MAX_TRAIN_PIXELS_PER_SUBSET:
            idx = RNG.choice(len(y), MAX_TRAIN_PIXELS_PER_SUBSET, replace=False)
            X = X[idx]
            y = y[idx]

        if mode == "rf":
            clf = RandomForestClassifier(
                n_estimators=120,
                max_depth=25,
                n_jobs=-1,
                random_state=SEED,
            )
            clf.fit(X, y)
        elif mode == "svm":
            clf = make_pipeline(StandardScaler(), LinearSVC(random_state=SEED, max_iter=5000))
            clf.fit(X, y)
        else:
            raise ValueError(mode)
        models[subset_id] = clf
    return models


def predict_method(method: str, img_rgb: np.ndarray, k: int, subset_id: str, trained=None) -> np.ndarray:
    if method == "kmeans_rgb":
        return model_cluster(feat_rgb(img_rgb), k, "kmeans").reshape(img_rgb.shape[:2])
    if method == "gmm_rgb":
        return model_cluster(feat_rgb(img_rgb), k, "gmm").reshape(img_rgb.shape[:2])
    if method == "rgbgrad_kmeans":
        return model_cluster(feat_rgb_grad(img_rgb), k, "kmeans").reshape(img_rgb.shape[:2])
    if method == "rgbgrad_gmm":
        return model_cluster(feat_rgb_grad(img_rgb), k, "gmm").reshape(img_rgb.shape[:2])
    if method == "canny_watershed":
        return canny_watershed(img_rgb, k)
    if method == "sobel_watershed":
        return sobel_watershed(img_rgb, k)
    if method == "slic_cluster":
        return slic_cluster(img_rgb, k)
    if method == "felzenszwalb_cluster":
        return felzenszwalb_cluster(img_rgb, k)
    if method == "lbp_kmeans":
        return model_cluster(feat_texture_lbp(img_rgb), k, "kmeans").reshape(img_rgb.shape[:2])
    if method == "gabor_kmeans":
        return model_cluster(feat_texture_gabor(img_rgb), k, "kmeans").reshape(img_rgb.shape[:2])
    if method == "rf_pixel":
        f = sanitize_features(feat_rgb_grad(img_rgb))
        return trained[subset_id].predict(f).reshape(img_rgb.shape[:2])
    if method == "svm_pixel":
        f = sanitize_features(feat_rgb_grad(img_rgb))
        return trained[subset_id].predict(f).reshape(img_rgb.shape[:2])
    raise ValueError(method)


def run():
    pairs, k_by_subset, subset_meta = load_dataset_pairs()
    split = deterministic_split(pairs)
    centers = estimate_mask_centroids(split, k_by_subset)

    methods = [
        ("kmeans_rgb", "baseline"),
        ("gmm_rgb", "baseline"),
        ("canny_watershed", "edge"),
        ("sobel_watershed", "edge"),
        ("slic_cluster", "contour_region"),
        ("felzenszwalb_cluster", "contour_region"),
        ("lbp_kmeans", "texture"),
        ("gabor_kmeans", "texture"),
        ("rf_pixel", "metallography_learned"),
        ("svm_pixel", "metallography_learned"),
    ]

    trained_models = {
        "rf_pixel": train_pixel_model(split, centers, "rf"),
        "svm_pixel": train_pixel_model(split, centers, "svm"),
    }

    rows = []
    for method, category in methods:
        for subset_id, sdata in split.items():
            k = k_by_subset[subset_id]
            for sample in sdata.test:
                img = read_image(sample.original_path, mode="RGB")
                mask = read_image(sample.mask_path, mode="RGB")
                gt = mask_to_labels(mask, centers[subset_id])
                pred = predict_method(
                    method,
                    img,
                    k,
                    subset_id,
                    trained=trained_models.get(method),
                )
                pred = hu_map(pred, gt, k)
                m = metrics(pred, gt, k)
                rows.append(
                    {
                        "method": method,
                        "category": category,
                        "subset": subset_id,
                        "family": subset_meta[subset_id]["family"],
                        "miou": m["miou"],
                        "dice": m["dice"],
                        "pixel_acc": m["pixel_acc"],
                        "image": sample.original_path.name,
                    }
                )

    df = pd.DataFrame(rows)
    df.to_csv(RESULT_DIR / "benchmark_raw_per_image.csv", index=False)

    per_subset = (
        df.groupby(["method", "category", "subset"], as_index=False)[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values(["method", "subset"])
    )
    per_subset.to_csv(RESULT_DIR / "benchmark_per_subset.csv", index=False)

    summary = (
        df.groupby(["method", "category"], as_index=False)[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values("miou", ascending=False)
    )
    summary.to_csv(RESULT_DIR / "benchmark_summary.csv", index=False)

    # macro over subsets
    macro_subset = (
        per_subset.groupby(["method", "category"], as_index=False)[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values("miou", ascending=False)
    )
    macro_subset.to_csv(RESULT_DIR / "benchmark_macro_over_subsets.csv", index=False)

    # markdown table for the paper
    md_lines = [
        "| Rank | Method | Category | mIoU | Dice | Pixel Acc |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for i, r in macro_subset.reset_index(drop=True).iterrows():
        md_lines.append(
            f"| {i+1} | {r['method']} | {r['category']} | {r['miou']:.4f} | {r['dice']:.4f} | {r['pixel_acc']:.4f} |"
        )

    (RESULT_DIR / "benchmark_table.md").write_text("\n".join(md_lines))

    protocol = {
        "seed": SEED,
        "img_size": IMG_SIZE,
        "train_fraction": TRAIN_FRACTION,
        "n_pairs": len(pairs),
        "test_images": int(sum(len(v.test) for v in split.values())),
        "methods": [m for m, _ in methods],
        "subset_test_counts": {k: len(v.test) for k, v in split.items()},
    }
    (RESULT_DIR / "benchmark_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved results to", RESULT_DIR)
    print(macro_subset.to_string(index=False))


if __name__ == "__main__":
    run()
