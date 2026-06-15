#!/usr/bin/env python
"""Create a blind second-reader VHR interpretation template."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "data" / "reference_samples_verified_622_public.csv"
OUT_DIR = ROOT / "docs" / "second_reader_vhr_agreement"
DATE_TAG = "20260616"

PRIMARY_LABELS = [
    "oil_palm",
    "rubber",
    "paddy",
    "other_agri",
    "forest",
    "builtup_other",
]
EXTRA_LABELS = ["uncertain", "uninterpretable"]
CONFIDENCE_VALUES = ["high", "medium", "low"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = utc_now()
    with REF_PATH.open(newline="", encoding="utf-8-sig") as fh:
        source_rows = list(csv.DictReader(fh))

    template_rows = []
    for row in source_rows:
        lon = row["longitude"]
        lat = row["latitude"]
        template_rows.append(
            {
                "sample_id": row["sample_id"],
                "longitude": lon,
                "latitude": lat,
                "map_url": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
                "second_reader_class_name": "",
                "second_reader_confidence": "",
                "imagery_source_used": "",
                "imagery_date_visible": "",
                "reviewer_initials": "",
                "review_timestamp_utc": "",
                "interpretation_notes": "",
            }
        )

    template_path = OUT_DIR / f"second_reader_blind_vhr_interpretation_template_{DATE_TAG}.csv"
    xlsx_companion_path = OUT_DIR / f"second_reader_blind_vhr_interpretation_template_{DATE_TAG}.xlsx"
    with template_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(template_rows[0].keys()))
        writer.writeheader()
        writer.writerows(template_rows)

    allowed_labels_path = OUT_DIR / f"second_reader_allowed_values_{DATE_TAG}.csv"
    with allowed_labels_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["field", "allowed_value", "meaning"])
        writer.writeheader()
        for label in PRIMARY_LABELS:
            writer.writerow(
                {
                    "field": "second_reader_class_name",
                    "allowed_value": label,
                    "meaning": "primary manuscript legend class",
                }
            )
        writer.writerow(
            {
                "field": "second_reader_class_name",
                "allowed_value": "uncertain",
                "meaning": "human reader cannot confidently assign one primary class",
            }
        )
        writer.writerow(
            {
                "field": "second_reader_class_name",
                "allowed_value": "uninterpretable",
                "meaning": "available imagery is not interpretable for this point",
            }
        )
        for value in CONFIDENCE_VALUES:
            writer.writerow(
                {
                    "field": "second_reader_confidence",
                    "allowed_value": value,
                    "meaning": "reader confidence in the assigned class",
                }
            )

    manifest = {
        "timestamp_utc": timestamp,
        "status": "OK",
        "purpose": "blind second-reader VHR interpretation template",
        "input_file": REF_PATH.relative_to(ROOT).as_posix(),
        "input_sha256": sha256_file(REF_PATH),
        "reference_rows": len(source_rows),
        "template_rows": len(template_rows),
        "template_is_blind": True,
        "hidden_from_template": [
            "class_code",
            "class_name",
            "verification_source",
            "verification_notes",
            "extension_stratum",
            "final_review_decision",
        ],
        "primary_labels": PRIMARY_LABELS,
        "extra_labels": EXTRA_LABELS,
        "output_files": [
            xlsx_companion_path.relative_to(ROOT).as_posix(),
            template_path.relative_to(ROOT).as_posix(),
            allowed_labels_path.relative_to(ROOT).as_posix(),
        ],
        "xlsx_note": "The XLSX companion is a convenience artifact generated from the CSV template for manual data entry.",
        "notes": [
            "The template contains no second-reader results until a human fills it.",
            "The template does not expose the locked reference class labels.",
            "Use uncertain or uninterpretable rather than guessing.",
        ],
    }
    manifest_path = OUT_DIR / f"second_reader_template_manifest_{DATE_TAG}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
