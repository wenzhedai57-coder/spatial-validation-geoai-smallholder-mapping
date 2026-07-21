# IJRS supplementary reproducibility package

This package supports *Validation distance, training support, and label re-review jointly shape GeoAI performance estimates in Malaysian smallholder mapping*.

## Canonical evidence branches

- `author_led_vhr_label_rereview_20260720/`: W.D. (Dai Wenzhe) author-led repeat VHR interpretation and internal resolution log.
- `author_resolved_label_sensitivity_20260618/`: analyses using the 525-record author-resolved working label set. A complete four-fold q25 estimate is not available under current class support.
- `active_q25_rerun/`: fully evaluable four-fold sensitivity benchmark based on the 622 original labels. It is not independently verified ground truth.
- Remaining folders contain fold-support, nearest-neighbour distance, conformal, trust-routing, transfer, figure-provenance, and prospective-validation diagnostics.

## Claim boundary

W.D. performed both the repeat interpretation and internal resolution. The procedure is an internal author re-review, not an independent validation study. Five records remain unresolved after internal resolution; 92 uncertain or uninterpretable records are excluded. The resulting 525-record working set contains 16 rubber records, so rubber results are exploratory and a complete four-fold q25 estimate is not available. Licensed VHR contact sheets are not redistributed.

Historical review files and superseded wording are preserved in a separate internal archive that is explicitly excluded from the submission package. Machine status codes remain only in data and provenance files where they are part of the reproducible schema.

The two canonical author-led re-review CSVs are submission-facing terminology derivatives. Their provenance-oriented field names and source descriptions were neutralised without changing any identifiers, coordinates, labels, inclusion flags, resolution statuses, or analytical results. `author_led_vhr_label_rereview_20260720/SUBMISSION_FACING_DERIVATIVE_PROVENANCE_20260721.json` records the exact field mapping, invariance checks, and source/derivative hashes. The byte-identical pre-derivative CSVs remain in a non-submitted internal archive.

Start with `SUPPLEMENT_INDEX.md` for a manuscript-to-file map.
