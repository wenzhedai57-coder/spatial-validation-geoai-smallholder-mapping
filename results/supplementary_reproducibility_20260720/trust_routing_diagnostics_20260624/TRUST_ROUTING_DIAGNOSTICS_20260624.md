# Trust-routing diagnostics (20260624)

This diagnostic converts the validation outputs into a conservative triage table. Routing uses only predicted class, known region/extension strata, Mondrian conformal set size, and q25 nearest-training distance. Ground-truth labels are used only to evaluate route-level error after assignment.

Routes:

- `manual_vhr_field_review`: broad conformal set or rubber-transfer risk.
- `local_calibration_required`: q25 spatial support breach or moderate conformal uncertainty.
- `low_risk_screening_only`: small conformal set, no rubber-transfer risk, and within q25 support distance.

Files written:

- `trust_routing_point_assignments_20260624.csv`
- `trust_routing_route_summary_20260624.csv`
- `trust_routing_split_summary_20260624.csv`
- `trust_routing_error_capture_20260624.csv`
- `trust_routing_provenance_20260624.json`
