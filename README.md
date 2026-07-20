# Validation distance, training support, and label re-review jointly shape GeoAI performance estimates in Malaysian smallholder mapping

This repository is the public code, data, result, figure, and provenance package supporting the IJRS manuscript *Validation distance, training support, and label re-review jointly shape GeoAI performance estimates in Malaysian smallholder mapping*.

## Two label versions, two estimands

The repository intentionally distinguishes two evidence branches:

1. **525-record author-resolved working label set.** W.D. (Dai Wenzhe) repeated the VHR interpretation and performed the internal resolution. This is an author-led internal re-review, not independent validation. It supports label-provenance and sensitivity analysis, but a complete four-fold q25 estimate is not available under current class support. Only 16 rubber records remain.
2. **622-record original-label sensitivity benchmark.** This preserves all four evaluable q25 folds and supports complete-fold sensitivity comparisons. It is not independently verified ground truth, and its results are conditional on the original labels and uneven training support.

The historical filename `data/reference_samples_verified_622_public.csv` and its Boolean `verified` field mean that a row was included in the original benchmark. They do **not** indicate independent verification, adjudicated gold-standard status, or design-based map accuracy. See `data/REFERENCE_LABEL_SEMANTICS.md`.

## Current evidence map

- Canonical supplementary package: `results/supplementary_reproducibility_20260720/`
- Manuscript-to-file index: `results/supplementary_reproducibility_20260720/SUPPLEMENT_INDEX.md`
- Author-led re-review log: `results/supplementary_reproducibility_20260720/author_led_vhr_label_rereview_20260720/`
- 525-record working-label sensitivity: `results/supplementary_reproducibility_20260720/author_resolved_label_sensitivity_20260618/`
- 622-record original-label q25 sensitivity: `results/active_q25_rerun/` and `results/supplementary_reproducibility_20260720/active_q25_rerun/`
- Feature stacks: `data/features_fold3_teacher_vhr_repair_20260613/`
- Configurations: `config/`
- Analysis scripts: `scripts/`
- Current manuscript figures: `figures/manuscript/`
- Public-repository manifest and checksums: `manifests_checksums/`

## Interpretation boundary

The current reference sample is not a probability sample and has no design weights. Reported overall accuracy (OA) and macro-averaged F1 (macro-F1) are sample-based validation diagnostics, not design-unbiased map-accuracy estimates. The q25 split is an approximately 126.8 km spatial-separation stress test for the 622-record original-label benchmark under the observed training support. Fold means and pooled out-of-fold metrics answer different aggregation questions and are both retained.

The VHR review log records Esri World Imagery viewed at zoom level 18. Imagery dates and native resolution were not consistently exposed, so unknown values are retained rather than inferred. Licensed VHR contact sheets are not redistributed. Natural Earth vector data used for map context are public domain; source and licence notes are in figure captions and `docs/THIRD_PARTY_DATA_NOTICE.md`.

## Reproduction

Use `config/config_public_reproduction_20260615.yaml` as the public-path configuration. The original run configuration, seeds, hashes, logs, prediction files, fold-support audits, and result tables are retained. Start with `docs/REPRODUCIBILITY.md` and the supplement index.
