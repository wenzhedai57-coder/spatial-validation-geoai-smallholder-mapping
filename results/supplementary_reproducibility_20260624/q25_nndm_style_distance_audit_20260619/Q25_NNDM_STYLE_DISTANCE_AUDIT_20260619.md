# Q25 NNDM-style nearest-neighbour distance audit

Status: OK

This audit addresses the reviewer-facing concern that the q25 spatial split should be defended against ordinary random cross-validation. It is an NNDM/kNNDM-style nearest-neighbour distance diagnostic, not a full NNDM or kNNDM design, because no prediction-domain target grid or external prediction point distribution was supplied.

Inputs:

- Config: `C:\Users\m1761\Documents\New project\IJRS_ADJUDICATED_SENSITIVITY_20260618\config\config_fold3_teacher_vhr_repair_20260613.yaml`
- Reference samples: `C:\Users\m1761\Documents\New project\IJRS_ADJUDICATED_SENSITIVITY_20260618\data\reference_samples_verified_622_public.csv`
- Variogram choice: `C:\Users\m1761\Documents\New project\IJRS_ADJUDICATED_SENSITIVITY_20260618\results\active_q25_rerun\variogram_choice.json`
- Random seed: `42`
- q25 block distance: `126783.51747145985` m

Key computed outputs:

- Random CV: median nearest train distance = `5102.212994971584` m; test points below q25 block distance = `622` of `622`.
- Q25 spatial CV: median nearest train distance = `185684.7382436528` m; test points below q25 block distance = `0` of `622`; zero-leakage folds = `4` of `4`.
- Median nearest-distance ratio, q25 spatial over random = `36.392980541316454`.

Interpretation:

The q25 split is not presented as design-unbiased map accuracy or as a substitute for a full NNDM/kNNDM prediction-domain design. It is a conservative class-structure-informed split whose folds pass a nearest-neighbour zero-leakage audit at the variogram-derived q25 distance. The random split remains a close-neighbour interpolation comparator.
