# Fold3 Teacher-VHR AlphaEarth Spatial Paired Bootstrap Audit

Paired sample-level bootstrap on pooled q25 spatial RandomForest predictions after the Cao Wang fold-3 VHR repair. This is an uncertainty diagnostic, not a fold-level bootstrap; fold-level bootstrap is marked insufficient because only four spatial folds exist.

| comparison | n_paired_samples | observed_pooled_oa_diff | ci_lower_2_5 | ci_upper_97_5 | ci_contains_zero | fold_mean_diff | fold_diff_min | fold_diff_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B2_vs_B0_RF_spatial | 622 | 0.156 | 0.121 | 0.193 | False | 0.165 | 0.105 | 0.234 |
| B3_vs_B1_RF_spatial | 622 | 0.076 | 0.045 | 0.106 | False | 0.090 | 0.009 | 0.242 |
| B3_vs_B2_RF_spatial | 622 | -0.010 | -0.026 | 0.006 | True | -0.011 | -0.036 | 0.000 |
