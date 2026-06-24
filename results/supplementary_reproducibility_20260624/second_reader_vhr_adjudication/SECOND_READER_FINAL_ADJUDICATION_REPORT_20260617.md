# Final second-reader adjudication report

Generated UTC: 2026-06-16T16:32:02Z
Status: OK

## Result

- Full audit rows: 622
- Strict two-reader/adjudicated included rows: 525
- Excluded or unresolved rows: 97

## Pre-adjudication second-reader agreement

- Scorable rows: 530
- Agreement rows: 370
- Disagreement rows: 160
- Non-scorable rows: 92
- Observed agreement: 69.8%
- Cohen kappa: 0.632407

## Adjudication decisions on 160 disagreements

| Decision | n |
|---|---:|
| accept_second_reader | 147 |
| keep_original | 8 |
| needs_third_reader | 5 |

## Final resolution across 622 rows

| Resolution status | n |
|---|---:|
| AGREED_ORIGINAL_AND_SECOND_READER | 370 |
| ADJUDICATED_ACCEPT_SECOND_READER | 147 |
| NOT_SCORABLE_SECOND_READER_UNCERTAIN | 73 |
| NOT_SCORABLE_SECOND_READER_UNINTERPRETABLE | 19 |
| ADJUDICATED_KEEP_ORIGINAL | 8 |
| UNRESOLVED_NEEDS_THIRD_READER | 5 |

## Included class counts

| Final class | n |
|---|---:|
| forest | 150 |
| builtup_other | 121 |
| oil_palm | 105 |
| paddy | 71 |
| other_agri | 62 |
| rubber | 16 |

## Output files

- Full audit table: `reference_samples_second_reader_adjudicated_AUDIT_20260617.csv`
- Included strict reference table: `reference_samples_second_reader_adjudicated_INCLUDED_20260617.csv`
- Summary JSON: `second_reader_final_adjudication_summary_20260617.json`
- Resolution counts: `second_reader_final_resolution_counts_20260617.csv`
- Included class counts: `second_reader_final_included_class_counts_20260617.csv`
- Decision counts: `second_reader_adjudication_decision_counts_20260617.csv`

## Claim boundary

- This is VHR second-reader/adjudication evidence; no in-situ reference record is claimed.
- Second-reader uncertain/uninterpretable rows are not included in the strict two-reader/adjudicated reference table.
- `needs_third_reader` rows remain unresolved and are not final ground truth.
- Weak products and model predictions were not used as ground truth.
