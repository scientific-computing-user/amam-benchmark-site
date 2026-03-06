## Metallography-Oriented Deep Models (15)

| Rank | Model | Category | mIoU | Dice | Pixel Acc | Params (M) | Train min |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | Metal-U-Net++ CLAHE (EfficientNet-B0) | micrograph-contrast | 0.6427 | 0.7456 | 0.8684 | 6.07 | 0.3 |
| 2 | Metal-MAnet RGB+Sobel (EfficientNet-B0) | edge-aware | 0.5987 | 0.7059 | 0.8294 | 8.67 | 0.3 |
| 3 | Metal-U-Net CLAHE (ResNet34) | micrograph-contrast | 0.5857 | 0.6962 | 0.8144 | 24.44 | 0.3 |
| 4 | Metal-U-Net RGB+Sobel (ResNet34) | edge-aware | 0.5784 | 0.6860 | 0.7984 | 24.44 | 0.3 |
| 5 | Metal-SegFormer CLAHE (MiT-B0) | micrograph-contrast | 0.5766 | 0.6848 | 0.8258 | 3.72 | 1.2 |
| 6 | Metal-U-Net Gray (ResNet34) | micrograph-contrast | 0.5713 | 0.6905 | 0.7555 | 24.43 | 0.3 |
| 7 | Metal-U-Net++ Gray (ResNet34) | micrograph-contrast | 0.5646 | 0.6914 | 0.7667 | 26.07 | 0.6 |
| 8 | Metal-DeepLabV3+ CLAHE (ResNet34) | micrograph-contrast | 0.5600 | 0.6829 | 0.7603 | 22.44 | 0.4 |
| 9 | Metal-LinkNet RGB+Sobel (ResNet34) | edge-aware | 0.5362 | 0.6546 | 0.7630 | 21.78 | 0.3 |
| 10 | MLography U-Net (2022-style) | metallography-original | 0.5115 | 0.6347 | 0.7489 | 23.75 | 0.4 |
| 11 | Metal-U-Net LBP Stack (ResNet34) | texture-aware | 0.4882 | 0.5945 | 0.6861 | 24.44 | 0.3 |
| 12 | Metal-SegFormer Gray (MiT-B2) | micrograph-contrast | 0.4802 | 0.5961 | 0.6941 | 24.72 | 3.9 |
| 13 | Metal-FPN Gabor Stack (ResNet34) | texture-aware | 0.4508 | 0.5565 | 0.7075 | 23.16 | 0.3 |
| 14 | Metal-U-Net Gabor Stack (ResNet34) | texture-aware | 0.3900 | 0.5017 | 0.6471 | 24.44 | 0.4 |
| 15 | Metal-UPerNet CLAHE (MiT-B2) | micrograph-contrast | 0.3650 | 0.4664 | 0.6175 | 32.53 | 4.6 |