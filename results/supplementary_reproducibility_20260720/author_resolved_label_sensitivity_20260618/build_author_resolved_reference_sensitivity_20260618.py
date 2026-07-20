"""Build the author-led internally resolved reference table for sensitivity reruns.

This script does not create new labels. It converts the existing
author-led internally resolved INCLUDED table into the pipeline's reference schema,
joins region metadata from the 622-row original-label benchmark table, and writes
traceable class counts/provenance for the rerun.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLASS_MAP = {
    "oil_palm": 1,
    "rubber": 2,
    "paddy": 3,
    "other_agri": 4,
    "forest": 5,
    "builtup_other": 6,
}


OUTPUT_COLUMNS = [
    "sample_id",
    "longitude",
    "latitude",
    "class_code",
    "class_name",
    "verified",
    "region_key",
    "extension_stratum",
    "final_review_decision",
    "user_confirmation_status",
    "user_confirmation_timestamp_utc",
    "verification_source",
    "verification_notes",
    "second_reader_class_name",
    "second_reader_confidence",
    "final_resolution_status",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locked-reference", default="data/reference_samples_verified_622_public.csv")
    parser.add_argument(
        "--author-resolved-included",
        default="author_led_vhr_label_rereview_20260720/reference_samples_author_resolved_INCLUDED_20260720.csv",
    )
    parser.add_argument("--output-reference", default="data/reference_samples.csv")
    parser.add_argument("--results-dir", default="results/author_resolved_label_sensitivity_20260618")
    args = parser.parse_args()

    root = Path.cwd()
    locked_path = (root / args.locked_reference).resolve()
    author_resolved_path = (root / args.author_resolved_included).resolve()
    output_path = (root / args.output_reference).resolve()
    results_dir = (root / args.results_dir).resolve()
    timestamp = utc_stamp()

    status_rows: list[dict[str, Any]] = []

    def status(status_value: str, reason: str) -> None:
        row = {
            "timestamp": timestamp,
            "status": status_value,
            "reason": reason,
            "input_files": "|".join(str(p) for p in [locked_path, author_resolved_path]),
            "output_reference": str(output_path),
        }
        status_rows.append(row)
        print(f"{status_value}: {reason}")

    if not locked_path.exists():
        status("ERROR", f"Missing original-label benchmark reference: {locked_path}")
    if not author_resolved_path.exists():
        status("ERROR", f"Missing author-resolved INCLUDED reference: {author_resolved_path}")
    if status_rows:
        write_csv(results_dir / "author_resolved_reference_build_status.csv", list(status_rows[0].keys()), status_rows)
        return 1

    locked_rows = read_csv(locked_path)
    author_resolved_rows = read_csv(author_resolved_path)
    locked_by_id = {row["sample_id"]: row for row in locked_rows}

    output_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for row in author_resolved_rows:
        sample_id = row.get("sample_id", "").strip()
        final_include = truthy(row.get("final_include_in_two_reader_author_resolved_reference", ""))
        final_class = row.get("final_class_name", "").strip()

        if not sample_id:
            skipped_rows.append({**row, "skip_reason": "missing sample_id"})
            continue
        if sample_id in seen_ids:
            skipped_rows.append({**row, "skip_reason": "duplicate sample_id"})
            continue
        seen_ids.add(sample_id)
        if not final_include:
            skipped_rows.append({**row, "skip_reason": "final_include_in_two_reader_author_resolved_reference is not True"})
            continue
        if final_class not in CLASS_MAP:
            skipped_rows.append({**row, "skip_reason": f"unknown final_class_name: {final_class}"})
            continue
        if sample_id not in locked_by_id:
            skipped_rows.append({**row, "skip_reason": "sample_id not found in locked 622-row reference"})
            continue

        locked = locked_by_id[sample_id]
        output_rows.append(
            {
                "sample_id": sample_id,
                "longitude": row.get("longitude", locked.get("longitude", "")),
                "latitude": row.get("latitude", locked.get("latitude", "")),
                "class_code": CLASS_MAP[final_class],
                "class_name": final_class,
                "verified": "True",
                "region_key": locked.get("region_key", ""),
                "extension_stratum": locked.get("extension_stratum", ""),
                "final_review_decision": "SECOND_READER_AUTHOR_RESOLVED_INCLUDED",
                "user_confirmation_status": locked.get("user_confirmation_status", ""),
                "user_confirmation_timestamp_utc": locked.get("user_confirmation_timestamp_utc", ""),
                "verification_source": "second_reader_vhr_author_resolved_INCLUDED_20260617",
                "verification_notes": row.get("final_resolution_status", ""),
                "second_reader_class_name": row.get("second_reader_class_name", ""),
                "second_reader_confidence": row.get("second_reader_confidence", ""),
                "final_resolution_status": row.get("final_resolution_status", ""),
            }
        )

    if not output_rows:
        status("ERROR", "No author-resolved INCLUDED rows could be converted to pipeline reference schema.")
        write_csv(results_dir / "author_resolved_reference_build_status.csv", list(status_rows[0].keys()), status_rows)
        return 1

    write_csv(output_path, OUTPUT_COLUMNS, output_rows)

    class_counts: dict[str, int] = {}
    for row in output_rows:
        class_counts[row["class_name"]] = class_counts.get(row["class_name"], 0) + 1

    count_rows = [
        {
            "timestamp": timestamp,
            "class_code": CLASS_MAP[name],
            "class_name": name,
            "verified_count": count,
            "status": "OK" if count >= 30 else "LOW_COUNT_BELOW_MIN_CLASS_COUNT_30",
            "reason": "" if count >= 30 else "Class has fewer than config.min_class_count=30 and must be dropped or marked unstable by downstream metrics.",
        }
        for name, count in sorted(class_counts.items(), key=lambda item: CLASS_MAP[item[0]])
    ]
    write_csv(
        results_dir / "author_resolved_reference_class_counts_20260618.csv",
        ["timestamp", "class_code", "class_name", "verified_count", "status", "reason"],
        count_rows,
    )

    if skipped_rows:
        write_csv(
            results_dir / "author_resolved_reference_conversion_skipped_rows_20260618.csv",
            sorted({key for row in skipped_rows for key in row.keys()}),
            skipped_rows,
        )

    provenance = {
        "timestamp": timestamp,
        "script": str(Path(__file__).resolve()),
        "locked_reference": str(locked_path),
        "locked_reference_sha256": sha256_file(locked_path),
        "author_resolved_included": str(author_resolved_path),
        "author_resolved_included_sha256": sha256_file(author_resolved_path),
        "output_reference": str(output_path),
        "output_reference_sha256": sha256_file(output_path),
        "input_locked_rows": len(locked_rows),
        "input_author_resolved_rows": len(author_resolved_rows),
        "output_verified_rows": len(output_rows),
        "skipped_rows": len(skipped_rows),
        "class_counts": class_counts,
        "class_map": CLASS_MAP,
        "note": "Converted existing author-led internally resolved INCLUDED labels only; no labels were inferred or fabricated.",
    }
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "author_resolved_reference_build_provenance_20260618.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8"
    )

    status("OK", f"Wrote {len(output_rows)} author-resolved verified rows to {output_path}")
    write_csv(results_dir / "author_resolved_reference_build_status.csv", list(status_rows[0].keys()), status_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
