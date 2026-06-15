#!/usr/bin/env python
"""Run the no-fabrication GeoAI land-cover pipeline.

The script is deliberately conservative. If a required input is missing, it
writes an ERROR/SKIPPED row with provenance instead of emitting placeholder
metrics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

os.environ.setdefault("MPLBACKEND", "Agg")

try:
    import yaml
except Exception as exc:  # pragma: no cover - dependency gate
    yaml = None
    YAML_IMPORT_ERROR = exc
else:
    YAML_IMPORT_ERROR = None


BASE_TABLE_COLUMNS = [
    "timestamp",
    "config_hash",
    "input_files",
    "random_seed",
    "status",
    "reason",
]

TABLE_HEADERS: Dict[str, List[str]] = {
    "table3": BASE_TABLE_COLUMNS
    + ["stack", "stack_label", "model", "split", "fold", "oa", "macro_f1"],
    "table4": BASE_TABLE_COLUMNS
    + ["stack", "model", "metric", "random_value", "spatial_value", "optimism_gap"],
    "table5": BASE_TABLE_COLUMNS
    + ["contrast", "model", "split", "metric", "baseline_value", "alphaearth_value", "difference"],
    "table6": BASE_TABLE_COLUMNS
    + ["stack", "model", "split", "fold", "ece", "n_samples", "n_bins"],
    "table7": BASE_TABLE_COLUMNS
    + [
        "stack",
        "model",
        "split",
        "alpha",
        "target_coverage",
        "empirical_coverage",
        "average_set_size",
        "n_calibration",
        "n_test",
        "classes_retained",
    ],
    "table8": BASE_TABLE_COLUMNS
    + ["stack", "model", "split", "fold", "variable", "morans_i", "n_samples", "distance_threshold_m"],
    "table9": BASE_TABLE_COLUMNS
    + ["outcome", "predictor", "coefficient", "standard_error", "p_value", "n_samples"],
}


@dataclass
class RunContext:
    root: Path
    config_path: Path
    config: Dict[str, Any]
    config_hash: str
    timestamp: str
    seed: int
    results_dir: Path
    figures_dir: Path
    status_rows: List[Dict[str, Any]] = field(default_factory=list)
    missing_feature_rows: List[Dict[str, Any]] = field(default_factory=list)
    missing_feature_keys: set[str] = field(default_factory=set)

    def provenance(self, input_files: Iterable[Path | str] = ()) -> Dict[str, Any]:
        names = []
        for path in input_files:
            text = str(path)
            names.append(text)
        return {
            "timestamp": self.timestamp,
            "config_hash": self.config_hash,
            "input_files": ";".join(names),
            "random_seed": self.seed,
        }

    def report(self, artifact: str, status: str, reason: str, input_files: Iterable[Path | str] = ()) -> None:
        row = self.provenance(input_files)
        row.update({"artifact": artifact, "status": status, "reason": reason})
        self.status_rows.append(row)
        print(f"{status}: {artifact}: {reason}")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_config(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError(f"PyYAML import failed: {YAML_IMPORT_ERROR}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ensure_dirs(root: Path, config: Dict[str, Any]) -> Tuple[Path, Path]:
    paths = config.get("paths", {})
    results_dir = root / paths.get("results", "results/")
    figures_dir = root / paths.get("figures", "figures/")
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    return results_dir, figures_dir


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def table_path(ctx: RunContext, key: str) -> Path:
    configured = ctx.config.get("tables", {}).get(key)
    if configured:
        return ctx.root / configured
    return ctx.results_dir / f"{key}.csv"


def error_row(ctx: RunContext, reason: str, input_files: Iterable[Path | str] = ()) -> Dict[str, Any]:
    row = ctx.provenance(input_files)
    row.update({"status": "ERROR", "reason": reason})
    return row


def skipped_row(ctx: RunContext, reason: str, input_files: Iterable[Path | str] = ()) -> Dict[str, Any]:
    row = ctx.provenance(input_files)
    row.update({"status": "SKIPPED", "reason": reason})
    return row


def write_table(ctx: RunContext, key: str, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        rows = [skipped_row(ctx, "No computable rows were produced.")]
    write_csv(table_path(ctx, key), TABLE_HEADERS[key], rows)


def library_versions() -> Dict[str, str]:
    libs = {
        "python": sys.version.replace("/n", " "),
        "platform": platform.platform(),
        "numpy": getattr(np, "__version__", "unknown"),
        "pandas": getattr(pd, "__version__", "unknown"),
    }
    for name in ["sklearn", "matplotlib", "scipy", "xgboost", "ee"]:
        try:
            mod = __import__(name)
        except Exception as exc:
            libs[name] = f"ERROR: {type(exc).__name__}: {exc}"
        else:
            libs[name] = getattr(mod, "__version__", "available")
    return libs


def write_run_log(
    ctx: RunContext,
    asset_rows: Sequence[Dict[str, Any]],
    class_count_rows: Sequence[Dict[str, Any]],
) -> None:
    log_path = ctx.results_dir / f"RUN_LOG_{ctx.timestamp}.txt"
    lines = [
        f"timestamp_utc: {ctx.timestamp}",
        f"config_path: {ctx.config_path}",
        f"config_hash_sha256: {ctx.config_hash}",
        f"random_seed: {ctx.seed}",
        "",
        "[config]",
        json.dumps(ctx.config, indent=2, sort_keys=True),
        "",
        "[assets]",
        json.dumps(asset_rows, indent=2, sort_keys=True),
        "",
        "[per_class_sample_counts]",
        json.dumps(class_count_rows, indent=2, sort_keys=True),
        "",
        "[library_versions]",
        json.dumps(library_versions(), indent=2, sort_keys=True),
        "",
    ]
    log_path.write_text("/n".join(lines), encoding="utf-8")


def verify_gee_assets(ctx: RunContext) -> List[Dict[str, Any]]:
    assets = ctx.config.get("assets", {})
    rows: List[Dict[str, Any]] = []
    prov = ctx.provenance([ctx.config_path])

    try:
        import ee  # type: ignore
    except Exception as exc:
        reason = f"earthengine-api import failed: {type(exc).__name__}: {exc}"
        for key, asset_id in assets.items():
            row = dict(prov)
            row.update({"asset_key": key, "asset_id": asset_id, "status": "ERROR", "reason": reason, "bands": ""})
            rows.append(row)
        ctx.report("gee_asset_verification", "ERROR", reason, [ctx.config_path])
        write_csv(ctx.results_dir / "gee_asset_verification.csv", list(rows[0].keys()) if rows else [], rows)
        return rows

    try:
        ee.Initialize()
    except Exception as exc:
        reason = f"Earth Engine initialization failed. Authenticate/configure GEE before export: {type(exc).__name__}: {exc}"
        for key, asset_id in assets.items():
            row = dict(prov)
            row.update({"asset_key": key, "asset_id": asset_id, "status": "ERROR", "reason": reason, "bands": ""})
            rows.append(row)
        ctx.report("gee_asset_verification", "ERROR", reason, [ctx.config_path])
        write_csv(ctx.results_dir / "gee_asset_verification.csv", list(rows[0].keys()) if rows else [], rows)
        return rows

    for key, asset_id in assets.items():
        row = dict(prov)
        row.update({"asset_key": key, "asset_id": asset_id})
        if key == "s1_grd":
            try:
                bbox = ctx.config.get("study_area", {}).get("bbox")
                year = int(ctx.config.get("year", 2024))
                if not bbox or len(bbox) != 4:
                    raise RuntimeError("study_area.bbox is required for scoped S1 band verification.")
                start, end = f"{year}-01-01", f"{year + 1}-01-01"
                geom = ee.Geometry.Rectangle([float(x) for x in bbox])
                collection = ee.ImageCollection(asset_id).filterBounds(geom).filterDate(start, end)
                image_count = int(collection.size().getInfo())
                if image_count <= 0:
                    raise RuntimeError("S1 collection is empty after study-area/year filtering.")
                bands = list(collection.median().bandNames().getInfo())
                row.update(
                    {
                        "asset_type": "ImageCollection.filtered_median",
                        "status": "OK",
                        "reason": "",
                        "bands": "|".join(bands),
                        "audit_scope": "study_area_year_filtered",
                        "filter": f"bounds=study_area.bbox;date={start}/{end}",
                        "image_count": image_count,
                    }
                )
            except Exception as exc:
                row.update(
                    {
                        "asset_type": "ImageCollection.filtered_median",
                        "status": "ERROR",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "bands": "",
                        "audit_scope": "study_area_year_filtered",
                        "filter": "",
                        "image_count": "",
                    }
                )
                ctx.report("gee_asset_verification", "ERROR", f"{asset_id}: {row['reason']}", [ctx.config_path])
            rows.append(row)
            continue
        bands: Optional[List[str]] = None
        reasons: List[str] = []
        for mode in ["ImageCollection", "Image"]:
            try:
                if mode == "ImageCollection":
                    image = ee.ImageCollection(asset_id).limit(1).first()
                else:
                    image = ee.Image(asset_id)
                band_info = image.bandNames().getInfo()
                if band_info:
                    bands = list(band_info)
                    row["asset_type"] = mode
                    break
            except Exception as exc:  # pragma: no cover - live GEE branch
                reasons.append(f"{mode}: {type(exc).__name__}: {exc}")
        if bands:
            row.update({"status": "OK", "reason": "", "bands": "|".join(bands), "audit_scope": "broad_live_asset_check", "filter": "", "image_count": ""})
        else:
            row.update({"status": "ERROR", "reason": "; ".join(reasons), "bands": "", "audit_scope": "broad_live_asset_check", "filter": "", "image_count": ""})
            ctx.report("gee_asset_verification", "ERROR", f"{asset_id}: {row['reason']}", [ctx.config_path])
        rows.append(row)

    fieldnames = BASE_TABLE_COLUMNS + ["asset_key", "asset_id", "asset_type", "bands", "audit_scope", "filter", "image_count"]
    write_csv(ctx.results_dir / "gee_asset_verification.csv", fieldnames, rows)
    return rows


def parse_bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def load_reference_samples(ctx: RunContext) -> Tuple[Optional[pd.DataFrame], List[Dict[str, Any]]]:
    ref_cfg = ctx.config.get("reference_samples", {})
    ref_path = ctx.root / ref_cfg.get("file", "data/reference_samples.csv")
    audit_rows: List[Dict[str, Any]] = []
    class_rows: List[Dict[str, Any]] = []

    if not ref_path.exists():
        reason = "Missing data/reference_samples.csv. Final reference labels must come from verified rows in this file."
        ctx.report("reference_samples", "ERROR", reason, [ref_path])
        audit_rows.append(error_row(ctx, reason, [ref_path]))
        write_csv(ctx.results_dir / "reference_sample_audit.csv", BASE_TABLE_COLUMNS, audit_rows)
        return None, class_rows

    try:
        df = pd.read_csv(ref_path)
    except Exception as exc:
        reason = f"Could not read reference samples: {type(exc).__name__}: {exc}"
        ctx.report("reference_samples", "ERROR", reason, [ref_path])
        audit_rows.append(error_row(ctx, reason, [ref_path]))
        write_csv(ctx.results_dir / "reference_sample_audit.csv", BASE_TABLE_COLUMNS, audit_rows)
        return None, class_rows

    required = [
        ref_cfg.get("id_column", "sample_id"),
        ref_cfg.get("verified_column", "verified"),
        ref_cfg.get("longitude_column", "longitude"),
        ref_cfg.get("latitude_column", "latitude"),
        ref_cfg.get("class_code_column", "class_code"),
        ref_cfg.get("class_name_column", "class_name"),
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        reason = "reference_samples.csv is missing required columns: " + ", ".join(missing)
        ctx.report("reference_samples", "ERROR", reason, [ref_path])
        audit_rows.append(error_row(ctx, reason, [ref_path]))
        write_csv(ctx.results_dir / "reference_sample_audit.csv", BASE_TABLE_COLUMNS, audit_rows)
        return None, class_rows

    verified_col = ref_cfg.get("verified_column", "verified")
    df = df.copy()
    df["_verified_bool"] = parse_bool_series(df[verified_col])
    verified = df[df["_verified_bool"]].copy()

    if verified.empty:
        reason = "No rows have verified == True. Weak labels cannot be used as ground truth."
        ctx.report("reference_samples", "ERROR", reason, [ref_path])
        audit_rows.append(error_row(ctx, reason, [ref_path]))
        write_csv(ctx.results_dir / "reference_sample_audit.csv", BASE_TABLE_COLUMNS, audit_rows)
        return None, class_rows

    code_col = ref_cfg.get("class_code_column", "class_code")
    name_col = ref_cfg.get("class_name_column", "class_name")
    count_df = (
        verified.groupby([code_col, name_col], dropna=False)
        .size()
        .reset_index(name="verified_count")
        .sort_values([code_col, name_col])
    )
    for _, rec in count_df.iterrows():
        row = ctx.provenance([ref_path])
        row.update(
            {
                "status": "OK",
                "reason": "",
                "class_code": rec[code_col],
                "class_name": rec[name_col],
                "verified_count": int(rec["verified_count"]),
            }
        )
        class_rows.append(row)

    audit_rows.append(
        {
            **ctx.provenance([ref_path]),
            "status": "OK",
            "reason": "",
            "total_rows": len(df),
            "verified_rows": len(verified),
        }
    )
    write_csv(ctx.results_dir / "reference_sample_audit.csv", BASE_TABLE_COLUMNS + ["total_rows", "verified_rows"], audit_rows)
    write_csv(
        ctx.results_dir / "class_counts_verified.csv",
        BASE_TABLE_COLUMNS + ["class_code", "class_name", "verified_count"],
        class_rows,
    )
    return verified, class_rows


def validate_study_area(ctx: RunContext) -> bool:
    bbox = ctx.config.get("study_area", {}).get("bbox", [])
    if not isinstance(bbox, list) or len(bbox) != 4:
        reason = "study_area.bbox is not set to a 4-value WGS84 bbox. GEE extraction is blocked."
        ctx.report("study_area", "ERROR", reason, [ctx.config_path])
        write_csv(ctx.results_dir / "study_area_audit.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [ctx.config_path])])
        return False
    row = ctx.provenance([ctx.config_path])
    row.update({"status": "OK", "reason": "", "bbox": json.dumps(bbox)})
    write_csv(ctx.results_dir / "study_area_audit.csv", BASE_TABLE_COLUMNS + ["bbox"], [row])
    return True


def project_lonlat_to_meters(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 110_574.0
    return np.column_stack([x, y])


def compute_variogram(ctx: RunContext, ref: pd.DataFrame) -> Optional[Dict[str, Any]]:
    ref_cfg = ctx.config.get("reference_samples", {})
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")
    variable = ctx.config.get("variogram", {}).get("variable", ref_cfg.get("class_code_column", "class_code"))
    n_bins = int(ctx.config.get("variogram", {}).get("n_bins", 12))
    max_pairs = int(ctx.config.get("variogram", {}).get("max_pair_count", 250000))
    sill_fraction = float(ctx.config.get("variogram", {}).get("sill_fraction_for_range", 0.95))
    ref_path = ctx.root / ref_cfg.get("file", "data/reference_samples.csv")

    needed = [lon_col, lat_col, variable]
    missing = [col for col in needed if col not in ref.columns]
    if missing:
        reason = "Cannot compute variogram; missing columns: " + ", ".join(missing)
        ctx.report("variogram", "ERROR", reason, [ref_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [ref_path])])
        return None

    work = ref[needed].dropna().copy()
    if len(work) < 3:
        reason = "Cannot compute variogram; fewer than 3 verified samples with coordinates and variable."
        ctx.report("variogram", "ERROR", reason, [ref_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [ref_path])])
        return None

    lon = work[lon_col].astype(float).to_numpy()
    lat = work[lat_col].astype(float).to_numpy()
    z = work[variable].astype(float).to_numpy()
    coords = project_lonlat_to_meters(lon, lat)
    n = len(work)
    total_pairs = n * (n - 1) // 2
    rng = np.random.default_rng(ctx.seed)

    if total_pairs <= max_pairs:
        i_idx, j_idx = np.triu_indices(n, k=1)
    else:
        i_idx = rng.integers(0, n, size=max_pairs)
        j_idx = rng.integers(0, n, size=max_pairs)
        keep = i_idx != j_idx
        i_idx = i_idx[keep]
        j_idx = j_idx[keep]

    distances = np.linalg.norm(coords[i_idx] - coords[j_idx], axis=1)
    semivar = 0.5 * (z[i_idx] - z[j_idx]) ** 2
    keep = np.isfinite(distances) & np.isfinite(semivar) & (distances > 0)
    distances = distances[keep]
    semivar = semivar[keep]

    if len(distances) < n_bins:
        reason = "Cannot compute variogram; too few positive-distance pairs for configured bins."
        ctx.report("variogram", "ERROR", reason, [ref_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [ref_path])])
        return None

    edges = np.linspace(0, float(np.nanmax(distances)), n_bins + 1)
    rows: List[Dict[str, Any]] = []
    mids: List[float] = []
    gammas: List[float] = []
    for idx in range(n_bins):
        lo, hi = edges[idx], edges[idx + 1]
        in_bin = (distances >= lo) & (distances < hi if idx < n_bins - 1 else distances <= hi)
        if not np.any(in_bin):
            continue
        gamma = float(np.nanmean(semivar[in_bin]))
        midpoint = float((lo + hi) / 2.0)
        mids.append(midpoint)
        gammas.append(gamma)
        row = ctx.provenance([ref_path])
        row.update(
            {
                "status": "OK",
                "reason": "",
                "bin": idx + 1,
                "distance_midpoint_m": midpoint,
                "semivariance": gamma,
                "pair_count": int(np.sum(in_bin)),
                "variable": variable,
            }
        )
        rows.append(row)

    if not gammas or max(gammas) <= 0:
        reason = "Cannot choose variogram range; empirical sill is zero or unavailable."
        ctx.report("variogram", "ERROR", reason, [ref_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [ref_path])])
        return None

    sill = float(max(gammas))
    threshold = sill_fraction * sill
    chosen_range = None
    for midpoint, gamma in zip(mids, gammas):
        if gamma >= threshold:
            chosen_range = float(midpoint)
            break
    if chosen_range is None:
        chosen_range = float(mids[-1])

    write_csv(
        ctx.results_dir / "variogram_bins.csv",
        BASE_TABLE_COLUMNS + ["bin", "distance_midpoint_m", "semivariance", "pair_count", "variable"],
        rows,
    )
    choice = {
        **ctx.provenance([ref_path]),
        "status": "OK",
        "reason": "",
        "variable": variable,
        "sill": sill,
        "sill_fraction_for_range": sill_fraction,
        "range_threshold": threshold,
        "chosen_block_distance_m": chosen_range,
        "n_samples": int(n),
        "pair_count_used": int(len(distances)),
    }
    write_json(ctx.results_dir / "variogram_choice.json", choice)

    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=160)
        ax.plot(mids, gammas, marker="o", color="#235789", linewidth=1.8)
        ax.axhline(threshold, color="#C1292E", linestyle="--", linewidth=1.2)
        ax.axvline(chosen_range, color="#C1292E", linestyle=":", linewidth=1.2)
        ax.set_xlabel("Pair distance midpoint (m)")
        ax.set_ylabel("Empirical semivariance")
        ax.set_title("Empirical variogram and derived spatial block distance")
        ax.grid(True, linewidth=0.3, alpha=0.5)
        fig.tight_layout()
        fig.savefig(ctx.figures_dir / "variogram_range.png")
        plt.close(fig)
    except Exception as exc:
        ctx.report("variogram_plot", "ERROR", f"Could not save variogram plot: {type(exc).__name__}: {exc}", [ref_path])

    return choice


def load_precomputed_variogram_choice(ctx: RunContext) -> Optional[Dict[str, Any]]:
    variogram_cfg = ctx.config.get("variogram", {})
    source_value = variogram_cfg.get("precomputed_indicator_summary_file")
    if not source_value:
        return None

    source_path = (ctx.root / source_value).resolve()
    if not source_path.exists():
        reason = f"Configured precomputed indicator variogram summary is missing: {source_path}"
        ctx.report("variogram_precomputed_choice", "ERROR", reason, [ctx.config_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [ctx.config_path])])
        return None

    try:
        with source_path.open("r", encoding="utf-8") as fh:
            summary = json.load(fh)
    except Exception as exc:
        reason = f"Could not read precomputed indicator variogram summary: {type(exc).__name__}: {exc}"
        ctx.report("variogram_precomputed_choice", "ERROR", reason, [source_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [source_path])])
        return None

    distance = summary.get("suggested_block_distance_m")
    if distance is None:
        reason = "Precomputed indicator variogram summary lacks suggested_block_distance_m."
        ctx.report("variogram_precomputed_choice", "ERROR", reason, [source_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [source_path])])
        return None

    try:
        distance_float = float(distance)
    except Exception:
        reason = f"Precomputed indicator variogram distance is not numeric: {distance}"
        ctx.report("variogram_precomputed_choice", "ERROR", reason, [source_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [source_path])])
        return None

    if not np.isfinite(distance_float) or distance_float <= 0:
        reason = f"Precomputed indicator variogram distance is invalid: {distance}"
        ctx.report("variogram_precomputed_choice", "ERROR", reason, [source_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [source_path])])
        return None

    source_method = summary.get("method", "")
    if "indicator" not in str(source_method).lower():
        reason = "Precomputed variogram summary is not marked as an indicator-variogram method."
        ctx.report("variogram_precomputed_choice", "ERROR", reason, [source_path])
        write_csv(ctx.results_dir / "variogram_bins.csv", BASE_TABLE_COLUMNS, [error_row(ctx, reason, [source_path])])
        return None

    row = ctx.provenance([ctx.config_path, source_path])
    row.update(
        {
            "status": "OK",
            "reason": "Using code-generated one-vs-rest indicator variogram summary as the spatial block-distance source.",
            "bin": "",
            "distance_midpoint_m": "",
            "semivariance": "",
            "pair_count": "",
            "variable": "one_vs_rest_indicator_summary",
        }
    )
    write_csv(
        ctx.results_dir / "variogram_bins.csv",
        BASE_TABLE_COLUMNS + ["bin", "distance_midpoint_m", "semivariance", "pair_count", "variable"],
        [row],
    )
    choice = {
        **ctx.provenance([ctx.config_path, source_path]),
        "status": "OK",
        "reason": "Using code-generated one-vs-rest indicator variogram summary as the spatial block-distance source.",
        "variable": "one_vs_rest_indicator_summary",
        "method": source_method,
        "chosen_block_distance_m": distance_float,
        "chosen_block_distance_source": str(source_path),
        "source_summary_sha256": sha256_file(source_path),
        "source_reference_file": summary.get("reference_file", ""),
        "source_reference_sha256": summary.get("reference_sha256", ""),
        "source_block_distance_rule": summary.get("block_distance_rule", ""),
        "n_samples": summary.get("verified_rows", ""),
        "pair_count_used": "",
        "sill": "",
        "sill_fraction_for_range": summary.get("sill_fraction_for_range", ""),
        "range_threshold": "",
    }
    write_json(ctx.results_dir / "variogram_choice.json", choice)
    ctx.report("variogram_precomputed_choice", "OK", f"Using indicator-derived block distance {distance_float} m.", [source_path])
    return choice


def feature_columns(df: pd.DataFrame, id_col: str) -> List[str]:
    excluded = {id_col}
    cols = [col for col in df.columns if col not in excluded and pd.api.types.is_numeric_dtype(df[col])]
    return cols


def read_feature_stack(ctx: RunContext, stack_key: str, stack_cfg: Dict[str, Any], ref: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], str]:
    ref_cfg = ctx.config.get("reference_samples", {})
    id_col = ref_cfg.get("id_column", "sample_id")
    path = ctx.root / stack_cfg.get("file", f"data/features/{stack_key}.csv")
    if not path.exists():
        return None, f"Missing feature file for {stack_key}: {path}"
    try:
        feat = pd.read_csv(path)
    except Exception as exc:
        return None, f"Could not read {path}: {type(exc).__name__}: {exc}"
    if id_col not in feat.columns:
        return None, f"{path} is missing id column {id_col}"
    numeric = feature_columns(feat, id_col)
    if not numeric:
        return None, f"{path} has no numeric feature columns"
    merged = ref.merge(feat[[id_col] + numeric], on=id_col, how="inner")
    if merged.empty:
        return None, f"{path} has no sample_id overlap with verified reference samples"
    merged = apply_missing_feature_policy(ctx, stack_key, path, merged, numeric)
    merged.attrs["feature_columns"] = numeric
    return merged, ""


def apply_missing_feature_policy(ctx: RunContext, stack_key: str, path: Path, merged: pd.DataFrame, feature_cols: Sequence[str]) -> pd.DataFrame:
    preprocessing = ctx.config.get("preprocessing", {})
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
            reason = (
                f"{sentinel_cells} cells equal missing_feature_sentinel={sentinel}; "
                "set preprocessing.missing_feature_policy to sentinel_to_nan_then_median_impute or remove the sentinel."
            )
            ctx.report("missing_feature_policy", "ERROR", reason, [path])
    nan_after = int(features.isna().sum().sum())
    rows_missing_after = int(features.isna().any(axis=1).sum())
    work.loc[:, feature_cols] = features

    audit_key = f"{stack_key}|{path}|{policy}|{sentinel}"
    if audit_key not in ctx.missing_feature_keys:
        ctx.missing_feature_keys.add(audit_key)
        row = ctx.provenance([path])
        row.update(
            {
                "status": status,
                "reason": reason,
                "stack": stack_key,
                "feature_file": str(path),
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
        ctx.missing_feature_rows.append(row)
    return work


def apply_global_low_count_policy(ctx: RunContext, df: pd.DataFrame, source: str) -> pd.DataFrame:
    ref_cfg = ctx.config.get("reference_samples", {})
    code_col = ref_cfg.get("class_code_column", "class_code")
    name_col = ref_cfg.get("class_name_column", "class_name")
    min_count = int(ctx.config.get("min_class_count", 30))
    policy = ctx.config.get("low_count_policy", "drop")
    counts = df.groupby(code_col).size()
    low_codes = [code for code, count in counts.items() if count < min_count]
    rows: List[Dict[str, Any]] = []
    for code in low_codes:
        names = sorted(set(df.loc[df[code_col] == code, name_col].astype(str))) if name_col in df.columns else [""]
        row = ctx.provenance([source])
        row.update(
            {
                "status": "OK",
                "reason": f"class has fewer samples than min_class_count={min_count}",
                "scope": "global_verified_samples",
                "policy": policy,
                "class_code": code,
                "class_name": "|".join(names),
                "sample_count": int(counts.loc[code]),
            }
        )
        rows.append(row)
        ctx.report("class_merge_drop", "SKIPPED" if policy != "drop" else "OK", row["reason"], [source])
    if rows:
        write_csv(
            ctx.results_dir / "class_merge_drop_log.csv",
            BASE_TABLE_COLUMNS + ["scope", "policy", "class_code", "class_name", "sample_count"],
            rows,
        )
    if policy == "drop" and low_codes:
        return df[~df[code_col].isin(low_codes)].copy()
    if low_codes:
        raise RuntimeError("Only low_count_policy: drop is implemented. Configure drop or implement an explicit merge map.")
    return df


def make_model(ctx: RunContext, model_name: str, labels: np.ndarray):
    if model_name == "RandomForest":
        from sklearn.ensemble import RandomForestClassifier

        params = dict(ctx.config.get("random_forest", {}))
        params["random_state"] = ctx.seed
        return RandomForestClassifier(**params), None
    if model_name == "XGBoost":
        try:
            from xgboost import XGBClassifier
        except Exception as exc:
            return None, f"XGBoost unavailable: {type(exc).__name__}: {exc}"
        params = dict(ctx.config.get("xgboost", {}))
        n_classes = len(np.unique(labels))
        if n_classes <= 2:
            params.update({"random_state": ctx.seed, "eval_metric": "logloss", "objective": "binary:logistic"})
        else:
            params.update(
                {
                    "random_state": ctx.seed,
                    "eval_metric": "mlogloss",
                    "objective": "multi:softprob",
                    "num_class": n_classes,
                }
            )
        return XGBClassifier(**params), None
    return None, f"Unknown model {model_name}"


def train_predict(model_obj: Any, model_name: str, X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    X_train, X_test = fit_transform_features(X_train, X_test)
    if model_name == "XGBoost":
        from sklearn.preprocessing import LabelEncoder

        model = model_obj
        encoder = LabelEncoder()
        encoder.fit(y_train)
        y_train_enc = encoder.transform(y_train)
        model.fit(X_train, y_train_enc)
        pred_enc = model.predict(X_test)
        pred = encoder.inverse_transform(pred_enc.astype(int))
        proba = model.predict_proba(X_test)
        return pred, proba
    model = model_obj
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)
    return pred, proba


def fit_transform_features(X_train: np.ndarray, *others: np.ndarray) -> Tuple[np.ndarray, ...]:
    """Apply the same deterministic preprocessing to every feature stack."""
    from sklearn.impute import SimpleImputer

    imputer = SimpleImputer(strategy="median")
    train_out = imputer.fit_transform(X_train)
    outputs = [train_out]
    for arr in others:
        outputs.append(imputer.transform(arr))
    return tuple(outputs)


def metric_rows_for_fold(
    ctx: RunContext,
    stack: str,
    stack_label: str,
    model_name: str,
    split: str,
    fold: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    proba: Optional[np.ndarray],
    input_files: Iterable[Path | str],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

    row = ctx.provenance(input_files)
    row.update(
        {
            "status": "OK",
            "reason": "",
            "stack": stack,
            "stack_label": stack_label,
            "model": model_name,
            "split": split,
            "fold": fold,
            "oa": float(accuracy_score(y_true, y_pred)),
            "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        }
    )

    ece_row = ctx.provenance(input_files)
    if proba is None or len(proba) == 0:
        ece_row.update({"status": "SKIPPED", "reason": "predict_proba unavailable", "stack": stack, "model": model_name, "split": split, "fold": fold})
    else:
        ece = expected_calibration_error(y_true, y_pred, proba)
        ece_row.update(
            {
                "status": "OK",
                "reason": "",
                "stack": stack,
                "model": model_name,
                "split": split,
                "fold": fold,
                "ece": ece,
                "n_samples": len(y_true),
                "n_bins": 10,
            }
        )

    labels = sorted(set(y_true) | set(y_pred))
    p, r, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    per_class = []
    for label, pp, rr, ff, ss in zip(labels, p, r, f1, support):
        pr = ctx.provenance(input_files)
        pr.update(
            {
                "status": "OK",
                "reason": "",
                "stack": stack,
                "model": model_name,
                "split": split,
                "fold": fold,
                "class_code": label,
                "precision": float(pp),
                "recall": float(rr),
                "f1": float(ff),
                "support": int(ss),
            }
        )
        per_class.append(pr)
    return row, ece_row, per_class


def expected_calibration_error(y_true: np.ndarray, y_pred: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    confidences = np.max(proba, axis=1)
    correct = (y_true == y_pred).astype(float)
    ece = 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for idx in range(n_bins):
        lo, hi = edges[idx], edges[idx + 1]
        mask = (confidences >= lo) & (confidences <= hi if idx == n_bins - 1 else confidences < hi)
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(float(np.mean(correct[mask])) - float(np.mean(confidences[mask])))
    return ece


def random_folds(ctx: RunContext, y: np.ndarray) -> Optional[List[Tuple[np.ndarray, np.ndarray, str]]]:
    try:
        from sklearn.model_selection import StratifiedKFold
    except Exception as exc:
        ctx.report("random_folds", "ERROR", f"scikit-learn unavailable: {type(exc).__name__}: {exc}")
        return None
    k = int(ctx.config.get("cv", {}).get("k_folds", 5))
    counts = pd.Series(y).value_counts()
    if counts.min() < k:
        ctx.report("random_folds", "SKIPPED", f"At least one class has fewer than k_folds={k} samples after filtering.")
        return None
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=ctx.seed)
    return [(train, test, str(i + 1)) for i, (train, test) in enumerate(skf.split(np.zeros(len(y)), y))]


def spatial_folds(ctx: RunContext, coords: np.ndarray, block_distance_m: float) -> Optional[List[Tuple[np.ndarray, np.ndarray, str]]]:
    k = int(ctx.config.get("cv", {}).get("k_folds", 5))
    if not np.isfinite(block_distance_m) or block_distance_m <= 0:
        reason = "Invalid variogram-derived block distance."
        ctx.report("spatial_folds", "ERROR", reason)
        row = error_row(ctx, reason, ["verified_reference_samples"])
        row.update(
            {
                "fold": "",
                "train_count": "",
                "test_count": "",
                "buffered_out_count": "",
                "block_distance_m": block_distance_m,
                "minimum_train_test_distance_m": "",
                "zero_leakage_assertion": "",
                "available_spatial_blocks": "",
                "required_spatial_blocks": k,
            }
        )
        write_csv(
            ctx.results_dir / "spatial_fold_leakage_audit.csv",
            BASE_TABLE_COLUMNS
            + [
                "fold",
                "train_count",
                "test_count",
                "buffered_out_count",
                "block_distance_m",
                "minimum_train_test_distance_m",
                "zero_leakage_assertion",
                "available_spatial_blocks",
                "required_spatial_blocks",
            ],
            [row],
        )
        return None
    cells_x = np.floor(coords[:, 0] / block_distance_m).astype(int)
    cells_y = np.floor(coords[:, 1] / block_distance_m).astype(int)
    cell_ids = np.array([f"{x}:{y}" for x, y in zip(cells_x, cells_y)])
    unique_cells = np.unique(cell_ids)
    if len(unique_cells) < k:
        reason = f"Only {len(unique_cells)} spatial blocks are available for k_folds={k}."
        ctx.report("spatial_folds", "SKIPPED", reason)
        row = skipped_row(ctx, reason, ["verified_reference_samples"])
        row.update(
            {
                "fold": "",
                "train_count": "",
                "test_count": "",
                "buffered_out_count": "",
                "block_distance_m": block_distance_m,
                "minimum_train_test_distance_m": "",
                "zero_leakage_assertion": "",
                "available_spatial_blocks": int(len(unique_cells)),
                "required_spatial_blocks": k,
            }
        )
        write_csv(
            ctx.results_dir / "spatial_fold_leakage_audit.csv",
            BASE_TABLE_COLUMNS
            + [
                "fold",
                "train_count",
                "test_count",
                "buffered_out_count",
                "block_distance_m",
                "minimum_train_test_distance_m",
                "zero_leakage_assertion",
                "available_spatial_blocks",
                "required_spatial_blocks",
            ],
            [row],
        )
        return None
    rng = np.random.default_rng(ctx.seed)
    shuffled = unique_cells.copy()
    rng.shuffle(shuffled)
    cell_to_fold = {cell: idx % k for idx, cell in enumerate(shuffled)}
    folds = []
    fold_audit_rows = []
    for fold_idx in range(k):
        test_mask = np.array([cell_to_fold[cell] == fold_idx for cell in cell_ids])
        if not np.any(test_mask):
            continue
        near_test = within_distance_mask(coords, coords[test_mask], block_distance_m)
        train_mask = (~test_mask) & (~near_test)
        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]
        leakage_ok, min_dist = leakage_assertion(coords[train_idx], coords[test_idx], block_distance_m)
        empty_partition = len(train_idx) == 0 or len(test_idx) == 0
        row = ctx.provenance(["verified_reference_samples"])
        row.update(
            {
                "status": "ERROR" if not leakage_ok else ("SKIPPED" if empty_partition else "OK"),
                "reason": (
                    "test sample lies within block distance of training sample"
                    if not leakage_ok
                    else ("Empty train or test partition after spatial buffering." if empty_partition else "")
                ),
                "fold": fold_idx + 1,
                "train_count": int(len(train_idx)),
                "test_count": int(len(test_idx)),
                "buffered_out_count": int(np.sum((~test_mask) & near_test)),
                "block_distance_m": block_distance_m,
                "minimum_train_test_distance_m": min_dist,
                "zero_leakage_assertion": bool(leakage_ok),
                "available_spatial_blocks": int(len(unique_cells)),
                "required_spatial_blocks": k,
            }
        )
        fold_audit_rows.append(row)
        if not leakage_ok:
            ctx.report("spatial_folds", "ERROR", f"Leakage assertion failed for fold {fold_idx + 1}.")
            write_csv(
                ctx.results_dir / "spatial_fold_leakage_audit.csv",
                BASE_TABLE_COLUMNS
                + [
                    "fold",
                    "train_count",
                    "test_count",
                    "buffered_out_count",
                    "block_distance_m",
                    "minimum_train_test_distance_m",
                    "zero_leakage_assertion",
                    "available_spatial_blocks",
                    "required_spatial_blocks",
                ],
                fold_audit_rows,
            )
            return None
        folds.append((train_idx, test_idx, str(fold_idx + 1)))
    write_csv(
        ctx.results_dir / "spatial_fold_leakage_audit.csv",
        BASE_TABLE_COLUMNS
        + [
            "fold",
            "train_count",
            "test_count",
            "buffered_out_count",
            "block_distance_m",
            "minimum_train_test_distance_m",
            "zero_leakage_assertion",
            "available_spatial_blocks",
            "required_spatial_blocks",
        ],
        fold_audit_rows,
    )
    return folds


def within_distance_mask(all_coords: np.ndarray, query_coords: np.ndarray, distance: float) -> np.ndarray:
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(all_coords)
        query_tree = cKDTree(query_coords)
        pairs = tree.query_ball_tree(query_tree, r=distance)
        return np.array([len(p) > 0 for p in pairs], dtype=bool)
    except Exception:
        distances = np.linalg.norm(all_coords[:, None, :] - query_coords[None, :, :], axis=2)
        return np.any(distances <= distance, axis=1)


def leakage_assertion(train_coords: np.ndarray, test_coords: np.ndarray, distance: float) -> Tuple[bool, float]:
    if len(train_coords) == 0 or len(test_coords) == 0:
        return True, float("inf")
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(train_coords)
        dists, _ = tree.query(test_coords, k=1)
        min_dist = float(np.min(dists))
    except Exception:
        dists = np.linalg.norm(train_coords[:, None, :] - test_coords[None, :, :], axis=2)
        min_dist = float(np.min(dists))
    return min_dist >= distance, min_dist


def evaluate_feature_stacks(
    ctx: RunContext,
    ref: Optional[pd.DataFrame],
    variogram_choice: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    table3_rows: List[Dict[str, Any]] = []
    table6_rows: List[Dict[str, Any]] = []
    per_class_rows: List[Dict[str, Any]] = []
    prediction_rows: List[Dict[str, Any]] = []
    ref_cfg = ctx.config.get("reference_samples", {})
    id_col = ref_cfg.get("id_column", "sample_id")
    code_col = ref_cfg.get("class_code_column", "class_code")
    name_col = ref_cfg.get("class_name_column", "class_name")
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")

    if ref is None:
        reason = "Verified reference samples are unavailable."
        for stack, cfg in ctx.config.get("feature_stacks", {}).items():
            for key, rows in [("table3", table3_rows), ("table6", table6_rows)]:
                row = error_row(ctx, reason, [cfg.get("file", "")])
                row.update({"stack": stack, "stack_label": cfg.get("label", ""), "model": "", "split": "", "fold": ""})
                rows.append(row)
        return table3_rows, table6_rows, per_class_rows

    ref_path = ctx.root / ref_cfg.get("file", "data/reference_samples.csv")
    filtered_ref = apply_global_low_count_policy(ctx, ref, str(ref_path))
    if filtered_ref.empty:
        reason = "All verified classes were dropped by min_class_count policy."
        for stack, cfg in ctx.config.get("feature_stacks", {}).items():
            row = error_row(ctx, reason, [ref_path, cfg.get("file", "")])
            row.update({"stack": stack, "stack_label": cfg.get("label", "")})
            table3_rows.append(row)
        return table3_rows, table6_rows, per_class_rows

    block_distance = None
    if variogram_choice and variogram_choice.get("status") == "OK":
        block_distance = float(variogram_choice["chosen_block_distance_m"])

    for stack, cfg in ctx.config.get("feature_stacks", {}).items():
        merged, reason = read_feature_stack(ctx, stack, cfg, filtered_ref)
        feature_path = ctx.root / cfg.get("file", f"data/features/{stack}.csv")
        if merged is None:
            ctx.report(f"feature_stack_{stack}", "ERROR", reason, [feature_path])
            for target_rows in [table3_rows, table6_rows]:
                row = error_row(ctx, reason, [ref_path, feature_path])
                row.update({"stack": stack, "stack_label": cfg.get("label", "")})
                target_rows.append(row)
            continue

        features = list(merged.attrs.get("feature_columns", []))
        if not features:
            features = feature_columns(merged, id_col)
        X = merged[features].to_numpy(dtype=float)
        y = merged[code_col].to_numpy()
        coords = project_lonlat_to_meters(merged[lon_col].astype(float).to_numpy(), merged[lat_col].astype(float).to_numpy())
        fold_sets: List[Tuple[str, Optional[List[Tuple[np.ndarray, np.ndarray, str]]]]] = [
            ("random", random_folds(ctx, y)),
            ("spatial", spatial_folds(ctx, coords, block_distance) if block_distance else None),
        ]
        if block_distance is None:
            row = error_row(ctx, "Spatial folds require a variogram-derived block distance.", [ref_path])
            row.update({"stack": stack, "stack_label": cfg.get("label", ""), "split": "spatial"})
            table3_rows.append(row)

        for model_name in ["RandomForest", "XGBoost"]:
            model_obj, model_reason = make_model(ctx, model_name, y)
            if model_reason:
                row = skipped_row(ctx, model_reason, [feature_path])
                row.update({"stack": stack, "stack_label": cfg.get("label", ""), "model": model_name})
                table3_rows.append(row)
                continue
            for split_name, folds in fold_sets:
                if not folds:
                    row = skipped_row(ctx, f"No valid {split_name} folds.", [ref_path, feature_path])
                    row.update({"stack": stack, "stack_label": cfg.get("label", ""), "model": model_name, "split": split_name})
                    table3_rows.append(row)
                    continue
                for train_idx, test_idx, fold_label in folds:
                    if len(train_idx) == 0 or len(test_idx) == 0:
                        row = skipped_row(ctx, "Empty train or test partition after spatial buffering.", [ref_path, feature_path])
                        row.update({"stack": stack, "stack_label": cfg.get("label", ""), "model": model_name, "split": split_name, "fold": fold_label})
                        table3_rows.append(row)
                        continue
                    try:
                        pred, proba = train_predict(model_obj, model_name, X[train_idx], y[train_idx], X[test_idx])
                    except Exception as exc:
                        row = error_row(ctx, f"Model fit/predict failed: {type(exc).__name__}: {exc}", [ref_path, feature_path])
                        row.update({"stack": stack, "stack_label": cfg.get("label", ""), "model": model_name, "split": split_name, "fold": fold_label})
                        table3_rows.append(row)
                        continue
                    mrow, erow, pcrows = metric_rows_for_fold(
                        ctx,
                        stack,
                        cfg.get("label", ""),
                        model_name,
                        split_name,
                        fold_label,
                        y[test_idx],
                        pred,
                        proba,
                        [ref_path, feature_path],
                    )
                    table3_rows.append(mrow)
                    table6_rows.append(erow)
                    per_class_rows.extend(pcrows)
                    for sample_id, true_y, pred_y, xx, yy in zip(
                        merged.iloc[test_idx][id_col], y[test_idx], pred, coords[test_idx, 0], coords[test_idx, 1]
                    ):
                        prow = ctx.provenance([ref_path, feature_path])
                        prow.update(
                            {
                                "status": "OK",
                                "reason": "",
                                "sample_id": sample_id,
                                "stack": stack,
                                "model": model_name,
                                "split": split_name,
                                "fold": fold_label,
                                "true_class_code": true_y,
                                "predicted_class_code": pred_y,
                                "x_m": xx,
                                "y_m": yy,
                                "incorrect": int(true_y != pred_y),
                            }
                        )
                        prediction_rows.append(prow)

    if per_class_rows:
        write_csv(
            ctx.results_dir / "per_class_metrics.csv",
            BASE_TABLE_COLUMNS + ["stack", "model", "split", "fold", "class_code", "precision", "recall", "f1", "support"],
            per_class_rows,
        )
    if prediction_rows:
        write_csv(
            ctx.results_dir / "predictions_by_fold.csv",
            BASE_TABLE_COLUMNS
            + ["sample_id", "stack", "model", "split", "fold", "true_class_code", "predicted_class_code", "x_m", "y_m", "incorrect"],
            prediction_rows,
        )
    return table3_rows, table6_rows, per_class_rows


def compute_derived_tables(ctx: RunContext, table3_rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ok_rows = [r for r in table3_rows if r.get("status") == "OK"]
    if not ok_rows:
        reason = "No OK rows in table3; derived comparisons cannot be computed."
        return [error_row(ctx, reason)], [error_row(ctx, reason)]
    df = pd.DataFrame(ok_rows)
    for col in ["oa", "macro_f1"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    summary = df.groupby(["stack", "model", "split"], as_index=False)[["oa", "macro_f1"]].mean()

    table4: List[Dict[str, Any]] = []
    for (stack, model), group in summary.groupby(["stack", "model"]):
        for metric in ["oa", "macro_f1"]:
            random_vals = group.loc[group["split"] == "random", metric]
            spatial_vals = group.loc[group["split"] == "spatial", metric]
            if random_vals.empty or spatial_vals.empty:
                row = skipped_row(ctx, "Both random and spatial summaries are required.")
                row.update({"stack": stack, "model": model, "metric": metric})
            else:
                random_value = float(random_vals.iloc[0])
                spatial_value = float(spatial_vals.iloc[0])
                row = ctx.provenance(["results/table3_accuracy_by_stack_split.csv"])
                row.update(
                    {
                        "status": "OK",
                        "reason": "",
                        "stack": stack,
                        "model": model,
                        "metric": metric,
                        "random_value": random_value,
                        "spatial_value": spatial_value,
                        "optimism_gap": random_value - spatial_value,
                    }
                )
            table4.append(row)

    table5: List[Dict[str, Any]] = []
    contrasts = [("B2_vs_B0", "B0", "B2"), ("B3_vs_B1", "B1", "B3")]
    for contrast, base, ae in contrasts:
        for (model, split), group in summary.groupby(["model", "split"]):
            for metric in ["oa", "macro_f1"]:
                b = group.loc[group["stack"] == base, metric]
                a = group.loc[group["stack"] == ae, metric]
                if b.empty or a.empty:
                    row = skipped_row(ctx, "Both contrast stacks are required.")
                    row.update({"contrast": contrast, "model": model, "split": split, "metric": metric})
                else:
                    base_value = float(b.iloc[0])
                    ae_value = float(a.iloc[0])
                    row = ctx.provenance(["results/table3_accuracy_by_stack_split.csv"])
                    row.update(
                        {
                            "status": "OK",
                            "reason": "",
                            "contrast": contrast,
                            "model": model,
                            "split": split,
                            "metric": metric,
                            "baseline_value": base_value,
                            "alphaearth_value": ae_value,
                            "difference": ae_value - base_value,
                        }
                    )
                table5.append(row)
    return table4, table5


def compute_conformal(
    ctx: RunContext,
    ref: Optional[pd.DataFrame],
    variogram_choice: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    decision_rows: List[Dict[str, Any]] = []
    alpha = float(ctx.config.get("cv", {}).get("conformal_alpha", 0.10))
    target_coverage = 1.0 - alpha
    ref_cfg = ctx.config.get("reference_samples", {})
    ref_path = ctx.root / ref_cfg.get("file", "data/reference_samples.csv")
    id_col = ref_cfg.get("id_column", "sample_id")
    code_col = ref_cfg.get("class_code_column", "class_code")
    name_col = ref_cfg.get("class_name_column", "class_name")
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")

    if ref is None:
        reason = "Verified reference samples are unavailable; conformal coverage cannot be computed."
        for stack, cfg in ctx.config.get("feature_stacks", {}).items():
            for model_name in ["RandomForest", "XGBoost"]:
                for split in ["random", "spatial"]:
                    row = error_row(ctx, reason, [cfg.get("file", "")])
                    row.update({"stack": stack, "model": model_name, "split": split, "alpha": alpha, "target_coverage": target_coverage})
                    rows.append(row)
        return rows

    min_count = int(ctx.config.get("min_class_count", 30))
    policy = ctx.config.get("low_count_policy", "drop")
    filtered_ref = apply_global_low_count_policy(ctx, ref, str(ref_path))
    block_distance = None
    if variogram_choice and variogram_choice.get("status") == "OK":
        block_distance = float(variogram_choice["chosen_block_distance_m"])

    for stack, cfg in ctx.config.get("feature_stacks", {}).items():
        feature_path = ctx.root / cfg.get("file", f"data/features/{stack}.csv")
        merged, reason = read_feature_stack(ctx, stack, cfg, filtered_ref)
        if merged is None:
            for model_name in ["RandomForest", "XGBoost"]:
                for split in ["random", "spatial"]:
                    row = error_row(ctx, reason, [ref_path, feature_path])
                    row.update({"stack": stack, "model": model_name, "split": split, "alpha": alpha, "target_coverage": target_coverage})
                    rows.append(row)
            continue

        features = list(merged.attrs.get("feature_columns", []))
        if not features:
            features = feature_columns(merged, id_col)
        X = merged[features].to_numpy(dtype=float)
        y = merged[code_col].to_numpy()
        class_name_map = {}
        if name_col in merged.columns:
            class_name_map = {
                code: str(name)
                for code, name in zip(merged[code_col].to_numpy(), merged[name_col].to_numpy())
            }
        coords = project_lonlat_to_meters(merged[lon_col].astype(float).to_numpy(), merged[lat_col].astype(float).to_numpy())
        splitters = {
            "random": conformal_random_split(ctx, y),
            "spatial": conformal_spatial_split(ctx, coords, block_distance, y=y, min_count=min_count) if block_distance else None,
        }
        if block_distance is None:
            row = error_row(ctx, "Spatial conformal split requires a variogram-derived block distance.", [ref_path])
            row.update({"stack": stack, "model": "RandomForest", "split": "spatial", "alpha": alpha, "target_coverage": target_coverage})
            rows.append(row)

        for model_name in ["RandomForest", "XGBoost"]:
            for split_name, parts in splitters.items():
                if parts is None:
                    row = skipped_row(ctx, f"No valid {split_name} train/calibration/test split.", [ref_path, feature_path])
                    row.update({"stack": stack, "model": model_name, "split": split_name, "alpha": alpha, "target_coverage": target_coverage})
                    rows.append(row)
                    continue
                train_idx, cal_idx, test_idx = parts
                retained = calibration_retained_classes(y[cal_idx], min_count)
                dropped = sorted(set(y[cal_idx]) - set(retained))
                for code in dropped:
                    drow = ctx.provenance([ref_path, feature_path])
                    drow.update(
                        {
                            "status": "OK",
                            "reason": f"calibration class has fewer samples than min_class_count={min_count}",
                            "scope": f"conformal_{split_name}",
                            "policy": policy,
                            "class_code": code,
                            "class_name": class_name_map.get(code, ""),
                            "sample_count": int(np.sum(y[cal_idx] == code)),
                        }
                    )
                    decision_rows.append(drow)
                if policy != "drop" and dropped:
                    row = error_row(ctx, "Only low_count_policy: drop is implemented for conformal decisions.", [ref_path, feature_path])
                    row.update({"stack": stack, "model": model_name, "split": split_name, "alpha": alpha, "target_coverage": target_coverage})
                    rows.append(row)
                    continue
                keep_train = np.isin(y[train_idx], retained)
                keep_cal = np.isin(y[cal_idx], retained)
                keep_test = np.isin(y[test_idx], retained)
                train_use = train_idx[keep_train]
                cal_use = cal_idx[keep_cal]
                test_use = test_idx[keep_test]
                if len(train_use) == 0 or len(cal_use) == 0 or len(test_use) == 0 or len(retained) < 1:
                    row = skipped_row(ctx, "Insufficient train/calibration/test samples after min_class_count policy.", [ref_path, feature_path])
                    row.update({"stack": stack, "model": model_name, "split": split_name, "alpha": alpha, "target_coverage": target_coverage})
                    rows.append(row)
                    continue
                try:
                    classes, cal_proba, test_proba = fit_predict_proba(
                        ctx,
                        model_name,
                        X[train_use],
                        y[train_use],
                        X[cal_use],
                        X[test_use],
                    )
                    cal_scores = true_class_nonconformity(classes, cal_proba, y[cal_use])
                    qhat = conformal_quantile(cal_scores, alpha)
                    prediction_sets = test_proba >= (1.0 - qhat)
                    class_to_pos = {label: pos for pos, label in enumerate(classes)}
                    covered = []
                    sizes = []
                    for true_label, pred_set in zip(y[test_use], prediction_sets):
                        pos = class_to_pos.get(true_label)
                        covered.append(bool(pos is not None and pred_set[pos]))
                        sizes.append(int(np.sum(pred_set)))
                except Exception as exc:
                    row = error_row(ctx, f"Conformal fit/evaluation failed: {type(exc).__name__}: {exc}", [ref_path, feature_path])
                    row.update({"stack": stack, "model": model_name, "split": split_name, "alpha": alpha, "target_coverage": target_coverage})
                    rows.append(row)
                    continue
                row = ctx.provenance([ref_path, feature_path])
                row.update(
                    {
                        "status": "OK",
                        "reason": "",
                        "stack": stack,
                        "model": model_name,
                        "split": split_name,
                        "alpha": alpha,
                        "target_coverage": target_coverage,
                        "empirical_coverage": float(np.mean(covered)),
                        "average_set_size": float(np.mean(sizes)),
                        "n_calibration": int(len(cal_use)),
                        "n_test": int(len(test_use)),
                        "classes_retained": "|".join(str(x) for x in sorted(retained)),
                    }
                )
                rows.append(row)

    if decision_rows:
        write_csv(
            ctx.results_dir / "class_merge_drop_conformal_log.csv",
            BASE_TABLE_COLUMNS + ["scope", "policy", "class_code", "class_name", "sample_count"],
            decision_rows,
        )
    return rows


def conformal_random_split(ctx: RunContext, y: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    try:
        from sklearn.model_selection import train_test_split
    except Exception as exc:
        ctx.report("conformal_random_split", "ERROR", f"scikit-learn unavailable: {type(exc).__name__}: {exc}")
        return None
    test_fraction = float(ctx.config.get("cv", {}).get("random_test_fraction", 0.20))
    cal_fraction = float(ctx.config.get("cv", {}).get("random_calibration_fraction", 0.20))
    indices = np.arange(len(y))
    counts = pd.Series(y).value_counts()
    if counts.min() < 3:
        ctx.report("conformal_random_split", "SKIPPED", "At least one class has fewer than 3 samples.")
        return None
    try:
        train_cal, test = train_test_split(indices, test_size=test_fraction, random_state=ctx.seed, stratify=y)
        rel_cal = cal_fraction / (1.0 - test_fraction)
        train, cal = train_test_split(train_cal, test_size=rel_cal, random_state=ctx.seed, stratify=y[train_cal])
    except Exception as exc:
        ctx.report("conformal_random_split", "SKIPPED", f"Could not create stratified conformal split: {type(exc).__name__}: {exc}")
        return None
    return train, cal, test


def conformal_spatial_split(
    ctx: RunContext,
    coords: np.ndarray,
    block_distance_m: Optional[float],
    y: Optional[np.ndarray] = None,
    min_count: Optional[int] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    audit_fields = BASE_TABLE_COLUMNS + [
        "train_count",
        "calibration_count",
        "test_count",
        "block_distance_m",
        "minimum_calibration_test_distance_m",
        "zero_leakage_assertion",
        "available_spatial_blocks",
        "required_spatial_blocks",
        "split_strategy",
        "selected_test_cell_ids",
        "selected_calibration_cell_ids",
        "classes_retained_by_calibration",
        "required_class_codes",
        "required_class_codes_satisfied",
        "required_class_codes_missing",
        "split_score",
        "candidate_sets_evaluated",
        "candidate_search_truncated",
    ]
    if block_distance_m is None or not np.isfinite(block_distance_m) or block_distance_m <= 0:
        reason = "Invalid variogram-derived block distance."
        ctx.report("conformal_spatial_split", "ERROR", reason)
        audit = error_row(ctx, reason, ["verified_reference_samples"])
        audit.update(
            {
                "train_count": "",
                "calibration_count": "",
                "test_count": "",
                "block_distance_m": block_distance_m,
                "minimum_calibration_test_distance_m": "",
                "zero_leakage_assertion": "",
                "available_spatial_blocks": "",
                "required_spatial_blocks": int(ctx.config.get("cv", {}).get("k_folds", 5)),
                "split_strategy": "",
                "selected_test_cell_ids": "",
                "selected_calibration_cell_ids": "",
                "classes_retained_by_calibration": "",
                "required_class_codes": "",
                "required_class_codes_satisfied": "",
                "required_class_codes_missing": "",
                "split_score": "",
                "candidate_sets_evaluated": "",
                "candidate_search_truncated": "",
            }
        )
        write_csv(ctx.results_dir / "spatial_conformal_split_audit.csv", audit_fields, [audit])
        return None
    cells_x = np.floor(coords[:, 0] / block_distance_m).astype(int)
    cells_y = np.floor(coords[:, 1] / block_distance_m).astype(int)
    cell_ids = np.array([f"{x}:{y}" for x, y in zip(cells_x, cells_y)])
    unique_cells = np.unique(cell_ids)
    min_blocks = int(ctx.config.get("cv", {}).get("k_folds", 5))
    if len(unique_cells) < min_blocks:
        reason = f"Fewer than configured k_folds={min_blocks} spatial blocks are available."
        ctx.report(
            "conformal_spatial_split",
            "SKIPPED",
            reason,
        )
        audit = skipped_row(ctx, reason, ["verified_reference_samples"])
        audit.update(
            {
                "train_count": "",
                "calibration_count": "",
                "test_count": "",
                "block_distance_m": block_distance_m,
                "minimum_calibration_test_distance_m": "",
                "zero_leakage_assertion": "",
                "available_spatial_blocks": int(len(unique_cells)),
                "required_spatial_blocks": min_blocks,
                "split_strategy": "",
                "selected_test_cell_ids": "",
                "selected_calibration_cell_ids": "",
                "classes_retained_by_calibration": "",
                "required_class_codes": "",
                "required_class_codes_satisfied": "",
                "required_class_codes_missing": "",
                "split_score": "",
                "candidate_sets_evaluated": "",
                "candidate_search_truncated": "",
            }
        )
        write_csv(ctx.results_dir / "spatial_conformal_split_audit.csv", audit_fields, [audit])
        return None
    cells = unique_cells.copy()
    rng = np.random.default_rng(ctx.seed)
    rng.shuffle(cells)
    cv_cfg = ctx.config.get("cv", {})
    split_strategy = str(cv_cfg.get("spatial_conformal_split_strategy", "max_retained_classes"))
    required_labels_cfg = cv_cfg.get("spatial_conformal_required_class_codes", [])
    required_labels: set[Any] = set()
    if y is not None and min_count is not None and split_strategy in {"class_aware", "require_all_classes"}:
        if required_labels_cfg:
            required_labels = set(required_labels_cfg)
        else:
            required_labels = set(pd.Series(y).dropna().unique().tolist())

    best: Optional[Tuple[Tuple[Any, ...], np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]] = None
    max_test_cells = min(3, len(cells))
    max_test_sets = int(cv_cfg.get("spatial_conformal_max_test_cell_sets", 300))
    max_cal_sets_per_test = int(cv_cfg.get("spatial_conformal_max_calibration_cell_sets_per_test", 200))
    test_priority = spatial_cell_priority(cell_ids, np.ones(len(cell_ids), dtype=bool), cells, y, required_labels)
    test_cell_sets, test_sets_truncated = bounded_cell_sets(cells, max_test_cells, rng, max_test_sets, test_priority)
    candidate_sets_evaluated = 0
    candidate_search_truncated = bool(test_sets_truncated)
    for test_cells_tuple in test_cell_sets:
            test_mask_candidate = np.isin(cell_ids, test_cells_tuple)
            if not np.any(test_mask_candidate):
                continue
            near_test = within_distance_mask(coords, coords[test_mask_candidate], block_distance_m)
            calibration_pool = (~near_test) & (~test_mask_candidate)
            eligible_cal_cells = [cell for cell in cells if np.any((cell_ids == cell) & calibration_pool)]
            if len(eligible_cal_cells) < 1:
                continue
            max_cal_cells = min(6, len(eligible_cal_cells))
            cal_priority = spatial_cell_priority(cell_ids, calibration_pool, np.array(eligible_cal_cells), y, required_labels)
            cal_cell_sets, cal_sets_truncated = bounded_cell_sets(
                np.array(eligible_cal_cells),
                max_cal_cells,
                rng,
                max_cal_sets_per_test,
                cal_priority,
            )
            candidate_search_truncated = candidate_search_truncated or bool(cal_sets_truncated)
            for cal_cells_tuple in cal_cell_sets:
                    candidate_sets_evaluated += 1
                    cal_mask_candidate = np.isin(cell_ids, cal_cells_tuple) & calibration_pool
                    train_mask_candidate = (~test_mask_candidate) & (~cal_mask_candidate)
                    if (
                        not np.any(train_mask_candidate)
                        or not np.any(cal_mask_candidate)
                        or not np.any(test_mask_candidate)
                    ):
                        continue
                    if y is not None and min_count is not None:
                        cal_counts = pd.Series(y[cal_mask_candidate]).value_counts()
                        retained = [label for label, count in cal_counts.items() if count >= min_count]
                        if len(retained) < 1:
                            continue
                        if not set(retained).issubset(set(y[train_mask_candidate])):
                            continue
                        if not set(retained).issubset(set(y[test_mask_candidate])):
                            continue
                        retained_set = set(retained)
                        satisfied_required = sorted(required_labels.intersection(retained_set), key=str)
                        missing_required = sorted(required_labels.difference(retained_set), key=str)
                        if split_strategy == "require_all_classes" and missing_required:
                            continue
                        retained_test_n = int(np.isin(y[test_mask_candidate], retained).sum())
                        retained_train_n = int(np.isin(y[train_mask_candidate], retained).sum())
                        min_retained_cal = int(min(cal_counts.loc[retained]))
                        if split_strategy in {"class_aware", "require_all_classes"}:
                            min_required_cal = int(min(cal_counts.loc[satisfied_required])) if satisfied_required else 0
                            score = (
                                len(satisfied_required),
                                min_required_cal,
                                len(retained),
                                min_retained_cal,
                                retained_test_n,
                                retained_train_n,
                                int(np.sum(cal_mask_candidate)),
                            )
                        else:
                            score = (
                                len(retained),
                                min_retained_cal,
                                retained_test_n,
                                retained_train_n,
                                int(np.sum(cal_mask_candidate)),
                            )
                        metadata = {
                            "split_strategy": split_strategy,
                            "selected_test_cell_ids": "|".join(str(cell) for cell in test_cells_tuple),
                            "selected_calibration_cell_ids": "|".join(str(cell) for cell in cal_cells_tuple),
                            "classes_retained_by_calibration": "|".join(str(x) for x in sorted(retained, key=str)),
                            "required_class_codes": "|".join(str(x) for x in sorted(required_labels, key=str)),
                            "required_class_codes_satisfied": "|".join(str(x) for x in satisfied_required),
                            "required_class_codes_missing": "|".join(str(x) for x in missing_required),
                            "split_score": "|".join(str(x) for x in score),
                            "candidate_sets_evaluated": candidate_sets_evaluated,
                            "candidate_search_truncated": candidate_search_truncated,
                        }
                    else:
                        score = (
                            int(np.sum(cal_mask_candidate)),
                            int(np.sum(test_mask_candidate)),
                            int(np.sum(train_mask_candidate)),
                        )
                        metadata = {
                            "split_strategy": split_strategy,
                            "selected_test_cell_ids": "|".join(str(cell) for cell in test_cells_tuple),
                            "selected_calibration_cell_ids": "|".join(str(cell) for cell in cal_cells_tuple),
                            "classes_retained_by_calibration": "",
                            "required_class_codes": "",
                            "required_class_codes_satisfied": "",
                            "required_class_codes_missing": "",
                            "split_score": "|".join(str(x) for x in score),
                            "candidate_sets_evaluated": candidate_sets_evaluated,
                            "candidate_search_truncated": candidate_search_truncated,
                        }
                    if best is None or score > best[0]:
                        best = (score, train_mask_candidate, cal_mask_candidate, test_mask_candidate, metadata)

    if best is None:
        reason = "No spatial split satisfied the block-distance and class-count constraints."
        ctx.report("conformal_spatial_split", "SKIPPED", reason)
        audit = skipped_row(ctx, reason, ["verified_reference_samples"])
        audit.update(
            {
                "train_count": "",
                "calibration_count": "",
                "test_count": "",
                "block_distance_m": block_distance_m,
                "minimum_calibration_test_distance_m": "",
                "zero_leakage_assertion": "",
                "available_spatial_blocks": int(len(unique_cells)),
                "required_spatial_blocks": min_blocks,
                "split_strategy": split_strategy,
                "selected_test_cell_ids": "",
                "selected_calibration_cell_ids": "",
                "classes_retained_by_calibration": "",
                "required_class_codes": "|".join(str(x) for x in sorted(required_labels, key=str)),
                "required_class_codes_satisfied": "",
                "required_class_codes_missing": "",
                "split_score": "",
                "candidate_sets_evaluated": candidate_sets_evaluated,
                "candidate_search_truncated": candidate_search_truncated,
            }
        )
        write_csv(ctx.results_dir / "spatial_conformal_split_audit.csv", audit_fields, [audit])
        return None
    _, train_mask, cal_mask, test_mask, split_metadata = best
    cal_idx = np.where(cal_mask)[0]
    test_idx = np.where(test_mask)[0]
    train_idx = np.where(train_mask)[0]
    ok, min_dist = leakage_assertion(coords[cal_idx], coords[test_idx], block_distance_m)
    audit = ctx.provenance(["verified_reference_samples"])
    audit.update(
        {
            "status": "OK" if ok else "ERROR",
            "reason": "" if ok else "calibration sample lies within block distance of test sample",
            "train_count": int(len(train_idx)),
            "calibration_count": int(len(cal_idx)),
            "test_count": int(len(test_idx)),
            "block_distance_m": block_distance_m,
            "minimum_calibration_test_distance_m": min_dist,
            "zero_leakage_assertion": bool(ok),
            "available_spatial_blocks": int(len(unique_cells)),
            "required_spatial_blocks": min_blocks,
            **split_metadata,
        }
    )
    write_csv(
        ctx.results_dir / "spatial_conformal_split_audit.csv",
        audit_fields,
        [audit],
    )
    if not ok or len(train_idx) == 0 or len(cal_idx) == 0 or len(test_idx) == 0:
        ctx.report("conformal_spatial_split", "ERROR", "Spatial conformal split failed zero-leakage or nonempty-partition checks.")
        return None
    return train_idx, cal_idx, test_idx


def spatial_cell_priority(
    cell_ids: np.ndarray,
    pool_mask: np.ndarray,
    cells: np.ndarray,
    y: Optional[np.ndarray],
    required_labels: set[Any],
) -> List[Any]:
    scores: List[Tuple[Tuple[int, int, int], Any]] = []
    for cell in cells:
        mask = (cell_ids == cell) & pool_mask
        total = int(np.sum(mask))
        if y is None or total == 0:
            scores.append(((0, 0, total), cell))
            continue
        counts = pd.Series(y[mask]).value_counts()
        required_present = int(sum(label in counts.index for label in required_labels))
        diversity = int(len(counts))
        scores.append(((required_present, diversity, total), cell))
    scores.sort(key=lambda item: item[0], reverse=True)
    return [cell for _, cell in scores]


def bounded_cell_sets(
    cells: np.ndarray,
    max_size: int,
    rng: np.random.Generator,
    limit: int,
    priority_cells: Sequence[Any],
) -> Tuple[List[Tuple[Any, ...]], bool]:
    from itertools import combinations

    cells_list = [cell for cell in cells.tolist()]
    max_size = max(1, min(max_size, len(cells_list)))
    total_possible = sum(math.comb(len(cells_list), size) for size in range(1, max_size + 1))
    if total_possible <= limit:
        return [
            tuple(combo)
            for size in range(1, max_size + 1)
            for combo in combinations(cells_list, size)
        ], False

    ordered_priority = [cell for cell in priority_cells if cell in set(cells_list)]
    ordered_priority.extend([cell for cell in cells_list if cell not in set(ordered_priority)])
    seen: set[Tuple[Any, ...]] = set()
    candidates: List[Tuple[Any, ...]] = []

    def add(combo: Sequence[Any]) -> None:
        key = tuple(sorted(combo, key=str))
        if len(key) == 0 or len(key) > max_size or key in seen or len(candidates) >= limit:
            return
        seen.add(key)
        candidates.append(tuple(combo))

    for cell in ordered_priority:
        add((cell,))
    for size in range(2, max_size + 1):
        add(tuple(ordered_priority[:size]))
    for size in range(2, max_size + 1):
        for combo in combinations(ordered_priority[: min(len(ordered_priority), 10)], size):
            add(combo)
            if len(candidates) >= limit:
                return candidates, True

    attempts = 0
    max_attempts = max(limit * 25, 1000)
    while len(candidates) < limit and attempts < max_attempts:
        attempts += 1
        size = int(rng.integers(1, max_size + 1))
        combo = tuple(rng.choice(cells_list, size=size, replace=False).tolist())
        add(combo)
    return candidates, True


def calibration_retained_classes(y_cal: np.ndarray, min_count: int) -> List[Any]:
    counts = pd.Series(y_cal).value_counts()
    return [label for label, count in counts.items() if count >= min_count]


def fit_predict_proba(
    ctx: RunContext,
    model_name: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_cal: np.ndarray,
    X_test: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    unique_train = np.unique(y_train)
    if len(unique_train) == 1:
        classes = unique_train
        cal_proba = np.ones((len(X_cal), 1), dtype=float)
        test_proba = np.ones((len(X_test), 1), dtype=float)
        return classes, cal_proba, test_proba
    model_obj, reason = make_model(ctx, model_name, y_train)
    if reason:
        raise RuntimeError(reason)
    X_train, X_cal, X_test = fit_transform_features(X_train, X_cal, X_test)
    if model_name == "XGBoost":
        from sklearn.preprocessing import LabelEncoder

        model = model_obj
        encoder = LabelEncoder()
        encoder.fit(y_train)
        y_train_enc = encoder.transform(y_train)
        model.fit(X_train, y_train_enc)
        return encoder.classes_, model.predict_proba(X_cal), model.predict_proba(X_test)
    model = model_obj
    model.fit(X_train, y_train)
    return model.classes_, model.predict_proba(X_cal), model.predict_proba(X_test)


def true_class_nonconformity(classes: np.ndarray, proba: np.ndarray, y_true: np.ndarray) -> np.ndarray:
    class_to_pos = {label: pos for pos, label in enumerate(classes)}
    scores = []
    for idx, label in enumerate(y_true):
        pos = class_to_pos.get(label)
        if pos is None:
            raise RuntimeError(f"True label {label} was absent from fitted model classes.")
        scores.append(1.0 - float(proba[idx, pos]))
    return np.asarray(scores, dtype=float)


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    if len(scores) == 0:
        raise RuntimeError("No calibration scores.")
    sorted_scores = np.sort(scores)
    rank = int(math.ceil((len(sorted_scores) + 1) * (1.0 - alpha)))
    rank = min(max(rank, 1), len(sorted_scores))
    return float(sorted_scores[rank - 1])


def compute_morans_i_table(ctx: RunContext, variogram_choice: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pred_path = ctx.results_dir / "predictions_by_fold.csv"
    if not pred_path.exists():
        return [error_row(ctx, "predictions_by_fold.csv is unavailable; Moran's I cannot be computed.", [pred_path])]
    if not variogram_choice or variogram_choice.get("status") != "OK":
        return [error_row(ctx, "Variogram-derived distance threshold is unavailable.", [pred_path])]
    df = pd.read_csv(pred_path)
    rows: List[Dict[str, Any]] = []
    threshold = float(variogram_choice["chosen_block_distance_m"])
    for keys, group in df.groupby(["stack", "model", "split", "fold"]):
        stack, model, split, fold = keys
        values = group["incorrect"].astype(float).to_numpy()
        coords = group[["x_m", "y_m"]].astype(float).to_numpy()
        if len(values) < 3 or np.nanvar(values) == 0:
            row = skipped_row(ctx, "Too few or constant residual values for Moran's I.", [pred_path])
            row.update({"stack": stack, "model": model, "split": split, "fold": fold, "variable": "incorrect"})
            rows.append(row)
            continue
        moran = morans_i(values, coords, threshold)
        row = ctx.provenance([pred_path])
        row.update(
            {
                "status": "OK",
                "reason": "",
                "stack": stack,
                "model": model,
                "split": split,
                "fold": fold,
                "variable": "incorrect",
                "morans_i": moran,
                "n_samples": len(values),
                "distance_threshold_m": threshold,
            }
        )
        rows.append(row)
    return rows


def morans_i(values: np.ndarray, coords: np.ndarray, threshold: float) -> float:
    centered = values - np.mean(values)
    denom = float(np.sum(centered**2))
    if denom == 0:
        return float("nan")
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(coords)
        pairs = tree.query_pairs(r=threshold, output_type="ndarray")
        if len(pairs) == 0:
            return float("nan")
        # query_pairs returns each unordered pair once; Moran's I with a symmetric
        # binary weights matrix counts both directions, so multiply by two.
        products = centered[pairs[:, 0]] * centered[pairs[:, 1]]
        numerator = float(2.0 * np.sum(products))
        w_sum = float(2 * len(pairs))
    except Exception:
        distances = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
        weights = ((distances > 0) & (distances <= threshold)).astype(float)
        w_sum = float(np.sum(weights))
        if w_sum == 0:
            return float("nan")
        numerator = float(np.sum(weights * centered[:, None] * centered[None, :]))
    return (len(values) / w_sum) * (numerator / denom)


def compute_landscape_regression(ctx: RunContext) -> List[Dict[str, Any]]:
    cov_path = ctx.root / ctx.config.get("landscape_covariates", {}).get("file", "data/landscape_covariates.csv")
    pred_path = ctx.results_dir / "predictions_by_fold.csv"
    if not cov_path.exists():
        return [error_row(ctx, "data/landscape_covariates.csv is unavailable; landscape regression cannot be computed.", [cov_path])]
    if not pred_path.exists():
        return [error_row(ctx, "results/predictions_by_fold.csv is unavailable; landscape regression cannot be computed.", [pred_path])]
    try:
        cov = pd.read_csv(cov_path)
        pred = pd.read_csv(pred_path)
    except Exception as exc:
        return [error_row(ctx, f"Could not read landscape regression inputs: {type(exc).__name__}: {exc}", [cov_path, pred_path])]
    if "sample_id" not in cov.columns or "sample_id" not in pred.columns or "incorrect" not in pred.columns:
        return [error_row(ctx, "Landscape regression inputs must contain sample_id and predictions must contain incorrect.", [cov_path, pred_path])]

    pred = pred[pred.get("status", "OK").astype(str).eq("OK")].copy()
    pred["incorrect"] = pd.to_numeric(pred["incorrect"], errors="coerce")
    outcome = pred.groupby("sample_id", as_index=False)["incorrect"].mean().rename(columns={"incorrect": "prediction_error_rate"})
    merged = outcome.merge(cov, on="sample_id", how="inner")
    if merged.empty:
        return [error_row(ctx, "No overlap between landscape covariates and prediction rows.", [cov_path, pred_path])]

    try:
        from scipy import stats
    except Exception as exc:
        return [error_row(ctx, f"scipy unavailable for p-values: {type(exc).__name__}: {exc}", [cov_path, pred_path])]

    rows: List[Dict[str, Any]] = []
    predictor_cols = [
        col
        for col in merged.columns
        if col not in {"sample_id", "prediction_error_rate"} and pd.api.types.is_numeric_dtype(merged[col])
    ]
    for predictor in predictor_cols:
        work = merged[["prediction_error_rate", predictor]].dropna()
        row = ctx.provenance([cov_path, pred_path])
        row.update({"outcome": "sample_prediction_error_rate", "predictor": predictor})
        if len(work) < 3 or work[predictor].nunique() < 2:
            row.update(
                {
                    "status": "SKIPPED",
                    "reason": "Predictor has too few nonmissing or unique values for OLS.",
                    "coefficient": "",
                    "standard_error": "",
                    "p_value": "",
                    "n_samples": int(len(work)),
                }
            )
            rows.append(row)
            continue
        y = work["prediction_error_rate"].to_numpy(dtype=float)
        x = work[predictor].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(x)), x])
        beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
        residuals = y - design @ beta
        dof = len(y) - design.shape[1]
        if dof <= 0:
            se = float("nan")
            p_value = float("nan")
        else:
            sigma2 = float(np.sum(residuals**2) / dof)
            cov_beta = sigma2 * np.linalg.inv(design.T @ design)
            se = float(np.sqrt(cov_beta[1, 1]))
            t_stat = float(beta[1] / se) if se > 0 else float("nan")
            p_value = float(2.0 * stats.t.sf(abs(t_stat), dof)) if np.isfinite(t_stat) else float("nan")
        row.update(
            {
                "status": "OK",
                "reason": "",
                "coefficient": float(beta[1]),
                "standard_error": se,
                "p_value": p_value,
                "n_samples": int(len(work)),
            }
        )
        rows.append(row)
    if not rows:
        return [skipped_row(ctx, "No numeric landscape predictors were available.", [cov_path, pred_path])]
    return rows


def write_provenance(ctx: RunContext, asset_rows: Sequence[Dict[str, Any]], class_rows: Sequence[Dict[str, Any]]) -> None:
    payload = {
        "timestamp_utc": ctx.timestamp,
        "config_path": str(ctx.config_path),
        "config_hash_sha256": ctx.config_hash,
        "random_seed": ctx.seed,
        "assets": list(asset_rows),
        "class_counts": list(class_rows),
        "status": ctx.status_rows,
        "library_versions": library_versions(),
    }
    write_json(ctx.results_dir / "provenance.json", payload)


def write_status(ctx: RunContext) -> None:
    fieldnames = BASE_TABLE_COLUMNS + ["artifact"]
    write_csv(ctx.results_dir / "run_status.csv", fieldnames, ctx.status_rows)


def write_missing_feature_audit(ctx: RunContext) -> None:
    fieldnames = BASE_TABLE_COLUMNS + [
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
    ]
    if not ctx.missing_feature_rows:
        row = skipped_row(ctx, "No feature stacks were read; missing-feature audit was not generated.")
        ctx.missing_feature_rows.append(row)
    write_csv(ctx.results_dir / "feature_missing_value_policy_audit.csv", fieldnames, ctx.missing_feature_rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args(argv)

    root = Path.cwd()
    config_path = (root / args.config).resolve()
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        config = read_config(config_path)
    except Exception as exc:
        print(f"ERROR: could not read config: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    results_dir, figures_dir = ensure_dirs(root, config)
    seed = int(config.get("seeds", {}).get("global", 42))
    np.random.seed(seed)
    ctx = RunContext(
        root=root,
        config_path=config_path,
        config=config,
        config_hash=sha256_file(config_path),
        timestamp=now_stamp(),
        seed=seed,
        results_dir=results_dir,
        figures_dir=figures_dir,
    )

    asset_rows = verify_gee_assets(ctx)
    validate_study_area(ctx)
    ref, class_rows = load_reference_samples(ctx)
    write_run_log(ctx, asset_rows, class_rows)
    variogram_choice = None
    if ref is not None:
        variogram_choice = load_precomputed_variogram_choice(ctx)
        if variogram_choice is None:
            variogram_choice = compute_variogram(ctx, ref)

    table3, table6, _ = evaluate_feature_stacks(ctx, ref, variogram_choice)
    table4, table5 = compute_derived_tables(ctx, table3)
    table7 = compute_conformal(ctx, ref, variogram_choice)
    table8 = compute_morans_i_table(ctx, variogram_choice)
    table9 = compute_landscape_regression(ctx)

    write_table(ctx, "table3", table3)
    write_table(ctx, "table4", table4)
    write_table(ctx, "table5", table5)
    write_table(ctx, "table6", table6)
    write_table(ctx, "table7", table7)
    write_table(ctx, "table8", table8)
    write_table(ctx, "table9", table9)
    write_missing_feature_audit(ctx)
    write_provenance(ctx, asset_rows, class_rows)
    write_status(ctx)

    has_error = any(row.get("status") == "ERROR" for row in ctx.status_rows)
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
