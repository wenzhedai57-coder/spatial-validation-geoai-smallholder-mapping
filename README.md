# Spatial validation choices reshape GeoAI accuracy estimates in Malaysian smallholder mapping

This repository is a public reproducibility package for the evidence, code, figures, and provenance supporting the manuscript "Spatial validation choices reshape GeoAI accuracy estimates in Malaysian smallholder mapping".

## Repository status

This staging repository has been cleaned from the IJRS submission package so that the main repository folders contain the active evidence line rather than draft review queues or legacy package history. The manuscript Data Availability statement should cite the stable commit URL for the release used at submission. A GitHub release or Zenodo DOI can still be added later, but is not required for stable commit-URL wording.

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
- variogram/block-distance evidence: `results/variogram/`
- generated variogram figure: `figures/variogram/variogram_indicator_ranges.png`
- manuscript figures: `figures/manuscript/`
- package checksums and verification files: `manifests_checksums/`

## Evidence boundaries

Final metric labels come only from rows with `verified == True` in `data/reference_samples_verified_622_public.csv`. ESA WorldCover, Google Dynamic World, GlobalOilPalm, and Forest Data Partnership probabilities are weak screening or contextual sources only; they are not ground truth.

The reference labels are image/VHR-reviewed. The completed second-reader VHR adjudication QA workpack is a submission supplementary reproducibility artifact, not part of this public GitHub release. The primary manuscript metrics were computed on the locked 622-row reference table and must be rerun before using the adjudicated subset as a replacement metric base. No design weights or sampling probabilities are available for design-unbiased map accuracy. Reported OA and macro-F1 values should therefore be interpreted as sample-based validation diagnostics.

Targeted-validation candidate queues are not included as main data. They are review-planning/provenance artifacts only and must not be used as ground truth.

## Reproducing the analysis

The main pipeline and supporting scripts are in `scripts/`. The active configuration is in `config/`. The original run logs, configuration hashes, input file names, random seed, and library/version records are preserved in `results/active_q25_rerun/`.

The generated figures in this staging repository are already present. The variogram figure was generated from the packaged variogram CSV/JSON outputs and does not change any result value.

Point-level public imagery-date coverage is documented in `results/point_imagery_dates/`. This is a Sentinel-2 metadata audit for the 2024 analysis year, not an exact VHR basemap acquisition-date record.

## Remaining author-side checks

Unknown ORCID values for Wang Cao and Xuehui Hou are intentionally omitted rather than guessed. Final manuscript render QA and any future GitHub release or Zenodo DOI remain author-side options.
