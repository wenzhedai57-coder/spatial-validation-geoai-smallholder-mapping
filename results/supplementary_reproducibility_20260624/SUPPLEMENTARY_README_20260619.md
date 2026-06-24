# IJRS supplementary reproducibility package

This supplementary package supports the manuscript "Spatial validation choices reshape GeoAI accuracy estimates in Malaysian smallholder mapping."

Contents:

- `second_reader_vhr_adjudication/`: blinded second-reader VHR adjudication workpack and provenance.
- `adjudicated_sensitivity_20260618/`: adjudicated-subset sensitivity rerun artifacts.
- `fold3_support_sensitivity_20260613/`: manuscript-cited support-sensitivity evidence for the q25 fold-3 training-support limitation.
- `imputation_sensitivity_20260624/`: complete-case RandomForest sensitivity for the logged `-9999` sentinel-to-NaN median-imputation policy.
- `q25_nndm_style_distance_audit_20260619/`: q25 nearest-neighbour distance audit and provenance.
- `mondrian_conformal_sensitivity_20260619/`: Mondrian conformal sensitivity artifacts.
- `prospective_probability_validation_protocol_20260619/`: prospective Tier-1 probability-sampling and independent-review protocol. CSV templates are header-only and do not add new results.
- `rubber_belt_calibration_evidence_20260613/`: source summary/detail files for the rubber-belt local calibration and no-information baseline diagnostics cited in the manuscript.
- `supplementary_figures/`: supplementary variogram/block-distance figure and provenance.

Boundary:

- These files support transparency, sensitivity analysis, and future probability-validation design.
- They do not add uncomputed metrics or stronger accuracy claims beyond the manuscript.
- Third-party Earth-observation products and licensed VHR imagery are not redistributed as raw source products.
- `TARGETED_VHR_SUPPLEMENT_*` identifiers are public-facing candidate identifiers for targeted VHR supplement records. They are provenance labels only and do not denote synthetic data, placeholder records, or fabricated labels.
