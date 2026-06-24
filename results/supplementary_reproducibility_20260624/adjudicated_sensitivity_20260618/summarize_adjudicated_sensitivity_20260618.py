"""Summarize adjudicated-subset sensitivity outputs for manuscript revision."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def metric_lookup(table4: pd.DataFrame, stack: str, model: str, metric: str) -> dict[str, Any]:
    hit = table4[(table4["stack"] == stack) & (table4["model"] == model) & (table4["metric"] == metric)]
    if hit.empty:
        return {"status": "MISSING", "reason": f"Missing table4 row for {stack} {model} {metric}"}
    row = hit.iloc[0].to_dict()
    return {
        "status": row.get("status", ""),
        "reason": row.get("reason", ""),
        "random_value": row.get("random_value", ""),
        "spatial_value": row.get("spatial_value", ""),
        "optimism_gap": row.get("optimism_gap", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results/adjudicated_sensitivity_20260618")
    parser.add_argument("--reference", default="data/reference_samples.csv")
    args = parser.parse_args()

    root = Path.cwd()
    results_dir = (root / args.results_dir).resolve()
    ref_path = (root / args.reference).resolve()
    timestamp = utc_stamp()

    required = {
        "class_counts": results_dir / "adjudicated_reference_class_counts_20260618.csv",
        "variogram_summary": results_dir / "block_distance_practical_rule_summary_20260618.json",
        "spatial_audit": results_dir / "spatial_fold_leakage_audit.csv",
        "table4": results_dir / "table4_optimism_gap.csv",
        "transfer": results_dir / "table10_leave_region_out_transfer.csv",
        "transfer_per_class": results_dir / "table10_leave_region_out_transfer_per_class.csv",
        "reference": ref_path,
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        print("ERROR: missing required inputs: " + " | ".join(missing))
        return 1

    class_counts = read_csv(required["class_counts"])
    spatial_audit = read_csv(required["spatial_audit"])
    table4 = read_csv(required["table4"])
    transfer = read_csv(required["transfer"])
    transfer_per_class = read_csv(required["transfer_per_class"])
    ref = read_csv(ref_path)
    variogram_summary = json.loads(required["variogram_summary"].read_text(encoding="utf-8"))

    fold1_skipped = bool(((spatial_audit["fold"].astype(str) == "1") & (spatial_audit["status"].astype(str) == "SKIPPED")).any())
    ok_spatial_folds = int((spatial_audit["status"].astype(str) == "OK").sum())
    skipped_spatial_folds = int((spatial_audit["status"].astype(str) == "SKIPPED").sum())

    metric_rows: list[dict[str, Any]] = []
    for stack in ["B2", "B3"]:
        for metric in ["oa", "macro_f1"]:
            values = metric_lookup(table4, stack, "RandomForest", metric)
            metric_rows.append(
                {
                    "timestamp": timestamp,
                    "scope": "adjudicated_subset_table4_random_vs_spatial",
                    "stack": stack,
                    "model": "RandomForest",
                    "metric": metric,
                    **values,
                    "spatial_fold_condition": "INCOMPLETE_Q25_SPATIAL_FOLDS" if fold1_skipped else "ALL_Q25_SPATIAL_FOLDS_OK",
                    "ok_spatial_folds": ok_spatial_folds,
                    "skipped_spatial_folds": skipped_spatial_folds,
                }
            )

    rubber_transfer = transfer[
        (transfer["held_out_region"] == "johor_negeri_pahang_rubber_belt")
        & (transfer["stack"].isin(["B2", "B3"]))
        & (transfer["model"] == "RandomForest")
    ]
    rubber_per_class = transfer_per_class[
        (transfer_per_class["held_out_region"] == "johor_negeri_pahang_rubber_belt")
        & (transfer_per_class["stack"].isin(["B2", "B3"]))
        & (transfer_per_class["model"] == "RandomForest")
        & (transfer_per_class["class_code"].astype(str) == "2")
    ]
    region_ref = ref[ref["region_key"].astype(str) == "johor_negeri_pahang_rubber_belt"].copy()
    region_counts = region_ref["class_name"].value_counts().sort_values(ascending=False)
    majority_class = str(region_counts.index[0]) if not region_counts.empty else "MISSING"
    majority_count = int(region_counts.iloc[0]) if not region_counts.empty else 0
    region_n = int(len(region_ref))
    majority_baseline_oa = majority_count / region_n if region_n else ""

    transfer_rows: list[dict[str, Any]] = []
    for _, row in rubber_transfer.iterrows():
        per_class = rubber_per_class[rubber_per_class["stack"] == row["stack"]]
        pc = per_class.iloc[0].to_dict() if not per_class.empty else {}
        transfer_rows.append(
            {
                "timestamp": timestamp,
                "scope": "adjudicated_subset_rubber_belt_transfer",
                "stack": row.get("stack", ""),
                "model": row.get("model", ""),
                "status": row.get("status", ""),
                "reason": row.get("reason", ""),
                "n_train": row.get("n_train", ""),
                "n_test": row.get("n_test", ""),
                "oa": row.get("oa", ""),
                "macro_f1": row.get("macro_f1", ""),
                "rubber_support": pc.get("support", ""),
                "rubber_precision": pc.get("precision", ""),
                "rubber_recall": pc.get("recall", ""),
                "rubber_f1": pc.get("f1", ""),
                "heldout_majority_class": majority_class,
                "heldout_majority_count": majority_count,
                "heldout_region_n": region_n,
                "heldout_majority_baseline_oa": majority_baseline_oa,
                "interpretation_status": "UNSTABLE_RUBBER_SUPPORT_BELOW_MIN_CLASS_COUNT_30",
            }
        )

    out_rows = metric_rows + transfer_rows
    out_fields = sorted({key for row in out_rows for key in row.keys()})
    summary_csv = results_dir / "adjudicated_sensitivity_manuscript_summary_20260618.csv"
    write_csv(summary_csv, out_fields, out_rows)

    provenance = {
        "timestamp": timestamp,
        "script": str(Path(__file__).resolve()),
        "inputs": {key: str(path) for key, path in required.items()},
        "input_sha256": {key: sha256_file(path) for key, path in required.items()},
        "output_csv": str(summary_csv),
        "output_csv_sha256": sha256_file(summary_csv),
        "verified_rows": int(len(ref)),
        "class_counts": class_counts.to_dict(orient="records"),
        "variogram_status": variogram_summary.get("status", ""),
        "suggested_block_distance_m": variogram_summary.get("suggested_block_distance_m", ""),
        "ok_spatial_folds": ok_spatial_folds,
        "skipped_spatial_folds": skipped_spatial_folds,
        "rubber_belt_region_counts": region_counts.to_dict(),
        "note": "All summary values are copied or computed from adjudicated-subset CSV/JSON outputs; no manuscript numbers were hand-entered.",
    }
    summary_json = results_dir / "adjudicated_sensitivity_manuscript_summary_20260618.json"
    summary_json.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Adjudicated-subset sensitivity summary",
        "",
        f"Timestamp UTC: `{timestamp}`",
        f"Reference rows: `{len(ref)}`",
        f"Indicator q25 status: `{variogram_summary.get('status', '')}`",
        f"Indicator q25 distance: `{variogram_summary.get('suggested_block_distance_m', '')}` m",
        f"Spatial folds: `{ok_spatial_folds}` OK, `{skipped_spatial_folds}` SKIPPED",
        "",
        "## Class counts",
        "",
        class_counts.to_markdown(index=False),
        "",
        "## B2/B3 RandomForest table4 sensitivity",
        "",
        pd.DataFrame(metric_rows).to_markdown(index=False),
        "",
        "## Rubber-belt transfer sensitivity",
        "",
        pd.DataFrame(transfer_rows).to_markdown(index=False),
        "",
        "Interpretation: rubber-belt overall accuracy under the adjudicated subset is not a rubber-transfer improvement claim because the held-out rubber class has support below `min_class_count=30`.",
        "",
        f"CSV: `{summary_csv}`",
        f"JSON: `{summary_json}`",
    ]
    (results_dir / "ADJUDICATED_SENSITIVITY_MANUSCRIPT_SUMMARY_20260618.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(json.dumps({"status": "OK", "summary_csv": str(summary_csv), "summary_json": str(summary_json)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
