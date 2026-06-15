from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INDICATOR_SUMMARY = ROOT / "results_final_revision_20260612" / "variogram_indicator_summary.json"
REF_FILE = ROOT / "data" / "reference_samples_DAI_WENZHE_ADVISOR_VHR_ACCEPTED_95_CLEANED_20260612.csv"
OUT_DIR = ROOT / "results_final_revision_20260612"
K_FOLDS = 4
SEED = 42


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def project_lonlat_to_meters(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 110_574.0
    return np.column_stack([x, y])


def spatial_precheck(coords: np.ndarray, y: np.ndarray, distance_m: float) -> dict[str, Any]:
    cells_x = np.floor(coords[:, 0] / distance_m).astype(int)
    cells_y = np.floor(coords[:, 1] / distance_m).astype(int)
    cell_ids = np.array([f"{x}:{y_}" for x, y_ in zip(cells_x, cells_y)])
    unique_cells = np.unique(cell_ids)
    out: dict[str, Any] = {
        "distance_m": float(distance_m),
        "distance_km": float(distance_m) / 1000.0,
        "available_spatial_blocks": int(len(unique_cells)),
        "required_spatial_blocks": K_FOLDS,
        "all_folds_nonempty": False,
        "min_train_count_after_buffer": "",
        "min_test_count": "",
        "fold_train_test_buffered": "",
        "fold_train_classes": "",
        "fold_test_classes": "",
    }
    if len(unique_cells) < K_FOLDS:
        out["reason"] = f"Only {len(unique_cells)} spatial blocks are available for k_folds={K_FOLDS}."
        return out

    rng = np.random.default_rng(SEED)
    shuffled = unique_cells.copy()
    rng.shuffle(shuffled)
    cell_to_fold = {cell: idx % K_FOLDS for idx, cell in enumerate(shuffled)}
    train_counts: list[int] = []
    test_counts: list[int] = []
    buffered_counts: list[int] = []
    train_classes: list[int] = []
    test_classes: list[int] = []
    fold_notes: list[str] = []
    for fold_idx in range(K_FOLDS):
        test_mask = np.array([cell_to_fold[cell] == fold_idx for cell in cell_ids])
        test_coords = coords[test_mask]
        distances = np.linalg.norm(coords[:, None, :] - test_coords[None, :, :], axis=2)
        near_test = np.any(distances <= distance_m, axis=1)
        train_mask = (~test_mask) & (~near_test)
        train_count = int(np.sum(train_mask))
        test_count = int(np.sum(test_mask))
        buffered_count = int(np.sum((~test_mask) & near_test))
        tc = int(len(set(y[train_mask])))
        vc = int(len(set(y[test_mask])))
        train_counts.append(train_count)
        test_counts.append(test_count)
        buffered_counts.append(buffered_count)
        train_classes.append(tc)
        test_classes.append(vc)
        fold_notes.append(f"fold{fold_idx + 1}:train={train_count};test={test_count};buffered={buffered_count};train_classes={tc};test_classes={vc}")

    out.update(
        {
            "all_folds_nonempty": bool(min(train_counts) > 0 and min(test_counts) > 0),
            "min_train_count_after_buffer": int(min(train_counts)),
            "min_test_count": int(min(test_counts)),
            "fold_train_test_buffered": " | ".join(fold_notes),
            "fold_train_classes": "|".join(str(x) for x in train_classes),
            "fold_test_classes": "|".join(str(x) for x in test_classes),
            "reason": "",
        }
    )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = json.loads(INDICATOR_SUMMARY.read_text(encoding="utf-8"))
    ok_ranges = [row for row in summary["class_ranges"] if row.get("status") == "OK"]
    range_values = np.array([float(row["chosen_range_m"]) for row in ok_ranges], dtype=float)

    selected_distance = float(np.quantile(range_values, 0.25))
    ref = pd.read_csv(REF_FILE)
    work = ref[parse_bool(ref["verified"])].dropna(subset=["longitude", "latitude", "class_code"]).copy()
    coords = project_lonlat_to_meters(work["longitude"].astype(float).to_numpy(), work["latitude"].astype(float).to_numpy())
    y = work["class_code"].astype(str).to_numpy()

    candidates: list[tuple[str, float]] = []
    for row in ok_ranges:
        candidates.append((f"class_{row['class_code']}_{row['class_name']}", float(row["chosen_range_m"])))
    candidates.extend(
        [
            ("min_ok", float(np.min(range_values))),
            ("q25_ok_selected", selected_distance),
            ("median_ok", float(np.median(range_values))),
            ("q75_ok", float(np.quantile(range_values, 0.75))),
            ("max_ok", float(np.max(range_values))),
        ]
    )

    seen: set[tuple[str, float]] = set()
    rows: list[dict[str, Any]] = []
    for label, distance in candidates:
        key = (label, round(distance, 6))
        if key in seen:
            continue
        seen.add(key)
        pre = spatial_precheck(coords, y, distance)
        rows.append(
            {
                "timestamp_utc": timestamp,
                "candidate": label,
                "selection_status": "SELECTED" if label == "q25_ok_selected" else "NOT_SELECTED",
                **pre,
            }
        )

    fields = [
        "timestamp_utc",
        "candidate",
        "selection_status",
        "distance_m",
        "distance_km",
        "available_spatial_blocks",
        "required_spatial_blocks",
        "all_folds_nonempty",
        "min_train_count_after_buffer",
        "min_test_count",
        "fold_train_classes",
        "fold_test_classes",
        "fold_train_test_buffered",
        "reason",
    ]
    csv_path = OUT_DIR / "block_distance_practical_rule_candidates_20260612.csv"
    write_csv(csv_path, rows, fields)

    selected_row = next(row for row in rows if row["selection_status"] == "SELECTED")
    practical_summary = {
        "timestamp_utc": timestamp,
        "status": "OK" if selected_row["all_folds_nonempty"] else "SKIPPED",
        "method": "one_vs_rest_indicator_empirical_variogram_practical_q25_rule",
        "source_indicator_summary": str(INDICATOR_SUMMARY.relative_to(ROOT)).replace("//", "/"),
        "source_indicator_summary_sha256": sha256_file(INDICATOR_SUMMARY),
        "reference_file": str(REF_FILE.relative_to(ROOT)).replace("//", "/"),
        "reference_sha256": sha256_file(REF_FILE),
        "verified_rows": int(len(work)),
        "random_seed": SEED,
        "block_distance_rule": "q25_of_ok_one_vs_rest_indicator_ranges",
        "selection_rationale": "Use the 25th percentile of OK class-specific one-vs-rest indicator ranges. This remains indicator-derived while reducing sensitivity to very broad regional class ranges that make the configured spatial validation design infeasible. The rule uses only reference geometry and class-specific variogram diagnostics, not model accuracy.",
        "suggested_block_distance_m": selected_distance,
        "suggested_block_distance_km": selected_distance / 1000.0,
        "spatial_precheck": selected_row,
        "candidate_table": str(csv_path.relative_to(ROOT)).replace("//", "/"),
        "requires_full_spatial_rerun_before_manuscript_tables_can_use_this_distance": True,
    }
    json_path = OUT_DIR / "block_distance_practical_rule_summary_20260612.json"
    json_path.write_text(json.dumps(practical_summary, indent=2, ensure_ascii=False) + "/n", encoding="utf-8")

    md = [
        "# Practical Indicator Block-Distance Rule",
        "",
        f"Timestamp UTC: `{timestamp}`",
        "",
        "## Rule",
        "",
        "Selected rule: `q25_of_ok_one_vs_rest_indicator_ranges`.",
        "",
        "This uses the 25th percentile of class-specific one-vs-rest indicator variogram ranges. It remains derived from indicator variograms, avoids treating nominal `class_code` as a continuous variable, and reduces sensitivity to very broad regional class ranges that make the configured spatial validation design infeasible.",
        "",
        "The rule is based only on reference geometry and indicator diagnostics, not on model accuracy.",
        "",
        "## Selected Distance",
        "",
        f"- Distance: `{selected_distance}` m (`{selected_distance / 1000.0}` km)",
        f"- Available spatial blocks: `{selected_row['available_spatial_blocks']}`",
        f"- Required spatial blocks: `{selected_row['required_spatial_blocks']}`",
        f"- All folds nonempty after buffering: `{selected_row['all_folds_nonempty']}`",
        f"- Minimum training count after buffering: `{selected_row['min_train_count_after_buffer']}`",
        f"- Minimum test count: `{selected_row['min_test_count']}`",
        "",
        "## Candidate Audit",
        "",
        f"Candidate precheck table: `{csv_path.relative_to(ROOT).as_posix()}`",
        "",
        "## Submission Consequence",
        "",
        "This decision does not alter manuscript tables by itself. The pipeline must be rerun with this decision JSON as the block-distance source, and manuscript tables/figures may only be updated from the resulting CSV/JSON outputs.",
    ]
    md_path = OUT_DIR / "block_distance_practical_rule_20260612.md"
    md_path.write_text("/n".join(md) + "/n", encoding="utf-8")
    print(json.dumps({k: practical_summary[k] for k in ["status", "block_distance_rule", "suggested_block_distance_m", "suggested_block_distance_km", "spatial_precheck"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
