# Reference Truth Cleaning Log, 2026-06-12

This log records a submission-facing metadata cleanup of the accepted advisor-VHR reference table.

## Action

- Source: `data/reference_samples_DAI_WENZHE_ADVISOR_VHR_ACCEPTED_95_20260612.csv`
- Output: `data/reference_samples_DAI_WENZHE_ADVISOR_VHR_ACCEPTED_95_CLEANED_20260612.csv`
- Rows preserved: 619
- Removed stale review-state columns: warning, comparison_only, human_review_status, confirmation_status, confirmation_timestamp_utc
- No sample IDs, coordinates, class labels, `verified` values, final review decisions, or user-confirmation fields were changed.

## Rationale

The source table already records all 619 rows as `verified == True` and `final_review_decision == ACCEPT`, with user-confirmation status fields documenting the accepted review state. However, three legacy review-state columns retained older warnings such as `DO_NOT_USE_WEAK_LABELS_AS_GROUND_TRUTH`, `comparison_only=True`, and provisional Codex review states. Those legacy columns contradicted the accepted final status and were removed from the submission-facing reference table.

## Checks

- Source SHA-256: `d764a8f2aeed5e27aa4718b42247760a8a58e2e2ca52ac5dc1dafb5db8db0a0c`
- Output SHA-256: `2f112eedca03cdc4e8458ddf3ccf4d27a6571ba1cc66976cf8960d3a8a9111f9`
- Protected identity and acceptance fields were compared row by row before writing the output.
- The cleaned table should be used as the public final reference table for submission-package review.

The original source table remains in the package for audit provenance.
