## Metallography-Oriented Deep Models (3)

| Rank | Model | Category | mIoU | Dice | Pixel Acc | Params (M) | Train min |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | Metal-U-Net Gray (ResNet34) | micrograph-contrast | 0.5727 | 0.6888 | 0.7786 | 24.43 | 0.3 |
| 2 | Metal-U-Net CLAHE (ResNet34) | micrograph-contrast | 0.5721 | 0.6930 | 0.8084 | 24.44 | 0.4 |
| 3 | Metal-U-Net RGB+Sobel (ResNet34) | edge-aware | 0.5308 | 0.6497 | 0.7447 | 24.44 | 0.4 |