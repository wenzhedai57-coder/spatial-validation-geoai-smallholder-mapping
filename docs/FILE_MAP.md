# File Map

## Root

- `README.md`: repository overview and evidence boundary.
- `LICENSE`: license status; must be replaced before public release.
- `CITATION.cff`: citation metadata for the staging repository; repository URL/DOI is omitted until minted.
- `requirements.txt`: Python dependencies from the source package.

## Main folders

- `config/`: hash-preserved original run configuration plus a public path reproduction configuration.
- `scripts/`: public-oriented pipeline, export, variogram, manifest, and verification scripts. Old handoff/package scripts that required missing review queues were removed from the slim public repo.
- `data/`: cleaned active reference data, feature matrices, and landscape covariates.
- `results/`: active results, variogram outputs, evidence summaries, reviewer-risk audits, spatial-sensitivity support artifacts, review-planning support artifacts, point-level public Sentinel-2 imagery-date audit artifacts, and the 20260624 submission supplementary reproducibility artifacts.
- `figures/`: manuscript figure files, including 13 paired PNG/PDF files in the 20260624 update, and regenerated variogram plot.
- `manifests_checksums/`: source package records plus newly generated staging manifest/checksum/verification.
- `docs/`: data availability, reproducibility, limitations, and upload notes.
- `docs/POINT_LEVEL_IMAGERY_DATES.md`: scope and wording for the public Sentinel-2 point-level imagery-date audit.

