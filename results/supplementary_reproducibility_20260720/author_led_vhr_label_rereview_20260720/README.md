# Author-led VHR label re-review and internal resolution

W.D. (Dai Wenzhe) re-reviewed all 622 original reference records and internally resolved discordant cases. This is an author-led repeat interpretation and provenance audit, not an independent validation study.

The viewing source recorded in the audit is Esri World Imagery through an ArcGIS REST viewer at zoom level 18. Imagery dates and native spatial resolution were not consistently exposed by the viewer and are therefore recorded as unknown rather than inferred. The interpretation window is represented by the historical contact-sheet position identifiers. Licensed imagery is not redistributed; the submission package contains only the decision and provenance logs.

Five records remain unresolved after internal resolution. Ninety-two uncertain or uninterpretable records are excluded. The author-resolved working label set contains 525 records, including 16 rubber records; this is below the prespecified minimum class count of 30.

Canonical files:

- `reference_samples_author_rereview_resolved_AUDIT_20260720.csv`: submission-facing derivative of the complete decision/provenance log.
- `reference_samples_author_resolved_INCLUDED_20260720.csv`: submission-facing derivative containing the 525 included working-label records.
- `author_rereview_summary_20260720.json`: machine-readable counts and claim boundary.
- `AUTHOR_LED_VHR_LABEL_REREVIEW_REPORT_20260720.md`: reader-facing summary.
- `SUBMISSION_FACING_DERIVATIVE_PROVENANCE_20260721.json`: field mapping, source and derivative hashes, and invariance checks.

The two submission-facing CSVs replace three superseded schema fields with `historical_original_benchmark_included`, `historical_label_provenance_source`, and `historical_label_provenance_notes`. Historical confirmation and locked-set phrases are rendered as neutral original-benchmark inclusion records. Where a record can be attributed to the current re-review, it is described as an author-led VHR re-review by W.D. Sample identifiers, coordinates, all label fields, inclusion flags, resolution status values, and analysis results are unchanged. Byte-identical pre-derivative CSVs are retained only in an internal archive that is excluded from the submission and public repository.
