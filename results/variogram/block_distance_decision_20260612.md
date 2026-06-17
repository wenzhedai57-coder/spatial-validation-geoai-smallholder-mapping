# Superseded block-distance diagnostic

Timestamp UTC: `20260612T172427Z`

## Current status

This memo is retained only as historical provenance. It is superseded by the final practical q25 decision recorded in:

- `results/variogram/block_distance_practical_rule_20260613.md`
- `results/variogram/block_distance_practical_rule_summary_20260613.json`
- `results/variogram/block_distance_practical_rule_candidates_20260613.csv`

The final manuscript and active q25 rerun use `q25_of_ok_one_vs_rest_indicator_ranges`, with selected block distance `126783.51747145985` m (`126.78351747145986` km). The q25 candidate had 16 available spatial blocks, satisfied the configured 4-fold requirement, retained nonempty folds after buffering, and had minimum buffered training count 30. The maximum-rule distance of `729005.2254608942` m (`729.0052254608942` km) was not selected because it yielded only 2 available spatial blocks for `k_folds=4`.

## Purpose

This superseded memo records an early one-vs-rest indicator variogram diagnostic. It is kept to document why a nominal `class_code` variogram should not be treated as an ecological range or a design-based map-accuracy scale. The original text described a maximum-rule rerun as a possible conservative replacement, but that boundary case was later rejected by the practical-rule candidate audit because it is infeasible for the configured four-fold spatial validation in the current sample layout.

## Input

- Reference file: `data/reference_samples_verified_622_public.csv`
- Reference SHA-256: `abac92866b1925ec132cd26273a3a34fcbf4601e45fa83a80cea0dd2d3692779`
- Config file: `config_fold3_teacher_vhr_repair_20260613.yaml`
- Config SHA-256: `13c231aedc6c4af000cc8e3d111c543a4f647b4d8bedc4a01eb286ff8f65d8e5`
- Verified rows used: `622`
- Random seed: `42`

## Class-specific indicator ranges

| class_code | class_name | status | n_positive | n_negative | chosen_range_km | reason |
|---:|---|---|---:|---:|---:|---|
| 1 | oil_palm | OK | 109 | 513 | 95.088 |  |
| 2 | rubber | OK | 105 | 517 | 221.871 |  |
| 3 | paddy | OK | 105 | 517 | 665.613 |  |
| 4 | other_agri | OK | 89 | 533 | 729.005 |  |
| 5 | forest | OK | 129 | 493 | 95.088 |  |
| 6 | builtup_other | OK | 85 | 537 | 729.005 |  |

## Decision rule

- Superseded conservative boundary case: `729005.2254608942` m (`729.0052254608942` km).
- Superseded rule: maximum OK one-vs-rest indicator range across configured classes.
- Final selected rule: `q25_of_ok_one_vs_rest_indicator_ranges`, recorded in the practical-rule files listed above.
- Final selected distance: `126783.51747145985` m (`126.78351747145986` km).
- Final rationale: q25 remains indicator-derived while reducing sensitivity to very broad regional class ranges that make the configured spatial-validation design infeasible. The selection used reference geometry and indicator diagnostics, not model accuracy.

## Submission consequence

This superseded memo must not be used as the final block-distance decision for the IJRS submission. The submission-facing tables and figures are tied to the active q25 rerun and its provenance-stamped CSV/JSON outputs, including the leakage audit and conformal random/spatial reports.

## Output files

- Historical diagnostic family: `results_final_revision_20260612/variogram_indicator_*`
- Final practical-rule family: `results/variogram/block_distance_practical_rule_*`
- Active q25 rerun family: `results/active_q25_rerun/`
