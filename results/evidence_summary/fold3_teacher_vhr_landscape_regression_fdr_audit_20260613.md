# Fold3 Teacher-VHR Landscape Regression FDR Audit

Benjamini-Hochberg FDR correction over OK landscape-regression rows after the fold-3 VHR repair. Interpretation remains exploratory and non-causal because predictors are weak contextual covariates, not reference labels.

| predictor | coefficient | standard_error | p_value | fdr_bh_q_value | fdr_bh_0_05_significant | n_samples |
| --- | --- | --- | --- | --- | --- | --- |
| dw_flooded_vegetation | 3.044 | 0.605 | 6.83e-07 | 1.02e-06 | True | 523 |
| dw_water | 1.283 | 0.432 | 3.13e-03 | 3.76e-03 | True | 500 |
| dw_crops | 0.804 | 0.116 | 1.05e-11 | 4.73e-11 | True | 523 |
| dw_entropy_full_8class | 0.718 | 0.109 | 2.24e-10 | 4.03e-10 | True | 302 |
| dw_entropy | 0.703 | 0.106 | 1.79e-10 | 3.58e-10 | True | 303 |
| dw_entropy_partial_5class | 0.497 | 0.071 | 9.71e-12 | 4.73e-11 | True | 500 |
| fdp_rubber_probability_2023 | 0.142 | 0.077 | 6.45e-02 | 6.45e-02 | False | 502 |
| active_score | -0.036 | 0.014 | 1.22e-02 | 1.29e-02 | True | 221 |
