# Q25 NNDM-style Distance Audit

This folder contains a reproducible nearest-neighbour distance audit for the primary 622-row reference set. It was added to address the reviewer-facing concern that the q25 spatial block rule needs a clearer defence against ordinary random validation.

The audit is not a full NNDM or kNNDM design because no prediction-domain target grid or external prediction-point distribution is supplied. It is a distance-distribution check that compares the stratified random folds with the q25 spatial folds generated from the same random seed, reference samples, projection approximation, variogram-derived block distance, and buffering logic used by the main pipeline.

Key files:

- `compute_q25_nndm_style_distance_audit_20260619.py`: executable audit script.
- `config_fold3_teacher_vhr_repair_20260613.yaml`: config snapshot used by the primary q25 run.
- `reference_samples_verified_622_public.csv`: primary 622-row verified reference table used by the audit.
- `variogram_choice.json`: primary q25 block-distance choice.
- `q25_nndm_style_summary_20260619.csv`: manuscript-level summary table.
- `q25_nndm_style_fold_distance_audit_20260619.csv`: fold-level nearest-train distance audit.
- `q25_nndm_style_point_distance_audit_20260619.csv`: point-level nearest-train distance audit.
- `q25_nndm_style_provenance_20260619.json`: provenance, hashes, seed, and interpretation boundary.
- `Q25_NNDM_STYLE_DISTANCE_AUDIT_20260619.md`: short human-readable summary.

Interpretation boundary:

The q25 split is defended as a class-structure-informed zero-leakage spatial validation stress test. It is not claimed to be a design-unbiased map-accuracy estimator or a substitute for a full NNDM/kNNDM prediction-domain design.
