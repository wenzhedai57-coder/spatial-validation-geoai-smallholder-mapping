#!/usr/bin/env python
"""Recreate the packaged indicator-variogram figure from CSV/JSON artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
BINS = ROOT / "results" / "variogram" / "variogram_indicator_bins.csv"
SUMMARY = ROOT / "results" / "variogram" / "block_distance_practical_rule_summary_20260613.json"
OUT_DIR = ROOT / "figures" / "variogram"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    rows = read_rows(BINS)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    selected_m = float(summary["suggested_block_distance_m"])

    by_class: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row.get("status") != "OK":
            continue
        by_class.setdefault(row["class_name"], []).append(row)

    fig, ax = plt.subplots(figsize=(8.6, 5.3))
    for class_name, class_rows in sorted(by_class.items()):
        xs = [float(r["distance_midpoint_m"]) / 1000.0 for r in class_rows]
        ys = [float(r["semivariance"]) for r in class_rows]
        ax.plot(xs, ys, marker="o", linewidth=1.4, markersize=3.5, label=class_name)

    ax.axvline(selected_m / 1000.0, color="#1F2937", linestyle="--", linewidth=1.2)
    ax.text(
        selected_m / 1000.0,
        ax.get_ylim()[1] * 0.96,
        f"selected q25 distance = {selected_m / 1000.0:.1f} km",
        rotation=90,
        va="top",
        ha="right",
        fontsize=8,
        color="#1F2937",
    )
    ax.set_title("One-vs-rest class-indicator empirical variograms")
    ax.set_xlabel("Distance midpoint (km)")
    ax.set_ylabel("Semivariance")
    ax.grid(True, color="#E5E7EB", linewidth=0.7)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / "variogram_indicator_ranges.png"
    pdf = OUT_DIR / "variogram_indicator_ranges.pdf"
    fig.savefig(png, dpi=240, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)

    provenance = {
        "status": "OK",
        "inputs": [
            "results/variogram/variogram_indicator_bins.csv",
            "results/variogram/block_distance_practical_rule_summary_20260613.json",
        ],
        "outputs": [
            "figures/variogram/variogram_indicator_ranges.png",
            "figures/variogram/variogram_indicator_ranges.pdf",
        ],
        "note": "Figure recreated from packaged variogram artifacts; no result values are recomputed.",
    }
    (OUT_DIR / "variogram_indicator_ranges_plot_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
