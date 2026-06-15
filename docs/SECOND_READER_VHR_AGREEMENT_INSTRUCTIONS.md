# Second-Reader VHR Agreement Instructions

Follow these steps exactly. The second-reader labels must be produced by a human image interpreter.

## What You Need To Fill

Open:

`docs/second_reader_vhr_agreement/second_reader_blind_vhr_interpretation_template_20260616.xlsx`

If Excel cannot open the XLSX, use the CSV version:

`docs/second_reader_vhr_agreement/second_reader_blind_vhr_interpretation_template_20260616.csv`

The table is blind: it includes `sample_id`, coordinates, and a map link, but it does not show the locked original class label.

## Allowed Class Labels

Use exactly one of these values in `second_reader_class_name`:

- `oil_palm`
- `rubber`
- `paddy`
- `other_agri`
- `forest`
- `builtup_other`
- `uncertain`
- `uninterpretable`

Do not invent new labels. If the point cannot be assigned confidently, use `uncertain`. If imagery is unusable, use `uninterpretable`.

## Allowed Confidence Values

Use exactly one of these values in `second_reader_confidence`:

- `high`
- `medium`
- `low`

## Manual Interpretation Procedure

1. Open the template in Excel.
2. For each row, open the `map_url` or copy the `longitude` and `latitude` into Google Earth Pro, ArcGIS/Esri World Imagery, or another VHR imagery platform you can access.
3. Inspect the point itself and the immediate surrounding land-cover context.
4. Use VHR imagery as the main evidence. Do not copy labels from the existing reference table, model predictions, WorldCover, Dynamic World, or Sentinel-2 class products.
5. Fill `second_reader_class_name` with one allowed class value.
6. Fill `second_reader_confidence` with `high`, `medium`, or `low`.
7. Fill `imagery_source_used`, for example `Google Earth Pro`, `Esri World Imagery`, or another real source name.
8. Fill `imagery_date_visible` only if the imagery platform shows a date. Use `YYYY-MM-DD`, `YYYY-MM`, `YYYY`, or `unknown`.
9. Fill `reviewer_initials`.
10. Fill `review_timestamp_utc` in UTC if possible, for example `20260616T120000Z`.
11. Add short notes only when useful, especially for uncertain, mixed, boundary, cloudy, or changed points.

## Important Rules

- Do not change `sample_id`, `longitude`, `latitude`, or `map_url`.
- Do not sort the sheet unless you can restore the original rows by `sample_id`.
- Do not leave `second_reader_class_name` blank.
- Do not guess. Use `uncertain` or `uninterpretable` when appropriate.
- Do not ask me to fabricate second-reader labels. I can merge and calculate agreement after a human fills the file.

## Save The Completed File

Save a completed copy here:

`docs/second_reader_vhr_agreement/second_reader_blind_vhr_interpretation_FILLED_BY_<INITIALS>_<YYYYMMDD>.csv`

Example:

`docs/second_reader_vhr_agreement/second_reader_blind_vhr_interpretation_FILLED_BY_WD_20260620.csv`

Keep the original template unchanged.

## After You Finish

Ask me to merge the completed second-reader table, or run:

```powershell
cd "<repository root>"
python scripts\merge_second_reader_vhr_agreement.py --second-reader-csv "docs\second_reader_vhr_agreement\second_reader_blind_vhr_interpretation_FILLED_BY_WD_20260620.csv"
```

The script will create:

- `results/second_reader_vhr_agreement/second_reader_agreement_summary_<date>.json`
- `results/second_reader_vhr_agreement/second_reader_confusion_matrix_<date>.csv`
- `results/second_reader_vhr_agreement/second_reader_per_class_agreement_<date>.csv`
- `results/second_reader_vhr_agreement/second_reader_disagreements_for_adjudication_<date>.csv`
- `results/second_reader_vhr_agreement/second_reader_completion_audit_<date>.csv`

If any required cell is missing or invalid, the script writes `ERROR`/`SKIPPED` instead of inventing agreement results.
