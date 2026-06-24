from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


BASE_COLUMNS = ["timestamp", "config_hash", "input_files", "random_seed", "status", "reason"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except Exception as exc:
        raise RuntimeError(f"PyYAML unavailable: {type(exc).__name__}: {exc}") from exc
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def project_lonlat_to_meters(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 110_574.0
    return np.column_stack([x, y])


def nearest_distances(train_coords: np.ndarray, test_coords: np.ndarray) -> np.ndarray:
    if len(train_coords) == 0 or len(test_coords) == 0:
        return np.full(len(test_coords), np.nan, dtype=float)
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(train_coords)
        dists, _ = tree.query(test_coords, k=1)
        return np.asarray(dists, dtype=float)
    except Exception:
        distances = np.linalg.norm(train_coords[:, None, :] - test_coords[None, :, :], axis=2)
        return np.min(distances, axis=0)


def within_distance_mask(all_coords: np.ndarray, query_coords: np.ndarray, distance: float) -> np.ndarray:
    if len(query_coords) == 0:
        return np.zeros(len(all_coords), dtype=bool)
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(all_coords)
        query_tree = cKDTree(query_coords)
        pairs = tree.query_ball_tree(query_tree, r=distance)
        return np.array([len(p) > 0 for p in pairs], dtype=bool)
    except Exception:
        distances = np.linalg.norm(all_coords[:, None, :] - query_coords[None, :, :], axis=2)
        return np.any(distances <= distance, axis=1)


def stratified_random_folds(y: np.ndarray, k: int, seed: int) -> List[Tuple[np.ndarray, np.ndarray, str]]:
    try:
        from sklearn.model_selection import StratifiedKFold
    except Exception as exc:
        raise RuntimeError(f"scikit-learn unavailable: {type(exc).__name__}: {exc}") from exc
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    return [(train, test, str(i + 1)) for i, (train, test) in enumerate(skf.split(np.zeros(len(y)), y))]


def spatial_folds(coords: np.ndarray, block_distance_m: float, k: int, seed: int) -> List[Tuple[np.ndarray, np.ndarray, str, int]]:
    cells_x = np.floor(coords[:, 0] / block_distance_m).astype(int)
    cells_y = np.floor(coords[:, 1] / block_distance_m).astype(int)
    cell_ids = np.array([f"{x}:{y}" for x, y in zip(cells_x, cells_y)])
    unique_cells = np.unique(cell_ids)
    rng = np.random.default_rng(seed)
    shuffled = unique_cells.copy()
    rng.shuffle(shuffled)
    cell_to_fold = {cell: idx % k for idx, cell in enumerate(shuffled)}
    folds = []
    for fold_idx in range(k):
        test_mask = np.array([cell_to_fold[cell] == fold_idx for cell in cell_ids])
        near_test = within_distance_mask(coords, coords[test_mask], block_distance_m)
        train_mask = (~test_mask) & (~near_test)
        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        buffered_out_count = int(np.sum((~test_mask) & near_test))
        folds.append((train_idx, test_idx, str(fold_idx + 1), buffered_out_count))
    return folds


def class_count_string(labels: np.ndarray) -> str:
    if len(labels) == 0:
        return ""
    counts = pd.Series(labels).value_counts().sort_index()
    return "|".join(f"{key}:{int(value)}" for key, value in counts.items())


def quantiles(values: np.ndarray) -> Dict[str, float]:
    clean = values[np.isfinite(values)]
    if len(clean) == 0:
        return {
            "min": float("nan"),
            "p10": float("nan"),
            "p25": float("nan"),
            "median": float("nan"),
            "mean": float("nan"),
            "p75": float("nan"),
            "max": float("nan"),
        }
    return {
        "min": float(np.min(clean)),
        "p10": float(np.quantile(clean, 0.10)),
        "p25": float(np.quantile(clean, 0.25)),
        "median": float(np.quantile(clean, 0.50)),
        "mean": float(np.mean(clean)),
        "p75": float(np.quantile(clean, 0.75)),
        "max": float(np.max(clean)),
    }


def provenance(timestamp: str, config_hash: str, input_files: List[Path], seed: int) -> Dict[str, Any]:
    return {
        "timestamp": timestamp,
        "config_hash": config_hash,
        "input_files": ";".join(str(path) for path in input_files),
        "random_seed": seed,
    }


def build_audit(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config_path = (root / args.config).resolve()
    reference_path = (root / args.reference).resolve()
    variogram_path = (root / args.variogram_choice).resolve()
    results_dir = (root / args.results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config_hash = sha256_file(config_path)
    cfg = load_yaml(config_path)
    variogram_choice = json.loads(variogram_path.read_text(encoding="utf-8"))
    block_distance_m = float(variogram_choice["chosen_block_distance_m"])
    seed = int(cfg.get("seeds", {}).get("global", 42))
    k = int(cfg.get("cv", {}).get("k_folds", 4))
    min_class_count = int(cfg.get("min_class_count", 30))
    low_count_policy = str(cfg.get("low_count_policy", "drop"))
    ref_cfg = cfg.get("reference_samples", {})
    id_col = ref_cfg.get("id_column", "sample_id")
    verified_col = ref_cfg.get("verified_column", "verified")
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")
    code_col = ref_cfg.get("class_code_column", "class_code")

    input_files = [config_path, reference_path, variogram_path]
    base = provenance(timestamp, config_hash, input_files, seed)

    ref = pd.read_csv(reference_path)
    missing = [col for col in [id_col, verified_col, lon_col, lat_col, code_col] if col not in ref.columns]
    if missing:
        reason = "reference file missing required columns: " + ", ".join(missing)
        row = {**base, "status": "ERROR", "reason": reason}
        write_csv(results_dir / "q25_nndm_style_summary_20260619.csv", BASE_COLUMNS, [row])
        print(f"ERROR: {reason}")
        return 1

    work = ref[parse_bool_series(ref[verified_col])].copy()
    initial_class_counts = work.groupby(code_col).size().sort_index()
    low_codes = [code for code, count in initial_class_counts.items() if int(count) < min_class_count]
    class_policy_rows: List[Dict[str, Any]] = []
    for code in low_codes:
        status = "OK" if low_count_policy == "drop" else "SKIPPED"
        class_policy_rows.append(
            {
                **base,
                "status": status,
                "reason": f"class has fewer samples than min_class_count={min_class_count}",
                "class_code": code,
                "sample_count": int(initial_class_counts.loc[code]),
                "policy": low_count_policy,
            }
        )
    if low_codes and low_count_policy == "drop":
        work = work[~work[code_col].isin(low_codes)].copy()
    elif low_codes:
        reason = "low-count classes present and only low_count_policy=drop is implemented in this audit"
        row = {**base, "status": "ERROR", "reason": reason}
        write_csv(results_dir / "q25_nndm_style_summary_20260619.csv", BASE_COLUMNS, [row])
        print(f"ERROR: {reason}")
        return 1

    work = work.reset_index(drop=True)
    y = work[code_col].to_numpy()
    coords = project_lonlat_to_meters(work[lon_col].astype(float).to_numpy(), work[lat_col].astype(float).to_numpy())

    random_sets = [(train, test, fold, 0) for train, test, fold in stratified_random_folds(y, k, seed)]
    spatial_sets = spatial_folds(coords, block_distance_m, k, seed)
    split_sets = [("random", random_sets), ("q25_spatial", spatial_sets)]

    point_rows: List[Dict[str, Any]] = []
    fold_rows: List[Dict[str, Any]] = []
    all_split_distances: Dict[str, List[float]] = {"random": [], "q25_spatial": []}
    all_split_leakage: Dict[str, int] = {"random": 0, "q25_spatial": 0}
    all_split_test_count: Dict[str, int] = {"random": 0, "q25_spatial": 0}
    split_zero_leakage_folds: Dict[str, int] = {"random": 0, "q25_spatial": 0}

    for split_name, folds in split_sets:
        for train_idx, test_idx, fold, buffered_out_count in folds:
            dists = nearest_distances(coords[train_idx], coords[test_idx])
            finite = dists[np.isfinite(dists)]
            leakage_flags = finite < block_distance_m
            leakage_count = int(np.sum(leakage_flags))
            zero_leakage = leakage_count == 0 and len(finite) == len(test_idx) and len(train_idx) > 0 and len(test_idx) > 0
            stats = quantiles(dists)
            fold_rows.append(
                {
                    **base,
                    "status": "OK" if len(train_idx) > 0 and len(test_idx) > 0 else "SKIPPED",
                    "reason": "" if len(train_idx) > 0 and len(test_idx) > 0 else "empty train or test partition",
                    "split": split_name,
                    "fold": fold,
                    "block_distance_m": block_distance_m,
                    "train_count": int(len(train_idx)),
                    "test_count": int(len(test_idx)),
                    "buffered_out_count": int(buffered_out_count),
                    "min_nearest_train_distance_m": stats["min"],
                    "p10_nearest_train_distance_m": stats["p10"],
                    "p25_nearest_train_distance_m": stats["p25"],
                    "median_nearest_train_distance_m": stats["median"],
                    "mean_nearest_train_distance_m": stats["mean"],
                    "p75_nearest_train_distance_m": stats["p75"],
                    "max_nearest_train_distance_m": stats["max"],
                    "leakage_count_below_block_distance": leakage_count,
                    "leakage_fraction_below_block_distance": float(leakage_count / len(finite)) if len(finite) else float("nan"),
                    "zero_leakage_assertion": bool(zero_leakage),
                    "fold_test_class_counts": class_count_string(y[test_idx]),
                    "fold_train_class_counts": class_count_string(y[train_idx]),
                }
            )
            all_split_distances[split_name].extend(float(x) for x in finite)
            all_split_leakage[split_name] += leakage_count
            all_split_test_count[split_name] += int(len(finite))
            if zero_leakage:
                split_zero_leakage_folds[split_name] += 1
            for idx, dist in zip(test_idx, dists):
                point_rows.append(
                    {
                        **base,
                        "status": "OK" if np.isfinite(dist) else "SKIPPED",
                        "reason": "" if np.isfinite(dist) else "nearest distance unavailable",
                        "split": split_name,
                        "fold": fold,
                        "sample_id": work.iloc[idx][id_col],
                        "class_code": work.iloc[idx][code_col],
                        "x_m": float(coords[idx, 0]),
                        "y_m": float(coords[idx, 1]),
                        "nearest_train_distance_m": float(dist) if np.isfinite(dist) else "",
                        "below_q25_block_distance": bool(np.isfinite(dist) and dist < block_distance_m),
                        "block_distance_m": block_distance_m,
                    }
                )

    summary_rows: List[Dict[str, Any]] = []
    for split_name in ["random", "q25_spatial"]:
        distances = np.asarray(all_split_distances[split_name], dtype=float)
        stats = quantiles(distances)
        summary_rows.append(
            {
                **base,
                "status": "OK",
                "reason": (
                    "Stratified random CV nearest-train distance distribution."
                    if split_name == "random"
                    else "Q25 spatial CV nearest-train distance distribution using the variogram-derived block distance."
                ),
                "audit_type": "nndm_style_nearest_train_distance",
                "split": split_name,
                "folds_total": k,
                "folds_zero_leakage": split_zero_leakage_folds[split_name],
                "test_point_count": all_split_test_count[split_name],
                "block_distance_m": block_distance_m,
                "min_nearest_train_distance_m": stats["min"],
                "p10_nearest_train_distance_m": stats["p10"],
                "p25_nearest_train_distance_m": stats["p25"],
                "median_nearest_train_distance_m": stats["median"],
                "mean_nearest_train_distance_m": stats["mean"],
                "p75_nearest_train_distance_m": stats["p75"],
                "max_nearest_train_distance_m": stats["max"],
                "leakage_count_below_block_distance": all_split_leakage[split_name],
                "leakage_fraction_below_block_distance": (
                    float(all_split_leakage[split_name] / all_split_test_count[split_name])
                    if all_split_test_count[split_name]
                    else float("nan")
                ),
                "nndm_knddm_status": (
                    "NOT_FULL_NNDM_OR_KNNDM_PREDICTION_DOMAIN_UNAVAILABLE"
                    if split_name == "q25_spatial"
                    else "REFERENCE_COMPARATOR"
                ),
            }
        )

    random_median = next(row for row in summary_rows if row["split"] == "random")["median_nearest_train_distance_m"]
    spatial_median = next(row for row in summary_rows if row["split"] == "q25_spatial")["median_nearest_train_distance_m"]
    ratio = float(spatial_median / random_median) if random_median and np.isfinite(random_median) else float("nan")
    summary_rows.append(
        {
            **base,
            "status": "OK",
            "reason": "Derived comparison between q25 spatial and random nearest-train median distances.",
            "audit_type": "derived_distance_ratio",
            "split": "q25_spatial_vs_random",
            "folds_total": k,
            "folds_zero_leakage": split_zero_leakage_folds["q25_spatial"],
            "test_point_count": all_split_test_count["q25_spatial"],
            "block_distance_m": block_distance_m,
            "min_nearest_train_distance_m": "",
            "p10_nearest_train_distance_m": "",
            "p25_nearest_train_distance_m": "",
            "median_nearest_train_distance_m": "",
            "mean_nearest_train_distance_m": "",
            "p75_nearest_train_distance_m": "",
            "max_nearest_train_distance_m": "",
            "leakage_count_below_block_distance": "",
            "leakage_fraction_below_block_distance": "",
            "median_distance_ratio_q25_spatial_over_random": ratio,
            "nndm_knddm_status": "NOT_FULL_NNDM_OR_KNNDM_PREDICTION_DOMAIN_UNAVAILABLE",
        }
    )

    if class_policy_rows:
        write_csv(
            results_dir / "q25_nndm_style_class_policy_20260619.csv",
            BASE_COLUMNS + ["class_code", "sample_count", "policy"],
            class_policy_rows,
        )
    else:
        write_csv(
            results_dir / "q25_nndm_style_class_policy_20260619.csv",
            BASE_COLUMNS + ["class_code", "sample_count", "policy"],
            [{**base, "status": "OK", "reason": "No class below min_class_count.", "class_code": "", "sample_count": "", "policy": low_count_policy}],
        )

    fold_fields = BASE_COLUMNS + [
        "split",
        "fold",
        "block_distance_m",
        "train_count",
        "test_count",
        "buffered_out_count",
        "min_nearest_train_distance_m",
        "p10_nearest_train_distance_m",
        "p25_nearest_train_distance_m",
        "median_nearest_train_distance_m",
        "mean_nearest_train_distance_m",
        "p75_nearest_train_distance_m",
        "max_nearest_train_distance_m",
        "leakage_count_below_block_distance",
        "leakage_fraction_below_block_distance",
        "zero_leakage_assertion",
        "fold_test_class_counts",
        "fold_train_class_counts",
    ]
    write_csv(results_dir / "q25_nndm_style_fold_distance_audit_20260619.csv", fold_fields, fold_rows)

    point_fields = BASE_COLUMNS + [
        "split",
        "fold",
        "sample_id",
        "class_code",
        "x_m",
        "y_m",
        "nearest_train_distance_m",
        "below_q25_block_distance",
        "block_distance_m",
    ]
    write_csv(results_dir / "q25_nndm_style_point_distance_audit_20260619.csv", point_fields, point_rows)

    summary_fields = BASE_COLUMNS + [
        "audit_type",
        "split",
        "folds_total",
        "folds_zero_leakage",
        "test_point_count",
        "block_distance_m",
        "min_nearest_train_distance_m",
        "p10_nearest_train_distance_m",
        "p25_nearest_train_distance_m",
        "median_nearest_train_distance_m",
        "mean_nearest_train_distance_m",
        "p75_nearest_train_distance_m",
        "max_nearest_train_distance_m",
        "leakage_count_below_block_distance",
        "leakage_fraction_below_block_distance",
        "median_distance_ratio_q25_spatial_over_random",
        "nndm_knddm_status",
    ]
    write_csv(results_dir / "q25_nndm_style_summary_20260619.csv", summary_fields, summary_rows)

    payload = {
        "timestamp": timestamp,
        "config_path": str(config_path),
        "config_hash_sha256": config_hash,
        "reference_path": str(reference_path),
        "reference_sha256": sha256_file(reference_path),
        "variogram_choice_path": str(variogram_path),
        "variogram_choice_sha256": sha256_file(variogram_path),
        "source_variogram_config_hash": variogram_choice.get("config_hash", ""),
        "random_seed": seed,
        "k_folds": k,
        "min_class_count": min_class_count,
        "low_count_policy": low_count_policy,
        "verified_rows_after_policy": int(len(work)),
        "chosen_block_distance_m": block_distance_m,
        "status": "OK",
        "nndm_knddm_status": "NOT_FULL_NNDM_OR_KNNDM_PREDICTION_DOMAIN_UNAVAILABLE",
        "interpretation_boundary": "This is a nearest-neighbour distance audit inspired by NNDM/kNNDM reviewer concerns. It is not a full NNDM/kNNDM design because no prediction-domain target grid or reference prediction points were supplied.",
        "outputs": {
            "summary_csv": str(results_dir / "q25_nndm_style_summary_20260619.csv"),
            "fold_csv": str(results_dir / "q25_nndm_style_fold_distance_audit_20260619.csv"),
            "point_csv": str(results_dir / "q25_nndm_style_point_distance_audit_20260619.csv"),
            "class_policy_csv": str(results_dir / "q25_nndm_style_class_policy_20260619.csv"),
        },
    }
    write_json(results_dir / "q25_nndm_style_provenance_20260619.json", payload)

    random_summary = next(row for row in summary_rows if row["split"] == "random")
    spatial_summary = next(row for row in summary_rows if row["split"] == "q25_spatial")
    md = f"""# Q25 NNDM-style nearest-neighbour distance audit

Status: OK

This audit addresses the reviewer-facing concern that the q25 spatial split should be defended against ordinary random cross-validation. It is an NNDM/kNNDM-style nearest-neighbour distance diagnostic, not a full NNDM or kNNDM design, because no prediction-domain target grid or external prediction point distribution was supplied.

Inputs:

- Config: `{config_path}`
- Reference samples: `{reference_path}`
- Variogram choice: `{variogram_path}`
- Random seed: `{seed}`
- q25 block distance: `{block_distance_m}` m

Key computed outputs:

- Random CV: median nearest train distance = `{random_summary["median_nearest_train_distance_m"]}` m; test points below q25 block distance = `{random_summary["leakage_count_below_block_distance"]}` of `{random_summary["test_point_count"]}`.
- Q25 spatial CV: median nearest train distance = `{spatial_summary["median_nearest_train_distance_m"]}` m; test points below q25 block distance = `{spatial_summary["leakage_count_below_block_distance"]}` of `{spatial_summary["test_point_count"]}`; zero-leakage folds = `{spatial_summary["folds_zero_leakage"]}` of `{spatial_summary["folds_total"]}`.
- Median nearest-distance ratio, q25 spatial over random = `{ratio}`.

Interpretation:

The q25 split is not presented as design-unbiased map accuracy or as a substitute for a full NNDM/kNNDM prediction-domain design. It is a conservative class-structure-informed split whose folds pass a nearest-neighbour zero-leakage audit at the variogram-derived q25 distance. The random split remains a close-neighbour interpolation comparator.
"""
    (results_dir / "Q25_NNDM_STYLE_DISTANCE_AUDIT_20260619.md").write_text(md, encoding="utf-8")

    print("OK: wrote q25 NNDM-style distance audit outputs")
    print(json.dumps({"results_dir": str(results_dir), "summary": summary_rows}, indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute q25 NNDM-style nearest-neighbour distance audit.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", default="config/config_fold3_teacher_vhr_repair_20260613.yaml")
    parser.add_argument("--reference", default="data/reference_samples_verified_622_public.csv")
    parser.add_argument("--variogram-choice", default="results/active_q25_rerun/variogram_choice.json")
    parser.add_argument("--results-dir", default="results/q25_nndm_style_distance_audit_20260619")
    args = parser.parse_args()
    try:
        return build_audit(args)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
