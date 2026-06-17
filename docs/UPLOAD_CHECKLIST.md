# Upload Checklist

Complete these steps before making the repository public or linking it in a manuscript.

## Author-controlled items

- Choose and insert final license terms for code, data, figures, and documentation.
- Confirmed: final CRediT author contributions have been supplied for the manuscript.
- Confirm missing ORCID records outside this data repository if they remain in manuscript files.
- Current manuscript wording may cite the stable GitHub commit URL: https://github.com/wenzhedai57-coder/spatial-validation-geoai-smallholder-mapping/tree/78d16cbaa5ca55922b0ccdd2fc595e81b135abd7. A GitHub release or Zenodo DOI is optional for a later archive upgrade.
- Replace manuscript placeholders with the stable GitHub commit URL already selected by the author.

## Evidence-strengthening items

- Confirm that the completed second-reader VHR adjudication QA artifact remains described as image/VHR review, not in-situ validation, and that it is routed as submission supplementary material rather than as part of the public GitHub release.
- Add NNDM/kNNDM or support-balanced spatial validation if run.
- Add complete-case or alternative-imputation sensitivity if run.
- Point-level public Sentinel-2 imagery-date audit is included in `results/point_imagery_dates/`; exact VHR basemap dates remain available only if recorded by the interpretation platform or author records.

## Repository QA

- Rerun manifest and checksum generation after any edits.
- Confirm that main data do not include targeted-validation candidate queues as ground truth.
- Confirm that no private access material or authentication files are present.
- Confirm that raw third-party VHR imagery or restricted data are not redistributed without permission.
