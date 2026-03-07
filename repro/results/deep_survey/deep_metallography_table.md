## Metallography-Oriented Deep Models (14)

| Rank | Model | Category | mIoU | Dice | Pixel Acc | Params (M) | Train min |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | Metal-MAnet RGB+Sobel (EfficientNet-B0) | edge-aware | 0.6290 | 0.7368 | 0.8457 | 8.67 | 0.3 |
| 2 | Metal-U-Net++ CLAHE (EfficientNet-B0) | micrograph-contrast | 0.5869 | 0.6950 | 0.8287 | 6.07 | 0.3 |
| 3 | Metal-U-Net Gray (ResNet34) | micrograph-contrast | 0.5727 | 0.6888 | 0.7786 | 24.43 | 0.3 |
| 4 | Metal-U-Net CLAHE (ResNet34) | micrograph-contrast | 0.5721 | 0.6930 | 0.8084 | 24.44 | 0.4 |
| 5 | Metal-DeepLabV3+ CLAHE (ResNet34) | micrograph-contrast | 0.5629 | 0.6831 | 0.7977 | 22.44 | 0.5 |
| 6 | Metal-U-Net Gabor Stack (ResNet34) | texture-aware | 0.5609 | 0.6731 | 0.7770 | 24.44 | 0.6 |
| 7 | Metal-U-Net RGB+Sobel (ResNet34) | edge-aware | 0.5308 | 0.6497 | 0.7447 | 24.44 | 0.4 |
| 8 | Metal-SegFormer CLAHE (MiT-B0) | micrograph-contrast | 0.5307 | 0.6423 | 0.7332 | 3.72 | 1.3 |
| 9 | Metal-SegFormer Gray (MiT-B2) | micrograph-contrast | 0.5244 | 0.6392 | 0.7218 | 24.72 | 4.4 |
| 10 | Metal-U-Net LBP Stack (ResNet34) | texture-aware | 0.4884 | 0.6155 | 0.7110 | 24.44 | 0.4 |
| 11 | Metal-U-Net++ Gray (ResNet34) | micrograph-contrast | 0.4776 | 0.5968 | 0.6874 | 26.07 | 0.8 |
| 12 | Metal-LinkNet RGB+Sobel (ResNet34) | edge-aware | 0.4642 | 0.5937 | 0.6781 | 21.78 | 0.3 |
| 13 | Metal-UPerNet CLAHE (MiT-B2) | micrograph-contrast | 0.4413 | 0.5378 | 0.7015 | 32.53 | 5.0 |
| 14 | Metal-FPN Gabor Stack (ResNet34) | texture-aware | 0.4139 | 0.5113 | 0.6899 | 23.16 | 0.4 |