# CEA R12 Evidence-Aligned Archive

This repository contains the public release materials for the CEA R12 manuscript package:

**Spatially honest trust routing for smallholder land-cover mapping under scarce verified labels**.

## Current Release

The valid evidence-aligned release for this manuscript is:

- package: `submission_packages/CEA_R12_FINAL_EVIDENCE_ALIGNED_QA_PACKAGE_20260623.zip`
- SHA256: `c34eca318fa94a545903d21e51dabbd9c428aa0ba85bcf77a6d3811951ea7cd0`
- active manuscript: `manuscript/CEA_trust_router_R12_CEA_FORMATTED_20260623_final_evidence_aligned.docx`
- QA: `qa/final_evidence_aligned_qa_20260623/`
- manifest and package checks: `manifests_checksums/final_evidence_aligned_qa_20260623/`

This package is anchored to the manuscript evidence index and the 524-sample CEA R12 evidence chain. It includes the manuscript, manuscript figures, result CSV/JSON evidence, second-reader evidence, final QA logs, manifest, package summary, package verification, and SHA256 sidecars.

## Evidence Boundary

For the CEA R12 manuscript, use the evidence inside the current release ZIP. In particular, the manuscript evidence chain is based on:

- `data/reference_samples_TARGETED_USER_CONFIRMED_80_20260603.csv`
- `results_revision9_variogram_20260614/`
- `results_revision10_mondrian_router_standard_20260614/`
- `results_revision10_spatial_crossfit_router_standard_20260614/`
- `results_revision11_class_support_repair_20260614/`
- `results_revision12_support_density_sensitivity_20260614/`
- `results_weak_reference_contamination_20260606/`
- `second_reader_evidence_20260620/`

Do not use the repository-level 622-sample `active_q25_rerun` files as evidence for this CEA R12 manuscript. They are retained only as legacy repository contents from an earlier public staging line and are not the active evidence base for the 2026-06-23 CEA R12 archive.

## QA Status

The final evidence-alignment QA passed with 38 checks, 0 warnings, and 0 failures. The DOCX rendered to a 30-page PDF; all 30 page PNGs were generated, and no blank-like pages were detected.

The second-reader V1 kappa status is interpreted as `OK_READABLE_PAIR_ONLY` in the rebuilt package. Numeric values are preserved from the source evidence: 500 scorable pairs, 24 unreadable rows, and Cohen's kappa 0.5189067216301492. This supports readable-pair remote visual agreement only; it is not field truth.

## Data Availability Note

No DOI has been minted for this package. The stable public archive is the GitHub tag for this release. A DOI-bearing OSF, Zenodo, or figshare archive can be added later without changing the experimental results.
