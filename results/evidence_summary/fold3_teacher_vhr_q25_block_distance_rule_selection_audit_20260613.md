# Fold3 Teacher-VHR q25 Block-Distance Rule Selection Audit

Source: persisted candidate precheck table. Model accuracy was not used for rule selection.

| candidate | selection_status | distance_km | available_spatial_blocks | all_folds_nonempty | min_train_count_after_buffer | fold_train_classes | manuscript_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| min_ok | NOT_SELECTED | 95.1 | 30 | True | 22 | 6/4/6/6 | diagnostic_lower_bound_not_primary |
| q25_ok_selected | SELECTED | 126.8 | 16 | True | 30 | 6/6/6/6 | PRIMARY_Q25_PRACTICAL_VALIDATION_DESIGN |
| median_ok | NOT_SELECTED | 443.7 | 5 | False | 0 | 4/0/0/6 | not_primary_nonempty_folds_fail |
| q75_ok | NOT_SELECTED | 713.2 | 3 | False | MISSING | MISSING | not_primary_insufficient_spatial_blocks |
| max_ok | NOT_SELECTED | 729.0 | 2 | False | MISSING | MISSING | conservative_stress_test_only_insufficient_spatial_blocks |
