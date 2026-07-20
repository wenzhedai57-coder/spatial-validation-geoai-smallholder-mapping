from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "03_Figure_files").exists() else HERE.parent.parent
FIG_DIR = ROOT / "03_Figure_files"
SUPP_DIR = ROOT / "_supplement_work" / "figure_provenance_20260720"
REFERENCE_CSV = SUPP_DIR / "reference_samples_original_label_622_for_figure2.csv"
RISK_CSV = (
    ROOT
    / "_supplement_work"
    / "figure13_planar_validation_risk_20260624"
    / "figure13_planar_validation_risk_grid_20260624.csv"
)

CLASS_ORDER = [
    "oil_palm",
    "rubber",
    "forest",
    "paddy",
    "other_agri",
    "builtup_other",
]
CLASS_LABEL = {
    "oil_palm": "Oil palm",
    "rubber": "Rubber",
    "forest": "Forest",
    "paddy": "Paddy",
    "other_agri": "Other agriculture",
    "builtup_other": "Built-up/other",
}
CLASS_COLOR = {
    "oil_palm": "#E69F00",
    "rubber": "#009E73",
    "forest": "#1B7837",
    "paddy": "#56B4E9",
    "other_agri": "#CC79A7",
    "builtup_other": "#6C6C6C",
}


def setup_style() -> None:
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 8.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=600, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def box(ax, xy, width, height, title, body, facecolor, edgecolor="#2F3E46"):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.4,
        facecolor=facecolor,
        edgecolor=edgecolor,
    )
    ax.add_patch(patch)
    ax.text(x + 0.018, y + height - 0.035, title, weight="bold", va="top", fontsize=10)
    ax.text(x + 0.018, y + height - 0.105, body, va="top", fontsize=8.6, linespacing=1.35)


def arrow(ax, start, end):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=1.2,
            color="#455A64",
            connectionstyle="arc3,rad=0",
        )
    )


def make_figure1() -> None:
    fig, ax = plt.subplots(figsize=(10.8, 6.25))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(
        0.5,
        0.965,
        "Two label versions define distinct validation estimands",
        ha="center",
        va="top",
        fontsize=14,
        weight="bold",
        color="#20323A",
    )
    ax.text(
        0.5,
        0.918,
        "Label provenance, validation distance, and training support must be reported together",
        ha="center",
        va="top",
        fontsize=9.7,
        color="#53656D",
    )

    box(
        ax,
        (0.055, 0.59),
        0.40,
        0.24,
        "525-record author-resolved working label set",
        "Internal author-led re-review and resolution\n"
        "Rubber: 16 records\n"
        "q25 separation: approximately 158.5 km\n"
        "One fold has no rubber training records",
        "#E9F4F1",
        "#1F7A68",
    )
    box(
        ax,
        (0.545, 0.59),
        0.40,
        0.24,
        "622-record original-label sensitivity benchmark",
        "Historical original labels retained for sensitivity analysis\n"
        "q25 separation: approximately 126.8 km\n"
        "All four folds evaluable, but training support is uneven\n"
        "Not independently verified ground truth",
        "#FFF3E5",
        "#C66A17",
    )

    box(
        ax,
        (0.085, 0.32),
        0.34,
        0.17,
        "Estimand available",
        "Label-source and internal re-review sensitivity\nComplete four-fold q25 performance: not estimable",
        "#F6FAF9",
        "#1F7A68",
    )
    box(
        ax,
        (0.575, 0.32),
        0.34,
        0.17,
        "Estimand available",
        "Complete-fold q25 sensitivity performance\nConditional on original labels and current training support",
        "#FFFAF3",
        "#C66A17",
    )
    arrow(ax, (0.255, 0.59), (0.255, 0.50))
    arrow(ax, (0.745, 0.59), (0.745, 0.50))

    box(
        ax,
        (0.20, 0.055),
        0.60,
        0.16,
        "Common reporting rule",
        "Hold the B0-B3 feature/model definitions fixed; report the label version, q25 distance,\n"
        "per-fold training support, unweighted fold mean, and pooled out-of-fold performance.",
        "#EEF2F5",
        "#516A78",
    )
    arrow(ax, (0.255, 0.32), (0.43, 0.215))
    arrow(ax, (0.745, 0.32), (0.57, 0.215))
    ax.text(
        0.5,
        0.005,
        "The two branches answer different questions; neither should be presented as a universal map-accuracy estimate.",
        ha="center",
        fontsize=8.7,
        color="#455A64",
        style="italic",
    )
    save(fig, "Figure_1_workflow")


def make_figure2() -> None:
    df = pd.read_csv(REFERENCE_CSV)
    extent = [df.longitude.min() - 0.65, df.longitude.max() + 0.65,
              df.latitude.min() - 0.55, df.latitude.max() + 0.55]
    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(8.4, 7.7))
    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(extent, crs=proj)
    ax.add_feature(cfeature.NaturalEarthFeature(
        "physical", "land", "10m", facecolor="#F2F0E8", edgecolor="none"), zorder=0)
    ax.add_feature(cfeature.NaturalEarthFeature(
        "physical", "ocean", "10m", facecolor="#EAF3F7", edgecolor="none"), zorder=0)
    ax.add_feature(cfeature.NaturalEarthFeature(
        "physical", "coastline", "10m", facecolor="none", edgecolor="#52656D"),
        linewidth=0.55, zorder=1)
    ax.add_feature(cfeature.NaturalEarthFeature(
        "cultural", "admin_0_boundary_lines_land", "10m", facecolor="none", edgecolor="#8A999F"),
        linewidth=0.35, linestyle="--", zorder=1)
    for cls in CLASS_ORDER:
        sub = df[df.class_name == cls]
        ax.scatter(
            sub.longitude,
            sub.latitude,
            s=13,
            c=CLASS_COLOR[cls],
            label=f"{CLASS_LABEL[cls]} (n={len(sub)})",
            edgecolors="white",
            linewidths=0.18,
            alpha=0.88,
            transform=proj,
            zorder=3,
        )
    gl = ax.gridlines(draw_labels=True, linewidth=0.35, color="#9AA8AE", alpha=0.65, linestyle=":")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}
    ax.set_title("Original-label sensitivity benchmark records", weight="bold", pad=10)
    ax.text(
        0.5,
        1.005,
        "Locations and original class labels for 622 records; not independently verified ground truth",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8.6,
        color="#53656D",
    )
    leg = ax.legend(
        loc="lower left",
        bbox_to_anchor=(0.015, 0.02),
        frameon=True,
        framealpha=0.94,
        title="Original label",
        borderpad=0.7,
    )
    leg.get_title().set_fontweight("bold")
    ax.text(
        0.985,
        0.018,
        "Basemap: Natural Earth public-domain data",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.3,
        color="#53656D",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 2.5},
    )
    save(fig, "Figure_2_original_label_benchmark_map")


def make_figure13() -> None:
    df = pd.read_csv(RISK_CSV)
    metrics = list(df.metric.drop_duplicates())
    ncols = min(3, len(metrics))
    nrows = int(np.ceil(len(metrics) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(11.0, 4.6 * nrows), squeeze=False)
    vmin = float(df.mean_value.min())
    vmax = float(df.mean_value.max())
    cmap = plt.get_cmap("viridis")
    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
    for ax, metric in zip(axes.ravel(), metrics):
        sub = df[df.metric == metric]
        for row in sub.itertuples():
            face = cmap(norm(row.mean_value)) if row.status == "OK" else "#D9D9D9"
            ax.add_patch(
                Rectangle(
                    (row.cell_lon_min, row.cell_lat_min),
                    row.cell_lon_max - row.cell_lon_min,
                    row.cell_lat_max - row.cell_lat_min,
                    facecolor=face,
                    edgecolor="white",
                    linewidth=0.28,
                )
            )
        ax.set_xlim(df.cell_lon_min.min(), df.cell_lon_max.max())
        ax.set_ylim(df.cell_lat_min.min(), df.cell_lat_max.max())
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(metric, weight="bold")
        ax.set_xlabel("Longitude (degrees)")
        ax.set_ylabel("Latitude (degrees)")
        ax.grid(False)
    for ax in axes.ravel()[len(metrics):]:
        ax.axis("off")
    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes([0.34, 0.105, 0.32, 0.022])
    fig.colorbar(sm, cax=cax, orientation="horizontal")
    cax.set_title("Cell mean diagnostic value", fontsize=8.8, pad=5)
    fig.suptitle(
        "Planar validation-risk diagnostics for the 622-record original-label sensitivity benchmark",
        fontsize=13,
        weight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.018,
        "Descriptive sample-support diagnostics only; this is not a calibrated spatial risk surface.",
        ha="center",
        fontsize=8.7,
        style="italic",
        color="#53656D",
    )
    fig.subplots_adjust(top=0.88, bottom=0.27, left=0.07, right=0.98, wspace=0.26)
    save(fig, "Figure_13_planar_validation_risk_map")


def write_provenance() -> None:
    SUPP_DIR.mkdir(parents=True, exist_ok=True)
    script_copy = SUPP_DIR / Path(__file__).name
    if Path(__file__).resolve() != script_copy.resolve():
        shutil.copy2(__file__, script_copy)
    shutil.copy2(RISK_CSV, SUPP_DIR / RISK_CSV.name)
    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "figure_1": {
            "method": "Author-designed deterministic schematic drawn with Python and Matplotlib; no generative image model used.",
            "outputs": ["Figure_1_workflow.png", "Figure_1_workflow.pdf"],
        },
        "figure_2": {
            "source_table": "data/reference_samples_verified_622_public.csv",
            "historical_schema_note": "The filename and verified field are historical inclusion identifiers, not independent-verification claims.",
            "basemap": "Natural Earth 1:10m land, ocean, coastline, and country boundary vector data (public domain).",
            "software": "Python, Matplotlib, Cartopy",
            "outputs": [
                "Figure_2_original_label_benchmark_map.png",
                "Figure_2_original_label_benchmark_map.pdf",
            ],
        },
        "figure_13": {
            "source_table": RISK_CSV.name,
            "interpretation": "Descriptive planar sample-support diagnostics; not a calibrated risk surface.",
            "outputs": ["Figure_13_planar_validation_risk_map.png", "Figure_13_planar_validation_risk_map.pdf"],
        },
        "versions": {
            "python": __import__("platform").python_version(),
            "matplotlib": matplotlib.__version__,
            "cartopy": __import__("cartopy").__version__,
            "pandas": pd.__version__,
        },
    }
    (SUPP_DIR / "FIGURE_PROVENANCE_20260720.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SUPP_DIR.mkdir(parents=True, exist_ok=True)
    if not REFERENCE_CSV.exists():
        external_source_text = os.environ.get("IJRS_REFERENCE_CSV", "")
        external_source = Path(external_source_text) if external_source_text else None
        if external_source is None:
            external_source = (
                ROOT.parent
                / "IJRS_GITHUB_SYNC_20260720"
                / "data"
                / "reference_samples_verified_622_public.csv"
            )
        if not external_source.exists():
            raise FileNotFoundError(
                "Set IJRS_REFERENCE_CSV to the 622-record original-label table before regeneration."
            )
        shutil.copy2(external_source, REFERENCE_CSV)
    setup_style()
    make_figure1()
    make_figure2()
    make_figure13()
    write_provenance()
    for old in [
        FIG_DIR / "Figure_2_locked_verified_samples_map.png",
        FIG_DIR / "Figure_2_locked_verified_samples_map.pdf",
    ]:
        if old.exists():
            old.unlink()
    print("Redrew Figures 1, 2, and 13 and wrote provenance.")


if __name__ == "__main__":
    main()
