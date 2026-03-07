## Metallography-Oriented Deep Models (8)

| Rank | Model | Category | mIoU | Dice | Pixel Acc | Params (M) | Train min |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | Metal-U-Net Gray (ResNet34) | micrograph-contrast | 0.5727 | 0.6888 | 0.7786 | 24.43 | 0.3 |
| 2 | Metal-U-Net CLAHE (ResNet34) | micrograph-contrast | 0.5721 | 0.6930 | 0.8084 | 24.44 | 0.4 |
| 3 | Metal-DeepLabV3+ CLAHE (ResNet34) | micrograph-contrast | 0.5629 | 0.6831 | 0.7977 | 22.44 | 0.5 |
| 4 | Metal-U-Net Gabor Stack (ResNet34) | texture-aware | 0.5609 | 0.6731 | 0.7770 | 24.44 | 0.6 |
| 5 | Metal-U-Net RGB+Sobel (ResNet34) | edge-aware | 0.5308 | 0.6497 | 0.7447 | 24.44 | 0.4 |
| 6 | Metal-U-Net LBP Stack (ResNet34) | texture-aware | 0.4884 | 0.6155 | 0.7110 | 24.44 | 0.4 |
| 7 | Metal-U-Net++ Gray (ResNet34) | micrograph-contrast | 0.4776 | 0.5968 | 0.6874 | 26.07 | 0.8 |
| 8 | Metal-FPN Gabor Stack (ResNet34) | texture-aware | 0.4139 | 0.5113 | 0.6899 | 23.16 | 0.4 |