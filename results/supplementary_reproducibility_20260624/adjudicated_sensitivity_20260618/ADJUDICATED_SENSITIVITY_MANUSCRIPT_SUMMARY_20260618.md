# Adjudicated-subset sensitivity summary

Timestamp UTC: `20260618T154527Z`
Reference rows: `525`
Indicator q25 status: `SKIPPED`
Indicator q25 distance: `158475.67167120945` m
Spatial folds: `3` OK, `1` SKIPPED

## Class counts

| timestamp        |   class_code | class_name    |   verified_count | status                             | reason                                                                                                       |
|:-----------------|-------------:|:--------------|-----------------:|:-----------------------------------|:-------------------------------------------------------------------------------------------------------------|
| 20260618T153422Z |            1 | oil_palm      |              105 | OK                                 | nan                                                                                                          |
| 20260618T153422Z |            2 | rubber        |               16 | LOW_COUNT_BELOW_MIN_CLASS_COUNT_30 | Class has fewer than config.min_class_count=30 and must be dropped or marked unstable by downstream metrics. |
| 20260618T153422Z |            3 | paddy         |               71 | OK                                 | nan                                                                                                          |
| 20260618T153422Z |            4 | other_agri    |               62 | OK                                 | nan                                                                                                          |
| 20260618T153422Z |            5 | forest        |              150 | OK                                 | nan                                                                                                          |
| 20260618T153422Z |            6 | builtup_other |              121 | OK                                 | nan                                                                                                          |

## B2/B3 RandomForest table4 sensitivity

| timestamp        | scope                                       | stack   | model        | metric   | status   |   reason |   random_value |   spatial_value |   optimism_gap | spatial_fold_condition       |   ok_spatial_folds |   skipped_spatial_folds |
|:-----------------|:--------------------------------------------|:--------|:-------------|:---------|:---------|---------:|---------------:|----------------:|---------------:|:-----------------------------|-------------------:|------------------------:|
| 20260618T154527Z | adjudicated_subset_table4_random_vs_spatial | B2      | RandomForest | oa       | OK       |      nan |       0.848748 |        0.52029  |       0.328458 | INCOMPLETE_Q25_SPATIAL_FOLDS |                  3 |                       1 |
| 20260618T154527Z | adjudicated_subset_table4_random_vs_spatial | B2      | RandomForest | macro_f1 | OK       |      nan |       0.820564 |        0.457659 |       0.362905 | INCOMPLETE_Q25_SPATIAL_FOLDS |                  3 |                       1 |
| 20260618T154527Z | adjudicated_subset_table4_random_vs_spatial | B3      | RandomForest | oa       | OK       |      nan |       0.850655 |        0.482697 |       0.367958 | INCOMPLETE_Q25_SPATIAL_FOLDS |                  3 |                       1 |
| 20260618T154527Z | adjudicated_subset_table4_random_vs_spatial | B3      | RandomForest | macro_f1 | OK       |      nan |       0.82082  |        0.457745 |       0.363075 | INCOMPLETE_Q25_SPATIAL_FOLDS |                  3 |                       1 |

## Rubber-belt transfer sensitivity

| timestamp        | scope                                   | stack   | model        | status   |   reason |   n_train |   n_test |       oa |   macro_f1 |   rubber_support |   rubber_precision |   rubber_recall |   rubber_f1 | heldout_majority_class   |   heldout_majority_count |   heldout_region_n |   heldout_majority_baseline_oa | interpretation_status                            |
|:-----------------|:----------------------------------------|:--------|:-------------|:---------|---------:|----------:|---------:|---------:|-----------:|-----------------:|-------------------:|----------------:|------------:|:-------------------------|-------------------------:|-------------------:|-------------------------------:|:-------------------------------------------------|
| 20260618T154527Z | adjudicated_subset_rubber_belt_transfer | B2      | RandomForest | OK       |      nan |       473 |       52 | 0.653846 |   0.409524 |                3 |                  0 |               0 |           0 | forest                   |                       27 |                 52 |                       0.519231 | UNSTABLE_RUBBER_SUPPORT_BELOW_MIN_CLASS_COUNT_30 |
| 20260618T154527Z | adjudicated_subset_rubber_belt_transfer | B3      | RandomForest | OK       |      nan |       473 |       52 | 0.711538 |   0.483733 |                3 |                  0 |               0 |           0 | forest                   |                       27 |                 52 |                       0.519231 | UNSTABLE_RUBBER_SUPPORT_BELOW_MIN_CLASS_COUNT_30 |

Interpretation: rubber-belt overall accuracy under the adjudicated subset is not a rubber-transfer improvement claim because the held-out rubber class has support below `min_class_count=30`.

CSV: `C:\Users\m1761\Documents\New project\IJRS_ADJUDICATED_SENSITIVITY_20260618\results\adjudicated_sensitivity_20260618\adjudicated_sensitivity_manuscript_summary_20260618.csv`
JSON: `C:\Users\m1761\Documents\New project\IJRS_ADJUDICATED_SENSITIVITY_20260618\results\adjudicated_sensitivity_20260618\adjudicated_sensitivity_manuscript_summary_20260618.json`
