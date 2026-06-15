# Final-revision block-distance diagnostic

Timestamp UTC: `20260612T172427Z`

## Purpose

This memo records a one-vs-rest indicator variogram diagnostic computed from the cleaned 619-row verified reference table. It is added because the previous 95.1 km distance was derived from a nominal `class_code` variogram and should not be treated as an ecological range or a design-based map-accuracy scale.

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

- Suggested conservative replacement block distance, if the analysis is rerun from this diagnostic: `729005.225461` m (`729.005` km).
- Rule: maximum OK one-vs-rest indicator range across configured classes.
- Rationale: this is conservative across class-specific spatial structures and avoids treating the nominal multi-class code as a continuous variable.

## Submission consequence

This diagnostic does **not** update Table 3-12 or any figure by itself. If this replacement block distance is adopted, the spatial CV, leakage audit, conformal random/spatial reporting, Moran's I, transfer outputs, figures, manuscript tables, manifest, and checksums must be regenerated. Until that rerun exists, the current manuscript results remain tied to the older 95.1 km stress-test distance and should be treated as `MAJOR_REVISION_FIRST`, not final submission-ready evidence.

## Output files

- `results_final_revision_20260612/variogram_indicator_bins.csv`
- `results_final_revision_20260612/variogram_indicator_ranges.csv`
- `results_final_revision_20260612/variogram_indicator_summary.json`
- `figures_final_revision_20260612/variogram_indicator_ranges.png`
