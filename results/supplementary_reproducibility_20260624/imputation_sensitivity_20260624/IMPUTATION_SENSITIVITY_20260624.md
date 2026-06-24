# Complete-case missing-feature sensitivity (20260624)

This diagnostic compares the primary `sentinel_to_nan_then_median_impute` policy with a complete-case rerun for the primary RandomForest model.

Rows with `NaN` or the configured missing-feature sentinel were removed within each feature stack before training and testing. The original table-3 fold means are retained as the median-imputed reference.

## Summary

| Stack | Split | Sentinel rows | Test rows dropped | Original OA | Complete-case OA | Delta OA | Original macro-F1 | Complete-case macro-F1 | Delta macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | random | 14 | 14 | 0.544975 | 0.544388 | -0.000588 | 0.540031 | 0.538303 | -0.001728 |
| B0 | spatial | 14 | 14 | 0.328879 | 0.333596 | 0.004716 | 0.283852 | 0.288503 | 0.004651 |
| B1 | random | 14 | 14 | 0.614165 | 0.610189 | -0.003976 | 0.604104 | 0.600181 | -0.003923 |
| B1 | spatial | 14 | 14 | 0.393565 | 0.403061 | 0.009495 | 0.329275 | 0.339448 | 0.010174 |
| B2 | random | 0 | 0 | 0.734739 | 0.734739 | 0.000000 | 0.728581 | 0.728581 | 0.000000 |
| B2 | spatial | 0 | 0 | 0.494242 | 0.494242 | 0.000000 | 0.426641 | 0.426641 | 0.000000 |
| B3 | random | 14 | 14 | 0.721888 | 0.727000 | 0.005112 | 0.715094 | 0.719183 | 0.004088 |
| B3 | spatial | 14 | 14 | 0.483233 | 0.494367 | 0.011133 | 0.411103 | 0.422282 | 0.011180 |

Files written:

- `imputation_sensitivity_fold_metrics_20260624.csv`
- `imputation_sensitivity_summary_20260624.csv`
- `imputation_sensitivity_spatial_leakage_audit_20260624.csv`
- `imputation_sensitivity_class_counts_20260624.csv`
- `imputation_sensitivity_provenance_20260624.json`

B2 contains no sentinel/NaN feature rows, so its complete-case rerun is a no-missing reference rather than a stress test of imputation.
