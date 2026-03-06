# AMAM-128 Reproducibility Audit (45 Models)

- Status: **PASS**
- Git commit: `7c3036b4de5e27c7a36cccb377d6fc50e82df811`
- Model counts:
  - Classical: 10
  - Deep general: 14
  - Deep metallography: 15
  - Foundation/edge: 6
  - Total: 45

## Consistency Checks
- Classical summary/per-image/per-subset IDs match: `True`
- Deep summary/per-image/per-subset IDs match: `True`
- Foundation summary/per-image/per-subset IDs match: `True`
- Provenance manifest matches results IDs: `True`

## Key Artifacts (SHA256)
- `repro/results/classical/benchmark_summary.csv`: `59ea2daa61828ea99e7f362a7715f9e4997edcde15b010b24a7a969dfdba51bb`
- `repro/results/classical/benchmark_raw_per_image.csv`: `fa65da35b21da685601ba91aaa9744bc862117efb32c19cefa29c3ddcfffbab0`
- `repro/results/classical/benchmark_per_subset.csv`: `2f908f440c9822cb5bc989c35bed64dca4bbac9ae452bc94b2c6a74aa77b777a`
- `repro/results/deep_survey/deep_general_summary.csv`: `9fd9d6e33c6681985f0b39c1e5f12d50234774bc42afe76106c00a5e6dd97eef`
- `repro/results/deep_survey/deep_metallography_summary.csv`: `e0d9d765d209b5ede75f2bd703132356fc019e6e77f1371988dd0c4698bccab6`
- `repro/results/deep_survey/deep_per_image.csv`: `71364e52c22d8530cfb667946e33f18665977ae75e41a91d49fe80058341b639`
- `repro/results/deep_survey/deep_per_subset.csv`: `bbad9acc6ee18a05aec0791fa0f8984348d6aa4a51c5d54c6f23238831b40e15`
- `repro/results/foundation_edge/foundation_edge_summary.csv`: `030492186028fe0f9db47c70a7f32bca506881923288dbbab3b4b7c50714079a`
- `repro/results/foundation_edge/foundation_edge_per_image.csv`: `95536886244b614115f471e9cbe6e9e9a41d046b48c4709a0f01f5b91638bbe3`
- `repro/results/foundation_edge/foundation_edge_per_subset.csv`: `56646c792047b8b494ebf3f498d211f30a0041288bb3011504ebc3e188d38197`
- `repro/results/classical/benchmark_protocol.json`: `6db5cfbfaeab7bc8ee63cdafc426cce49752ed725b465a3b64aa4d74c149ad16`
- `repro/results/deep_survey/deep_protocol.json`: `a9fdd197533d74490b6472924d2c9c6b5fa3f7cceb89cce59777b7e33e4ec1df`
- `repro/results/foundation_edge/foundation_edge_protocol.json`: `2853d10f60e30349dab230aaf9e71c6a486dfde83e5395764081f03598481665`
- `repro/results/model_provenance_manifest.csv`: `436fc44adea38600601d74bb4ba890b977808d469fac33c440a148bed635670e`
