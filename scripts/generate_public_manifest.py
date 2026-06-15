#!/usr/bin/env python
"""Generate public-package manifest, checksums, and verification summary."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manifests_checksums"
DATE_TAG = "20260616"


def is_public_payload_file(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if ".git" in rel_parts or "__pycache__" in rel_parts:
        return False
    if path.suffix.lower() == ".pyc":
        return False
    return path.is_file()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def text_for_scan(path: Path) -> str | None:
    if path.suffix.lower() not in {
        ".md",
        ".txt",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".py",
        ".cff",
        ".tsv",
    }:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        if old.is_file():
            old.unlink()

    files = sorted(p for p in ROOT.rglob("*") if is_public_payload_file(p))
    manifest_rows = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        manifest_rows.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    manifest = OUT / f"PUBLIC_REPO_MANIFEST_{DATE_TAG}.csv"
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    checksums = OUT / f"PUBLIC_REPO_CHECKSUMS_SHA256_{DATE_TAG}.txt"
    checksums.write_text(
        "".join(f"{row['sha256']}  {row['path']}\n" for row in manifest_rows),
        encoding="utf-8",
    )

    marker_sets = {
        "unresolved_author_placeholders": [
            "ARCHIVE" + "_DOI_OR_STABLE_URL_REQUIRED",
            "AUTHOR" + "_INPUT_REQUIRED",
            "AUTHOR" + "_INPUT_REQUIRED_CREDIT",
        ],
        "legacy_template_placeholders": [
            "EDIT" + "_ME",
            "PENDING" + "_USER_CONFIRMATION",
        ],
        "expected_result_status_terms": [
            "NOT" + "_VERIFIED",
            "MISSING",
            "SKIPPED",
            "ERROR",
        ],
        "review_queue_boundary_terms": [
            "NOT" + "_GROUND_TRUTH",
            "UN" + "VERIFIED",
            "RE" + "CONSTRUCTED",
            "RAW" + "_SOURCES_MISSING",
        ],
    }
    scan = {}
    for group, terms in marker_sets.items():
        hits = []
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith("manifests_checksums/"):
                continue
            if group == "expected_result_status_terms" and rel.startswith("scripts/"):
                continue
            text = text_for_scan(path)
            if text is None:
                continue
            count = sum(text.count(term) for term in terms)
            if count:
                hits.append({"path": rel, "count": count})
        scan[group] = {
            "file_count": len(hits),
            "occurrences": sum(h["count"] for h in hits),
            "sample_files": [h["path"] for h in hits[:10]],
        }

    reference_rows = None
    all_verified = None
    ref = ROOT / "data" / "reference_samples_verified_622_public.csv"
    if ref.exists():
        with ref.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        reference_rows = len(rows)
        all_verified = all(str(r.get("verified", "")).strip().lower() == "true" for r in rows)

    manuscript_png = len(list((ROOT / "figures" / "manuscript").glob("*.png")))
    manuscript_pdf = len(list((ROOT / "figures" / "manuscript").glob("*.pdf")))
    large_files = [
        p.relative_to(ROOT).as_posix()
        for p in files
        if p.stat().st_size > 100 * 1024 * 1024
    ]
    full_queues = [
        p.relative_to(ROOT).as_posix()
        for p in files
        if p.name.startswith("targeted_validation_candidates" + "_REVIEW")
    ]
    local_path_hits = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = text_for_scan(path)
        if text and "C:\\Users\\m1761" in text:
            local_path_hits.append(rel)

    generated_manifest_files = [
        f"manifests_checksums/PUBLIC_REPO_MANIFEST_{DATE_TAG}.csv",
        f"manifests_checksums/PUBLIC_REPO_CHECKSUMS_SHA256_{DATE_TAG}.txt",
        f"manifests_checksums/PUBLIC_REPO_VERIFICATION_{DATE_TAG}.json",
    ]
    verification = {
        "status": "OK" if not large_files else "CHECK",
        "payload_file_count_excluding_generated_manifest_files": len(files),
        "generated_manifest_files": generated_manifest_files,
        "expected_zip_entry_count_after_manifest_generation": len(files) + len(generated_manifest_files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "required_root_entries": {
            name: (ROOT / name).exists()
            for name in [
                "README.md",
                "LICENSE",
                "CITATION.cff",
                "config",
                "scripts",
                "data",
                "results",
                "figures",
                "manifests_checksums",
                "docs",
            ]
        },
        "checks": {
            "active_reference_rows": reference_rows,
            "active_reference_all_verified": all_verified,
            "feature_stack_count": len(list((ROOT / "data" / "features_fold3_teacher_vhr_repair_20260613").glob("B*.csv"))),
            "manuscript_png_count": manuscript_png,
            "manuscript_pdf_count": manuscript_pdf,
            "variogram_png_exists": (ROOT / "figures" / "variogram" / "variogram_indicator_ranges.png").exists(),
            "variogram_pdf_exists": (ROOT / "figures" / "variogram" / "variogram_indicator_ranges.pdf").exists(),
            "spatial_sensitivity_table13_exists": (ROOT / "results" / "spatial_sensitivity" / "table13_spatial_cv_sensitivity_summary.csv").exists(),
            "review_planning_summary_exists": (ROOT / "results" / "review_planning" / "targeted_validation_candidate_summary_review_planning_20260613.csv").exists(),
            "point_level_public_sentinel2_imagery_date_audit_exists": any((ROOT / "results" / "point_imagery_dates").glob("point_level_public_sentinel2_imagery_dates_*.csv")),
            "full_targeted_review_queues_excluded": len(full_queues) == 0,
            "no_file_over_100mb": len(large_files) == 0,
        },
        "marker_scan_excluding_manifests": scan,
        "local_absolute_path_hits": local_path_hits,
        "large_files": large_files,
        "full_targeted_review_queue_files": full_queues,
        "notes": [
            "The hash-preserved original run configuration may contain original local provenance strings; use config_public_reproduction_20260615.yaml for repository-relative reruns.",
            "Expected result status terms are retained where they are genuine audit outcomes.",
            "Review-planning summaries are retained outside data/ and are not ground truth.",
        ],
    }
    verification_path = OUT / f"PUBLIC_REPO_VERIFICATION_{DATE_TAG}.json"
    verification_path.write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(verification, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
