# Final evidence-alignment QA (2026-06-23)

Package root: `C:\Users\m1761\Desktop\cea23\s\CEA_R12_FINAL_EVIDENCE_ALIGNED_QA_PACKAGE_20260623`
PASS/WARN/FAIL: 38/0/0

## Failed checks
- None

## Key confirmed evidence
- Reference CSV row count is 524 and the class count table is 86/75/92/62/126/83.
- Variogram block distance is 150850.82331783767 m with exponential_model range choice.
- Four spatial folds have zero leakage and minimum train-test distance above the block distance.
- B3 spatial crossfit all-test and retained-class values match the R12 CSV artifacts.
- B3 risk-controlled auto-map row is n=32, accuracy=0.9375, Wilson CI [0.7985287685584542, 0.982689432968359], errors=2.
- Second-reader V1 status is package-corrected to OK_READABLE_PAIR_ONLY with 500 scorable pairs, 24 unreadable rows, and kappa=0.5189067216301492 preserved.
