# Prospective Tier-1 probability-validation protocol

Created: 2026-06-19T01:45:01+08:00

## Scope

This protocol defines the future data-collection work needed to upgrade the present IJRS manuscript from a validation-sensitivity diagnostic study to a stronger design-based accuracy-assessment study. It does not create current results.

## Non-negotiable boundaries

- Do not add any row to the verified reference set until it has a final adjudicated label and `verified == True`.
- Do not use ESA WorldCover, Google Dynamic World, GlobalOilPalm, Forest Data Partnership, or any other weak product as ground truth.
- Do not report area-adjusted accuracy until inclusion probabilities and design weights exist for the sampled records.
- Do not report unstable class-specific F1 or conformal metrics when class support falls below `config.min_class_count`.
- Do not substitute plausible labels, weights, field status, or VHR dates when the evidence is missing.

## Step 1. Freeze the current diagnostic baseline

Preserve the current 622-row analysis as the v1 diagnostic baseline. The future probability-sampled extension should be stored as a separate v2 validation line. This prevents the current non-probability diagnostic sample from being mixed silently with a future probability sample.

## Step 2. Define the future estimand

Before drawing samples, the authors must choose the target estimand. The recommended primary estimand is design-based map accuracy for the defined study area and class legend. Secondary estimands may include class-specific accuracy, rubber-belt transfer accuracy, and feature-stack sensitivity.

## Step 3. Build the sampling frame

Create a sampling frame over the intended prediction domain or validation domain. Each frame unit must have a known stratum assignment and a computable inclusion probability. Candidate strata may use predicted class, geographic subregion, uncertainty, or known low-support classes, but weak reference products remain screening aids only.

## Step 4. Oversample low-support and unstable strata

Rubber must be prioritized because the adjudicated-subset rerun leaves only 16 rubber samples. Other visually confusable agricultural classes should also be prioritized if they remain under-supported within key folds or regions. Oversampling is acceptable only if the inclusion probabilities and design weights are recorded.

## Step 5. Draw the probability sample

Use a documented random or systematic probability design within each stratum. Every selected row must record the sampling frame version, stratum, draw seed, inclusion probability, and design weight. The header-only file `probability_sample_frame_template_20260619.csv` defines the required fields.

## Step 6. Conduct independent label interpretation

At least two readers should independently assign labels from date-stamped VHR evidence. Disagreements must be routed to an independent third reader. The header-only file `third_reader_adjudication_template_20260619.csv` defines the required adjudication fields.

## Step 7. Anchor a random subset with field or high-quality VHR evidence

A random subset should be anchored with field observations or high-quality date-stamped VHR imagery. The anchor must record evidence date, evidence source, confidence, and temporal alignment with the 2024 feature year. The header-only file `field_vhr_anchor_log_template_20260619.csv` defines the required fields.

## Step 8. Update the verified reference file

Only rows with final labels, evidence status, and `verified == True` may enter the future reference file. Ambiguous rows should remain as `NOT_VERIFIED`, `NEEDS_THIRD_READER`, `FIELD_CHECK_REQUIRED`, or another explicit non-metric status.

## Step 9. Recompute the full pipeline

After the future verified reference file exists, rerun the complete pipeline. Recompute class counts, variogram ranges, spatial block distances, leakage assertions, random and spatial CV, random and spatial conformal diagnostics, transfer diagnostics, area-adjusted accuracy, and confidence intervals. All new numerical results must be written to disk with timestamp, config hash, input file names, and seed.

## Step 10. Rewrite the manuscript only after the new artifacts exist

Only after the new probability sample, adjudication records, and area-adjusted outputs exist should the manuscript claim design-based map accuracy or class-specific confidence intervals. Until then, the current manuscript should remain framed as a validation-sensitivity diagnostic study.
