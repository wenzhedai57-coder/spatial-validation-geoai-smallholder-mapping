# Adjudicated-subset sensitivity rerun

This folder contains a label-provenance sensitivity analysis, not a replacement primary metric base.

## Purpose

The main manuscript reports primary metrics from the locked 622-row verified reference table. The second-reader VHR adjudication audit produced 525 included rows after adjudication. This folder converts those 525 rows to the same pipeline reference schema and reruns the fixed analysis to test how strongly the interpretation depends on label adjudication.

## Main interpretation

- The adjudicated subset contains only 16 rubber samples, below `min_class_count=30`.
- Rubber-class metrics from this subset must be treated as unstable.
- The adjudicated one-vs-rest indicator q25 distance is 158475.67167120945 m.
- The adjudicated q25 spatial rerun has 3 OK folds and 1 SKIPPED fold because one fold has 0 retained training samples after buffering.
- The adjudicated rerun is therefore sensitivity evidence only. It should not overwrite the primary 622-row table 4 or transfer results.

## Key files

- `reference_samples.csv`: converted 525-row adjudicated sensitivity reference.
- `config_adjudicated_sensitivity_20260618.yaml`: rerun configuration.
- `adjudicated_reference_class_counts_20260618.csv`: class counts and low-count status.
- `block_distance_practical_rule_summary_20260618.json`: indicator-variogram q25 distance and spatial precheck status.
- `spatial_fold_leakage_audit.csv`: q25 fold support and zero-leakage audit.
- `table3_accuracy_by_stack_split.csv` and `table4_optimism_gap.csv`: adjudicated-subset random and spatial sensitivity outputs.
- `table10_leave_region_out_transfer.csv` and `table10_leave_region_out_transfer_per_class.csv`: adjudicated-subset leave-region-out transfer outputs.
- `adjudicated_sensitivity_manuscript_summary_20260618.csv`: manuscript-facing summary generated from the result tables.
- `*.py`: scripts used to build, rerun, and summarize the sensitivity analysis.

All new numbers in the revised manuscript that refer to this sensitivity analysis are copied from the CSV/JSON artifacts in this folder.
