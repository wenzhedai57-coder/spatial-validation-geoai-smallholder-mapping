#!/usr/bin/env python
"""Regenerate the final submission Figure 13 without any third-party basemap."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle


HERE = Path(__file__).resolve().parent
GRID = HERE / "figure13_planar_validation_risk_grid_20260624.csv"
OUT_PNG = HERE / "Figure_13_planar_validation_risk_map_plain_grid.png"
OUT_PDF = HERE / "Figure_13_planar_validation_risk_map_plain_grid.pdf"
PROVENANCE = HERE / "figure13_plain_grid_provenance_20260624.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rows() -> list[dict[str, float | int | str]]:
    rows = []
    with GRID.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("status") != "OK":
                continue
            rows.append(
                {
                    "metric": r["metric"],
                    "x0": float(r["cell_lon_min"]),
                    "x1": float(r["cell_lon_max"]),
                    "y0": float(r["cell_lat_min"]),
                    "y1": float(r["cell_lat_max"]),
                    "n": int(float(r["n_samples"])),
                    "value": float(r["mean_value"]),
                }
            )
    return rows


def main() -> int:
    rows = load_rows()
    metrics = list(dict.fromkeys(str(r["metric"]) for r in rows))
    if len(metrics) != 3:
        raise RuntimeError(f"Expected 3 Figure 13 metrics, found {metrics}")

    all_x0 = min(float(r["x0"]) for r in rows)
    all_x1 = max(float(r["x1"]) for r in rows)
    all_y0 = min(float(r["y0"]) for r in rows)
    all_y1 = max(float(r["y1"]) for r in rows)
    xs = sorted({float(r["x0"]) for r in rows} | {float(r["x1"]) for r in rows})
    ys = sorted({float(r["y0"]) for r in rows} | {float(r["y1"]) for r in rows})

    labels = {
        "Random-CV disagreement": "a. Random-CV disagreement",
        "Strict-spatial B3 error": "b. Strict-spatial B3 error",
        "Trust-routing review/calibration burden": "c. Trust-routing burden",
    }
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 5.8), constrained_layout=False)
    fig.subplots_adjust(left=0.055, right=0.905, top=0.84, bottom=0.18, wspace=0.08)
    cmap = plt.get_cmap("viridis")
    norm = Normalize(vmin=0, vmax=1)

    for ax, metric in zip(axes, metrics):
        subset = [r for r in rows if r["metric"] == metric]
        ax.set_facecolor("#f6f7f8")
        for x in xs:
            ax.plot([x, x], [all_y0, all_y1], color="#d0d4d9", linewidth=0.25, zorder=1)
        for y in ys:
            ax.plot([all_x0, all_x1], [y, y], color="#d0d4d9", linewidth=0.25, zorder=1)
        for r in subset:
            ax.add_patch(
                Rectangle(
                    (float(r["x0"]), float(r["y0"])),
                    float(r["x1"]) - float(r["x0"]),
                    float(r["y1"]) - float(r["y0"]),
                    facecolor=cmap(norm(float(r["value"]))),
                    edgecolor="#4f5661",
                    linewidth=0.2,
                    zorder=3,
                )
            )
            if int(r["n"]) >= 10:
                ax.text(
                    (float(r["x0"]) + float(r["x1"])) / 2,
                    (float(r["y0"]) + float(r["y1"])) / 2,
                    str(r["n"]),
                    ha="center",
                    va="center",
                    fontsize=4.6,
                    color="white",
                    zorder=4,
                )
        ax.set_title(labels.get(metric, metric), fontsize=9.4, weight="bold", pad=8)
        ax.set_xlim(all_x0 - 0.1, all_x1 + 0.1)
        ax.set_ylim(all_y0 - 0.1, all_y1 + 0.1)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("Longitude", labelpad=5)
        if ax is axes[0]:
            ax.set_ylabel("Latitude", labelpad=6)
        ax.tick_params(labelsize=7, length=2.5)
        ax.spines[["top", "right"]].set_visible(False)

    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes([0.925, 0.28, 0.014, 0.48])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_label("Occupied-cell mean diagnostic value", fontsize=8, labelpad=8)
    cbar.ax.tick_params(labelsize=7)
    fig.suptitle(
        "Planar validation-risk diagnostics from original-label benchmark evidence only",
        fontsize=12,
        weight="bold",
        y=0.955,
    )
    fig.text(
        0.5,
        0.055,
        "Plain geographic grid; no third-party basemap. Cell color is the occupied-cell mean; "
        "numbers mark occupied cells with n >= 10 samples. Empty cells are not interpolated.",
        ha="center",
        fontsize=8,
    )
    fig.savefig(OUT_PNG, dpi=600)
    fig.savefig(OUT_PDF)
    plt.close(fig)

    provenance = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "method": "plain_geographic_grid_no_third_party_basemap",
        "input_file": GRID.name,
        "input_sha256": sha256(GRID),
        "output_png": OUT_PNG.name,
        "output_png_sha256": sha256(OUT_PNG),
        "output_pdf": OUT_PDF.name,
        "output_pdf_sha256": sha256(OUT_PDF),
        "random_seed": "NOT_USED",
        "note": "No metric values are changed; the plot redraws occupied-grid means from the packaged grid CSV.",
    }
    PROVENANCE.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(provenance, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
