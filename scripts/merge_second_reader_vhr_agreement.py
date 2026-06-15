#!/usr/bin/env python
"""Merge a filled second-reader table with locked labels and compute agreement."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "data" / "reference_samples_verified_622_public.csv"
DEFAULT_OUT_DIR = ROOT / "results" / "second_reader_vhr_agreement"
PRIMARY_LABELS = [
    "oil_palm",
    "rubber",
    "paddy",
    "other_agri",
    "forest",
    "builtup_other",
]
EXTRA_LABELS = ["uncertain", "uninterpretable"]
ALL_ALLOWED_LABELS = set(PRIMARY_LABELS + EXTRA_LABELS)
ALLOWED_CONFIDENCE = {"high", "medium", "low", ""}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def cohen_kappa(confusion: dict[str, dict[str, int]]) -> tuple[str, str]:
    total = sum(sum(row.values()) for row in confusion.values())
    if total == 0:
        return "SKIPPED", "No interpretable rows available."
    observed = sum(confusion[label].get(label, 0) for label in PRIMARY_LABELS) / total
    row_totals = {label: sum(confusion[label].values()) for label in PRIMARY_LABELS}
    col_totals = {
        label: sum(confusion[row_label].get(label, 0) for row_label in PRIMARY_LABELS)
        for label in PRIMARY_LABELS
    }
    expected = sum(row_totals[label] * col_totals[label] for label in PRIMARY_LABELS) / (total * total)
    if expected == 1:
        return "SKIPPED", "Expected agreement is 1.0, so kappa is undefined."
    return f"{(observed - expected) / (1 - expected):.12g}", ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--second-reader-csv", required=True, type=Path)
    parser.add_argument("--output-dir", default=DEFAULT_OUT_DIR, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    timestamp = utc_now()
    tag = date_tag()
    second_path = args.second_reader_csv.resolve()
    out_dir = args.output_dir.resolve()
    if not second_path.exists():
        raise FileNotFoundError(second_path)

    reference_rows = read_csv(REF_PATH)
    second_rows = read_csv(second_path)
    reference_by_id = {row["sample_id"]: row for row in reference_rows}
    second_by_id = {row["sample_id"]: row for row in second_rows if row.get("sample_id")}

    completion_rows = []
    merged_rows = []
    error_count = 0
    missing_count = 0
    invalid_label_count = 0
    invalid_confidence_count = 0
    uncertain_count = 0
    uninterpretable_count = 0
    interpretable_count = 0
    agreement_count = 0
    confusion = {label: {inner: 0 for inner in PRIMARY_LABELS} for label in PRIMARY_LABELS}

    for ref in reference_rows:
        sample_id = ref["sample_id"]
        second = second_by_id.get(sample_id, {})
        label = str(second.get("second_reader_class_name", "")).strip()
        confidence = str(second.get("second_reader_confidence", "")).strip()
        row_errors = []
        if not label:
            row_errors.append("MISSING_SECOND_READER_CLASS")
            missing_count += 1
        elif label not in ALL_ALLOWED_LABELS:
            row_errors.append("INVALID_SECOND_READER_CLASS")
            invalid_label_count += 1
        if confidence not in ALLOWED_CONFIDENCE:
            row_errors.append("INVALID_CONFIDENCE")
            invalid_confidence_count += 1
        if row_errors:
            error_count += 1
        original = ref["class_name"]
        interpretable = label in PRIMARY_LABELS and not row_errors
        agreed = interpretable and label == original
        if label == "uncertain":
            uncertain_count += 1
        if label == "uninterpretable":
            uninterpretable_count += 1
        if interpretable:
            interpretable_count += 1
            confusion[original][label] += 1
            if agreed:
                agreement_count += 1
        completion_status = "OK" if not row_errors else "ERROR"
        completion_rows.append(
            {
                "sample_id": sample_id,
                "completion_status": completion_status,
                "reason": ";".join(row_errors),
                "second_reader_class_name": label,
                "second_reader_confidence": confidence,
            }
        )
        merged_rows.append(
            {
                "sample_id": sample_id,
                "longitude": ref["longitude"],
                "latitude": ref["latitude"],
                "original_class_name": original,
                "second_reader_class_name": label,
                "second_reader_confidence": confidence,
                "agreement_status": "AGREE" if agreed else ("DISAGREE" if interpretable else "NOT_SCORED"),
                "needs_adjudication": "False" if agreed else "True",
                "imagery_source_used": second.get("imagery_source_used", ""),
                "imagery_date_visible": second.get("imagery_date_visible", ""),
                "reviewer_initials": second.get("reviewer_initials", ""),
                "review_timestamp_utc": second.get("review_timestamp_utc", ""),
                "interpretation_notes": second.get("interpretation_notes", ""),
            }
        )

    kappa_value, kappa_reason = cohen_kappa(confusion)
    agreement_rate = "" if interpretable_count == 0 else f"{agreement_count / interpretable_count:.12g}"
    status = "OK" if error_count == 0 else "ERROR"
    reason = "" if error_count == 0 else "Second-reader table is incomplete or contains invalid values."

    per_class_rows = []
    for label in PRIMARY_LABELS:
        n = sum(confusion[label].values())
        agreed_n = confusion[label].get(label, 0)
        per_class_rows.append(
            {
                "original_class_name": label,
                "interpretable_count": n,
                "agreement_count": agreed_n,
                "agreement_rate": "" if n == 0 else f"{agreed_n / n:.12g}",
            }
        )

    matrix_rows = []
    for label in PRIMARY_LABELS:
        row = {"original_class_name": label}
        row.update(confusion[label])
        matrix_rows.append(row)

    disagreements = [
        row for row in merged_rows if row["needs_adjudication"] == "True"
    ]
    summary = {
        "timestamp_utc": timestamp,
        "status": status,
        "reason": reason,
        "input_files": {
            "locked_reference": REF_PATH.relative_to(ROOT).as_posix(),
            "second_reader_csv": str(second_path),
        },
        "input_sha256": {
            REF_PATH.relative_to(ROOT).as_posix(): sha256_file(REF_PATH),
            str(second_path): sha256_file(second_path),
        },
        "total_reference_rows": len(reference_rows),
        "second_reader_rows": len(second_rows),
        "missing_second_reader_class_rows": missing_count,
        "invalid_second_reader_class_rows": invalid_label_count,
        "invalid_confidence_rows": invalid_confidence_count,
        "uncertain_rows": uncertain_count,
        "uninterpretable_rows": uninterpretable_count,
        "interpretable_scored_rows": interpretable_count,
        "agreement_count": agreement_count,
        "agreement_rate": agreement_rate,
        "cohen_kappa": kappa_value if status == "OK" else "SKIPPED",
        "cohen_kappa_reason": kappa_reason if kappa_reason else (reason if status != "OK" else ""),
        "allowed_primary_labels": PRIMARY_LABELS,
        "allowed_extra_labels": EXTRA_LABELS,
    }

    if args.dry_run:
        print(json.dumps(summary, indent=2))
        return 0 if status == "OK" else 2

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / f"second_reader_agreement_summary_{tag}.json"
    completion_path = out_dir / f"second_reader_completion_audit_{tag}.csv"
    merged_path = out_dir / f"second_reader_merged_labels_{tag}.csv"
    matrix_path = out_dir / f"second_reader_confusion_matrix_{tag}.csv"
    per_class_path = out_dir / f"second_reader_per_class_agreement_{tag}.csv"
    disagreements_path = out_dir / f"second_reader_disagreements_for_adjudication_{tag}.csv"
    run_log_path = out_dir / f"RUN_LOG_second_reader_agreement_{timestamp}.txt"

    summary["output_files"] = [
        summary_path.relative_to(ROOT).as_posix(),
        completion_path.relative_to(ROOT).as_posix(),
        merged_path.relative_to(ROOT).as_posix(),
        matrix_path.relative_to(ROOT).as_posix(),
        per_class_path.relative_to(ROOT).as_posix(),
        disagreements_path.relative_to(ROOT).as_posix(),
        run_log_path.relative_to(ROOT).as_posix(),
    ]
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    run_log_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(completion_path, completion_rows, list(completion_rows[0].keys()))
    write_csv(merged_path, merged_rows, list(merged_rows[0].keys()))
    write_csv(matrix_path, matrix_rows, ["original_class_name"] + PRIMARY_LABELS)
    write_csv(per_class_path, per_class_rows, list(per_class_rows[0].keys()))
    write_csv(disagreements_path, disagreements, list(merged_rows[0].keys()))
    print(json.dumps(summary, indent=2))
    return 0 if status == "OK" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
