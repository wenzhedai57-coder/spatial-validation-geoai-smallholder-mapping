# Reproducibility Notes

## Active run

The active run is the fold-3 teacher-VHR q25 rerun. The main configuration is:

- `config/config_fold3_teacher_vhr_repair_20260613.yaml` (hash-preserved original run configuration)
- `config/config_public_reproduction_20260615.yaml` (same run settings with repository-relative public paths)

The active run records configuration hash, input files, random seed, status, and run logs in:

- `results/active_q25_rerun/`

## Core files

- Verified reference sample table: `data/reference_samples_verified_622_public.csv`
- Reference provenance: `results/active_q25_rerun/fold3_teacher_vhr_merge_audit_20260613.*`; older reference-cleaning history is in `docs/provenance/legacy_reference_cleaning/`
- Feature stacks: `data/features_fold3_teacher_vhr_repair_20260613/B0.csv` through `B3.csv`
- Accuracy and diagnostic outputs: `results/active_q25_rerun/`
- Spatial sensitivity support outputs: `results/spatial_sensitivity/`
- Review-planning support outputs: `results/review_planning/`
- Variogram and block-distance outputs: `results/variogram/`
- Second-round reviewer-risk evidence: `results/results/second_round_evidence/`
- Reviewer-risk evidence: `results/results/reviewer_risk_evidence/`

## No-fabrication rule

All manuscript result numbers should be read from the CSV/JSON/TXT artifacts in this repository. Missing, skipped, or unverified conditions are preserved as explicit audit states rather than being replaced by guessed values.

