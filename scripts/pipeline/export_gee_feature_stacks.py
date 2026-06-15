#!/usr/bin/env python
"""Export B0-B3 feature stacks from Google Earth Engine for verified samples.

The script queries asset band names at runtime and writes the band inventory to
disk before any export. It does not create labels and does not use weak
reference products as ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd
import yaml


MISSING_FEATURE_VALUE = -9999


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: List[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def load_verified_points(config: Dict[str, Any], root: Path) -> pd.DataFrame:
    ref_cfg = config.get("reference_samples", {})
    ref_path = root / ref_cfg.get("file", "data/reference_samples.csv")
    if not ref_path.exists():
        raise RuntimeError(f"Missing verified reference sample file: {ref_path}")
    df = pd.read_csv(ref_path)
    required = [
        ref_cfg.get("id_column", "sample_id"),
        ref_cfg.get("longitude_column", "longitude"),
        ref_cfg.get("latitude_column", "latitude"),
        ref_cfg.get("class_code_column", "class_code"),
        ref_cfg.get("verified_column", "verified"),
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"reference_samples.csv is missing columns: {', '.join(missing)}")
    verified = df[parse_bool(df[ref_cfg.get("verified_column", "verified")])].copy()
    if verified.empty:
        raise RuntimeError("No rows have verified == True; weak references cannot be exported as final labels.")
    return verified


def to_feature_collection(ee, df: pd.DataFrame, config: Dict[str, Any]):
    ref_cfg = config.get("reference_samples", {})
    id_col = ref_cfg.get("id_column", "sample_id")
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")
    code_col = ref_cfg.get("class_code_column", "class_code")
    features = []
    for _, row in df.iterrows():
        geom = ee.Geometry.Point([float(row[lon_col]), float(row[lat_col])])
        feat = ee.Feature(
            geom,
            {
                id_col: str(row[id_col]),
                code_col: int(row[code_col]),
            },
        )
        features.append(feat)
    return ee.FeatureCollection(features)


def points_bounds(ee, df: pd.DataFrame, config: Dict[str, Any]):
    ref_cfg = config.get("reference_samples", {})
    lon_col = ref_cfg.get("longitude_column", "longitude")
    lat_col = ref_cfg.get("latitude_column", "latitude")
    min_lon = float(df[lon_col].astype(float).min())
    min_lat = float(df[lat_col].astype(float).min())
    max_lon = float(df[lon_col].astype(float).max())
    max_lat = float(df[lat_col].astype(float).max())
    pad = 0.05
    return ee.Geometry.Rectangle([min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad])


def get_collection_image(ee, asset_id: str, geom, start: str, end: str, reducer: str = "median"):
    collection = ee.ImageCollection(asset_id).filterBounds(geom).filterDate(start, end)
    if reducer == "first":
        return ee.Image(collection.first())
    return collection.median()


def band_names(image) -> List[str]:
    bands = image.bandNames().getInfo()
    if not bands:
        raise RuntimeError("Asset image has no bands after filtering.")
    return list(bands)


def present(bands: Iterable[str], desired: Iterable[str]) -> List[str]:
    band_set = set(bands)
    return [band for band in desired if band in band_set]


def build_s2(ee, config: Dict[str, Any], geom, start: str, end: str, audit_rows: List[Dict[str, Any]]):
    asset = config["assets"]["s2_sr"]
    cloud_max = float(config.get("preprocessing", {}).get("s2_cloudy_pixel_percentage_max", 20))
    collection = (
        ee.ImageCollection(asset)
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_max))
    )
    image_count = int(collection.size().getInfo())
    if image_count == 0:
        raise RuntimeError(f"S2 collection is empty after CLOUDY_PIXEL_PERCENTAGE < {cloud_max}.")
    raw = collection.median()
    bands = band_names(raw)
    audit_rows.append(
        {
            "asset_key": "s2_sr",
            "asset_id": asset,
            "bands": "|".join(bands),
            "status": "OK",
            "filter": f"CLOUDY_PIXEL_PERCENTAGE < {cloud_max}",
            "image_count": image_count,
        }
    )
    selected = present(bands, ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"])
    if not selected:
        raise RuntimeError("S2 asset has no recognized spectral bands after runtime band query.")
    image = raw.select(selected)
    if {"B8", "B4"}.issubset(bands):
        image = image.addBands(raw.normalizedDifference(["B8", "B4"]).rename("NDVI"))
    if {"B3", "B8"}.issubset(bands):
        image = image.addBands(raw.normalizedDifference(["B3", "B8"]).rename("NDWI"))
    if {"B8", "B12"}.issubset(bands):
        image = image.addBands(raw.normalizedDifference(["B8", "B12"]).rename("NBR"))
    if {"B11", "B8"}.issubset(bands):
        image = image.addBands(raw.normalizedDifference(["B11", "B8"]).rename("NDBI"))
    return image


def build_s1(ee, config: Dict[str, Any], geom, start: str, end: str, audit_rows: List[Dict[str, Any]]):
    asset = config["assets"]["s1_grd"]
    raw = get_collection_image(ee, asset, geom, start, end)
    bands = band_names(raw)
    audit_rows.append({"asset_key": "s1_grd", "asset_id": asset, "bands": "|".join(bands), "status": "OK"})
    selected = present(bands, ["VV", "VH", "HH", "HV", "angle"])
    if not selected:
        raise RuntimeError("S1 asset has no recognized radar bands after runtime band query.")
    image = raw.select(selected)
    if {"VV", "VH"}.issubset(bands):
        image = image.addBands(raw.select("VV").subtract(raw.select("VH")).rename("VV_minus_VH"))
    return image


def build_alphaearth(ee, config: Dict[str, Any], geom, start: str, end: str, audit_rows: List[Dict[str, Any]]):
    asset = config["assets"]["alphaearth"]
    collection = ee.ImageCollection(asset).filterBounds(geom).filterDate(start, end)
    image_count = int(collection.size().getInfo())
    if image_count == 0:
        raise RuntimeError("AlphaEarth collection is empty after spatial/date filtering.")
    first = ee.Image(collection.first())
    bands = band_names(first)
    audit_rows.append(
        {
            "asset_key": "alphaearth",
            "asset_id": asset,
            "bands": "|".join(bands),
            "status": "OK",
            "filter": "annual tiles mosaicked after bounds/date filter",
            "image_count": image_count,
        }
    )
    return collection.select(bands).mosaic()


def sample_image(ee, image, points, id_col: str, scale: int):
    return image.sampleRegions(collection=points, properties=[id_col], scale=scale, geometries=False)


def write_local_feature_csv(fc_info: Dict[str, Any], out: Path, id_col: str) -> None:
    rows = []
    for feature in fc_info.get("features", []):
        props = dict(feature.get("properties", {}))
        if id_col in props:
            rows.append(props)
    if not rows:
        raise RuntimeError(f"No sampled rows returned for {out}")
    cols = [id_col] + sorted([k for k in rows[0] if k != id_col])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def count_missing_sentinel(path: Path, id_col: str) -> Dict[str, int]:
    df = pd.read_csv(path)
    numeric_cols = [col for col in df.columns if col != id_col]
    missing_cells = int((df[numeric_cols] == MISSING_FEATURE_VALUE).sum().sum()) if numeric_cols else 0
    rows_with_missing = int((df[numeric_cols] == MISSING_FEATURE_VALUE).any(axis=1).sum()) if numeric_cols else 0
    return {
        "rows": int(len(df)),
        "feature_columns": int(len(numeric_cols)),
        "missing_sentinel_cells": missing_cells,
        "rows_with_missing_sentinel": rows_with_missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--project", default=None, help="Earth Engine / Google Cloud project ID.")
    parser.add_argument("--mode", choices=["local", "drive"], default="local")
    parser.add_argument("--drive-folder", default="gee_geoai_exports")
    parser.add_argument("--scale", type=int, default=10)
    parser.add_argument("--stacks", default="B0,B1,B2,B3", help="Comma-separated stack IDs to export, e.g. B0,B1,B2.")
    args = parser.parse_args()

    root = Path.cwd()
    config_path = root / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    timestamp = now_stamp()
    config_hash = sha256_file(config_path)
    results_dir = root / config.get("paths", {}).get("results", "results/")
    results_dir.mkdir(parents=True, exist_ok=True)

    import ee

    project = args.project or config.get("gee", {}).get("project")
    if not project:
        raise RuntimeError("Earth Engine project is required. Pass --project YOUR_PROJECT or set gee.project in config.yaml.")
    ee.Initialize(project=project)

    year = int(config.get("year", 2024))
    start, end = f"{year}-01-01", f"{year + 1}-01-01"
    verified = load_verified_points(config, root)
    points = to_feature_collection(ee, verified, config)
    geom = points_bounds(ee, verified, config)
    id_col = config.get("reference_samples", {}).get("id_column", "sample_id")

    audit_rows: List[Dict[str, Any]] = []
    s2 = build_s2(ee, config, geom, start, end, audit_rows)
    s1 = build_s1(ee, config, geom, start, end, audit_rows)
    ae = build_alphaearth(ee, config, geom, start, end, audit_rows)
    write_csv(results_dir / f"gee_asset_bands_live_{timestamp}.csv", audit_rows)

    stacks = {
        "B0": s2,
        "B1": s2.addBands(s1),
        "B2": ae,
        "B3": ae.addBands(s2).addBands(s1),
    }
    requested_stacks = [item.strip() for item in args.stacks.split(",") if item.strip()]
    unknown = sorted(set(requested_stacks) - set(stacks))
    if unknown:
        raise RuntimeError(f"Unknown feature stack(s): {unknown}")
    export_rows = []
    for stack in requested_stacks:
        image = stacks[stack]
        sampled = sample_image(ee, image.unmask(MISSING_FEATURE_VALUE, False), points, id_col, args.scale)
        if args.mode == "drive":
            task = ee.batch.Export.table.toDrive(
                collection=sampled,
                description=f"geoai_{stack}_{timestamp}",
                folder=args.drive_folder,
                fileNamePrefix=stack,
                fileFormat="CSV",
            )
            task.start()
            export_rows.append(
                {
                    "timestamp": timestamp,
                    "config_hash": config_hash,
                    "stack": stack,
                    "mode": "drive",
                    "task_id": task.id,
                    "status": "STARTED",
                    "output": f"Google Drive/{args.drive_folder}/{stack}.csv",
                }
            )
            print(f"STARTED: {stack}: {task.id}")
        else:
            stack_cfg = config.get("feature_stacks", {}).get(stack, {})
            out = root / stack_cfg.get("file", f"data/features/{stack}.csv")
            write_local_feature_csv(sampled.getInfo(), out, id_col)
            missing_summary = count_missing_sentinel(out, id_col)
            export_rows.append(
                {
                    "timestamp": timestamp,
                    "config_hash": config_hash,
                    "stack": stack,
                    "mode": "local",
                    "task_id": "",
                    "status": "OK",
                    "output": str(out),
                    **missing_summary,
                }
            )
            print(f"OK: {stack}: {out}")
    write_csv(results_dir / f"gee_feature_export_log_{timestamp}.csv", export_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
