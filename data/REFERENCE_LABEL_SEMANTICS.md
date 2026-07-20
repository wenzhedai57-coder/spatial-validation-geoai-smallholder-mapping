# Original-label benchmark schema note

`reference_samples_verified_622_public.csv` is a historical filename retained to avoid breaking scripts and hashes in the original analysis line. In this repository version:

- the 622 rows are called the **original-label sensitivity benchmark**;
- the `verified` Boolean is a historical inclusion flag, not a claim of independent verification;
- original class labels and coordinates are unchanged;
- reader-facing provenance notes have been clarified to remove superseded `locked` and independent-validation implications;
- the author-led re-review and 525-record working label set are separate files under `results/supplementary_reproducibility_20260720/author_led_vhr_label_rereview_20260720/`.

Do not use the 622-row table as independently adjudicated ground truth. Use it only for the original-label sensitivity estimand described in the manuscript.
