# Spatial validation choices reshape GeoAI accuracy estimates in Malaysian smallholder mapping

This repository is a GitHub/Zenodo-ready staging package for the evidence, code, figures, and provenance supporting the manuscript "Spatial validation choices reshape GeoAI accuracy estimates in Malaysian smallholder mapping".

## Repository status

This staging repository has been cleaned from the IJRS submission package so that the main repository folders contain the active evidence line rather than draft review queues or legacy package history. It is not yet the final public archival record until the authors choose a license and create a GitHub release or Zenodo record.

## Main evidence line

The active evidence line is the fold-3 teacher-VHR q25 rerun:

- hash-preserved original run configuration: `config/config_fold3_teacher_vhr_repair_20260613.yaml`
- public path reproduction configuration: `config/config_public_reproduction_20260615.yaml`
- verified reference table: `data/reference_samples_verified_622_public.csv`
- reference provenance: `results/active_q25_rerun/fold3_teacher_vhr_merge_audit_20260613.*`; older reference-cleaning history is in `docs/provenance/legacy_reference_cleaning/`
- feature stacks: `data/features_fold3_teacher_vhr_repair_20260613/`
- active result tables and audits: `results/active_q25_rerun/`
- spatial-sensitivity support artifacts: `results/spatial_sensitivity/`
- review-planning support artifacts: `results/review_planning/`
- point-level public Sentinel-2 imagery-date audit: `results/point_imagery_dates/`
- second-reader VHR agreement template and merge script: `docs/second_reader_vhr_agreement/`, `scripts/merge_second_reader_vhr_agreement.py`
- variogram/block-distance evidence: `results/variogram/`
- generated variogram figure: `figures/variogram/variogram_indicator_ranges.png`
- manuscript figures: `figures/manuscript/`
- package checksums and verification files: `manifests_checksums/`

## Evidence boundaries

Final metric labels come only from rows with `verified == True` in `data/reference_samples_verified_622_public.csv`. ESA WorldCover, Google Dynamic World, GlobalOilPalm, and Forest Data Partnership probabilities are weak screening or contextual sources only; they are not ground truth.

The reference labels are image/VHR-verified. They are not field-validated, no second-reader agreement is included in this staging package, and no design weights or sampling probabilities are available for design-unbiased map accuracy. Reported OA and macro-F1 values should therefore be interpreted as sample-based validation diagnostics.

Targeted-validation candidate queues are not included as main data. They are review-planning/provenance artifacts only and must not be used as ground truth.

## Reproducing the analysis

The main pipeline and supporting scripts are in `scripts/`. The active configuration is in `config/`. The original run logs, configuration hashes, input file names, random seed, and library/version records are preserved in `results/active_q25_rerun/`.

The generated figures in this staging repository are already present. The variogram figure was generated from the packaged variogram CSV/JSON outputs and does not change any result value.

Point-level public imagery-date coverage is documented in `results/point_imagery_dates/`. This is a Sentinel-2 metadata audit for the 2024 analysis year, not field validation and not an exact VHR basemap acquisition-date record.

A blind second-reader VHR agreement workflow is provided in `docs/SECOND_READER_VHR_AGREEMENT_INSTRUCTIONS.md`. It requires a human second reader to fill the template before any agreement metric can be computed.

## Before public release

Before making this repository public or linking it in a manuscript, complete the author-controlled items listed in `docs/UPLOAD_CHECKLIST.md`, especially the public release/DOI, author contribution confirmation, ORCID confirmation, manuscript render QA, and license choice.

