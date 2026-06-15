# Upload Checklist

Complete these steps before making the repository public or linking it in a manuscript.

## Author-controlled items

- Choose and insert final license terms for code, data, figures, and documentation.
- Confirm final CRediT author contributions.
- Confirm missing ORCID records outside this data repository if they remain in manuscript files.
- Create a GitHub release and, preferably, archive the release through Zenodo to obtain a DOI.
- Replace the manuscript Data Availability record with the final public release URL or DOI.

## Evidence-strengthening items

- Add second-reader VHR agreement or field validation if available.
- Add NNDM/kNNDM or support-balanced spatial validation if run.
- Add complete-case or alternative-imputation sensitivity if run.
- Point-level public Sentinel-2 imagery-date audit is included in `results/point_imagery_dates/`; exact VHR basemap dates remain available only if recorded by the interpretation platform or author records.

## Repository QA

- Rerun manifest and checksum generation after any edits.
- Confirm that main data do not include targeted-validation candidate queues as ground truth.
- Confirm that no private access material or authentication files are present.
- Confirm that raw third-party VHR imagery or restricted data are not redistributed without permission.

