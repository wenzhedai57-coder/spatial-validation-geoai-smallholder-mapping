#!/usr/bin/env python
"""Audit point-level public Sentinel-2 acquisition dates for reference samples."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "data" / "reference_samples_verified_622_public.csv"
CONFIG_PATH = ROOT / "config" / "config_public_reproduction_20260615.yaml"
OUT_DIR = ROOT / "results" / "point_imagery_dates"
STAC_ENDPOINT = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
STAC_COLLECTION = "sentinel-2-l2a"
START = "2024-01-01T00:00:00Z"
END = "2025-01-01T00:00:00Z"
DATE_TAG = "20260616"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def post_json(payload: dict, retries: int = 4) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        STAC_ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
            "User-Agent": "ijrs-public-point-date-audit/1.0",
        },
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 >= retries:
                raise RuntimeError(f"STAC request failed after {retries} attempts: {exc}") from exc
            time.sleep(2**attempt)
    raise RuntimeError("unreachable retry state")


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    if not ring:
        return False
    prev_x, prev_y = ring[-1]
    for cur_x, cur_y in ring:
        crosses = (cur_y > y) != (prev_y > y)
        if crosses:
            x_at_y = (prev_x - cur_x) * (y - cur_y) / (prev_y - cur_y) + cur_x
            if x < x_at_y:
                inside = not inside
        prev_x, prev_y = cur_x, cur_y
    return inside


def point_in_polygon(x: float, y: float, coords: list) -> bool:
    if not coords or not point_in_ring(x, y, coords[0]):
        return False
    return not any(point_in_ring(x, y, hole) for hole in coords[1:])


def geometry_contains_point(geometry: dict, x: float, y: float) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        return point_in_polygon(x, y, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon(x, y, poly) for poly in coords)
    return False


def bbox_contains_point(bbox: list[float] | None, x: float, y: float) -> bool:
    if not bbox or len(bbox) < 4:
        return True
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def load_reference_rows() -> list[dict]:
    with REF_PATH.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["longitude_float"] = float(row["longitude"])
        row["latitude_float"] = float(row["latitude"])
    return rows


def reference_bbox(rows: list[dict], pad_degrees: float = 0.05) -> list[float]:
    xs = [row["longitude_float"] for row in rows]
    ys = [row["latitude_float"] for row in rows]
    return [
        min(xs) - pad_degrees,
        min(ys) - pad_degrees,
        max(xs) + pad_degrees,
        max(ys) + pad_degrees,
    ]


def fetch_sentinel2_items(bbox: list[float]) -> list[dict]:
    payload = {
        "collections": [STAC_COLLECTION],
        "bbox": bbox,
        "datetime": f"{START}/{END}",
        "limit": 100,
    }
    items: list[dict] = []
    seen_ids: set[str] = set()
    while True:
        data = post_json(payload)
        for item in data.get("features", []):
            item_id = str(item.get("id", ""))
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                items.append(item)
        next_link = next((link for link in data.get("links", []) if link.get("rel") == "next"), None)
        if not next_link:
            break
        payload = next_link.get("body")
        if not isinstance(payload, dict):
            break
    return items


def item_record(item: dict) -> dict:
    props = item.get("properties", {})
    dt = props.get("datetime", "")
    return {
        "id": item.get("id", ""),
        "datetime": dt,
        "date": dt[:10] if dt else "",
        "dt_obj": parse_dt(dt) if dt else datetime.max.replace(tzinfo=timezone.utc),
        "cloud": props.get("eo:cloud_cover"),
        "platform": props.get("platform", ""),
        "mgrs_tile": props.get("s2:mgrs_tile", ""),
        "bbox": item.get("bbox"),
        "geometry": item.get("geometry", {}),
    }


def cloud_sort_value(value) -> float:
    if value is None or value == "":
        return float("inf")
    return float(value)


def summarize_class_status(rows: list[dict]) -> dict:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        cls = row["class_name"]
        status = row["audit_status"]
        summary.setdefault(cls, {})
        summary[cls][status] = summary[cls].get(status, 0) + 1
    return summary


def main() -> int:
    timestamp = utc_now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    reference_rows = load_reference_rows()
    bbox = reference_bbox(reference_rows)
    items = [item_record(item) for item in fetch_sentinel2_items(bbox)]

    output_rows: list[dict] = []
    selection_rule = (
        "For each point, select the 2024 Sentinel-2 L2A item that intersects the point "
        "and has the lowest item-level eo:cloud_cover; ties are resolved by earliest datetime."
    )
    limitation = (
        "Public Sentinel-2 acquisition metadata are not field validation and are not exact VHR "
        "interpretation-platform imagery dates; cloud cover is item-level, not point-pixel cloud."
    )
    for ref in reference_rows:
        lon = ref["longitude_float"]
        lat = ref["latitude_float"]
        matches = [
            item
            for item in items
            if bbox_contains_point(item["bbox"], lon, lat)
            and geometry_contains_point(item["geometry"], lon, lat)
        ]
        matches.sort(key=lambda item: item["dt_obj"])
        selected = None
        if matches:
            selected = min(matches, key=lambda item: (cloud_sort_value(item["cloud"]), item["dt_obj"]))
        status = "OK" if selected else "ERROR"
        reason = "" if selected else "No public Sentinel-2 L2A STAC item intersected this point in 2024."
        output_rows.append(
            {
                "timestamp_utc": timestamp,
                "sample_id": ref["sample_id"],
                "longitude": ref["longitude"],
                "latitude": ref["latitude"],
                "class_code": ref["class_code"],
                "class_name": ref["class_name"],
                "verified": ref["verified"],
                "region_key": ref.get("region_key", ""),
                "audit_status": status,
                "reason": reason,
                "audit_source": "Microsoft Planetary Computer STAC",
                "source_collection": STAC_COLLECTION,
                "audit_period_start_utc": START,
                "audit_period_end_utc": END,
                "matched_s2_item_count_2024": len(matches),
                "first_s2_datetime_utc": matches[0]["datetime"] if matches else "",
                "last_s2_datetime_utc": matches[-1]["datetime"] if matches else "",
                "selected_s2_datetime_utc": selected["datetime"] if selected else "",
                "selected_s2_date_utc": selected["date"] if selected else "",
                "selected_s2_item_id": selected["id"] if selected else "",
                "selected_s2_cloud_cover_percent": selected["cloud"] if selected else "",
                "selected_s2_platform": selected["platform"] if selected else "",
                "selected_s2_mgrs_tile": selected["mgrs_tile"] if selected else "",
                "selection_rule": selection_rule,
                "can_use_as_field_validation": "False",
                "can_use_as_exact_vhr_imagery_date": "False",
                "limitation": limitation,
            }
        )

    csv_path = OUT_DIR / f"point_level_public_sentinel2_imagery_dates_{DATE_TAG}.csv"
    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    ok_rows = sum(1 for row in output_rows if row["audit_status"] == "OK")
    error_rows = sum(1 for row in output_rows if row["audit_status"] != "OK")
    summary = {
        "timestamp_utc": timestamp,
        "status": "OK" if error_rows == 0 else "CHECK",
        "input_files": [REF_PATH.relative_to(ROOT).as_posix(), CONFIG_PATH.relative_to(ROOT).as_posix()],
        "input_sha256": {
            REF_PATH.relative_to(ROOT).as_posix(): sha256_file(REF_PATH),
            CONFIG_PATH.relative_to(ROOT).as_posix(): sha256_file(CONFIG_PATH),
        },
        "stac_endpoint": STAC_ENDPOINT,
        "source_collection": STAC_COLLECTION,
        "source_dataset": "Sentinel-2 Level-2A public STAC metadata",
        "audit_period_start_utc": START,
        "audit_period_end_utc": END,
        "query_bbox": bbox,
        "stac_items_loaded": len(items),
        "reference_rows": len(reference_rows),
        "point_rows_ok": ok_rows,
        "point_rows_error": error_rows,
        "class_status_counts": summarize_class_status(output_rows),
        "selection_rule": selection_rule,
        "output_csv": csv_path.relative_to(ROOT).as_posix(),
        "limitations": [
            "This is a public Sentinel-2 metadata date audit, not field validation.",
            "This is not an exact VHR basemap acquisition-date record.",
            "The selected cloud-cover value is item-level eo:cloud_cover, not a point-level cloud mask.",
            "The 2024 annual window follows the repository configuration year.",
        ],
        "public_documentation_urls": [
            "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a",
            "https://planetarycomputer.microsoft.com/docs/quickstarts/reading-stac/",
            "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        ],
    }
    summary_path = OUT_DIR / f"point_level_public_sentinel2_imagery_dates_summary_{DATE_TAG}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    run_log = OUT_DIR / f"RUN_LOG_point_imagery_dates_{timestamp}.txt"
    run_log.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if error_rows == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
