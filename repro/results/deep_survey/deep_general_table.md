## General Deep Segmentation Models (14)

| Rank | Model | Category | mIoU | Dice | Pixel Acc | Params (M) | Train min |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | U-Net (EfficientNet-B0) | encoder-decoder | 0.6126 | 0.7220 | 0.8165 | 5.84 | 0.3 |
| 2 | DeepLabV3+ (EfficientNet-B0) | context-atrous | 0.6000 | 0.7111 | 0.8349 | 4.50 | 0.2 |
| 3 | U-Net (ResNet34) | encoder-decoder | 0.5853 | 0.6911 | 0.8184 | 24.44 | 0.3 |
| 4 | MAnet (ResNet34) | attention | 0.5794 | 0.6924 | 0.7606 | 31.79 | 0.3 |
| 5 | SegFormer (MiT-B2) | transformer | 0.5781 | 0.6850 | 0.8009 | 24.73 | 3.9 |
| 6 | DeepLabV3+ (ResNet34) | context-atrous | 0.5612 | 0.6818 | 0.7734 | 22.44 | 0.3 |
| 7 | U-Net++ (ResNet34) | encoder-decoder | 0.5516 | 0.6666 | 0.7663 | 26.08 | 0.4 |
| 8 | SegFormer (MiT-B0) | transformer | 0.5451 | 0.6560 | 0.7740 | 3.72 | 1.0 |
| 9 | PSPNet (ResNet34) | pyramid | 0.4818 | 0.5912 | 0.7352 | 21.49 | 0.1 |
| 10 | FPN (ResNet34) | pyramid | 0.4598 | 0.5750 | 0.6940 | 23.16 | 0.3 |
| 11 | UPerNet (MiT-B0) | transformer | 0.4501 | 0.5539 | 0.6486 | 10.74 | 1.5 |
| 12 | LinkNet (ResNet34) | lightweight | 0.4343 | 0.5550 | 0.6561 | 21.77 | 0.2 |
| 13 | UPerNet (MiT-B2) | transformer | 0.3878 | 0.4869 | 0.5977 | 32.53 | 4.5 |
| 14 | DeepLabV3 (ResNet34) | context-atrous | 0.3430 | 0.4134 | 0.6698 | 26.01 | 0.6 |