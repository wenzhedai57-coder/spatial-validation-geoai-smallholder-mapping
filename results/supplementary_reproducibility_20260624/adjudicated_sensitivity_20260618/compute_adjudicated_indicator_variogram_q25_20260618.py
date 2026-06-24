"""Compute adjudicated-subset one-vs-rest indicator variograms and q25 block distance."""

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


def parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def project_lonlat_to_meters(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 110_574.0
    return np.column_stack([x, y])


def provenance(timestamp: str, config_hash: str, input_files: list[Path], seed: int, status: str, reason: str = "") -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "config_hash": config_hash,
        "input_files": "|".join(str(path) for path in input_files),
        "random_seed": seed,
        "status": status,
        "reason": reason,
    }


def compute_indicator_range(
    timestamp: str,
    config_hash: str,
    ref_path: Path,
    seed: int,
    min_class_count: int,
    n_bins: int,
    max_pair_count: int,
    sill_fraction: float,
    work: pd.DataFrame,
    coords: np.ndarray,
    class_code: Any,
    class_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    z = (work["class_code"].astype(str) == str(class_code)).astype(float).to_numpy()
    n = len(work)
    n_positive = int(np.sum(z == 1.0))
    n_negative = int(np.sum(z == 0.0))
    total_pairs = n * (n - 1) // 2
    base = {
        "class_code": class_code,
        "class_name": class_name,
        "indicator_variable": f"is_{class_name}",
        "n_samples": n,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "total_pair_count": total_pairs,
        "n_bins": n_bins,
        "sill_fraction_for_range": sill_fraction,
        "min_class_count": min_class_count,
        "method": "one_vs_rest_binary_indicator_empirical_variogram",
    }

    if n_positive < min_class_count:
        reason = f"SKIPPED: positive class count {n_positive} below min_class_count={min_class_count}."
        return [], {**provenance(timestamp, config_hash, [ref_path], seed, "SKIPPED", reason), **base}
    if n_negative < min_class_count:
        reason = f"SKIPPED: one-vs-rest negative count {n_negative} below min_class_count={min_class_count}."
        return [], {**provenance(timestamp, config_hash, [ref_path], seed, "SKIPPED", reason), **base}

    rng = np.random.default_rng(seed)
    if total_pairs <= max_pair_count:
        i_idx, j_idx = np.triu_indices(n, k=1)
    else:
        i_idx = rng.integers(0, n, size=max_pair_count)
        j_idx = rng.integers(0, n, size=max_pair_count)
        keep = i_idx != j_idx
        i_idx = i_idx[keep]
        j_idx = j_idx[keep]

    distances = np.linalg.norm(coords[i_idx] - coords[j_idx], axis=1)
    semivar = 0.5 * (z[i_idx] - z[j_idx]) ** 2
    keep = np.isfinite(distances) & np.isfinite(semivar) & (distances > 0)
    distances = distances[keep]
    semivar = semivar[keep]

    if len(distances) < n_bins:
        reason = f"SKIPPED: only {len(distances)} positive-distance pairs for n_bins={n_bins}."
        return [], {**provenance(timestamp, config_hash, [ref_path], seed, "SKIPPED", reason), **base, "pair_count_used": int(len(distances))}

    edges = np.linspace(0, float(np.nanmax(distances)), n_bins + 1)
    rows: list[dict[str, Any]] = []
    mids: list[float] = []
    gammas: list[float] = []
    for idx in range(n_bins):
        lo = float(edges[idx])
        hi = float(edges[idx + 1])
        in_bin = (distances >= lo) & (distances < hi if idx < n_bins - 1 else distances <= hi)
        if not np.any(in_bin):
            continue
        midpoint = float((lo + hi) / 2.0)
        gamma = float(np.nanmean(semivar[in_bin]))
        mids.append(midpoint)
        gammas.append(gamma)
        rows.append(
            {
                **provenance(timestamp, config_hash, [ref_path], seed, "OK", ""),
                **base,
                "bin": idx + 1,
                "distance_low_m": lo,
                "distance_high_m": hi,
                "distance_midpoint_m": midpoint,
                "semivariance": gamma,
                "pair_count": int(np.sum(in_bin)),
                "pair_count_used": int(len(distances)),
            }
        )

    if not gammas or max(gammas) <= 0:
        reason = "SKIPPED: empirical sill is zero or unavailable."
        return rows, {**provenance(timestamp, config_hash, [ref_path], seed, "SKIPPED", reason), **base, "pair_count_used": int(len(distances))}

    sill = float(max(gammas))
    threshold = sill_fraction * sill
    chosen = None
    for midpoint, gamma in zip(mids, gammas):
        if gamma >= threshold:
            chosen = float(midpoint)
            break
    if chosen is None:
        chosen = float(mids[-1])

    for row in rows:
        row["sill"] = sill
        row["range_threshold"] = threshold
        row["chosen_range_m"] = chosen

    summary = {
        **provenance(timestamp, config_hash, [ref_path], seed, "OK", ""),
        **base,
        "pair_count_used": int(len(distances)),
        "sill": sill,
        "range_threshold": threshold,
        "chosen_range_m": chosen,
    }
    return rows, summary


def spatial_precheck(coords: np.ndarray, y: np.ndarray, distance_m: float, k_folds: int, seed: int) -> dict[str, Any]:
    cells_x = np.floor(coords[:, 0] / distance_m).astype(int)
    cells_y = np.floor(coords[:, 1] / distance_m).astype(int)
    cell_ids = np.array([f"{x}:{y_}" for x, y_ in zip(cells_x, cells_y)])
    unique_cells = np.unique(cell_ids)
    out: dict[str, Any] = {
        "distance_m": float(distance_m),
        "distance_km": float(distance_m) / 1000.0,
        "available_spatial_blocks": int(len(unique_cells)),
        "required_spatial_blocks": int(k_folds),
        "all_folds_nonempty": False,
        "min_train_count_after_buffer": "",
        "min_test_count": "",
        "fold_train_classes": "",
        "fold_test_classes": "",
        "fold_train_test_buffered": "",
        "reason": "",
    }
    if len(unique_cells) < k_folds:
        out["reason"] = f"Only {len(unique_cells)} spatial blocks are available for k_folds={k_folds}."
        return out

    rng = np.random.default_rng(seed)
    shuffled = unique_cells.copy()
    rng.shuffle(shuffled)
    cell_to_fold = {cell: idx % k_folds for idx, cell in enumerate(shuffled)}
    train_counts: list[int] = []
    test_counts: list[int] = []
    train_classes: list[int] = []
    test_classes: list[int] = []
    notes: list[str] = []
    for fold_idx in range(k_folds):
        test_mask = np.array([cell_to_fold[cell] == fold_idx for cell in cell_ids])
        test_coords = coords[test_mask]
        distances = np.linalg.norm(coords[:, None, :] - test_coords[None, :, :], axis=2)
        near_test = np.any(distances <= distance_m, axis=1)
        train_mask = (~test_mask) & (~near_test)
        train_count = int(np.sum(train_mask))
        test_count = int(np.sum(test_mask))
        buffered_count = int(np.sum((~test_mask) & near_test))
        train_counts.append(train_count)
        test_counts.append(test_count)
        train_classes.append(int(len(set(y[train_mask]))))
        test_classes.append(int(len(set(y[test_mask]))))
        notes.append(
            f"fold{fold_idx + 1}:train={train_count};test={test_count};buffered={buffered_count};"
            f"train_classes={train_classes[-1]};test_classes={test_classes[-1]}"
        )

    out.update(
        {
            "all_folds_nonempty": bool(min(train_counts) > 0 and min(test_counts) > 0),
            "min_train_count_after_buffer": int(min(train_counts)),
            "min_test_count": int(min(test_counts)),
            "fold_train_classes": "|".join(str(x) for x in train_classes),
            "fold_test_classes": "|".join(str(x) for x in test_classes),
            "fold_train_test_buffered": " | ".join(notes),
        }
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config_adjudicated_sensitivity_20260618.yaml")
    args = parser.parse_args()

    root = Path.cwd()
    config_path = (root / args.config).resolve()
    timestamp = utc_stamp()
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}")
        return 1

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_hash = sha256_file(config_path)
    seed = int(config.get("seeds", {}).get("global", 42))
    min_class_count = int(config.get("min_class_count", 30))
    cv_cfg = config.get("cv", {})
    k_folds = int(cv_cfg.get("k_folds", 4))
    variogram_cfg = config.get("variogram", {})
    n_bins = int(variogram_cfg.get("n_bins", 12))
    max_pair_count = int(variogram_cfg.get("max_pair_count", 250000))
    sill_fraction = float(variogram_cfg.get("sill_fraction_for_range", 0.95))
    results_dir = (root / config.get("paths", {}).get("results", "results/adjudicated_sensitivity_20260618")).resolve()
    figures_dir = (root / config.get("paths", {}).get("figures", "figures/adjudicated_sensitivity_20260618")).resolve()
    ref_cfg = config.get("reference_samples", {})
    ref_path = (root / ref_cfg.get("file", "data/reference_samples.csv")).resolve()

    if not ref_path.exists():
        print(f"ERROR: reference file not found: {ref_path}")
        return 1

    ref = pd.read_csv(ref_path)
    required = ["sample_id", "longitude", "latitude", "class_code", "class_name", "verified"]
    missing = [col for col in required if col not in ref.columns]
    if missing:
        print("ERROR: reference missing required columns: " + ", ".join(missing))
        return 1

    work = ref[parse_bool(ref["verified"])].dropna(subset=["longitude", "latitude", "class_code", "class_name"]).copy()
    if len(work) < 3:
        print("ERROR: fewer than 3 verified rows after filtering.")
        return 1

    work["class_code"] = work["class_code"].astype(int)
    coords = project_lonlat_to_meters(work["longitude"].astype(float).to_numpy(), work["latitude"].astype(float).to_numpy())
    y = work["class_code"].to_numpy()

    class_df = (
        work.groupby(["class_code", "class_name"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values("class_code")
    )

    all_bins: list[dict[str, Any]] = []
    ranges: list[dict[str, Any]] = []
    for rec in class_df.to_dict(orient="records"):
        rows, summary = compute_indicator_range(
            timestamp,
            config_hash,
            ref_path,
            seed,
            min_class_count,
            n_bins,
            max_pair_count,
            sill_fraction,
            work,
            coords,
            rec["class_code"],
            str(rec["class_name"]),
        )
        all_bins.extend(rows)
        ranges.append(summary)
        print(f"{summary['status']}: class={summary['class_name']} n_positive={summary['n_positive']} reason={summary.get('reason', '')}")

    bin_fields = BASE_COLUMNS + [
        "class_code",
        "class_name",
        "indicator_variable",
        "n_samples",
        "n_positive",
        "n_negative",
        "total_pair_count",
        "n_bins",
        "sill_fraction_for_range",
        "min_class_count",
        "method",
        "bin",
        "distance_low_m",
        "distance_high_m",
        "distance_midpoint_m",
        "semivariance",
        "pair_count",
        "pair_count_used",
        "sill",
        "range_threshold",
        "chosen_range_m",
    ]
    range_fields = [field for field in bin_fields if field not in {"bin", "distance_low_m", "distance_high_m", "distance_midpoint_m", "semivariance", "pair_count"}]
    write_csv(results_dir / "variogram_indicator_bins_20260618.csv", bin_fields, all_bins)
    write_csv(results_dir / "variogram_indicator_ranges_20260618.csv", range_fields, ranges)

    ok_ranges = [row for row in ranges if row.get("status") == "OK"]
    if not ok_ranges:
        summary = {
            "timestamp": timestamp,
            "status": "ERROR",
            "reason": "No class-specific indicator variogram returned OK.",
            "method": "one_vs_rest_indicator_empirical_variogram_practical_q25_rule",
            "reference_file": str(ref_path),
            "reference_sha256": sha256_file(ref_path),
            "config_file": str(config_path),
            "config_hash": config_hash,
            "verified_rows": int(len(work)),
            "class_ranges": ranges,
        }
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "block_distance_practical_rule_summary_20260618.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("ERROR: no OK indicator ranges.")
        return 1

    range_values = np.array([float(row["chosen_range_m"]) for row in ok_ranges], dtype=float)
    selected_distance = float(np.quantile(range_values, 0.25))
    candidate_rows: list[dict[str, Any]] = []
    candidates = [(f"class_{row['class_code']}_{row['class_name']}", float(row["chosen_range_m"])) for row in ok_ranges]
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
    for label, distance in candidates:
        key = (label, round(distance, 6))
        if key in seen:
            continue
        seen.add(key)
        pre = spatial_precheck(coords, y, distance, k_folds, seed)
        candidate_rows.append(
            {
                "timestamp": timestamp,
                "candidate": label,
                "selection_status": "SELECTED" if label == "q25_ok_selected" else "NOT_SELECTED",
                **pre,
            }
        )

    candidate_fields = [
        "timestamp",
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
    candidate_path = results_dir / "block_distance_practical_rule_candidates_20260618.csv"
    write_csv(candidate_path, candidate_fields, candidate_rows)
    selected_row = next(row for row in candidate_rows if row["selection_status"] == "SELECTED")

    summary = {
        "timestamp": timestamp,
        "status": "OK" if selected_row["all_folds_nonempty"] else "SKIPPED",
        "reason": "" if selected_row["all_folds_nonempty"] else "Selected q25 distance did not pass spatial precheck; retain explicit SKIPPED status.",
        "method": "one_vs_rest_indicator_empirical_variogram_practical_q25_rule",
        "reference_file": str(ref_path),
        "reference_sha256": sha256_file(ref_path),
        "config_file": str(config_path),
        "config_hash": config_hash,
        "verified_rows": int(len(work)),
        "random_seed": seed,
        "min_class_count": min_class_count,
        "block_distance_rule": "q25_of_ok_one_vs_rest_indicator_ranges",
        "selection_rationale": "Use the 25th percentile of OK class-specific one-vs-rest indicator ranges. The rule uses only reference geometry and class-specific label-structure variogram diagnostics, not model accuracy.",
        "suggested_block_distance_m": selected_distance,
        "suggested_block_distance_km": selected_distance / 1000.0,
        "class_ranges": ranges,
        "candidate_table": str(candidate_path),
        "spatial_precheck": selected_row,
    }
    summary_path = results_dir / "block_distance_practical_rule_summary_20260618.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    try:
        import matplotlib.pyplot as plt

        figures_dir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(8, 4.8), dpi=160)
        for row in ok_ranges:
            class_rows = [r for r in all_bins if str(r.get("class_code")) == str(row["class_code"])]
            class_rows = sorted(class_rows, key=lambda r: int(r["bin"]))
            ax.plot(
                [float(r["distance_midpoint_m"]) / 1000.0 for r in class_rows],
                [float(r["semivariance"]) for r in class_rows],
                marker="o",
                linewidth=1.3,
                label=f"{row['class_name']} ({float(row['chosen_range_m']) / 1000.0:.1f} km)",
            )
        ax.axvline(selected_distance / 1000.0, color="black", linestyle="--", linewidth=1.0, label="q25 selected")
        ax.set_xlabel("Pair distance midpoint (km)")
        ax.set_ylabel("Empirical semivariance")
        ax.set_title("Adjudicated-subset one-vs-rest indicator variograms")
        ax.grid(True, linewidth=0.3, alpha=0.5)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(figures_dir / "adjudicated_variogram_indicator_ranges_20260618.png")
        fig.savefig(figures_dir / "adjudicated_variogram_indicator_ranges_20260618.pdf")
        plt.close(fig)
    except Exception as exc:
        print(f"SKIPPED: variogram plot failed: {type(exc).__name__}: {exc}")

    print(
        json.dumps(
            {
                "status": summary["status"],
                "verified_rows": summary["verified_rows"],
                "suggested_block_distance_m": summary["suggested_block_distance_m"],
                "suggested_block_distance_km": summary["suggested_block_distance_km"],
                "summary": str(summary_path),
            },
            indent=2,
        )
    )
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
