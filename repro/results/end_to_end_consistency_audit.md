# AMAM End-to-End Consistency Audit

Scope: paper claims/tables, released CSV metrics, website report assets, dataset metadata counts, and reproducibility audit.

## Canonical Metrics (45-model subset-macro benchmark)
- Model count: **45**
- Best mIoU: **0.6519** (rf_pixel)
- Median mIoU: **0.5362**
- Gap to perfect: **0.3481**
- Best Dice: **0.7580**
- Best Pixel Acc: **0.8684**

## Release Accounting (from local metadata)
- Paired tuples: **128**
- Local originals: **136**
- totalImages field: **136**
- Pair coverage: **94.1%**

## Cross-Artifact Equality Checks
- paper_site_classical_equal: **True**
- paper_repro_classical_equal: **True**
- paper_site_deep_equal: **True**
- paper_site_foundation_equal: **True**
- metadata_totalImages_matches_locals: **True**

## Reproducibility Audit Status
- status: **PASS**
- total_unique_models: **45**
- classical/deep/foundation consistency flags: **{'classical_consistent': True, 'deep_consistent': True, 'foundation_consistent': True, 'manifest_matches_results': True}**

Result: **PASS** (no numeric mismatches detected in the audited scope).
