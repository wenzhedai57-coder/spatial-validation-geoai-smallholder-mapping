# Reproducibility guide

1. Read `../README.md` and `../data/REFERENCE_LABEL_SEMANTICS.md`.
2. Use `../config/config_public_reproduction_20260615.yaml` for portable paths.
3. Inspect the manuscript-to-file map in `../results/supplementary_reproducibility_20260720/SUPPLEMENT_INDEX.md`.
4. Reproduce the 622-record sensitivity results from `../results/active_q25_rerun/` and the feature stacks under `../data/`.
5. Treat the 525-record branch as an author-resolved working-label sensitivity analysis; one q25 fold is not estimable.
6. Verify files with `../manifests_checksums/PUBLIC_REPO_MANIFEST_20260720.csv` and `PUBLIC_REPO_CHECKSUMS_SHA256_20260720.txt`.

Seeds, configuration hashes, prediction files, and fold-support audits are retained. Local historical disk paths have been replaced by `${{REPOSITORY_ROOT}}/` placeholders in the current supplementary package.
