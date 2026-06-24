# Mondrian/Class-Conditional Conformal Sensitivity

Status: OK

Alpha: `0.1`; target coverage: `0.9`.

This sensitivity recomputes split conformal prediction with class-conditional (Mondrian) thresholds. Each class receives its own quantile from calibration examples whose true label is that class. Classes below `min_class_count` are dropped per config and logged explicitly.

## Primary B2 RandomForest rows

- `random`: coverage `0.88`, average set size `1.784`, n_calibration `311`, n_test `125`.
- `spatial`: coverage `0.9859154929577465`, average set size `3.387323943661972`, n_calibration `362`, n_test `142`.

## Global versus Mondrian comparison for B2 RandomForest

- `random`: global coverage `0.904` -> Mondrian coverage `0.88`; global set size `1.784` -> Mondrian set size `1.784`.
- `spatial`: global coverage `0.9859154929577464` -> Mondrian coverage `0.9859154929577464`; global set size `5.619718309859155` -> Mondrian set size `3.387323943661972`.

Interpretation boundary:

This is a sensitivity analysis. It does not repair exchangeability under spatial shift; it tests whether class-conditional calibration changes the coverage/informativeness trade-off already reported in the manuscript.
