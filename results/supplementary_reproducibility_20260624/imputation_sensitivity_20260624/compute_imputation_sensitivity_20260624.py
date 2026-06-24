#!/usr/bin/env python
"""Complete-case sensitivity for the IJRS missing-feature policy.

This script compares the primary median-imputed RandomForest table-3 results
against a complete-case rerun that drops samples containing the configured
missing-feature sentinel for each stack. It writes explicit SKIPPED/ERROR rows
instead of substituting values when a fold cannot be evaluated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold


TAG = "20260624"
MODEL_NAME = "RandomForest"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def project_lonlat_to_meters(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 110_574.0
    return np.column_stack([x, y])


def within_distance_mask(all_coords: np.ndarray, query_coords: np.ndarray, distance: float) -> np.ndarray:
    if len(all_coords) == 0 or len(query_coords) == 0:
        return np.zeros(len(all_coords), dtype=bool)
    tree = cKDTree(all_coords)
    query_tree = cKDTree(query_coords)
    pairs = tree.query_ball_tree(query_tree, distance)
    return np.array([len(p) > 0 for p in pairs], dtype=bool)


def leakage_assertion(train_coords: np.ndarray, test_coords: np.ndarray, distance: float) -> tuple[bool, float | str]:
    if len(train_coords) == 0 or len(test_coords) == 0:
        return False, ""
    tree = cKDTree(train_coords)
    dists, _ = tree.query(test_coords, k=1)
    min_dist = float(np.min(dists))
    return bool(np.all(dists >= distance)), min_dist


def spatial_folds(coords: np.ndarray, block_distance_m: float, k: int, seed: int) -> tuple[list[tuple[np.ndarray, np.ndarray, str]], list[dict[str, Any]]]:
    cells_x = np.floor(coords[:, 0] / block_distance_m).astype(int)
    cells_y = np.floor(coords[:, 1] / block_distance_m).astype(int)
    cell_ids = np.array([f"{x}:{y}" for x, y in zip(cells_x, cells_y)])
    unique_cells = np.unique(cell_ids)
    if len(unique_cells) < k:
        reason = f"Only {len(unique_cells)} spatial blocks are available for k_folds={k}."
        return [], [{
            "status": "SKIPPED",
            "reason": reason,
            "fold": "",
            "train_count_original": "",
            "test_count_original": "",
            "buffered_out_count": "",
            "block_distance_m": block_distance_m,
            "minimum_train_test_distance_m": "",
            "zero_leakage_assertion": "",
            "available_spatial_blocks": int(len(unique_cells)),
            "required_spatial_blocks": k,
        }]
    rng = np.random.default_rng(seed)
    shuffled = unique_cells.copy()
    rng.shuffle(shuffled)
    cell_to_fold = {cell: idx % k for idx, cell in enumerate(shuffled)}
    folds: list[tuple[np.ndarray, np.ndarray, str]] = []
    audit_rows: list[dict[str, Any]] = []
    for fold_idx in range(k):
        test_mask = np.array([cell_to_fold[cell] == fold_idx for cell in cell_ids])
        near_test = within_distance_mask(coords, coords[test_mask], block_distance_m)
        train_mask = (~test_mask) & (~near_test)
        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        leakage_ok, min_dist = leakage_assertion(coords[train_idx], coords[test_idx], block_distance_m)
        empty_partition = len(train_idx) == 0 or len(test_idx) == 0
        status = "ERROR" if not leakage_ok else ("SKIPPED" if empty_partition else "OK")
        reason = ""
        if not leakage_ok:
            reason = "test sample lies within block distance of training sample"
        elif empty_partition:
            reason = "Empty train or test partition after spatial buffering."
        audit_rows.append({
            "status": status,
            "reason": reason,
            "fold": str(fold_idx + 1),
            "train_count_original": int(len(train_idx)),
            "test_count_original": int(len(test_idx)),
            "buffered_out_count": int(np.sum((~test_mask) & near_test)),
            "block_distance_m": block_distance_m,
            "minimum_train_test_distance_m": min_dist,
            "zero_leakage_assertion": bool(leakage_ok),
            "available_spatial_blocks": int(len(unique_cells)),
            "required_spatial_blocks": k,
        })
        if leakage_ok and not empty_partition:
            folds.append((train_idx, test_idx, str(fold_idx + 1)))
    return folds, audit_rows


def feature_columns(df: pd.DataFrame, id_col: str) -> list[str]:
    excluded = {id_col}
    return [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]


def row_base(timestamp: str, config_hash: str, input_files: str, seed: int) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "config_hash": config_hash,
        "input_files": input_files,
        "random_seed": seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    repo = Path(args.repo_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = utc_timestamp()
    config_path = repo / "config" / "config_fold3_teacher_vhr_repair_20260613.yaml"
    ref_path = repo / "data" / "reference_samples_verified_622_public.csv"
    table3_path = repo / "results" / "active_q25_rerun" / "table3_accuracy_by_stack_split.csv"
    variogram_path = repo / "results" / "active_q25_rerun" / "variogram_choice.json"

    config_hash = sha256_file(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    seed = int(config.get("seeds", {}).get("global", 42))
    k_folds = int(config.get("cv", {}).get("k_folds", 4))
    min_class_count = int(config.get("min_class_count", 30))
    sentinel = config.get("preprocessing", {}).get("missing_feature_sentinel", -9999)
    sentinel_value = float(sentinel)
    rf_params = dict(config.get("random_forest", {}))
    rf_params["random_state"] = seed

    with variogram_path.open("r", encoding="utf-8") as f:
        variogram = json.load(f)
    block_distance_m = float(variogram["chosen_block_distance_m"])

    ref = pd.read_csv(ref_path)
    id_col = "sample_id"
    class_col = "class_code"
    lon_col = "longitude"
    lat_col = "latitude"

    table3 = pd.read_csv(table3_path)
    table3 = table3[(table3["model"] == MODEL_NAME) & (table3["status"] == "OK")].copy()

    fold_fields = [
        "timestamp", "config_hash", "input_files", "random_seed", "status", "reason",
        "stack", "stack_label", "model", "split", "fold",
        "original_policy", "sensitivity_policy", "missing_sentinel",
        "rows_with_missing_before_policy", "sentinel_cells_before_policy",
        "train_count_original", "test_count_original",
        "train_count_complete_case", "test_count_complete_case",
        "train_rows_dropped_missing", "test_rows_dropped_missing",
        "original_table3_oa", "original_table3_macro_f1",
        "complete_case_oa", "complete_case_macro_f1",
        "delta_oa_complete_minus_original", "delta_macro_f1_complete_minus_original",
        "sklearn_version", "numpy_version", "pandas_version",
    ]
    summary_fields = [
        "timestamp", "config_hash", "input_files", "random_seed", "status", "reason",
        "stack", "stack_label", "model", "split",
        "rows_with_missing_before_policy", "sentinel_cells_before_policy",
        "ok_folds", "skipped_or_error_folds",
        "total_test_rows_original", "total_test_rows_complete_case", "total_test_rows_dropped_missing",
        "original_table3_mean_oa", "complete_case_mean_oa", "delta_mean_oa_complete_minus_original",
        "original_table3_mean_macro_f1", "complete_case_mean_macro_f1", "delta_mean_macro_f1_complete_minus_original",
    ]
    leakage_fields = [
        "timestamp", "config_hash", "input_files", "random_seed", "status", "reason",
        "stack", "fold", "train_count_original", "test_count_original",
        "train_count_complete_case", "test_count_complete_case",
        "buffered_out_count", "block_distance_m", "minimum_train_test_distance_m",
        "zero_leakage_assertion", "available_spatial_blocks", "required_spatial_blocks",
    ]
    class_count_fields = [
        "timestamp", "config_hash", "input_files", "random_seed", "status", "reason",
        "stack", "class_code", "complete_case_sample_count", "min_class_count",
    ]

    fold_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    class_count_rows: list[dict[str, Any]] = []

    stack_cfgs = config.get("feature_stacks", {})
    versions = {
        "sklearn_version": __import__("sklearn").__version__,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
    }

    for stack, stack_cfg in stack_cfgs.items():
        feature_path = repo / stack_cfg["file"]
        feat = pd.read_csv(feature_path)
        cols = feature_columns(feat, id_col)
        input_files = ";".join([
            str(ref_path.relative_to(repo)),
            str(feature_path.relative_to(repo)),
            str(config_path.relative_to(repo)),
            str(table3_path.relative_to(repo)),
            str(variogram_path.relative_to(repo)),
        ])
        merged = ref.merge(feat[[id_col] + cols], on=id_col, how="inner")
        if len(merged) != len(ref):
            base = row_base(timestamp, config_hash, input_files, seed)
            base.update({
                "status": "ERROR",
                "reason": f"Feature stack matched {len(merged)} rows but reference has {len(ref)} rows.",
                "stack": stack,
                "stack_label": stack_cfg.get("label", ""),
                "model": MODEL_NAME,
                "split": "",
                "fold": "",
            })
            fold_rows.append(base)
            print(f"ERROR {stack}: {base['reason']}")
            continue

        X_all = merged[cols].apply(pd.to_numeric, errors="coerce")
        missing_mask = X_all.isna().any(axis=1) | X_all.eq(sentinel_value).any(axis=1)
        rows_missing = int(missing_mask.sum())
        sentinel_cells = int(X_all.eq(sentinel_value).sum().sum())
        valid_mask = ~missing_mask.to_numpy()
        y = merged[class_col].astype(int).to_numpy()
        coords = project_lonlat_to_meters(
            merged[lon_col].astype(float).to_numpy(),
            merged[lat_col].astype(float).to_numpy(),
        )

        counts = pd.Series(y[valid_mask]).value_counts().sort_index()
        for class_code, count in counts.items():
            row = row_base(timestamp, config_hash, input_files, seed)
            row.update({
                "status": "OK" if int(count) >= min_class_count else "LOW_COUNT_BELOW_MIN_CLASS_COUNT",
                "reason": "" if int(count) >= min_class_count else f"class count below min_class_count={min_class_count}",
                "stack": stack,
                "class_code": int(class_code),
                "complete_case_sample_count": int(count),
                "min_class_count": min_class_count,
            })
            class_count_rows.append(row)

        random = StratifiedKFold(n_splits=k_folds, shuffle=True, random_state=seed)
        random_folds = [(train, test, str(i + 1)) for i, (train, test) in enumerate(random.split(np.zeros(len(y)), y))]
        spatial, spatial_audit = spatial_folds(coords, block_distance_m, k_folds, seed)

        for audit in spatial_audit:
            complete_train = ""
            complete_test = ""
            if audit["status"] == "OK":
                fold_label = str(audit["fold"])
                match = [f for f in spatial if f[2] == fold_label]
                if match:
                    train_idx, test_idx, _ = match[0]
                    complete_train = int(np.sum(valid_mask[train_idx]))
                    complete_test = int(np.sum(valid_mask[test_idx]))
                    ok, min_dist = leakage_assertion(coords[train_idx][valid_mask[train_idx]], coords[test_idx][valid_mask[test_idx]], block_distance_m)
                    audit = dict(audit)
                    audit["zero_leakage_assertion"] = bool(ok)
                    audit["minimum_train_test_distance_m"] = min_dist
            leak_row = row_base(timestamp, config_hash, input_files, seed)
            leak_row.update(audit)
            leak_row.update({
                "stack": stack,
                "train_count_complete_case": complete_train,
                "test_count_complete_case": complete_test,
            })
            leakage_rows.append(leak_row)

        split_folds = {"random": random_folds, "spatial": spatial}
        for split, folds in split_folds.items():
            for train_idx, test_idx, fold_label in folds:
                base = row_base(timestamp, config_hash, input_files, seed)
                base.update({
                    "stack": stack,
                    "stack_label": stack_cfg.get("label", ""),
                    "model": MODEL_NAME,
                    "split": split,
                    "fold": fold_label,
                    "original_policy": "sentinel_to_nan_then_median_impute",
                    "sensitivity_policy": "complete_case_drop_rows_with_nan_or_sentinel",
                    "missing_sentinel": sentinel,
                    "rows_with_missing_before_policy": rows_missing,
                    "sentinel_cells_before_policy": sentinel_cells,
                    "train_count_original": int(len(train_idx)),
                    "test_count_original": int(len(test_idx)),
                    "train_count_complete_case": int(np.sum(valid_mask[train_idx])),
                    "test_count_complete_case": int(np.sum(valid_mask[test_idx])),
                    "train_rows_dropped_missing": int(np.sum(~valid_mask[train_idx])),
                    "test_rows_dropped_missing": int(np.sum(~valid_mask[test_idx])),
                    **versions,
                })
                baseline = table3[
                    (table3["stack"] == stack)
                    & (table3["split"] == split)
                    & (table3["fold"].astype(str) == str(fold_label))
                ]
                if baseline.empty:
                    row = dict(base)
                    row.update({"status": "ERROR", "reason": "No matching primary table3 row.", "original_table3_oa": "", "original_table3_macro_f1": ""})
                    fold_rows.append(row)
                    print(f"ERROR {stack} {split} fold {fold_label}: no table3 row")
                    continue

                row = dict(base)
                row["original_table3_oa"] = float(baseline.iloc[0]["oa"])
                row["original_table3_macro_f1"] = float(baseline.iloc[0]["macro_f1"])

                train_cc = train_idx[valid_mask[train_idx]]
                test_cc = test_idx[valid_mask[test_idx]]
                if len(train_cc) == 0 or len(test_cc) == 0:
                    row.update({
                        "status": "SKIPPED",
                        "reason": "Empty train or test partition after complete-case filtering.",
                        "complete_case_oa": "",
                        "complete_case_macro_f1": "",
                        "delta_oa_complete_minus_original": "",
                        "delta_macro_f1_complete_minus_original": "",
                    })
                    fold_rows.append(row)
                    print(f"SKIPPED {stack} {split} fold {fold_label}: empty partition")
                    continue
                if len(np.unique(y[train_cc])) < 2:
                    row.update({
                        "status": "SKIPPED",
                        "reason": "Fewer than two training classes after complete-case filtering.",
                        "complete_case_oa": "",
                        "complete_case_macro_f1": "",
                        "delta_oa_complete_minus_original": "",
                        "delta_macro_f1_complete_minus_original": "",
                    })
                    fold_rows.append(row)
                    print(f"SKIPPED {stack} {split} fold {fold_label}: fewer than two training classes")
                    continue

                clf = RandomForestClassifier(**rf_params)
                X_train = X_all.iloc[train_cc].to_numpy(dtype=float)
                X_test = X_all.iloc[test_cc].to_numpy(dtype=float)
                y_train = y[train_cc]
                y_test = y[test_cc]
                clf.fit(X_train, y_train)
                pred = clf.predict(X_test)
                cc_oa = float(accuracy_score(y_test, pred))
                cc_macro = float(f1_score(y_test, pred, average="macro"))
                reason = ""
                if rows_missing == 0:
                    reason = "No sentinel/NaN feature rows in this stack; complete-case rerun is a no-missing reference."
                row.update({
                    "status": "OK",
                    "reason": reason,
                    "complete_case_oa": cc_oa,
                    "complete_case_macro_f1": cc_macro,
                    "delta_oa_complete_minus_original": cc_oa - row["original_table3_oa"],
                    "delta_macro_f1_complete_minus_original": cc_macro - row["original_table3_macro_f1"],
                })
                fold_rows.append(row)
                print(f"OK {stack} {split} fold {fold_label}: OA {cc_oa:.6f}, macro-F1 {cc_macro:.6f}")

            split_rows = [r for r in fold_rows if r.get("stack") == stack and r.get("split") == split]
            ok_rows = [r for r in split_rows if r.get("status") == "OK"]
            summary = row_base(timestamp, config_hash, input_files, seed)
            summary.update({
                "stack": stack,
                "stack_label": stack_cfg.get("label", ""),
                "model": MODEL_NAME,
                "split": split,
                "rows_with_missing_before_policy": rows_missing,
                "sentinel_cells_before_policy": sentinel_cells,
                "ok_folds": len(ok_rows),
                "skipped_or_error_folds": len(split_rows) - len(ok_rows),
                "total_test_rows_original": int(sum(int(r.get("test_count_original", 0) or 0) for r in split_rows)),
                "total_test_rows_complete_case": int(sum(int(r.get("test_count_complete_case", 0) or 0) for r in split_rows)),
                "total_test_rows_dropped_missing": int(sum(int(r.get("test_rows_dropped_missing", 0) or 0) for r in split_rows)),
            })
            if len(ok_rows) != len(folds):
                summary.update({
                    "status": "SKIPPED",
                    "reason": "At least one fold was not evaluable; see fold metrics.",
                })
            else:
                summary.update({"status": "OK", "reason": ""})
            if ok_rows:
                orig_oa = float(np.mean([float(r["original_table3_oa"]) for r in ok_rows]))
                cc_oa = float(np.mean([float(r["complete_case_oa"]) for r in ok_rows]))
                orig_macro = float(np.mean([float(r["original_table3_macro_f1"]) for r in ok_rows]))
                cc_macro = float(np.mean([float(r["complete_case_macro_f1"]) for r in ok_rows]))
                summary.update({
                    "original_table3_mean_oa": orig_oa,
                    "complete_case_mean_oa": cc_oa,
                    "delta_mean_oa_complete_minus_original": cc_oa - orig_oa,
                    "original_table3_mean_macro_f1": orig_macro,
                    "complete_case_mean_macro_f1": cc_macro,
                    "delta_mean_macro_f1_complete_minus_original": cc_macro - orig_macro,
                })
            summary_rows.append(summary)

    write_csv(out_dir / f"imputation_sensitivity_fold_metrics_{TAG}.csv", fold_rows, fold_fields)
    write_csv(out_dir / f"imputation_sensitivity_summary_{TAG}.csv", summary_rows, summary_fields)
    write_csv(out_dir / f"imputation_sensitivity_spatial_leakage_audit_{TAG}.csv", leakage_rows, leakage_fields)
    write_csv(out_dir / f"imputation_sensitivity_class_counts_{TAG}.csv", class_count_rows, class_count_fields)

    provenance = {
        "timestamp": timestamp,
        "status": "OK" if all(r.get("status") == "OK" for r in summary_rows) else "CHECK_ROWS",
        "script": str(Path(__file__).resolve()),
        "repo_root": str(repo.resolve()),
        "out_dir": str(out_dir.resolve()),
        "config_path": str(config_path.relative_to(repo)),
        "config_hash": config_hash,
        "reference_path": str(ref_path.relative_to(repo)),
        "reference_sha256": sha256_file(ref_path),
        "table3_path": str(table3_path.relative_to(repo)),
        "table3_sha256": sha256_file(table3_path),
        "variogram_path": str(variogram_path.relative_to(repo)),
        "variogram_sha256": sha256_file(variogram_path),
        "random_seed": seed,
        "k_folds": k_folds,
        "missing_feature_sentinel": sentinel,
        "sensitivity_policy": "complete_case_drop_rows_with_nan_or_sentinel",
        "model": MODEL_NAME,
        "random_forest_params": rf_params,
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "library_versions": versions,
    }
    (out_dir / f"imputation_sensitivity_provenance_{TAG}.json").write_text(
        json.dumps(provenance, indent=2),
        encoding="utf-8",
    )

    md_lines = [
        "# Complete-case missing-feature sensitivity (20260624)",
        "",
        "This diagnostic compares the primary `sentinel_to_nan_then_median_impute` policy with a complete-case rerun for the primary RandomForest model.",
        "",
        "Rows with `NaN` or the configured missing-feature sentinel were removed within each feature stack before training and testing. The original table-3 fold means are retained as the median-imputed reference.",
        "",
        "## Summary",
        "",
        "| Stack | Split | Sentinel rows | Test rows dropped | Original OA | Complete-case OA | Delta OA | Original macro-F1 | Complete-case macro-F1 | Delta macro-F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        def fmt(value: Any) -> str:
            if value == "" or pd.isna(value):
                return ""
            if isinstance(value, (int, np.integer)):
                return str(int(value))
            try:
                return f"{float(value):.6f}"
            except Exception:
                return str(value)

        md_lines.append(
            "| {stack} | {split} | {sentinel_rows} | {test_drop} | {orig_oa} | {cc_oa} | {delta_oa} | {orig_f1} | {cc_f1} | {delta_f1} |".format(
                stack=row["stack"],
                split=row["split"],
                sentinel_rows=row["rows_with_missing_before_policy"],
                test_drop=row["total_test_rows_dropped_missing"],
                orig_oa=fmt(row.get("original_table3_mean_oa", "")),
                cc_oa=fmt(row.get("complete_case_mean_oa", "")),
                delta_oa=fmt(row.get("delta_mean_oa_complete_minus_original", "")),
                orig_f1=fmt(row.get("original_table3_mean_macro_f1", "")),
                cc_f1=fmt(row.get("complete_case_mean_macro_f1", "")),
                delta_f1=fmt(row.get("delta_mean_macro_f1_complete_minus_original", "")),
            )
        )
    md_lines.extend([
        "",
        "Files written:",
        "",
        f"- `imputation_sensitivity_fold_metrics_{TAG}.csv`",
        f"- `imputation_sensitivity_summary_{TAG}.csv`",
        f"- `imputation_sensitivity_spatial_leakage_audit_{TAG}.csv`",
        f"- `imputation_sensitivity_class_counts_{TAG}.csv`",
        f"- `imputation_sensitivity_provenance_{TAG}.json`",
        "",
        "B2 contains no sentinel/NaN feature rows, so its complete-case rerun is a no-missing reference rather than a stress test of imputation.",
    ])
    (out_dir / f"IMPUTATION_SENSITIVITY_{TAG}.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"WROTE {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
