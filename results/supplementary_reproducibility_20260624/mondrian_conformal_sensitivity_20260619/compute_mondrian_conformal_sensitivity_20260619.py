from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

import run_reproducible_pipeline as pipe


BASE_COLUMNS = ["timestamp", "config_hash", "input_files", "random_seed", "status", "reason"]


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def parse_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def class_count_string(labels: np.ndarray) -> str:
    if len(labels) == 0:
        return ""
    counts = pd.Series(labels).value_counts().sort_index()
    return "|".join(f"{label}:{int(count)}" for label, count in counts.items())


def union_fieldnames(rows: Sequence[Dict[str, Any]], preferred: Sequence[str]) -> List[str]:
    seen = set(preferred)
    fields = list(preferred)
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    return fields


def retained_classes_from_calibration(y_cal: np.ndarray, min_count: int) -> Tuple[List[Any], List[Any], Dict[Any, int]]:
    counts = pd.Series(y_cal).value_counts().sort_index()
    retained = [label for label, count in counts.items() if int(count) >= min_count]
    dropped = [label for label, count in counts.items() if int(count) < min_count]
    return retained, dropped, {label: int(count) for label, count in counts.items()}


def classwise_qhats(
    classes: np.ndarray,
    cal_proba: np.ndarray,
    y_cal: np.ndarray,
    retained: Sequence[Any],
    alpha: float,
) -> Dict[Any, float]:
    class_to_pos = {label: pos for pos, label in enumerate(classes)}
    qhats: Dict[Any, float] = {}
    for label in retained:
        pos = class_to_pos.get(label)
        if pos is None:
            raise RuntimeError(f"Retained class {label} is absent from fitted model classes.")
        mask = y_cal == label
        scores = 1.0 - cal_proba[mask, pos]
        qhats[label] = pipe.conformal_quantile(scores, alpha)
    return qhats


def mondrian_prediction_sets(
    classes: np.ndarray,
    test_proba: np.ndarray,
    qhats: Dict[Any, float],
) -> Tuple[List[List[Any]], List[int]]:
    class_to_pos = {label: pos for pos, label in enumerate(classes)}
    ordered_labels = sorted(qhats.keys())
    pred_sets: List[List[Any]] = []
    sizes: List[int] = []
    for row in test_proba:
        labels: List[Any] = []
        for label in ordered_labels:
            pos = class_to_pos.get(label)
            if pos is None:
                continue
            if 1.0 - float(row[pos]) <= float(qhats[label]):
                labels.append(label)
        pred_sets.append(labels)
        sizes.append(len(labels))
    return pred_sets, sizes


def load_reference(ctx: pipe.RunContext) -> pd.DataFrame:
    ref_cfg = ctx.config.get("reference_samples", {})
    ref_path = ctx.root / ref_cfg.get("file", "data/reference_samples.csv")
    verified_col = ref_cfg.get("verified_column", "verified")
    if not ref_path.exists():
        raise RuntimeError(f"Missing reference file: {ref_path}")
    ref = pd.read_csv(ref_path)
    if verified_col not in ref.columns:
        raise RuntimeError(f"Reference file lacks verified column: {verified_col}")
    ref = ref[parse_bool_series(ref[verified_col])].copy()
    if ref.empty:
        raise RuntimeError("No verified reference rows after filtering.")
    return ref


def build_split_audit_row(
    ctx: pipe.RunContext,
    input_files: List[Path],
    stack: str,
    model: str,
    split: str,
    train_idx: np.ndarray,
    cal_idx: np.ndarray,
    test_idx: np.ndarray,
    y: np.ndarray,
    block_distance: float | None,
) -> Dict[str, Any]:
    row = ctx.provenance(input_files)
    row.update(
        {
            "status": "OK",
            "reason": "",
            "stack": stack,
            "model": model,
            "split": split,
            "train_count": int(len(train_idx)),
            "calibration_count": int(len(cal_idx)),
            "test_count": int(len(test_idx)),
            "block_distance_m": block_distance if block_distance is not None else "",
            "train_class_counts": class_count_string(y[train_idx]),
            "calibration_class_counts": class_count_string(y[cal_idx]),
            "test_class_counts": class_count_string(y[test_idx]),
        }
    )
    return row


def compute(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config_path = (root / args.config).resolve()
    variogram_choice_path = (root / args.variogram_choice).resolve()
    global_conformal_path = (root / args.global_conformal_table).resolve()
    results_dir = (root / args.results_dir).resolve()
    figures_dir = results_dir / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    config = pipe.read_config(config_path)
    config_hash = pipe.sha256_file(config_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    seed = int(config.get("seeds", {}).get("global", 42))
    ctx = pipe.RunContext(
        root=root,
        config_path=config_path,
        config=config,
        config_hash=config_hash,
        timestamp=timestamp,
        seed=seed,
        results_dir=results_dir,
        figures_dir=figures_dir,
    )
    alpha = float(config.get("cv", {}).get("conformal_alpha", 0.10))
    target_coverage = 1.0 - alpha
    min_count = int(config.get("min_class_count", 30))
    policy = str(config.get("low_count_policy", "drop"))
    if policy != "drop":
        raise RuntimeError("Only low_count_policy=drop is implemented for this sensitivity audit.")

    variogram_choice = json.loads(variogram_choice_path.read_text(encoding="utf-8"))
    if variogram_choice.get("status") != "OK":
        raise RuntimeError("Variogram choice is not OK.")
    block_distance = float(variogram_choice["chosen_block_distance_m"])

    ref_cfg = config.get("reference_samples", {})
    ref_path = root / ref_cfg.get("file", "data/reference_samples.csv")
    id_col = ref_cfg.get("id_column", "sample_id")
    code_col = ref_cfg.get("class_code_column", "class_code")
    name_col = ref_cfg.get("class_name_column", "class_name")
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")

    ref = load_reference(ctx)
    filtered_ref = pipe.apply_global_low_count_policy(ctx, ref, str(ref_path))
    if filtered_ref.empty:
        raise RuntimeError("All reference rows were removed by global low-count policy.")

    summary_rows: List[Dict[str, Any]] = []
    per_class_rows: List[Dict[str, Any]] = []
    point_rows: List[Dict[str, Any]] = []
    threshold_rows: List[Dict[str, Any]] = []
    split_audit_rows: List[Dict[str, Any]] = []
    class_policy_rows: List[Dict[str, Any]] = []

    for stack, stack_cfg in config.get("feature_stacks", {}).items():
        feature_path = root / stack_cfg.get("file", f"data/features/{stack}.csv")
        merged, reason = pipe.read_feature_stack(ctx, stack, stack_cfg, filtered_ref)
        if merged is None:
            for model in ["RandomForest", "XGBoost"]:
                for split in ["random", "spatial"]:
                    row = ctx.provenance([ref_path, feature_path, variogram_choice_path])
                    row.update(
                        {
                            "status": "ERROR",
                            "reason": reason,
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model,
                            "split": split,
                            "alpha": alpha,
                            "target_coverage": target_coverage,
                        }
                    )
                    summary_rows.append(row)
            continue

        features = list(merged.attrs.get("feature_columns", [])) or pipe.feature_columns(merged, id_col)
        X = merged[features].to_numpy(dtype=float)
        y = merged[code_col].to_numpy()
        coords = pipe.project_lonlat_to_meters(
            merged[lon_col].astype(float).to_numpy(),
            merged[lat_col].astype(float).to_numpy(),
        )
        class_name_map = {}
        if name_col in merged.columns:
            class_name_map = {
                code: str(name)
                for code, name in zip(merged[code_col].to_numpy(), merged[name_col].to_numpy())
            }

        splitters = {
            "random": pipe.conformal_random_split(ctx, y),
            "spatial": pipe.conformal_spatial_split(ctx, coords, block_distance, y=y, min_count=min_count),
        }

        for model_name in ["RandomForest", "XGBoost"]:
            for split_name, parts in splitters.items():
                input_files = [ref_path, feature_path, variogram_choice_path]
                if parts is None:
                    row = ctx.provenance(input_files)
                    row.update(
                        {
                            "status": "SKIPPED",
                            "reason": f"No valid {split_name} train/calibration/test split.",
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model_name,
                            "split": split_name,
                            "alpha": alpha,
                            "target_coverage": target_coverage,
                        }
                    )
                    summary_rows.append(row)
                    continue
                train_idx, cal_idx, test_idx = parts
                split_audit_rows.append(
                    build_split_audit_row(
                        ctx,
                        input_files,
                        stack,
                        model_name,
                        split_name,
                        train_idx,
                        cal_idx,
                        test_idx,
                        y,
                        block_distance if split_name == "spatial" else None,
                    )
                )
                retained, dropped, cal_counts = retained_classes_from_calibration(y[cal_idx], min_count)
                for code in dropped:
                    drow = ctx.provenance(input_files)
                    drow.update(
                        {
                            "status": "OK",
                            "reason": f"calibration class has fewer samples than min_class_count={min_count}",
                            "method": "mondrian_class_conditional",
                            "scope": f"mondrian_conformal_{split_name}",
                            "policy": policy,
                            "stack": stack,
                            "model": model_name,
                            "class_code": code,
                            "class_name": class_name_map.get(code, ""),
                            "sample_count": cal_counts.get(code, 0),
                        }
                    )
                    class_policy_rows.append(drow)
                if not retained:
                    row = ctx.provenance(input_files)
                    row.update(
                        {
                            "status": "SKIPPED",
                            "reason": "No retained classes after min_class_count policy.",
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model_name,
                            "split": split_name,
                            "alpha": alpha,
                            "target_coverage": target_coverage,
                        }
                    )
                    summary_rows.append(row)
                    continue

                keep_train = np.isin(y[train_idx], retained)
                keep_cal = np.isin(y[cal_idx], retained)
                keep_test = np.isin(y[test_idx], retained)
                train_use = train_idx[keep_train]
                cal_use = cal_idx[keep_cal]
                test_use = test_idx[keep_test]
                missing_from_train = sorted(set(retained) - set(y[train_use]))
                missing_from_test = sorted(set(retained) - set(y[test_use]))
                if len(train_use) == 0 or len(cal_use) == 0 or len(test_use) == 0 or missing_from_train or missing_from_test:
                    row = ctx.provenance(input_files)
                    row.update(
                        {
                            "status": "SKIPPED",
                            "reason": (
                                "Insufficient train/calibration/test samples after min_class_count policy; "
                                f"missing_from_train={missing_from_train}; missing_from_test={missing_from_test}"
                            ),
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model_name,
                            "split": split_name,
                            "alpha": alpha,
                            "target_coverage": target_coverage,
                            "classes_retained": "|".join(str(x) for x in sorted(retained)),
                        }
                    )
                    summary_rows.append(row)
                    continue

                try:
                    classes, cal_proba, test_proba = pipe.fit_predict_proba(
                        ctx,
                        model_name,
                        X[train_use],
                        y[train_use],
                        X[cal_use],
                        X[test_use],
                    )
                    qhats = classwise_qhats(classes, cal_proba, y[cal_use], retained, alpha)
                    pred_sets, sizes = mondrian_prediction_sets(classes, test_proba, qhats)
                except Exception as exc:
                    row = ctx.provenance(input_files)
                    row.update(
                        {
                            "status": "ERROR",
                            "reason": f"Mondrian conformal fit/evaluation failed: {type(exc).__name__}: {exc}",
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model_name,
                            "split": split_name,
                            "alpha": alpha,
                            "target_coverage": target_coverage,
                        }
                    )
                    summary_rows.append(row)
                    continue

                covered = np.array([label in pred_set for label, pred_set in zip(y[test_use], pred_sets)], dtype=bool)
                sizes_arr = np.array(sizes, dtype=float)
                qhat_values = np.array([float(qhats[label]) for label in retained], dtype=float)
                retained_sorted = sorted(retained)
                row = ctx.provenance(input_files)
                row.update(
                    {
                        "status": "OK",
                        "reason": "",
                        "method": "mondrian_class_conditional",
                        "stack": stack,
                        "stack_label": stack_cfg.get("label", ""),
                        "model": model_name,
                        "split": split_name,
                        "alpha": alpha,
                        "target_coverage": target_coverage,
                        "empirical_coverage": float(np.mean(covered)),
                        "average_set_size": float(np.mean(sizes_arr)),
                        "median_set_size": float(np.median(sizes_arr)),
                        "max_set_size": int(np.max(sizes_arr)),
                        "n_calibration": int(len(cal_use)),
                        "n_test": int(len(test_use)),
                        "classes_retained": "|".join(str(x) for x in retained_sorted),
                        "classes_dropped": "|".join(str(x) for x in sorted(dropped)),
                        "min_calibration_class_count": min(cal_counts[label] for label in retained),
                        "max_calibration_class_count": max(cal_counts[label] for label in retained),
                        "min_qhat": float(np.min(qhat_values)),
                        "max_qhat": float(np.max(qhat_values)),
                        "mean_qhat": float(np.mean(qhat_values)),
                    }
                )
                summary_rows.append(row)

                for label in retained_sorted:
                    label_mask_cal = y[cal_use] == label
                    label_mask_test = y[test_use] == label
                    class_covered = covered[label_mask_test]
                    class_sizes = sizes_arr[label_mask_test]
                    pcrow = ctx.provenance(input_files)
                    pcrow.update(
                        {
                            "status": "OK" if int(np.sum(label_mask_test)) > 0 else "SKIPPED",
                            "reason": "" if int(np.sum(label_mask_test)) > 0 else "No retained test samples for class.",
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model_name,
                            "split": split_name,
                            "class_code": label,
                            "class_name": class_name_map.get(label, ""),
                            "alpha": alpha,
                            "target_coverage": target_coverage,
                            "qhat": float(qhats[label]),
                            "probability_threshold": float(1.0 - qhats[label]),
                            "n_calibration_class": int(np.sum(label_mask_cal)),
                            "n_test_class": int(np.sum(label_mask_test)),
                            "empirical_coverage_class": float(np.mean(class_covered)) if int(np.sum(label_mask_test)) else "",
                            "average_set_size_for_true_class": float(np.mean(class_sizes)) if int(np.sum(label_mask_test)) else "",
                        }
                    )
                    per_class_rows.append(pcrow)
                    threshold_rows.append(
                        {
                            **ctx.provenance(input_files),
                            "status": "OK",
                            "reason": "",
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "model": model_name,
                            "split": split_name,
                            "class_code": label,
                            "class_name": class_name_map.get(label, ""),
                            "n_calibration_class": int(np.sum(label_mask_cal)),
                            "qhat": float(qhats[label]),
                            "probability_threshold": float(1.0 - qhats[label]),
                        }
                    )

                for pos, sample_idx in enumerate(test_use):
                    prow = ctx.provenance(input_files)
                    pred_set = pred_sets[pos]
                    prow.update(
                        {
                            "status": "OK",
                            "reason": "",
                            "method": "mondrian_class_conditional",
                            "stack": stack,
                            "stack_label": stack_cfg.get("label", ""),
                            "model": model_name,
                            "split": split_name,
                            "sample_id": merged.iloc[sample_idx][id_col],
                            "true_class_code": y[sample_idx],
                            "covered": bool(covered[pos]),
                            "set_size": int(sizes[pos]),
                            "prediction_set": "|".join(str(x) for x in pred_set),
                        }
                    )
                    point_rows.append(prow)

    summary_fields = BASE_COLUMNS + [
        "method",
        "stack",
        "stack_label",
        "model",
        "split",
        "alpha",
        "target_coverage",
        "empirical_coverage",
        "average_set_size",
        "median_set_size",
        "max_set_size",
        "n_calibration",
        "n_test",
        "classes_retained",
        "classes_dropped",
        "min_calibration_class_count",
        "max_calibration_class_count",
        "min_qhat",
        "max_qhat",
        "mean_qhat",
    ]
    write_csv(results_dir / "mondrian_conformal_summary_20260619.csv", summary_fields, summary_rows)

    per_class_fields = BASE_COLUMNS + [
        "method",
        "stack",
        "stack_label",
        "model",
        "split",
        "class_code",
        "class_name",
        "alpha",
        "target_coverage",
        "qhat",
        "probability_threshold",
        "n_calibration_class",
        "n_test_class",
        "empirical_coverage_class",
        "average_set_size_for_true_class",
    ]
    write_csv(results_dir / "mondrian_conformal_per_class_20260619.csv", per_class_fields, per_class_rows)

    threshold_fields = BASE_COLUMNS + [
        "method",
        "stack",
        "model",
        "split",
        "class_code",
        "class_name",
        "n_calibration_class",
        "qhat",
        "probability_threshold",
    ]
    write_csv(results_dir / "mondrian_conformal_thresholds_20260619.csv", threshold_fields, threshold_rows)

    point_fields = BASE_COLUMNS + [
        "method",
        "stack",
        "stack_label",
        "model",
        "split",
        "sample_id",
        "true_class_code",
        "covered",
        "set_size",
        "prediction_set",
    ]
    write_csv(results_dir / "mondrian_conformal_point_sets_20260619.csv", point_fields, point_rows)

    split_fields = BASE_COLUMNS + [
        "stack",
        "model",
        "split",
        "train_count",
        "calibration_count",
        "test_count",
        "block_distance_m",
        "train_class_counts",
        "calibration_class_counts",
        "test_class_counts",
    ]
    write_csv(results_dir / "mondrian_conformal_split_audit_20260619.csv", split_fields, split_audit_rows)

    if class_policy_rows:
        class_policy_fields = BASE_COLUMNS + [
            "method",
            "scope",
            "policy",
            "stack",
            "model",
            "class_code",
            "class_name",
            "sample_count",
        ]
        write_csv(results_dir / "mondrian_conformal_class_policy_20260619.csv", class_policy_fields, class_policy_rows)
    else:
        write_csv(
            results_dir / "mondrian_conformal_class_policy_20260619.csv",
            BASE_COLUMNS + ["method", "scope", "policy", "stack", "model", "class_code", "class_name", "sample_count"],
            [
                {
                    **ctx.provenance([ref_path]),
                    "status": "OK",
                    "reason": "No calibration class below min_class_count in retained Mondrian conformal runs.",
                    "method": "mondrian_class_conditional",
                    "scope": "all_mondrian_conformal_splits",
                    "policy": policy,
                    "stack": "",
                    "model": "",
                    "class_code": "",
                    "class_name": "",
                    "sample_count": "",
                }
            ],
        )

    comparison_rows = build_comparison_rows(
        ctx=ctx,
        global_conformal_path=global_conformal_path,
        mondrian_summary_path=results_dir / "mondrian_conformal_summary_20260619.csv",
    )
    comparison_fields = BASE_COLUMNS + [
        "stack",
        "model",
        "split",
        "global_empirical_coverage",
        "mondrian_empirical_coverage",
        "coverage_delta_mondrian_minus_global",
        "global_average_set_size",
        "mondrian_average_set_size",
        "set_size_delta_mondrian_minus_global",
        "target_coverage",
        "n_calibration",
        "n_test",
    ]
    write_csv(results_dir / "mondrian_vs_global_conformal_comparison_20260619.csv", comparison_fields, comparison_rows)

    if ctx.missing_feature_rows:
        write_csv(
            results_dir / "mondrian_feature_missing_value_policy_audit_20260619.csv",
            union_fieldnames(ctx.missing_feature_rows, BASE_COLUMNS),
            ctx.missing_feature_rows,
        )
    if ctx.status_rows:
        write_csv(
            results_dir / "mondrian_conformal_run_status_20260619.csv",
            union_fieldnames(ctx.status_rows, BASE_COLUMNS),
            ctx.status_rows,
        )

    provenance_payload = {
        "timestamp_utc": timestamp,
        "config_path": str(config_path),
        "config_hash_sha256": config_hash,
        "reference_path": str(ref_path),
        "reference_sha256": pipe.sha256_file(ref_path),
        "variogram_choice_path": str(variogram_choice_path),
        "variogram_choice_sha256": pipe.sha256_file(variogram_choice_path),
        "global_conformal_table_path": str(global_conformal_path),
        "global_conformal_table_sha256": pipe.sha256_file(global_conformal_path) if global_conformal_path.exists() else "",
        "random_seed": seed,
        "alpha": alpha,
        "target_coverage": target_coverage,
        "min_class_count": min_count,
        "low_count_policy": policy,
        "method": "mondrian_class_conditional_split_conformal",
        "status": "OK",
        "library_versions": pipe.library_versions(),
        "outputs": {
            "summary_csv": str(results_dir / "mondrian_conformal_summary_20260619.csv"),
            "per_class_csv": str(results_dir / "mondrian_conformal_per_class_20260619.csv"),
            "thresholds_csv": str(results_dir / "mondrian_conformal_thresholds_20260619.csv"),
            "point_sets_csv": str(results_dir / "mondrian_conformal_point_sets_20260619.csv"),
            "comparison_csv": str(results_dir / "mondrian_vs_global_conformal_comparison_20260619.csv"),
            "split_audit_csv": str(results_dir / "mondrian_conformal_split_audit_20260619.csv"),
        },
    }
    write_json(results_dir / "mondrian_conformal_provenance_20260619.json", provenance_payload)
    write_markdown_summary(results_dir, summary_rows, comparison_rows, alpha, target_coverage)

    print("OK: wrote Mondrian/class-conditional conformal sensitivity outputs")
    print(
        json.dumps(
            {
                "results_dir": str(results_dir),
                "summary_rows": len(summary_rows),
                "per_class_rows": len(per_class_rows),
                "point_rows": len(point_rows),
                "comparison_rows": len(comparison_rows),
            },
            indent=2,
        )
    )
    return 0


def build_comparison_rows(
    ctx: pipe.RunContext,
    global_conformal_path: Path,
    mondrian_summary_path: Path,
) -> List[Dict[str, Any]]:
    if not global_conformal_path.exists():
        return [
            {
                **ctx.provenance([global_conformal_path, mondrian_summary_path]),
                "status": "ERROR",
                "reason": "Global conformal table unavailable.",
            }
        ]
    global_df = pd.read_csv(global_conformal_path)
    mondrian_df = pd.read_csv(mondrian_summary_path)
    rows: List[Dict[str, Any]] = []
    for _, mrow in mondrian_df[mondrian_df["status"] == "OK"].iterrows():
        mask = (
            (global_df["stack"].astype(str) == str(mrow["stack"]))
            & (global_df["model"].astype(str) == str(mrow["model"]))
            & (global_df["split"].astype(str) == str(mrow["split"]))
            & (global_df["status"].astype(str) == "OK")
        )
        matches = global_df[mask]
        row = ctx.provenance([global_conformal_path, mondrian_summary_path])
        if matches.empty:
            row.update(
                {
                    "status": "SKIPPED",
                    "reason": "No matching OK global conformal row.",
                    "stack": mrow["stack"],
                    "model": mrow["model"],
                    "split": mrow["split"],
                }
            )
            rows.append(row)
            continue
        grow = matches.iloc[0]
        global_cov = float(grow["empirical_coverage"])
        mondrian_cov = float(mrow["empirical_coverage"])
        global_size = float(grow["average_set_size"])
        mondrian_size = float(mrow["average_set_size"])
        row.update(
            {
                "status": "OK",
                "reason": "",
                "stack": mrow["stack"],
                "model": mrow["model"],
                "split": mrow["split"],
                "global_empirical_coverage": global_cov,
                "mondrian_empirical_coverage": mondrian_cov,
                "coverage_delta_mondrian_minus_global": mondrian_cov - global_cov,
                "global_average_set_size": global_size,
                "mondrian_average_set_size": mondrian_size,
                "set_size_delta_mondrian_minus_global": mondrian_size - global_size,
                "target_coverage": float(mrow["target_coverage"]),
                "n_calibration": int(float(mrow["n_calibration"])),
                "n_test": int(float(mrow["n_test"])),
            }
        )
        rows.append(row)
    return rows


def write_markdown_summary(
    results_dir: Path,
    summary_rows: Sequence[Dict[str, Any]],
    comparison_rows: Sequence[Dict[str, Any]],
    alpha: float,
    target_coverage: float,
) -> None:
    summary_df = pd.DataFrame([row for row in summary_rows if row.get("status") == "OK"])
    comp_df = pd.DataFrame([row for row in comparison_rows if row.get("status") == "OK"])
    lines = [
        "# Mondrian/Class-Conditional Conformal Sensitivity",
        "",
        "Status: OK",
        "",
        f"Alpha: `{alpha}`; target coverage: `{target_coverage}`.",
        "",
        "This sensitivity recomputes split conformal prediction with class-conditional (Mondrian) thresholds. Each class receives its own quantile from calibration examples whose true label is that class. Classes below `min_class_count` are dropped per config and logged explicitly.",
        "",
    ]
    if not summary_df.empty:
        primary = summary_df[
            (summary_df["stack"] == "B2")
            & (summary_df["model"] == "RandomForest")
        ]
        if not primary.empty:
            lines.extend(["## Primary B2 RandomForest rows", ""])
            for _, row in primary.iterrows():
                lines.append(
                    f"- `{row['split']}`: coverage `{row['empirical_coverage']}`, average set size `{row['average_set_size']}`, "
                    f"n_calibration `{row['n_calibration']}`, n_test `{row['n_test']}`."
                )
            lines.append("")
    if not comp_df.empty:
        comp_primary = comp_df[
            (comp_df["stack"] == "B2")
            & (comp_df["model"] == "RandomForest")
        ]
        if not comp_primary.empty:
            lines.extend(["## Global versus Mondrian comparison for B2 RandomForest", ""])
            for _, row in comp_primary.iterrows():
                lines.append(
                    f"- `{row['split']}`: global coverage `{row['global_empirical_coverage']}` -> Mondrian coverage `{row['mondrian_empirical_coverage']}`; "
                    f"global set size `{row['global_average_set_size']}` -> Mondrian set size `{row['mondrian_average_set_size']}`."
                )
            lines.append("")
    lines.extend(
        [
            "Interpretation boundary:",
            "",
            "This is a sensitivity analysis. It does not repair exchangeability under spatial shift; it tests whether class-conditional calibration changes the coverage/informativeness trade-off already reported in the manuscript.",
            "",
        ]
    )
    (results_dir / "MONDRIAN_CONFORMAL_SENSITIVITY_20260619.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute Mondrian/class-conditional conformal sensitivity.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", default="config/config_public_reproduction_20260615.yaml")
    parser.add_argument("--variogram-choice", default="results/active_q25_rerun/variogram_choice.json")
    parser.add_argument("--global-conformal-table", default="results/active_q25_rerun/table7_conformal.csv")
    parser.add_argument("--results-dir", default="results/mondrian_conformal_sensitivity_20260619")
    args = parser.parse_args()
    try:
        return compute(args)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
