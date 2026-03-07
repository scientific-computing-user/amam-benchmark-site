# AMAM-128 Reproducibility Audit (45 Models)

- Status: **PASS**
- Git commit: `4c245d60b6af02230bcbd6eb8c459a2839d10542`
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
- `repro/results/classical/benchmark_summary.csv`: `9e6d6614392becaa6440b75fc5ae685bd7a634009d78af0b376b920be79bf2ce`
- `repro/results/classical/benchmark_raw_per_image.csv`: `9c7bc06c69d46e306d769b54fcc4ed65ffed29d48c2a2976f73b5a12de880b8f`
- `repro/results/classical/benchmark_per_subset.csv`: `53fd5c04f2e6b530b48eea3908bd5f5da7e458eb260b239b2f7a0f2ce4ca823c`
- `repro/results/deep_survey/deep_general_summary.csv`: `e6769e7f5b2c30790fd5b1b0bd02cf4f702f3f3db5588854f78ec27bafa685f9`
- `repro/results/deep_survey/deep_metallography_summary.csv`: `7fcca9147ecb16bf315550a9dc80dd8ac2e7d16843187990961c8da17ae36228`
- `repro/results/deep_survey/deep_per_image.csv`: `19723ef9cd0847da83b5da274e48c08303f45d8e4dd5251fc62de63ac0260e82`
- `repro/results/deep_survey/deep_per_subset.csv`: `82cfd67c5fcae0757da119d490feedb092997f8220e7fda4458ef7a1a15e46cb`
- `repro/results/foundation_edge/foundation_edge_summary.csv`: `20225ece312a6d154d5b6e41628050d16815164b6e7cf760708c7718e1a6e5a8`
- `repro/results/foundation_edge/foundation_edge_per_image.csv`: `1d243293a659557fd0520505c097107847035264f8dc590c6822dcb358dc0019`
- `repro/results/foundation_edge/foundation_edge_per_subset.csv`: `33aee7b5ecfb826102531258e5d14132fdcb8ed64ff083668c0c8a2168f96f32`
- `repro/results/classical/benchmark_protocol.json`: `80d0fbbdc106d5d24e6b8afa16df1eefd6c5da1bf61907663d08b62f6bdb3de0`
- `repro/results/deep_survey/deep_protocol.json`: `a3e2db22dad50220086cdf64d28b5d5bde3e7fe133a9ace00a24d617aa1d4f9b`
- `repro/results/foundation_edge/foundation_edge_protocol.json`: `e92463dc9129a36d175ed02e52eb2d5fb1fa044650c7fa703323c023e08b9ea1`
- `repro/results/model_provenance_manifest.csv`: `ed1d0db7501368ec01e791a9fa6502b85fe4fb5d99334c7fa8d28bf1e7ad4ccf`
