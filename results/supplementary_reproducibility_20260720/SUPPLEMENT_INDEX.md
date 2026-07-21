# Supplement index and manuscript-to-file map

All paths are relative to the root of this supplementary package.

| Manuscript element or claim | Primary supporting file(s) |
|---|---|
| Author-led re-review counts (622, 530, 370, 160, 92, 147, 8, 5, 525) | `author_led_vhr_label_rereview_20260720/author_rereview_summary_20260720.json`; submission-facing derivative `author_led_vhr_label_rereview_20260720/reference_samples_author_rereview_resolved_AUDIT_20260720.csv`; derivative mapping and hashes in `author_led_vhr_label_rereview_20260720/SUBMISSION_FACING_DERIVATIVE_PROVENANCE_20260721.json` |
| 525-record author-resolved working label set and class counts | submission-facing derivative `author_led_vhr_label_rereview_20260720/reference_samples_author_resolved_INCLUDED_20260720.csv`; `author_resolved_label_sensitivity_20260618/author_resolved_reference_class_counts_20260618.csv` |
| Why complete four-fold q25 performance is not estimable for the 525-record set | `author_resolved_label_sensitivity_20260618/spatial_fold_leakage_audit.csv`; `author_resolved_label_sensitivity_20260618/author_resolved_sensitivity_manuscript_summary_20260618.csv` |
| 622-record original-label sensitivity benchmark | `active_q25_rerun/reference_sample_audit.csv`; `active_q25_rerun/spatial_fold_leakage_audit.csv` |
| Table 4A fold-level performance | `active_q25_rerun/table3_accuracy_by_stack_split.csv` |
| Table 4B pooled out-of-fold performance | `table4_accuracy_foldmean_and_pooled_oof_20260720.csv`; predictions in `active_q25_rerun/predictions_by_fold.csv` |
| q25 candidate distance and support audit | `active_q25_rerun/variogram_choice.json`; `active_q25_rerun/spatial_fold_leakage_audit.csv`; `support_balanced_q25_sensitivity_20260624/` |
| Figure 1 deterministic schematic | `figure_provenance_20260720/redraw_evidence_figures.py`; `figure_provenance_20260720/FIGURE_PROVENANCE_20260720.json` |
| Figure 2 records and public-domain basemap disclosure | `figure_provenance_20260720/FIGURE_PROVENANCE_20260720.json`; original-label table in the public repository at `data/reference_samples_verified_622_public.csv` (historical filename) |
| Figure 13 planar diagnostic values | `figure_provenance_20260720/figure13_planar_validation_risk_grid_20260624.csv`; `figure_provenance_20260720/FIGURE_PROVENANCE_20260720.json` |
| Full landscape-regression coefficients | `active_q25_rerun/table9_landscape_regression.csv` |
| Trust-routing diagnostics | `trust_routing_diagnostics_20260624/`; `active_q25_rerun/table7_conformal.csv` |
| Conformal sensitivity | `mondrian_conformal_sensitivity_20260619/`; `active_q25_rerun/spatial_conformal_split_audit.csv` |

Historical filenames containing `verified` in the public repository are immutable schema identifiers for inclusion in the original benchmark; they do not indicate independent verification or gold-standard status. Historical review artifacts with superseded terminology are preserved separately and are not included in this submission package.
