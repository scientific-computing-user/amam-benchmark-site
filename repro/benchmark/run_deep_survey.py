#!/usr/bin/env python3
"""
AMAM deep-learning benchmark extension.

This script runs two model sweeps on the strict 128-pair release:
1) 14 general-purpose deep segmentation models
2) 15 metallography-oriented deep variants

Outputs are written to:
  amam-site/repro/results/deep_survey/
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import pandas as pd
import segmentation_models_pytorch as smp
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from skimage import feature, filters
from skimage.filters import gabor
from sklearn.cluster import KMeans
from torch.utils.data import DataLoader, Dataset

warnings.filterwarnings(
    "ignore",
    message=r".*urllib3 v2 only supports OpenSSL.*",
)
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

SEED = 17
SPLIT_MODE = "fullset_no_holdout"
MAX_PIXELS_PER_MASK = 20_000

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_JSON = REPO_ROOT / "assets/data/amam-dataset.json"
OUT_DIR = REPO_ROOT / "repro/results/deep_survey"
OUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class PairSample:
    subset_id: str
    subset_name: str
    family: str
    phase_count: int
    phases: List[str]
    original_path: Path
    mask_path: Path


@dataclass
class SplitData:
    train: List[PairSample]
    test: List[PairSample]


@dataclass
class SampleRecord:
    subset_id: str
    subset_name: str
    family: str
    image_name: str
    original_path: Path
    image_rgb: np.ndarray  # HxWx3 uint8
    gt_local: np.ndarray  # HxW int64 in [0, k-1]
    gt_global: np.ndarray  # HxW int64 in [0, C-1]
    subset_global_ids: List[int]
    phase_count: int
    split: str


@dataclass
class ModelSpec:
    model_id: str
    display_name: str
    group: str  # "general" or "metallography"
    category: str
    architecture: str
    encoder_name: str
    input_mode: str
    encoder_weights: str | None = "imagenet"


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_dataset_pairs() -> Tuple[List[PairSample], Dict[str, int], Dict[str, dict]]:
    data = json.loads(DATA_JSON.read_text())
    pairs: List[PairSample] = []
    phase_count: Dict[str, int] = {}
    subset_meta: Dict[str, dict] = {}

    for subset in data["subsets"]:
        subset_id = subset["id"]
        k = len(subset.get("phases", []))
        if k < 2:
            continue

        masks = {
            m["id"]: Path(REPO_ROOT / m["path"])
            for m in subset.get("gallery", {}).get("masks", [])
            if m.get("id") and m.get("path")
        }

        subset_meta[subset_id] = subset
        phase_count[subset_id] = k

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
                    phase_count=k,
                    phases=list(subset.get("phases", [])),
                    original_path=orig_path,
                    mask_path=mask_path,
                )
            )

    return pairs, phase_count, subset_meta


def deterministic_split(pairs: List[PairSample]) -> Dict[str, SplitData]:
    by_subset: Dict[str, List[PairSample]] = {}
    for p in pairs:
        by_subset.setdefault(p.subset_id, []).append(p)

    split: Dict[str, SplitData] = {}
    for subset_id, items in by_subset.items():
        items = sorted(items, key=lambda x: x.original_path.name)
        # No holdout split: supervised models are fit and evaluated on the full pair set.
        split[subset_id] = SplitData(train=items, test=items)
    return split


def read_image(path: Path, img_size: int, mode: str = "RGB", nearest: bool = False) -> np.ndarray:
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.BILINEAR
    img = Image.open(path).convert(mode).resize((img_size, img_size), resample)
    return np.array(img)


def estimate_mask_centroids(
    split: Dict[str, SplitData], phase_count: Dict[str, int], img_size: int
) -> Dict[str, np.ndarray]:
    centers: Dict[str, np.ndarray] = {}
    for subset_id, sdata in split.items():
        k = phase_count[subset_id]
        pixels = []
        for sample in sdata.train:
            mask = read_image(sample.mask_path, img_size=img_size, mode="RGB", nearest=False).reshape(-1, 3)
            if len(mask) > MAX_PIXELS_PER_MASK:
                idx = np.random.choice(len(mask), MAX_PIXELS_PER_MASK, replace=False)
                mask = mask[idx]
            pixels.append(mask.astype(np.float32))
        x = np.concatenate(pixels, axis=0).astype(np.float64, copy=False)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        x = np.clip(x, 0.0, 255.0)
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED)
        km.fit(x)
        centers[subset_id] = km.cluster_centers_
    return centers


def mask_to_local_labels(mask_rgb: np.ndarray, centers: np.ndarray) -> np.ndarray:
    flat = mask_rgb.reshape(-1, 3).astype(np.float32)
    d = cdist(flat, centers.astype(np.float32))
    labels = np.argmin(d, axis=1)
    return labels.reshape(mask_rgb.shape[:2]).astype(np.int64)


def build_subset_offsets(phase_count: Dict[str, int]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    offsets: Dict[str, int] = {}
    subset_ids: Dict[str, List[int]] = {}
    current = 0
    for sid in sorted(phase_count.keys()):
        offsets[sid] = current
        ids = list(range(current, current + phase_count[sid]))
        subset_ids[sid] = ids
        current += phase_count[sid]
    return offsets, subset_ids, current


def build_records(
    pairs: List[PairSample],
    split: Dict[str, SplitData],
    centers: Dict[str, np.ndarray],
    subset_offsets: Dict[str, int],
    subset_global_ids: Dict[str, List[int]],
    img_size: int,
) -> List[SampleRecord]:
    train_keys = {p.original_path for s in split.values() for p in s.train}
    test_keys = {p.original_path for s in split.values() for p in s.test}
    records: List[SampleRecord] = []
    for p in pairs:
        img = read_image(p.original_path, img_size=img_size, mode="RGB", nearest=False)
        mask = read_image(p.mask_path, img_size=img_size, mode="RGB", nearest=False)
        local = mask_to_local_labels(mask, centers[p.subset_id])
        global_mask = local + subset_offsets[p.subset_id]
        in_train = p.original_path in train_keys
        in_test = p.original_path in test_keys
        if in_train and in_test:
            split_name = "train_test"
        elif in_train:
            split_name = "train"
        else:
            split_name = "test"
        records.append(
            SampleRecord(
                subset_id=p.subset_id,
                subset_name=p.subset_name,
                family=p.family,
                image_name=p.original_path.name,
                original_path=p.original_path,
                image_rgb=img.astype(np.uint8),
                gt_local=local.astype(np.int64),
                gt_global=global_mask.astype(np.int64),
                subset_global_ids=subset_global_ids[p.subset_id],
                phase_count=p.phase_count,
                split=split_name,
            )
        )
    return records


def preprocess_rgb(img_rgb: np.ndarray, normalize_imagenet: bool = True) -> np.ndarray:
    x = img_rgb.astype(np.float32) / 255.0
    if normalize_imagenet:
        x = (x - IMAGENET_MEAN) / IMAGENET_STD
    return x


def preprocess_gray(img_rgb: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    return g[..., None]


def preprocess_clahe_rgb(img_rgb: np.ndarray, normalize_imagenet: bool = True) -> np.ndarray:
    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    out = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2RGB).astype(np.float32) / 255.0
    if normalize_imagenet:
        out = (out - IMAGENET_MEAN) / IMAGENET_STD
    return out


def preprocess_edge4(img_rgb: np.ndarray) -> np.ndarray:
    rgb = preprocess_rgb(img_rgb, normalize_imagenet=True)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    sob = filters.sobel(gray).astype(np.float32)
    sob = sob[..., None]
    return np.concatenate([rgb, sob], axis=-1)


def preprocess_gabor3(img_rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    r1, _ = gabor(gray, frequency=0.18, theta=0.0)
    r2, _ = gabor(gray, frequency=0.18, theta=np.pi / 2)
    stack = np.stack([gray, r1.astype(np.float32), r2.astype(np.float32)], axis=-1)
    mn = stack.mean(axis=(0, 1), keepdims=True)
    sd = stack.std(axis=(0, 1), keepdims=True)
    sd = np.where(sd < 1e-6, 1.0, sd)
    stack = (stack - mn) / sd
    return stack.astype(np.float32)


def preprocess_lbp3(img_rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    lbp = feature.local_binary_pattern(gray, P=8, R=1, method="uniform").astype(np.float32)
    lbp = lbp / (lbp.max() if lbp.max() > 0 else 1.0)
    sob = filters.sobel(gray.astype(np.float32) / 255.0).astype(np.float32)
    g = gray.astype(np.float32) / 255.0
    stack = np.stack([g, lbp, sob], axis=-1)
    return stack.astype(np.float32)


def make_input_features(img_rgb: np.ndarray, mode: str) -> np.ndarray:
    if mode == "rgb":
        return preprocess_rgb(img_rgb)
    if mode == "gray":
        return preprocess_gray(img_rgb)
    if mode == "clahe_rgb":
        return preprocess_clahe_rgb(img_rgb)
    if mode == "edge4":
        return preprocess_edge4(img_rgb)
    if mode == "gabor3":
        return preprocess_gabor3(img_rgb)
    if mode == "lbp3":
        return preprocess_lbp3(img_rgb)
    raise ValueError(f"Unknown input mode: {mode}")


class ModeFeatureCache:
    def __init__(self, records: List[SampleRecord], modes: List[str]):
        self.records = records
        self.modes = sorted(set(modes))
        self.cache: Dict[str, List[np.ndarray]] = {}

    def ensure(self, mode: str) -> None:
        if mode in self.cache:
            return
        feats = []
        for rec in self.records:
            x = make_input_features(rec.image_rgb, mode)
            feats.append(x.astype(np.float32))
        self.cache[mode] = feats

    def get(self, mode: str, idx: int) -> np.ndarray:
        self.ensure(mode)
        return self.cache[mode][idx]


class SegDataset(Dataset):
    def __init__(
        self,
        indices: List[int],
        records: List[SampleRecord],
        feature_cache: ModeFeatureCache,
        input_mode: str,
        augment: bool,
    ):
        self.indices = indices
        self.records = records
        self.feature_cache = feature_cache
        self.input_mode = input_mode
        self.augment = augment

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, i: int):
        idx = self.indices[i]
        rec = self.records[idx]
        x = self.feature_cache.get(self.input_mode, idx).copy()
        y = rec.gt_global.copy()

        if self.augment:
            if random.random() < 0.5:
                x = np.fliplr(x)
                y = np.fliplr(y)
            if random.random() < 0.5:
                x = np.flipud(x)
                y = np.flipud(y)

        if x.ndim == 2:
            x = x[..., None]
        x = np.transpose(x, (2, 0, 1)).astype(np.float32)
        y = y.astype(np.int64)
        return torch.from_numpy(x), torch.from_numpy(y)


def get_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def make_model(spec: ModelSpec, num_classes: int, in_channels: int) -> nn.Module:
    cls = getattr(smp, spec.architecture)
    model = cls(
        encoder_name=spec.encoder_name,
        encoder_weights=spec.encoder_weights,
        in_channels=in_channels,
        classes=num_classes,
    )
    return model


def metrics_local(pred: np.ndarray, gt: np.ndarray, k: int) -> Dict[str, float]:
    ious = []
    dices = []
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
    acc = (pred == gt).mean()
    return {"miou": float(np.mean(ious)), "dice": float(np.mean(dices)), "pixel_acc": float(acc)}


def count_params_m(model: nn.Module) -> float:
    return float(sum(p.numel() for p in model.parameters()) / 1e6)


def eval_model(
    model: nn.Module,
    records: List[SampleRecord],
    test_indices: List[int],
    feature_cache: ModeFeatureCache,
    input_mode: str,
    device: torch.device,
) -> List[dict]:
    model.eval()
    rows = []
    with torch.no_grad():
        for idx in test_indices:
            rec = records[idx]
            x = feature_cache.get(input_mode, idx)
            if x.ndim == 2:
                x = x[..., None]
            xt = torch.from_numpy(np.transpose(x, (2, 0, 1))).unsqueeze(0).float().to(device)
            logits = model(xt)
            if logits.shape[-2:] != rec.gt_local.shape:
                logits = F.interpolate(logits, size=rec.gt_local.shape, mode="bilinear", align_corners=False)
            logits = logits[0].detach().cpu().numpy()
            subset_logits = logits[rec.subset_global_ids, :, :]
            pred_local = np.argmax(subset_logits, axis=0).astype(np.int64)
            m = metrics_local(pred_local, rec.gt_local, rec.phase_count)
            rows.append(
                {
                    "subset": rec.subset_id,
                    "subset_name": rec.subset_name,
                    "family": rec.family,
                    "image": rec.image_name,
                    "miou": m["miou"],
                    "dice": m["dice"],
                    "pixel_acc": m["pixel_acc"],
                }
            )
    return rows


def train_single_model(
    spec: ModelSpec,
    records: List[SampleRecord],
    train_indices: List[int],
    test_indices: List[int],
    feature_cache: ModeFeatureCache,
    num_classes: int,
    device: torch.device,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    workers: int,
    ) -> Tuple[pd.DataFrame, dict]:
    in_channels = {
        "rgb": 3,
        "gray": 1,
        "clahe_rgb": 3,
        "edge4": 4,
        "gabor3": 3,
        "lbp3": 3,
    }[spec.input_mode]

    train_ds = SegDataset(
        indices=train_indices,
        records=records,
        feature_cache=feature_cache,
        input_mode=spec.input_mode,
        augment=True,
    )
    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        drop_last=False,
    )

    model = make_model(spec, num_classes=num_classes, in_channels=in_channels).to(device)
    params_m = count_params_m(model)

    # Class weighting for subset-unique global classes.
    class_hist = np.zeros((num_classes,), dtype=np.float64)
    for idx in train_indices:
        y = records[idx].gt_global
        vals, cnt = np.unique(y, return_counts=True)
        class_hist[vals] += cnt
    class_hist = np.maximum(class_hist, 1.0)
    inv = 1.0 / np.sqrt(class_hist)
    weights = (inv / inv.mean()).astype(np.float32)
    loss_fn = nn.CrossEntropyLoss(weight=torch.from_numpy(weights).to(device))

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    start = time.time()
    for _ in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb = xb.to(device).contiguous()
            yb = yb.to(device).contiguous()
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb).contiguous()
            if logits.shape[-2:] != yb.shape[-2:]:
                logits = F.interpolate(logits, size=yb.shape[-2:], mode="bilinear", align_corners=False)
            logits = logits.contiguous()
            loss = loss_fn(logits, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

    elapsed = time.time() - start

    rows = eval_model(
        model=model,
        records=records,
        test_indices=test_indices,
        feature_cache=feature_cache,
        input_mode=spec.input_mode,
        device=device,
    )
    df = pd.DataFrame(rows)

    meta = {
        "model_id": spec.model_id,
        "display_name": spec.display_name,
        "group": spec.group,
        "category": spec.category,
        "architecture": spec.architecture,
        "encoder": spec.encoder_name,
        "input_mode": spec.input_mode,
        "params_m": params_m,
        "train_seconds": elapsed,
        "device": str(device),
    }

    del model
    gc.collect()
    if hasattr(torch, "mps") and device.type == "mps":
        torch.mps.empty_cache()

    return df, meta


def aggregate_results(per_image: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    per_subset = (
        per_image.groupby(
            ["model_id", "display_name", "group", "category", "architecture", "encoder", "input_mode", "subset"],
            as_index=False,
        )[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values(["group", "miou"], ascending=[True, False])
    )
    macro = (
        per_subset.groupby(
            ["model_id", "display_name", "group", "category", "architecture", "encoder", "input_mode"],
            as_index=False,
        )[["miou", "dice", "pixel_acc"]]
        .mean()
        .sort_values(["group", "miou"], ascending=[True, False])
    )
    return per_subset, macro


def build_model_specs() -> List[ModelSpec]:
    general = [
        ModelSpec("dl_unet_r34", "U-Net (ResNet34)", "general", "encoder-decoder", "Unet", "resnet34", "rgb"),
        ModelSpec(
            "dl_unetpp_r34",
            "U-Net++ (ResNet34)",
            "general",
            "encoder-decoder",
            "UnetPlusPlus",
            "resnet34",
            "rgb",
        ),
        ModelSpec("dl_deeplabv3_r34", "DeepLabV3 (ResNet34)", "general", "context-atrous", "DeepLabV3", "resnet34", "rgb"),
        ModelSpec(
            "dl_deeplabv3p_r34",
            "DeepLabV3+ (ResNet34)",
            "general",
            "context-atrous",
            "DeepLabV3Plus",
            "resnet34",
            "rgb",
        ),
        ModelSpec("dl_fpn_r34", "FPN (ResNet34)", "general", "pyramid", "FPN", "resnet34", "rgb"),
        ModelSpec("dl_pspnet_r34", "PSPNet (ResNet34)", "general", "pyramid", "PSPNet", "resnet34", "rgb"),
        ModelSpec("dl_linknet_r34", "LinkNet (ResNet34)", "general", "lightweight", "Linknet", "resnet34", "rgb"),
        ModelSpec("dl_manet_r34", "MAnet (ResNet34)", "general", "attention", "MAnet", "resnet34", "rgb"),
        ModelSpec("dl_segformer_b0", "SegFormer (MiT-B0)", "general", "transformer", "Segformer", "mit_b0", "rgb"),
        ModelSpec("dl_upernet_b0", "UPerNet (MiT-B0)", "general", "transformer", "UPerNet", "mit_b0", "rgb"),
        ModelSpec("dl_segformer_b2", "SegFormer (MiT-B2)", "general", "transformer", "Segformer", "mit_b2", "rgb"),
        ModelSpec("dl_upernet_b2", "UPerNet (MiT-B2)", "general", "transformer", "UPerNet", "mit_b2", "rgb"),
        ModelSpec(
            "dl_unet_effb0",
            "U-Net (EfficientNet-B0)",
            "general",
            "encoder-decoder",
            "Unet",
            "tu-efficientnet_b0",
            "rgb",
        ),
        ModelSpec(
            "dl_deeplabv3p_effb0",
            "DeepLabV3+ (EfficientNet-B0)",
            "general",
            "context-atrous",
            "DeepLabV3Plus",
            "tu-efficientnet_b0",
            "rgb",
        ),
    ]

    metallography = [
        ModelSpec(
            "metal_unet_gray_r34",
            "Metal-U-Net Gray (ResNet34)",
            "metallography",
            "micrograph-contrast",
            "Unet",
            "resnet34",
            "gray",
        ),
        ModelSpec(
            "metal_unet_clahe_r34",
            "Metal-U-Net CLAHE (ResNet34)",
            "metallography",
            "micrograph-contrast",
            "Unet",
            "resnet34",
            "clahe_rgb",
        ),
        ModelSpec(
            "metal_unet_edge4_r34",
            "Metal-U-Net RGB+Sobel (ResNet34)",
            "metallography",
            "edge-aware",
            "Unet",
            "resnet34",
            "edge4",
        ),
        ModelSpec(
            "metal_unet_gabor_r34",
            "Metal-U-Net Gabor Stack (ResNet34)",
            "metallography",
            "texture-aware",
            "Unet",
            "resnet34",
            "gabor3",
        ),
        ModelSpec(
            "metal_unet_lbp_r34",
            "Metal-U-Net LBP Stack (ResNet34)",
            "metallography",
            "texture-aware",
            "Unet",
            "resnet34",
            "lbp3",
        ),
        ModelSpec(
            "metal_unetpp_gray_r34",
            "Metal-U-Net++ Gray (ResNet34)",
            "metallography",
            "micrograph-contrast",
            "UnetPlusPlus",
            "resnet34",
            "gray",
        ),
        ModelSpec(
            "metal_deeplabv3p_clahe_r34",
            "Metal-DeepLabV3+ CLAHE (ResNet34)",
            "metallography",
            "micrograph-contrast",
            "DeepLabV3Plus",
            "resnet34",
            "clahe_rgb",
        ),
        ModelSpec(
            "metal_fpn_gabor_r34",
            "Metal-FPN Gabor Stack (ResNet34)",
            "metallography",
            "texture-aware",
            "FPN",
            "resnet34",
            "gabor3",
        ),
        ModelSpec(
            "metal_linknet_edge4_r34",
            "Metal-LinkNet RGB+Sobel (ResNet34)",
            "metallography",
            "edge-aware",
            "Linknet",
            "resnet34",
            "edge4",
        ),
        ModelSpec(
            "metal_segformer_clahe_b0",
            "Metal-SegFormer CLAHE (MiT-B0)",
            "metallography",
            "micrograph-contrast",
            "Segformer",
            "mit_b0",
            "clahe_rgb",
        ),
        ModelSpec(
            "metal_upernet_clahe_b2",
            "Metal-UPerNet CLAHE (MiT-B2)",
            "metallography",
            "micrograph-contrast",
            "UPerNet",
            "mit_b2",
            "clahe_rgb",
        ),
        ModelSpec(
            "metal_segformer_gray_b2",
            "Metal-SegFormer Gray (MiT-B2)",
            "metallography",
            "micrograph-contrast",
            "Segformer",
            "mit_b2",
            "gray",
        ),
        ModelSpec(
            "metal_manet_edge4_effb0",
            "Metal-MAnet RGB+Sobel (EfficientNet-B0)",
            "metallography",
            "edge-aware",
            "MAnet",
            "tu-efficientnet_b0",
            "edge4",
        ),
        ModelSpec(
            "metal_unetpp_clahe_effb0",
            "Metal-U-Net++ CLAHE (EfficientNet-B0)",
            "metallography",
            "micrograph-contrast",
            "UnetPlusPlus",
            "tu-efficientnet_b0",
            "clahe_rgb",
        ),
        ModelSpec(
            "metal_mlography_unet_vgg16_gray",
            "MLography U-Net (2022-style)",
            "metallography",
            "metallography-original",
            "Unet",
            "vgg16",
            "gray",
            None,
        ),
    ]

    return general + metallography


def write_markdown_table(df: pd.DataFrame, out_path: Path, title: str) -> None:
    lines = [f"## {title}", "", "| Rank | Model | Category | mIoU | Dice | Pixel Acc | Params (M) | Train min |", "|---:|---|---|---:|---:|---:|---:|---:|"]
    for i, r in df.reset_index(drop=True).iterrows():
        lines.append(
            f"| {i+1} | {r['display_name']} | {r['category']} | {r['miou']:.4f} | {r['dice']:.4f} | {r['pixel_acc']:.4f} | {r['params_m']:.2f} | {r['train_minutes']:.1f} |"
        )
    out_path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run deep AMAM benchmark surveys.")
    p.add_argument("--img-size", type=int, default=192)
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--device", type=str, default="auto")
    p.add_argument(
        "--models",
        type=str,
        default="",
        help="Comma-separated model_ids to run (default: all deep models).",
    )
    p.add_argument("--max-models", type=int, default=0, help="For smoke runs only.")
    p.add_argument("--no-resume", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(SEED)

    device = get_device(args.device)
    print(f"[info] device={device}")

    pairs, phase_count, _subset_meta = load_dataset_pairs()
    split = deterministic_split(pairs)
    centers = estimate_mask_centroids(split=split, phase_count=phase_count, img_size=args.img_size)
    subset_offsets, subset_global_ids, num_classes = build_subset_offsets(phase_count)
    records = build_records(
        pairs=pairs,
        split=split,
        centers=centers,
        subset_offsets=subset_offsets,
        subset_global_ids=subset_global_ids,
        img_size=args.img_size,
    )

    train_indices = [i for i, r in enumerate(records) if r.split in {"train", "train_test"}]
    test_indices = [i for i, r in enumerate(records) if r.split in {"test", "train_test"}]
    print(f"[info] pairs={len(records)} train={len(train_indices)} test={len(test_indices)} num_classes={num_classes}")

    all_specs = build_model_specs()
    specs = list(all_specs)
    if args.models.strip():
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        specs = [s for s in specs if s.model_id in wanted]
        if not specs:
            raise ValueError("No matching model_ids in --models.")
    if args.max_models > 0:
        specs = specs[: args.max_models]

    used_modes = [s.input_mode for s in specs]
    feature_cache = ModeFeatureCache(records=records, modes=used_modes)

    per_image_csv = OUT_DIR / "deep_per_image.csv"
    meta_json = OUT_DIR / "deep_model_meta.json"

    all_rows: List[pd.DataFrame] = []
    meta_rows: Dict[str, dict] = {}
    done_ids = set()
    if per_image_csv.exists() and meta_json.exists() and not args.no_resume:
        prev = pd.read_csv(per_image_csv)
        all_rows.append(prev)
        done_ids = set(prev["model_id"].unique())
        meta_rows = json.loads(meta_json.read_text())
        print(f"[info] resume enabled, skipping {len(done_ids)} completed models")

    for spec in specs:
        if spec.model_id in done_ids:
            print(f"[skip] {spec.model_id}")
            continue
        print(f"[run] {spec.model_id} ({spec.display_name})")
        try:
            df, meta = train_single_model(
                spec=spec,
                records=records,
                train_indices=train_indices,
                test_indices=test_indices,
                feature_cache=feature_cache,
                num_classes=num_classes,
                device=device,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                weight_decay=args.weight_decay,
                workers=args.workers,
            )
        except RuntimeError as exc:
            if device.type == "mps":
                print(f"[warn] {spec.model_id} failed on MPS ({exc}). Retrying on CPU.")
                df, meta = train_single_model(
                    spec=spec,
                    records=records,
                    train_indices=train_indices,
                    test_indices=test_indices,
                    feature_cache=feature_cache,
                    num_classes=num_classes,
                    device=torch.device("cpu"),
                    epochs=args.epochs,
                    batch_size=args.batch_size,
                    lr=args.lr,
                    weight_decay=args.weight_decay,
                    workers=args.workers,
                )
            else:
                raise
        df["model_id"] = spec.model_id
        df["display_name"] = spec.display_name
        df["group"] = spec.group
        df["category"] = spec.category
        df["architecture"] = spec.architecture
        df["encoder"] = spec.encoder_name
        df["input_mode"] = spec.input_mode
        df["params_m"] = meta["params_m"]
        df["train_seconds"] = meta["train_seconds"]
        all_rows.append(df)
        meta_rows[spec.model_id] = meta

        # incremental save for crash-safe long sweeps
        merged = pd.concat(all_rows, ignore_index=True)
        merged.to_csv(per_image_csv, index=False)
        meta_json.write_text(json.dumps(meta_rows, indent=2))

    if not all_rows:
        raise RuntimeError("No model results produced.")

    per_image = pd.concat(all_rows, ignore_index=True)
    per_subset, macro = aggregate_results(per_image)

    # Add train meta to macro summary
    meta_df = pd.DataFrame(meta_rows.values())
    if not meta_df.empty:
        meta_df["train_minutes"] = meta_df["train_seconds"] / 60.0
        macro = macro.merge(
            meta_df[
                [
                    "model_id",
                    "params_m",
                    "train_seconds",
                    "train_minutes",
                ]
            ],
            on="model_id",
            how="left",
        )

    macro = macro.sort_values(["group", "miou"], ascending=[True, False]).reset_index(drop=True)
    per_subset = per_subset.sort_values(["group", "model_id", "subset"]).reset_index(drop=True)

    per_subset.to_csv(OUT_DIR / "deep_per_subset.csv", index=False)
    macro.to_csv(OUT_DIR / "deep_macro_over_subsets.csv", index=False)

    general = macro[macro["group"] == "general"].copy()
    metallography = macro[macro["group"] == "metallography"].copy()
    general.to_csv(OUT_DIR / "deep_general_summary.csv", index=False)
    metallography.to_csv(OUT_DIR / "deep_metallography_summary.csv", index=False)

    write_markdown_table(
        general,
        OUT_DIR / "deep_general_table.md",
        f"General Deep Segmentation Models ({len(general)})",
    )
    write_markdown_table(
        metallography,
        OUT_DIR / "deep_metallography_table.md",
        f"Metallography-Oriented Deep Models ({len(metallography)})",
    )

    protocol = {
        "seed": SEED,
        "img_size": args.img_size,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "split_mode": SPLIT_MODE,
        "n_pairs": len(records),
        "train_images": len(train_indices),
        "test_images": len(test_indices),
        "num_global_classes": num_classes,
        "models": [s.model_id for s in all_specs],
        "selected_models": [s.model_id for s in specs],
        "completed_models": sorted(per_image["model_id"].unique().tolist()),
        "resume_enabled": (not args.no_resume),
    }
    (OUT_DIR / "deep_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\n[done] saved results to", OUT_DIR)
    print("\n[general top]")
    print(general[["display_name", "miou", "dice", "pixel_acc"]].head(10).to_string(index=False))
    print("\n[metallography top]")
    print(metallography[["display_name", "miou", "dice", "pixel_acc"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
