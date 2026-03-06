#!/usr/bin/env python3
"""
Build representative appendix prediction assets for AMAM paper.

Produces, for each representative sample:
- best classical prediction (RF pixel model),
- best general deep prediction (U-Net EfficientNet-B0),
- best metallography-oriented deep prediction (Metal-U-Net++ CLAHE EfficientNet-B0).

Outputs are written to:
  amam-site/repro/figures/appendix_preds/
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from scipy.optimize import linear_sum_assignment
from torch.utils.data import DataLoader

import run_benchmark as rb
import run_deep_survey as rds

REPO_ROOT = Path(__file__).resolve().parents[2]
REPRO_ROOT = REPO_ROOT / "repro"
OUT_DIR = REPRO_ROOT / "figures" / "appendix_preds"
DATA_ROOT = REPO_ROOT / "data" / "local"
OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RepSample:
    slug: str
    subset_id: str
    original: Path
    mask: Path


REP_SAMPLES: List[RepSample] = [
    RepSample(
        slug="4130-steel",
        subset_id="4130-steel",
        original=DATA_ROOT / "4130-steel" / "images" / "4130x10 (1).jpg",
        mask=DATA_ROOT / "4130-steel" / "labels" / "6362 x 10 (1).png",
    ),
    RepSample(
        slug="6280-cast-iron-low",
        subset_id="6280-cast-iron-low",
        original=DATA_ROOT / "6280-cast-iron-low" / "images" / "6280 x 10 (1).jpg",
        mask=DATA_ROOT / "6280-cast-iron-low" / "labels" / "x10 (1).png",
    ),
    RepSample(
        slug="6280-cast-iron-high",
        subset_id="6280-cast-iron-high",
        original=DATA_ROOT / "6280-cast-iron-high" / "images" / "6280 x 20 (1).jpg",
        mask=DATA_ROOT / "6280-cast-iron-high" / "labels" / "x20 (1).png",
    ),
    RepSample(
        slug="5884-armor-steel",
        subset_id="5884-armor-steel",
        original=DATA_ROOT / "5884-armor-steel" / "images" / "armor steel  x 5 (3).jpg",
        mask=DATA_ROOT / "5884-armor-steel" / "labels" / "5884 x 5 (3).png",
    ),
    RepSample(
        slug="418-17-4ph-x5",
        subset_id="418-17-4ph-x5",
        original=DATA_ROOT / "418-17-4ph-x5" / "images" / "x5 (1).jpg",
        mask=DATA_ROOT / "418-17-4ph-x5" / "labels" / "x5 (1).png",
    ),
    RepSample(
        slug="418-17-4ph-x20",
        subset_id="418-17-4ph-x20",
        original=DATA_ROOT / "418-17-4ph-x20" / "images" / "x20 (1).jpg",
        mask=DATA_ROOT / "418-17-4ph-x20" / "labels" / "x20 (1).png",
    ),
]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def map_hungarian(pred: np.ndarray, gt: np.ndarray, k: int) -> np.ndarray:
    conf = np.zeros((k, k), dtype=np.int64)
    for i in range(k):
        for j in range(k):
            conf[i, j] = int(np.sum((pred == i) & (gt == j)))
    row_ind, col_ind = linear_sum_assignment(conf.max() - conf)
    mapped = np.zeros_like(pred)
    for r, c in zip(row_ind, col_ind):
        mapped[pred == r] = c
    return mapped


def labels_to_rgb(labels: np.ndarray, centers: np.ndarray) -> np.ndarray:
    palette = np.clip(np.round(centers), 0, 255).astype(np.uint8)
    return palette[labels]


def read_resized_rgb(path: Path, size: int) -> np.ndarray:
    return np.array(
        Image.open(path).convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    )


def train_best_classical_rf() -> tuple[Dict[str, object], Dict[str, np.ndarray], Dict[str, int]]:
    pairs, phase_count, _subset_meta = rb.load_dataset_pairs()
    split = rb.deterministic_split(pairs)
    centers = rb.estimate_mask_centroids(split, phase_count)
    models = rb.train_pixel_model(split=split, centers=centers, mode="rf")
    return models, centers, phase_count


def train_deep_model_return_model(
    spec: rds.ModelSpec,
    records: List[rds.SampleRecord],
    train_indices: List[int],
    feature_cache: rds.ModeFeatureCache,
    num_classes: int,
    device: torch.device,
    epochs: int = 5,
    batch_size: int = 4,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    workers: int = 0,
) -> nn.Module:
    in_channels = {
        "rgb": 3,
        "gray": 1,
        "clahe_rgb": 3,
        "edge4": 4,
        "gabor3": 3,
        "lbp3": 3,
    }[spec.input_mode]

    train_ds = rds.SegDataset(
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

    model = rds.make_model(spec, num_classes=num_classes, in_channels=in_channels).to(device)

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

    for _ in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb = xb.to(device).contiguous()
            yb = yb.to(device).contiguous()
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb).contiguous()
            if logits.shape[-2:] != yb.shape[-2:]:
                logits = F.interpolate(logits, size=yb.shape[-2:], mode="bilinear", align_corners=False)
            loss = loss_fn(logits, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

    model.eval()
    return model


def train_best_deep_models():
    set_seed(rds.SEED)
    pairs, phase_count, _subset_meta = rds.load_dataset_pairs()
    split = rds.deterministic_split(pairs)
    img_size = 192
    centers = rds.estimate_mask_centroids(split=split, phase_count=phase_count, img_size=img_size)
    subset_offsets, subset_global_ids, num_classes = rds.build_subset_offsets(phase_count)
    records = rds.build_records(
        pairs=pairs,
        split=split,
        centers=centers,
        subset_offsets=subset_offsets,
        subset_global_ids=subset_global_ids,
        img_size=img_size,
    )
    train_indices = [i for i, r in enumerate(records) if r.split == "train"]

    specs = {s.model_id: s for s in rds.build_model_specs()}
    spec_general = specs["dl_unet_effb0"]
    spec_metal = specs["metal_unetpp_clahe_effb0"]
    feature_cache = rds.ModeFeatureCache(records=records, modes=[spec_general.input_mode, spec_metal.input_mode])

    device = rds.get_device("auto")
    print(f"[deep] device={device}")

    def _train_with_fallback(spec: rds.ModelSpec) -> nn.Module:
        try:
            print(f"[deep] train {spec.model_id}")
            return train_deep_model_return_model(
                spec=spec,
                records=records,
                train_indices=train_indices,
                feature_cache=feature_cache,
                num_classes=num_classes,
                device=device,
            )
        except RuntimeError as exc:
            if device.type == "mps":
                print(f"[deep] retry on cpu for {spec.model_id} due to: {exc}")
                return train_deep_model_return_model(
                    spec=spec,
                    records=records,
                    train_indices=train_indices,
                    feature_cache=feature_cache,
                    num_classes=num_classes,
                    device=torch.device("cpu"),
                )
            raise

    model_general = _train_with_fallback(spec_general)
    model_metal = _train_with_fallback(spec_metal)

    return {
        "img_size": img_size,
        "centers": centers,
        "subset_global_ids": subset_global_ids,
        "spec_general": spec_general,
        "spec_metal": spec_metal,
        "model_general": model_general,
        "model_metal": model_metal,
    }


def infer_deep_local(
    model: nn.Module,
    spec: rds.ModelSpec,
    img_rgb: np.ndarray,
    subset_id: str,
    subset_global_ids: Dict[str, List[int]],
    device: torch.device,
) -> np.ndarray:
    x = rds.make_input_features(img_rgb, mode=spec.input_mode)
    if x.ndim == 2:
        x = x[..., None]
    xt = torch.from_numpy(np.transpose(x, (2, 0, 1))).unsqueeze(0).float().to(device)
    with torch.no_grad():
        logits = model(xt)[0].detach().cpu().numpy()
    local_logits = logits[subset_global_ids[subset_id], :, :]
    return np.argmax(local_logits, axis=0).astype(np.int64)


def save_png(path: Path, arr_rgb: np.ndarray) -> None:
    Image.fromarray(arr_rgb.astype(np.uint8)).save(path)


def main() -> None:
    set_seed(rb.SEED)
    print("[classic] train best classical model: RF pixel")
    rf_models, centers_classic, phase_count_classic = train_best_classical_rf()

    print("[deep] train best general + best metallography models")
    deep_bundle = train_best_deep_models()
    deep_device = next(deep_bundle["model_general"].parameters()).device
    metal_device = next(deep_bundle["model_metal"].parameters()).device

    for sample in REP_SAMPLES:
        print(f"[sample] {sample.slug}")
        k_classic = phase_count_classic[sample.subset_id]
        img_size_deep = int(deep_bundle["img_size"])

        # Use a unified 192x192 canvas for all displayed panels (original/mask/predictions)
        # so visual comparisons remain spatially aligned.
        img_viz = read_resized_rgb(sample.original, size=img_size_deep)
        mask_viz = read_resized_rgb(sample.mask, size=img_size_deep)
        save_png(OUT_DIR / f"{sample.slug}-viz-original.png", img_viz)
        save_png(OUT_DIR / f"{sample.slug}-viz-mask.png", mask_viz)

        img_classic = img_viz
        mask_classic = mask_viz
        gt_classic = rb.mask_to_labels(mask_classic, centers_classic[sample.subset_id])
        pred_classic = rb.predict_method(
            method="rf_pixel",
            img_rgb=img_classic,
            k=k_classic,
            subset_id=sample.subset_id,
            trained=rf_models,
        )
        pred_classic = rb.hu_map(pred_classic, gt_classic, k_classic)
        rgb_classic = labels_to_rgb(pred_classic, centers_classic[sample.subset_id])
        save_png(OUT_DIR / f"{sample.slug}-pred-classic-rf.png", rgb_classic)

        centers_deep = deep_bundle["centers"]
        subset_global_ids = deep_bundle["subset_global_ids"]
        k_deep = centers_deep[sample.subset_id].shape[0]

        img_deep = img_viz
        mask_deep = mask_viz
        gt_deep = rds.mask_to_local_labels(mask_deep, centers_deep[sample.subset_id])

        pred_general = infer_deep_local(
            model=deep_bundle["model_general"],
            spec=deep_bundle["spec_general"],
            img_rgb=img_deep,
            subset_id=sample.subset_id,
            subset_global_ids=subset_global_ids,
            device=deep_device,
        )
        pred_general = map_hungarian(pred_general, gt_deep, k_deep)
        rgb_general = labels_to_rgb(pred_general, centers_deep[sample.subset_id])
        save_png(OUT_DIR / f"{sample.slug}-pred-deep-unet-effb0.png", rgb_general)

        pred_metal = infer_deep_local(
            model=deep_bundle["model_metal"],
            spec=deep_bundle["spec_metal"],
            img_rgb=img_deep,
            subset_id=sample.subset_id,
            subset_global_ids=subset_global_ids,
            device=metal_device,
        )
        pred_metal = map_hungarian(pred_metal, gt_deep, k_deep)
        rgb_metal = labels_to_rgb(pred_metal, centers_deep[sample.subset_id])
        save_png(OUT_DIR / f"{sample.slug}-pred-metal-unetpp-clahe-effb0.png", rgb_metal)

    print(f"[done] wrote prediction assets to {OUT_DIR}")


if __name__ == "__main__":
    main()
