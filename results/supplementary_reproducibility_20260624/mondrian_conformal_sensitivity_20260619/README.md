# Mondrian/Class-Conditional Conformal Sensitivity

This folder contains a reproducible sensitivity analysis that recomputes conformal prediction with class-conditional, or Mondrian, thresholds.

Purpose:

- Test whether per-class calibration changes the coverage versus set-size trade-off reported in the main manuscript.
- Preserve the original random and spatial conformal split logic, model hyperparameters, feature preprocessing, `alpha=0.10`, and `min_class_count=30`.
- Keep the analysis as a sensitivity result, not a replacement for the primary global split-conformal table.

Key files:

- `compute_mondrian_conformal_sensitivity_20260619.py`: executable sensitivity script.
- `config_public_reproduction_20260615.yaml`: public reproduction config snapshot.
- `reference_samples_verified_622_public.csv`: primary 622-row verified reference table.
- `variogram_choice.json`: primary q25 spatial block-distance choice.
- `table7_conformal.csv`: primary global split-conformal table used for comparison.
- `mondrian_conformal_summary_20260619.csv`: stack/model/split-level Mondrian results.
- `mondrian_conformal_per_class_20260619.csv`: per-class coverage, calibration counts, qhat, and average set size.
- `mondrian_conformal_thresholds_20260619.csv`: class-specific thresholds.
- `mondrian_conformal_point_sets_20260619.csv`: point-level prediction sets.
- `mondrian_vs_global_conformal_comparison_20260619.csv`: global versus Mondrian coverage and set-size deltas.
- `mondrian_conformal_class_policy_20260619.csv`: min-class-count policy audit.
- `mondrian_conformal_provenance_20260619.json`: hashes, inputs, seed, package versions, and output paths.
- `MONDRIAN_CONFORMAL_SENSITIVITY_20260619.md`: short human-readable summary.

Interpretation boundary:

Mondrian conformal reduces spatial prediction-set sizes for AlphaEarth RandomForest rows while preserving high marginal spatial coverage in this sample. It does not remove exchangeability concerns under spatial shift, and it does not turn the conformal outputs into an operational trust layer.
