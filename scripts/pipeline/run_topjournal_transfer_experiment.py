"""Run leave-region-out transfer experiments for the top-journal extension."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


BASE_COLUMNS = ["timestamp", "config_hash", "input_files", "random_seed", "status", "reason"]


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def provenance(config_hash: str, inputs: list[Path], seed: int) -> dict[str, Any]:
    return {
        "timestamp": stamp(),
        "config_hash": config_hash,
        "input_files": ";".join(str(path) for path in inputs),
        "random_seed": seed,
    }


def parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def load_reference(root: Path, config: dict[str, Any]) -> pd.DataFrame:
    ref_cfg = config.get("reference_samples", {})
    configured_region_file = ref_cfg.get("region_file")
    if configured_region_file:
        with_region = root / configured_region_file
    else:
        configured_ref = root / ref_cfg.get("file", "data/reference_samples_EXPANDED_USER_CONFIRMED_PLUS_RUBBER2.csv")
        candidate = configured_ref.with_name(f"{configured_ref.stem}_WITH_REGION{configured_ref.suffix}")
        fallback = root / "data" / "reference_samples_EXPANDED_USER_CONFIRMED_PLUS_RUBBER2_WITH_REGION.csv"
        with_region = candidate if candidate.exists() else fallback
    if not with_region.exists():
        raise RuntimeError(f"Missing region-aware expanded reference file: {with_region}")
    ref = pd.read_csv(with_region)
    ref = ref[parse_bool(ref["verified"])].copy()
    return ref


def load_stack(root: Path, config: dict[str, Any], stack: str, ref: pd.DataFrame) -> tuple[pd.DataFrame, list[str], Path]:
    id_col = config["reference_samples"].get("id_column", "sample_id")
    feature_path = root / config["feature_stacks"][stack]["file"]
    features = pd.read_csv(feature_path)
    merged = ref.merge(features, on=id_col, how="inner")
    feature_cols = [col for col in features.columns if col != id_col]
    return merged, feature_cols, feature_path


def apply_missing_feature_policy(
    config: dict[str, Any],
    stack: str,
    feature_path: Path,
    merged: pd.DataFrame,
    feature_cols: list[str],
    config_hash: str,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    preprocessing = config.get("preprocessing", {})
    policy = preprocessing.get("missing_feature_policy", "none")
    sentinel = preprocessing.get("missing_feature_sentinel")
    imputer_strategy = preprocessing.get("imputer_strategy", "median")
    work = merged.copy()
    features = work.loc[:, feature_cols].apply(pd.to_numeric, errors="coerce")
    nan_before = int(features.isna().sum().sum())
    sentinel_cells = 0
    sentinel_rows = 0
    converted = 0
    status = "OK"
    reason = ""
    if sentinel is not None:
        sentinel_value = float(sentinel)
        sentinel_mask = features.eq(sentinel_value)
        sentinel_cells = int(sentinel_mask.sum().sum())
        sentinel_rows = int(sentinel_mask.any(axis=1).sum())
        if sentinel_cells and policy == "sentinel_to_nan_then_median_impute":
            features = features.mask(sentinel_mask, np.nan)
            converted = sentinel_cells
        elif sentinel_cells and policy != "sentinel_to_nan_then_median_impute":
            status = "ERROR"
            reason = f"{sentinel_cells} cells equal missing_feature_sentinel={sentinel} without an explicit conversion policy."
    nan_after = int(features.isna().sum().sum())
    rows_missing_after = int(features.isna().any(axis=1).sum())
    work.loc[:, feature_cols] = features
    row = provenance(config_hash, [feature_path], seed)
    row.update(
        {
            "status": status,
            "reason": reason,
            "stack": stack,
            "feature_file": str(feature_path),
            "policy": policy,
            "missing_feature_sentinel": sentinel if sentinel is not None else "",
            "imputer_strategy": imputer_strategy,
            "verified_rows_matched": int(len(work)),
            "feature_columns": int(len(feature_cols)),
            "nan_cells_before_policy": nan_before,
            "sentinel_cells_before_policy": sentinel_cells,
            "rows_with_sentinel_before_policy": sentinel_rows,
            "cells_converted_to_nan": converted,
            "nan_cells_after_policy": nan_after,
            "rows_with_any_missing_after_policy": rows_missing_after,
        }
    )
    return work, row


def make_model(config: dict[str, Any], model_name: str, y_train: np.ndarray, seed: int):
    if len(np.unique(y_train)) == 1:
        return None, None
    if model_name == "RandomForest":
        from sklearn.ensemble import RandomForestClassifier

        params = dict(config.get("random_forest", {}))
        params["random_state"] = seed
        return RandomForestClassifier(**params), None
    if model_name == "XGBoost":
        try:
            from xgboost import XGBClassifier
        except Exception as exc:  # noqa: BLE001
            return None, f"XGBoost unavailable: {type(exc).__name__}: {exc}"
        params = dict(config.get("xgboost", {}))
        n_classes = len(np.unique(y_train))
        if n_classes <= 2:
            params.update({"random_state": seed, "eval_metric": "logloss", "objective": "binary:logistic"})
        else:
            params.update(
                {
                    "random_state": seed,
                    "eval_metric": "mlogloss",
                    "objective": "multi:softprob",
                    "num_class": n_classes,
                }
            )
        return XGBClassifier(**params), None
    return None, f"Unknown model: {model_name}"


def transform_features(X_train: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    from sklearn.impute import SimpleImputer

    imputer = SimpleImputer(strategy="median")
    transformed = [imputer.fit_transform(X_train)]
    transformed.extend(imputer.transform(arr) for arr in others)
    return tuple(transformed)


def fit_predict(config: dict[str, Any], model_name: str, X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray, seed: int):
    if len(np.unique(y_train)) == 1:
        label = np.unique(y_train)[0]
        pred = np.repeat(label, len(X_test))
        proba = np.ones((len(X_test), 1), dtype=float)
        classes = np.array([label])
        return pred, proba, classes, None
    model, reason = make_model(config, model_name, y_train, seed)
    if reason:
        return None, None, None, reason
    X_train_t, X_test_t = transform_features(X_train, X_test)
    if model_name == "XGBoost":
        from sklearn.preprocessing import LabelEncoder

        encoder = LabelEncoder()
        y_enc = encoder.fit_transform(y_train)
        model.fit(X_train_t, y_enc)
        pred_enc = model.predict(X_test_t)
        pred = encoder.inverse_transform(pred_enc.astype(int))
        return pred, model.predict_proba(X_test_t), encoder.classes_, None
    model.fit(X_train_t, y_train)
    return model.predict(X_test_t), model.predict_proba(X_test_t), model.classes_, None


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    from sklearn.metrics import accuracy_score, f1_score

    return float(accuracy_score(y_true, y_pred)), float(f1_score(y_true, y_pred, average="macro", zero_division=0))


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = len(scores)
    q = math.ceil((n + 1) * (1 - alpha)) / n
    q = min(q, 1.0)
    return float(np.quantile(scores, q, method="higher"))


def make_transfer_calibration_split(y_train_region: np.ndarray, min_count: int, seed: int):
    rng = np.random.default_rng(seed)
    train_idx: list[int] = []
    cal_idx: list[int] = []
    dropped: dict[int, int] = {}
    for label in sorted(np.unique(y_train_region)):
        idx = np.where(y_train_region == label)[0]
        rng.shuffle(idx)
        if len(idx) <= min_count:
            dropped[int(label)] = int(len(idx))
            train_idx.extend(idx.tolist())
            continue
        cal_idx.extend(idx[:min_count].tolist())
        train_idx.extend(idx[min_count:].tolist())
    return np.array(train_idx, dtype=int), np.array(cal_idx, dtype=int), dropped


def transfer_conformal(
    config: dict[str, Any],
    model_name: str,
    X_train_region: np.ndarray,
    y_train_region: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    min_count: int,
    alpha: float,
    seed: int,
):
    train_rel, cal_rel, dropped = make_transfer_calibration_split(y_train_region, min_count, seed)
    retained = sorted(set(y_train_region[cal_rel])) if len(cal_rel) else []
    if len(retained) < 1:
        return None, dropped, retained, "No retained calibration class meets min_class_count."
    test_keep = np.isin(y_test, retained)
    if not np.any(test_keep):
        return None, dropped, retained, "Held-out region has no test samples in retained conformal classes."
    train_keep = np.isin(y_train_region[train_rel], retained)
    if not np.any(train_keep):
        return None, dropped, retained, "No retained-class training samples remain after calibration allocation."
    X_tr = X_train_region[train_rel][train_keep]
    y_tr = y_train_region[train_rel][train_keep]
    X_cal = X_train_region[cal_rel]
    y_cal = y_train_region[cal_rel]
    X_te = X_test[test_keep]
    y_te = y_test[test_keep]
    X_tr_t, X_cal_t, X_te_t = transform_features(X_tr, X_cal, X_te)
    if len(np.unique(y_tr)) == 1:
        classes = np.array([np.unique(y_tr)[0]])
        cal_proba = np.ones((len(X_cal_t), 1), dtype=float)
        test_proba = np.ones((len(X_te_t), 1), dtype=float)
    else:
        model, reason = make_model(config, model_name, y_tr, seed)
        if reason:
            return None, dropped, retained, reason
        if model_name == "XGBoost":
            from sklearn.preprocessing import LabelEncoder

            encoder = LabelEncoder()
            y_enc = encoder.fit_transform(y_tr)
            model.fit(X_tr_t, y_enc)
            classes = encoder.classes_
            cal_proba = model.predict_proba(X_cal_t)
            test_proba = model.predict_proba(X_te_t)
        else:
            model.fit(X_tr_t, y_tr)
            classes = model.classes_
            cal_proba = model.predict_proba(X_cal_t)
            test_proba = model.predict_proba(X_te_t)

    class_to_pos = {label: pos for pos, label in enumerate(classes)}
    cal_scores = np.array([1.0 - cal_proba[i, class_to_pos[y]] for i, y in enumerate(y_cal) if y in class_to_pos])
    if len(cal_scores) == 0:
        return None, dropped, retained, "No calibration scores available after class alignment."
    qhat = conformal_quantile(cal_scores, alpha)
    pred_sets = test_proba >= (1.0 - qhat)
    covered = []
    sizes = []
    for i, y in enumerate(y_te):
        pos = class_to_pos.get(y)
        covered.append(bool(pos is not None and pred_sets[i, pos]))
        sizes.append(int(np.sum(pred_sets[i])))
    return {
        "empirical_coverage": float(np.mean(covered)),
        "average_set_size": float(np.mean(sizes)),
        "n_train": int(len(y_tr)),
        "n_calibration": int(len(y_cal)),
        "n_test": int(len(y_te)),
        "classes_retained": "|".join(str(int(x)) for x in sorted(retained)),
    }, dropped, retained, ""


def project_lonlat(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 111_320.0
    return np.column_stack([x, y])


def morans_i(values: np.ndarray, coords: np.ndarray, threshold: float) -> float:
    centered = values - np.mean(values)
    denom = float(np.sum(centered**2))
    if denom == 0:
        return float("nan")
    distances = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    weights = ((distances > 0) & (distances <= threshold)).astype(float)
    w_sum = float(np.sum(weights))
    if w_sum == 0:
        return float("nan")
    return float((len(values) / w_sum) * (np.sum(weights * np.outer(centered, centered)) / denom))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config_expanded_plus_rubber2.yaml")
    args = parser.parse_args(argv)

    root = Path.cwd()
    config_path = root / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_hash = sha256(config_path)
    seed = int(config.get("seeds", {}).get("global", 42))
    results_dir = root / config.get("paths", {}).get("results", "results/")
    results_dir.mkdir(parents=True, exist_ok=True)
    min_count = int(config.get("min_class_count", 30))
    alpha = float(config.get("cv", {}).get("conformal_alpha", 0.10))

    ref = load_reference(root, config)
    regions = sorted(ref["region_key"].dropna().astype(str).unique())
    variogram_path = results_dir / "variogram_choice.json"
    block_distance = json.loads(variogram_path.read_text(encoding="utf-8")).get("chosen_block_distance_m")

    accuracy_rows: list[dict[str, Any]] = []
    per_class_rows: list[dict[str, Any]] = []
    conformal_rows: list[dict[str, Any]] = []
    moran_rows: list[dict[str, Any]] = []
    missing_policy_rows: list[dict[str, Any]] = []

    from sklearn.metrics import precision_recall_fscore_support

    for stack in config["feature_stacks"]:
        merged, feature_cols, feature_path = load_stack(root, config, stack, ref)
        merged, missing_policy_row = apply_missing_feature_policy(config, stack, feature_path, merged, feature_cols, config_hash, seed)
        missing_policy_rows.append(missing_policy_row)
        X = merged[feature_cols].to_numpy(dtype=float)
        y = merged["class_code"].to_numpy()
        for held_out in regions:
            test_mask = merged["region_key"].astype(str).to_numpy() == held_out
            train_mask = ~test_mask
            if not np.any(test_mask) or not np.any(train_mask):
                continue
            train_classes = set(y[train_mask])
            known_test_mask = test_mask & np.isin(y, list(train_classes))
            dropped_test = int(np.sum(test_mask & (~known_test_mask)))
            for model_name in ["RandomForest", "XGBoost"]:
                base = provenance(config_hash, [config_path, feature_path], seed)
                base.update({"stack": stack, "model": model_name, "held_out_region": held_out})
                if not np.any(known_test_mask):
                    row = {**base, "status": "SKIPPED", "reason": "No held-out samples have classes present in training."}
                    accuracy_rows.append(row)
                    continue
                pred, proba, classes, reason = fit_predict(
                    config,
                    model_name,
                    X[train_mask],
                    y[train_mask],
                    X[known_test_mask],
                    seed,
                )
                if reason:
                    accuracy_rows.append({**base, "status": "SKIPPED", "reason": reason})
                    continue
                oa, macro_f1 = metrics(y[known_test_mask], pred)
                row = {
                    **base,
                    "status": "OK",
                    "reason": "",
                    "n_train": int(np.sum(train_mask)),
                    "n_test": int(np.sum(known_test_mask)),
                    "n_test_dropped_unseen_class": dropped_test,
                    "oa": oa,
                    "macro_f1": macro_f1,
                    "classes_train": "|".join(str(int(c)) for c in sorted(train_classes)),
                    "classes_test_evaluated": "|".join(str(int(c)) for c in sorted(set(y[known_test_mask]))),
                }
                accuracy_rows.append(row)

                labels = sorted(set(y[known_test_mask]) | set(pred))
                precision, recall, f1, support = precision_recall_fscore_support(
                    y[known_test_mask], pred, labels=labels, zero_division=0
                )
                for label, p, r, f1v, sup in zip(labels, precision, recall, f1, support):
                    per_class_rows.append(
                        {
                            **base,
                            "status": "OK",
                            "reason": "",
                            "class_code": int(label),
                            "precision": float(p),
                            "recall": float(r),
                            "f1": float(f1v),
                            "support": int(sup),
                        }
                    )

                conf_result, dropped, retained, conf_reason = transfer_conformal(
                    config,
                    model_name,
                    X[train_mask],
                    y[train_mask],
                    X[known_test_mask],
                    y[known_test_mask],
                    min_count,
                    alpha,
                    seed,
                )
                conf_row = {**base, "alpha": alpha, "target_coverage": 1.0 - alpha}
                if conf_result is None:
                    conf_row.update({"status": "SKIPPED", "reason": conf_reason})
                else:
                    conf_row.update({"status": "OK", "reason": "", **conf_result})
                conf_row["classes_dropped_below_min_count"] = "|".join(
                    f"{int(k)}:{int(v)}" for k, v in sorted(dropped.items())
                )
                conformal_rows.append(conf_row)

                residual = (pred != y[known_test_mask]).astype(float)
                coords = project_lonlat(
                    merged.loc[known_test_mask, "longitude"].astype(float).to_numpy(),
                    merged.loc[known_test_mask, "latitude"].astype(float).to_numpy(),
                )
                moran_row = {**base, "distance_threshold_m": block_distance}
                if len(residual) < 3 or np.nanvar(residual) == 0:
                    moran_row.update({"status": "SKIPPED", "reason": "Too few or constant transfer residuals.", "morans_i": "", "n_samples": int(len(residual))})
                else:
                    moran_row.update({"status": "OK", "reason": "", "morans_i": morans_i(residual, coords, float(block_distance)), "n_samples": int(len(residual))})
                moran_rows.append(moran_row)

    write_csv(
        results_dir / "table10_leave_region_out_transfer.csv",
        accuracy_rows,
        BASE_COLUMNS + ["stack", "model", "held_out_region", "n_train", "n_test", "n_test_dropped_unseen_class", "oa", "macro_f1", "classes_train", "classes_test_evaluated"],
    )
    write_csv(
        results_dir / "table10_leave_region_out_transfer_per_class.csv",
        per_class_rows,
        BASE_COLUMNS + ["stack", "model", "held_out_region", "class_code", "precision", "recall", "f1", "support"],
    )
    write_csv(
        results_dir / "table11_region_transfer_conformal.csv",
        conformal_rows,
        BASE_COLUMNS + ["stack", "model", "held_out_region", "alpha", "target_coverage", "empirical_coverage", "average_set_size", "n_train", "n_calibration", "n_test", "classes_retained", "classes_dropped_below_min_count"],
    )
    write_csv(
        results_dir / "table12_region_transfer_morans_i.csv",
        moran_rows,
        BASE_COLUMNS + ["stack", "model", "held_out_region", "morans_i", "n_samples", "distance_threshold_m"],
    )
    write_csv(
        results_dir / "transfer_missing_value_policy_audit.csv",
        missing_policy_rows,
        BASE_COLUMNS
        + [
            "stack",
            "feature_file",
            "policy",
            "missing_feature_sentinel",
            "imputer_strategy",
            "verified_rows_matched",
            "feature_columns",
            "nan_cells_before_policy",
            "sentinel_cells_before_policy",
            "rows_with_sentinel_before_policy",
            "cells_converted_to_nan",
            "nan_cells_after_policy",
            "rows_with_any_missing_after_policy",
        ],
    )
    provenance_doc = {
        "timestamp_utc": stamp(),
        "config": str(config_path),
        "config_hash": config_hash,
        "reference_rows": int(len(ref)),
        "regions": regions,
        "outputs": [
            "table10_leave_region_out_transfer.csv",
            "table10_leave_region_out_transfer_per_class.csv",
            "table11_region_transfer_conformal.csv",
            "table12_region_transfer_morans_i.csv",
            "transfer_missing_value_policy_audit.csv",
        ],
        "note": "Leave-region-out transfer uses fixed configured models and no per-region tuning.",
    }
    (results_dir / "topjournal_transfer_experiment_provenance.json").write_text(
        json.dumps(provenance_doc, indent=2), encoding="utf-8"
    )
    print(json.dumps(provenance_doc, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
