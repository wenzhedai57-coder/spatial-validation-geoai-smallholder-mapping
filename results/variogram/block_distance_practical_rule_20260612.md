# Practical Indicator Block-Distance Rule

Timestamp UTC: `20260612T172431Z`

## Rule

Selected rule: `q25_of_ok_one_vs_rest_indicator_ranges`.

This uses the 25th percentile of class-specific one-vs-rest indicator variogram ranges. It remains derived from indicator variograms, avoids treating nominal `class_code` as a continuous variable, and reduces sensitivity to very broad regional class ranges that make the configured spatial validation design infeasible.

The rule is based only on reference geometry and indicator diagnostics, not on model accuracy.

## Selected Distance

- Distance: `126783.51747145985` m (`126.78351747145986` km)
- Available spatial blocks: `16`
- Required spatial blocks: `4`
- All folds nonempty after buffering: `True`
- Minimum training count after buffering: `30`
- Minimum test count: `124`

## Candidate Audit

Candidate precheck table: `results/variogram/block_distance_practical_rule_candidates_20260612.csv`

## Submission Consequence

This decision does not alter manuscript tables by itself. The pipeline must be rerun with this decision JSON as the block-distance source, and manuscript tables/figures may only be updated from the resulting CSV/JSON outputs.
