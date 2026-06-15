# Second-Reader VHR Agreement Workflow

This folder contains the blind second-reader interpretation template and allowed-value list.

The second reader must fill the template manually from VHR/image interpretation. Do not fill the table from the locked reference labels, model predictions, Dynamic World, WorldCover, or any other weak product.

## Files

- `second_reader_blind_vhr_interpretation_template_20260616.xlsx`: Excel version for the human second reader, with instructions and drop-down values.
- `second_reader_blind_vhr_interpretation_template_20260616.csv`: machine-readable blind table for the human second reader.
- `second_reader_allowed_values_20260616.csv`: exact allowed class and confidence values.
- `second_reader_template_manifest_20260616.json`: provenance for the generated template.

## Human-Filled Output Name

After manual interpretation, save a copy as:

`second_reader_blind_vhr_interpretation_FILLED_BY_<INITIALS>_<YYYYMMDD>.csv`

Keep the original template unchanged.
