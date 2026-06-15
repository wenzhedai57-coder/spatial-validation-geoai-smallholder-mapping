# Known Limitations

This repository intentionally preserves the main evidence limitations rather than smoothing them over.

- Reference labels are image/VHR-verified, not field-validated.
- A second-reader agreement workflow/template is included, but no final second-reader agreement result is available until a human completes the blind interpretation table.
- Point-level public Sentinel-2 acquisition-date coverage is now audited in `results/point_imagery_dates/`; exact VHR basemap acquisition dates are still not available for every reference point.
- Sampling probabilities and design weights are not available, so reported OA and macro-F1 values are diagnostic sample-based metrics, not design-unbiased map accuracy estimates.
- The q25 spatial validation is zero-leakage but support-sensitive; fold 3 has limited training support.
- NNDM/kNNDM or a separate support-balanced spatial-validation rerun is not included in this staging repository.
- Complete-case or alternative-imputation sensitivity is not included.
- Targeted-validation candidate queues are not ground truth and are excluded from main data.
- Weak reference products are only screening/contextual evidence.
