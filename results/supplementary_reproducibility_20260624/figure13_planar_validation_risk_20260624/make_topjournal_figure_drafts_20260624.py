#!/usr/bin/env python
"""Create draft top-journal-style figure redesigns without touching submission figures."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.transforms import Affine2D
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageEnhance
from pyproj import Transformer

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import contextily as ctx
from cartopy.io import shapereader
from adjustText import adjust_text
from shapely.geometry import box


TAG = "20260624"


ROOT = Path(r"C:\Users\m1761\Documents\New project")
REV = ROOT / "IJRS_TRUST_REVISION_20260624"
REPO = ROOT / "IJRS_ADJUDICATED_SENSITIVITY_20260618"
OUT = REV / "figure_redesign_drafts_20260624"

REF_PATH = REPO / "data" / "reference_samples_verified_622_public.csv"
PRED_PATH = REPO / "results" / "active_q25_rerun" / "predictions_by_fold.csv"
TABLE3_PATH = REPO / "results" / "active_q25_rerun" / "table3_accuracy_by_stack_split.csv"
DISAGREE_PATH = REPO / "results" / "review_planning" / "sample_level_failure_disagreement.csv"
TRUST_PATH = REV / "supplement_work" / "trust_routing_diagnostics_20260624" / "trust_routing_point_assignments_20260624.csv"
TRANSFER_SIM_PATH = REPO / "results" / "second_round_evidence" / "region_transfer_similarity_20260613.csv"
FIGURE3_VALUES_PATH = OUT / f"figure3_random_vs_spatial_accuracy_values_{TAG}.csv"
FIGURE3_PROV_PATH = OUT / f"figure3_random_vs_spatial_accuracy_provenance_{TAG}.json"


CLASS_LABELS = {
    1: "oil palm",
    2: "rubber",
    3: "paddy",
    4: "other agri",
    5: "forest",
    6: "built-up/other",
}
CLASS_COLORS = {
    "oil_palm": "#1B9E77",
    "oil palm": "#1B9E77",
    "rubber": "#D95F02",
    "paddy": "#7570B3",
    "other_agri": "#E7298A",
    "other agri": "#E7298A",
    "forest": "#66A61E",
    "builtup_other": "#6B6B6B",
    "built-up/other": "#6B6B6B",
}
ROUTE_COLORS = {
    "low_risk_screening_only": "#2A9D8F",
    "local_calibration_required": "#E9C46A",
    "manual_vhr_field_review": "#E76F51",
}
ROUTE_LABELS = {
    "low_risk_screening_only": "low-risk screening",
    "local_calibration_required": "local calibration",
    "manual_vhr_field_review": "VHR/field review",
}
STACK_ORDER = ["B0", "B1", "B2", "B3"]
SPLIT_ORDER = ["random", "spatial"]
SPLIT_LABELS = {"random": "Random CV", "spatial": "q25 spatial"}
SPLIT_COLORS = {"random": "#4C78A8", "spatial": "#E68632"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def savefig(fig: plt.Figure, stem: str) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{stem}.png"
    pdf = OUT / f"{stem}.pdf"
    fig.savefig(png, dpi=450, bbox_inches="tight")
    plt.close(fig)
    with Image.open(png) as image:
        rgb = image.convert("RGB")
        rgb.save(pdf, "PDF", resolution=450.0, quality=95)
    return {"png": str(png), "pdf": str(pdf)}


def setup_style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.65,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.facecolor": "white",
    })


def add_map_base(ax, extent, grid=True) -> None:
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor="#F3F2EC", edgecolor="none", zorder=0)
    ax.add_feature(cfeature.OCEAN.with_scale("10m"), facecolor="#EEF5F7", edgecolor="none", zorder=0)
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.45, edgecolor="#7A7A7A", zorder=2)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.35, edgecolor="#9A9A9A", zorder=2)
    if grid:
        gl = ax.gridlines(
            draw_labels=True,
            linewidth=0.25,
            color="#B5B5B5",
            alpha=0.55,
            linestyle="-",
            x_inline=False,
            y_inline=False,
        )
        gl.top_labels = False
        gl.right_labels = False
        gl.xlabel_style = {"size": 6, "color": "#555555"}
        gl.ylabel_style = {"size": 6, "color": "#555555"}


def add_panel_label(ax, label: str) -> None:
    ax.text(
        0.01,
        0.99,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        path_effects=[pe.withStroke(linewidth=2.5, foreground="white")],
        zorder=20,
    )


def add_north_arrow(ax, x=0.95, y=0.92) -> None:
    ax.annotate(
        "N",
        xy=(x, y),
        xytext=(x, y - 0.10),
        xycoords=ax.transAxes,
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        arrowprops=dict(arrowstyle="-|>", color="0.2", lw=0.9),
        zorder=30,
    )


def add_scale_bar(ax, length_km=100, loc=(0.08, 0.08), lat=3.8) -> None:
    x0, y0 = loc
    extent = ax.get_extent(ccrs.PlateCarree())
    lon_span = extent[1] - extent[0]
    lat_span = extent[3] - extent[2]
    deg = length_km / (111.32 * math.cos(math.radians(lat)))
    lon0 = extent[0] + lon_span * x0
    lat0 = extent[2] + lat_span * y0
    ax.plot([lon0, lon0 + deg], [lat0, lat0], transform=ccrs.PlateCarree(), color="0.15", lw=1.8, solid_capstyle="butt", zorder=30)
    ax.text(lon0 + deg / 2, lat0 + lat_span * 0.02, f"{length_km} km", transform=ccrs.PlateCarree(), ha="center", va="bottom", fontsize=6, zorder=30)


def region_bounds(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for region, g in df.groupby("region_key"):
        rows.append({
            "region_key": region,
            "lon_min": g["longitude"].min(),
            "lon_max": g["longitude"].max(),
            "lat_min": g["latitude"].min(),
            "lat_max": g["latitude"].max(),
            "longitude": g["longitude"].mean(),
            "latitude": g["latitude"].mean(),
            "n": len(g),
        })
    return pd.DataFrame(rows)


def draw_extent_box(ax, df: pd.DataFrame, region: str, color: str, label: str | None = None, pad=0.05, lw=1.0) -> None:
    g = df[df["region_key"] == region]
    if g.empty:
        return
    x0, x1 = g["longitude"].min() - pad, g["longitude"].max() + pad
    y0, y1 = g["latitude"].min() - pad, g["latitude"].max() + pad
    rect = Rectangle((x0, y0), x1 - x0, y1 - y0, transform=ccrs.PlateCarree(), fill=False, edgecolor=color, lw=lw, zorder=9)
    ax.add_patch(rect)
    if label:
        ax.text(x0, y1 + 0.03, label, transform=ccrs.PlateCarree(), color=color, fontsize=6.5, weight="bold", zorder=10)


def figure3_values(table3: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "config_hash", "input_files", "random_seed", "status", "stack", "model", "split", "fold", "oa", "macro_f1"}
    missing = sorted(required - set(table3.columns))
    rows = []
    source_hash = sha256_file(TABLE3_PATH)
    if missing:
        for stack in STACK_ORDER:
            for split in SPLIT_ORDER:
                for metric in ["oa", "macro_f1"]:
                    rows.append({
                        "status": "ERROR",
                        "reason": "missing source columns: " + ";".join(missing),
                        "stack": stack,
                        "split": split,
                        "metric": metric,
                        "n_folds": 0,
                        "mean": "",
                        "sd": "",
                        "display_label": "ERROR",
                        "source_table": str(TABLE3_PATH),
                        "source_sha256": source_hash,
                    })
        values = pd.DataFrame(rows)
        values.to_csv(FIGURE3_VALUES_PATH, index=False)
        raise ValueError("Cannot compute Figure 3 values; missing source columns: " + ", ".join(missing))

    work = table3.copy()
    work = work[work["status"].eq("OK") & work["model"].eq("RandomForest")]
    work = work[work["stack"].isin(STACK_ORDER) & work["split"].isin(SPLIT_ORDER)]

    for stack in STACK_ORDER:
        for split in SPLIT_ORDER:
            g = work[(work["stack"] == stack) & (work["split"] == split)].copy()
            for metric in ["oa", "macro_f1"]:
                vals = pd.to_numeric(g[metric], errors="coerce").dropna()
                if vals.empty:
                    rows.append({
                        "status": "ERROR",
                        "reason": f"no numeric {metric} values for {stack}/{split}/RandomForest",
                        "stack": stack,
                        "split": split,
                        "metric": metric,
                        "n_folds": 0,
                        "mean": "",
                        "sd": "",
                        "display_label": "ERROR",
                        "source_table": str(TABLE3_PATH),
                        "source_sha256": source_hash,
                    })
                    continue
                mean = float(vals.mean())
                sd = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
                rows.append({
                    "status": "OK",
                    "reason": "",
                    "stack": stack,
                    "split": split,
                    "metric": metric,
                    "n_folds": int(len(vals)),
                    "mean": mean,
                    "sd": sd,
                    "display_label": f"{mean:.2f}",
                    "source_table": str(TABLE3_PATH),
                    "source_sha256": source_hash,
                    "source_timestamps": ";".join(sorted(g["timestamp"].dropna().astype(str).unique())),
                    "config_hashes": ";".join(sorted(g["config_hash"].dropna().astype(str).unique())),
                    "input_files": ";".join(sorted(g["input_files"].dropna().astype(str).unique())),
                    "random_seeds": ";".join(sorted(g["random_seed"].dropna().astype(str).unique())),
                    "folds": ";".join(sorted(g["fold"].dropna().astype(str).unique())),
                })

    values = pd.DataFrame(rows)
    values.to_csv(FIGURE3_VALUES_PATH, index=False)
    provenance = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "OK" if values["status"].eq("OK").all() else "ERROR",
        "figure": "Figure_3_random_vs_spatial_accuracy",
        "source_table": {"path": str(TABLE3_PATH), "sha256": source_hash, "rows": int(len(table3))},
        "filter": {"model": "RandomForest", "status": "OK", "stacks": STACK_ORDER, "splits": SPLIT_ORDER},
        "computed_metrics": "fold mean and sample standard deviation from source fold rows",
        "display_rule": "bar labels are source-computed means rounded to two decimals by this script",
        "values_csv": {"path": str(FIGURE3_VALUES_PATH), "sha256": sha256_file(FIGURE3_VALUES_PATH), "rows": int(len(values))},
    }
    FIGURE3_PROV_PATH.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    if not values["status"].eq("OK").all():
        bad = values[~values["status"].eq("OK")][["stack", "split", "metric", "reason"]]
        raise ValueError("Cannot plot Figure 3 because some computed values failed:\n" + bad.to_string(index=False))
    return values


def figure3_random_vs_spatial_accuracy(table3: pd.DataFrame) -> dict[str, str]:
    values = figure3_values(table3)
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.25), sharey=True)
    metrics = [("oa", "a", "Overall accuracy"), ("macro_f1", "b", "Macro-F1")]
    x = np.arange(len(STACK_ORDER), dtype=float)
    offsets = {"random": -0.18, "spatial": 0.18}
    bar_width = 0.32

    for ax, (metric, panel, title) in zip(axes, metrics):
        metric_df = values[values["metric"].eq(metric)].copy()
        metric_df["mean"] = pd.to_numeric(metric_df["mean"])
        metric_df["sd"] = pd.to_numeric(metric_df["sd"])
        for split in SPLIT_ORDER:
            sub = metric_df[metric_df["split"].eq(split)].set_index("stack").loc[STACK_ORDER].reset_index()
            xpos = x + offsets[split]
            bars = ax.bar(
                xpos,
                sub["mean"],
                yerr=sub["sd"],
                width=bar_width,
                color=SPLIT_COLORS[split],
                edgecolor="#222222",
                linewidth=0.45,
                capsize=3,
                error_kw={"elinewidth": 0.8, "capthick": 0.8, "ecolor": "#222222"},
                label=SPLIT_LABELS[split],
                zorder=3,
            )
        ax.set_title(title, loc="left", pad=4)
        ax.text(-0.08, 1.04, panel, transform=ax.transAxes, ha="left", va="bottom", fontsize=10, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(STACK_ORDER)
        ax.set_xlabel("Feature stack")
        ax.set_ylim(0, 1.0)
        ax.set_yticks(np.arange(0, 1.01, 0.2))
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.45, alpha=0.8, zorder=0)
        ax.margins(x=0.08)

    axes[0].set_ylabel("Fold mean +/- fold SD")
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, frameon=False, handlelength=1.4)
    fig.suptitle("Random validation remains optimistic under spatially honest q25 splits", x=0.02, ha="left", y=1.04, fontsize=9.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96], w_pad=1.5)
    return savefig(fig, "draft_Figure_3_random_vs_spatial_accuracy")


def figure2_reference_samples(ref: pd.DataFrame) -> dict[str, str]:
    fig = plt.figure(figsize=(8.8, 5.05))
    gs = GridSpec(3, 4, width_ratios=[1.18, 1.18, 1.02, 1.18], height_ratios=[0.95, 0.9, 0.9], hspace=0.48, wspace=0.54)
    ax_main = fig.add_subplot(gs[:, 0:2], projection=ccrs.PlateCarree())
    ax_over = fig.add_subplot(gs[0, 2:], projection=ccrs.PlateCarree())
    ax_reg = fig.add_subplot(gs[1, 2:])
    ax_cls = fig.add_subplot(gs[2, 2:])

    add_map_base(ax_over, [95.5, 108.2, -1.0, 8.3], grid=False)
    add_panel_label(ax_over, "b")
    ax_over.set_title("Regional context", loc="left", pad=3)
    x0, x1 = 99.5, 104.8
    y0, y1 = 1.0, 6.8
    ax_over.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, transform=ccrs.PlateCarree(), fill=False, edgecolor="#303030", lw=1.0, zorder=12))
    add_north_arrow(ax_over, x=0.90, y=0.92)

    add_map_base(ax_main, [99.7, 104.5, 1.05, 6.65])
    add_panel_label(ax_main, "a")
    ax_main.set_title("Verified reference samples by class and validation extension", loc="left", pad=3)
    for region, color, label in [
        ("study_area", "#4C78A8", "Johor core"),
        ("kedah_perlis_paddy_belt", "#F2C94C", "Kedah-Perlis paddy belt"),
        ("johor_negeri_pahang_rubber_belt", "#D95F02", "rubber belt"),
    ]:
        draw_extent_box(ax_main, ref, region, color, label=None, pad=0.08, lw=0.9)
    for cls, g in ref.groupby("class_name", sort=False):
        ax_main.scatter(
            g["longitude"],
            g["latitude"],
            s=13,
            color=CLASS_COLORS.get(cls, "#777777"),
            edgecolor="white",
            linewidth=0.25,
            alpha=0.90,
            transform=ccrs.PlateCarree(),
            label=cls.replace("_", " "),
            zorder=8,
        )
    add_north_arrow(ax_main, x=0.95, y=0.92)
    add_scale_bar(ax_main, length_km=100, loc=(0.08, 0.07), lat=3.8)

    region_counts = ref["region_key"].value_counts().rename_axis("region_key").reset_index(name="n")
    major = ["study_area", "kedah_perlis_paddy_belt", "johor_negeri_pahang_rubber_belt"]
    region_counts["group"] = np.where(region_counts["region_key"].isin(major), region_counts["region_key"], "advisor/teacher VHR cells")
    plot_counts = region_counts.groupby("group", as_index=False)["n"].sum()
    order = ["study_area", "kedah_perlis_paddy_belt", "johor_negeri_pahang_rubber_belt", "advisor/teacher VHR cells"]
    plot_counts["group"] = pd.Categorical(plot_counts["group"], order, ordered=True)
    plot_counts = plot_counts.sort_values("group")
    colors = ["#4C78A8", "#F2C94C", "#D95F02", "#9E9E9E"]
    ax_reg.barh(np.arange(len(plot_counts)), plot_counts["n"], color=colors, edgecolor="0.2", linewidth=0.4)
    compact_region = {
        "study_area": "Johor core",
        "kedah_perlis_paddy_belt": "Kedah-Perlis",
        "johor_negeri_pahang_rubber_belt": "rubber belt",
        "advisor/teacher VHR cells": "VHR cells",
    }
    ax_reg.set_yticks(np.arange(len(plot_counts)), [""] * len(plot_counts))
    ax_reg.tick_params(axis="y", length=0)
    ax_reg.invert_yaxis()
    ax_reg.set_xlabel("verified samples")
    ax_reg.set_title("Region support", loc="left", pad=3)
    ax_reg.text(-0.08, 1.10, "c", transform=ax_reg.transAxes, ha="left", va="bottom", fontsize=10, fontweight="bold", clip_on=False)
    for i, (group, n) in enumerate(zip(plot_counts["group"], plot_counts["n"])):
        label = compact_region.get(str(group), str(group))
        text_color = "white" if str(group) in {"study_area", "johor_negeri_pahang_rubber_belt"} else "black"
        ax_reg.text(6, i, label, va="center", ha="left", fontsize=6.7, color=text_color, fontweight="bold")
        ax_reg.text(n + 5, i, str(int(n)), va="center", fontsize=7)
    ax_reg.set_xlim(0, max(plot_counts["n"]) * 1.25)

    class_counts = ref["class_name"].value_counts().reindex(["forest", "oil_palm", "rubber", "paddy", "other_agri", "builtup_other"])
    ax_cls.bar(np.arange(len(class_counts)), class_counts.values, color=[CLASS_COLORS[c] for c in class_counts.index], edgecolor="0.2", linewidth=0.4)
    short_class = ["forest", "oil\npalm", "rubber", "paddy", "other\nagri", "built-up\nother"]
    ax_cls.set_xticks(np.arange(len(class_counts)), short_class, rotation=0)
    ax_cls.set_ylabel("verified samples")
    ax_cls.set_title("Class support", loc="left", pad=3)
    ax_cls.text(-0.08, 1.10, "d", transform=ax_cls.transAxes, ha="left", va="bottom", fontsize=10, fontweight="bold", clip_on=False)
    for i, n in enumerate(class_counts.values):
        ax_cls.text(i, n + 3, str(int(n)), ha="center", fontsize=7)
    ax_cls.set_ylim(0, max(class_counts.values) * 1.22)
    fig.suptitle("Spatial footprint and sample support of the verified diagnostic set", x=0.02, y=0.995, ha="left", fontsize=11, fontweight="bold")
    return savefig(fig, "draft_Figure_2_GIS_reference_samples")


def figure7_spatial_errors(disagree: pd.DataFrame) -> dict[str, str]:
    fig = plt.figure(figsize=(8.7, 4.8))
    gs = GridSpec(2, 3, width_ratios=[1.48, 1.05, 1.34], height_ratios=[1.0, 0.95], hspace=0.34, wspace=0.46)
    ax_map = fig.add_subplot(gs[:, 0], projection=ccrs.PlateCarree())
    ax_bar = fig.add_subplot(gs[0, 1:])
    ax_fold = fig.add_subplot(gs[1, 1])
    ax_class = fig.add_subplot(gs[1, 2])

    add_map_base(ax_map, [99.7, 104.5, 1.05, 6.65])
    add_panel_label(ax_map, "a")
    ax_map.set_title("Strict spatial B3 RandomForest outcomes", loc="left", pad=3)
    ok = disagree[disagree["strict_spatial_b3_rf_error_rate"].eq(0)]
    err = disagree[disagree["strict_spatial_b3_rf_error_rate"].eq(1)]
    ax_map.scatter(ok["longitude"], ok["latitude"], s=12, color="#2A9D8F", edgecolor="white", linewidth=0.25, alpha=0.80, transform=ccrs.PlateCarree(), label="correct", zorder=6)
    ax_map.scatter(err["longitude"], err["latitude"], s=18, marker="x", color="#D62828", linewidth=0.85, alpha=0.88, transform=ccrs.PlateCarree(), label="incorrect", zorder=8)
    add_north_arrow(ax_map, x=0.95, y=0.92)
    add_scale_bar(ax_map, 100, lat=3.8)

    add_panel_label(ax_bar, "b")
    cls = disagree.groupby("class_name").agg(n=("sample_id", "size"), errors=("strict_spatial_b3_rf_error_rate", "sum")).reset_index()
    cls["error_rate"] = cls["errors"] / cls["n"]
    cls = cls.sort_values("error_rate", ascending=True)
    y = np.arange(len(cls))
    ax_bar.barh(y, cls["error_rate"], color=[CLASS_COLORS.get(c, "#777777") for c in cls["class_name"]], edgecolor="0.25", linewidth=0.4)
    ax_bar.set_yticks(y, [""] * len(cls))
    ax_bar.tick_params(axis="y", length=0)
    ax_bar.set_xlabel("strict-spatial error rate")
    ax_bar.set_xlim(0, 1)
    ax_bar.set_title("Class-specific failure burden", loc="left", pad=3)
    label_lookup = {
        "oil_palm": "oil palm",
        "rubber": "rubber",
        "paddy": "paddy",
        "other_agri": "other agri",
        "forest": "forest",
        "builtup_other": "built-up/other",
    }
    for pos, (_, row) in enumerate(cls.iterrows()):
        text_color = "white" if row["error_rate"] > 0.42 else "black"
        ax_bar.text(0.02, pos, label_lookup.get(row["class_name"], row["class_name"]), va="center", ha="left", fontsize=7, color=text_color, fontweight="bold")
        value_x = max(row["error_rate"] + 0.02, 0.20)
        ax_bar.text(value_x, pos, f"{int(row['errors'])}/{int(row['n'])}", va="center", fontsize=7)

    add_panel_label(ax_fold, "c")
    folds = disagree.groupby("strict_spatial_b3_rf_fold").agg(n=("sample_id", "size"), errors=("strict_spatial_b3_rf_error_rate", "sum")).reset_index()
    folds["error_rate"] = folds["errors"] / folds["n"]
    ax_fold.bar(folds["strict_spatial_b3_rf_fold"].astype(str), folds["error_rate"], color="#457B9D", edgecolor="0.25", linewidth=0.4)
    ax_fold.set_ylim(0, 1)
    ax_fold.set_xlabel("q25 fold")
    ax_fold.set_ylabel("error rate")
    ax_fold.set_title("Fold-level spatial stress", loc="left", pad=3)
    for i, row in folds.iterrows():
        ax_fold.text(i, row["error_rate"] + 0.03, f"{int(row['errors'])}/{int(row['n'])}", ha="center", fontsize=7)

    add_panel_label(ax_class, "d")
    conf = pd.crosstab(disagree["class_name"], disagree["strict_spatial_b3_rf_predicted_class"])
    conf.columns = [CLASS_LABELS.get(int(c), str(c)) for c in conf.columns]
    focus = conf.reindex(["paddy", "forest", "rubber", "oil_palm", "other_agri", "builtup_other"]).fillna(0)
    im = ax_class.imshow(focus.values, cmap="Reds", aspect="auto")
    ylabels = ["paddy", "forest", "rubber", "oil palm", "other agri", "built-up"]
    xlabel_lookup = {
        "oil palm": "oil\npalm",
        "rubber": "rub.",
        "paddy": "paddy",
        "other agri": "other\nagri",
        "forest": "forest",
        "built-up/other": "built\nup",
    }
    ax_class.set_yticks(np.arange(len(focus.index)), ylabels)
    ax_class.set_xticks(np.arange(len(focus.columns)), [xlabel_lookup.get(x, x) for x in focus.columns], rotation=0)
    ax_class.tick_params(axis="x", labelsize=6, pad=1)
    ax_class.tick_params(axis="y", labelsize=6, pad=2)
    ax_class.set_title("Predicted classes", loc="left", pad=3)
    for i in range(focus.shape[0]):
        for j in range(focus.shape[1]):
            v = int(focus.iloc[i, j])
            if v:
                ax_class.text(j, i, str(v), ha="center", va="center", fontsize=6, color="black")
    cb = fig.colorbar(im, ax=ax_class, fraction=0.046, pad=0.02)
    cb.ax.set_ylabel("count", rotation=90)
    fig.suptitle("Strict spatial validation exposes where and which classes fail", x=0.02, y=0.995, ha="left", fontsize=11, fontweight="bold")
    return savefig(fig, "draft_Figure_7_spatial_error_diagnostics")


def figure8_trust_routing(disagree: pd.DataFrame, trust: pd.DataFrame) -> dict[str, str]:
    fig = plt.figure(figsize=(8.65, 4.85))
    gs = GridSpec(2, 3, width_ratios=[1.32, 1.08, 0.86], height_ratios=[1.0, 1.0], hspace=0.30, wspace=0.36, left=0.05, right=0.985, bottom=0.17, top=0.86)
    ax_dis = fig.add_subplot(gs[:, 0], projection=ccrs.PlateCarree())
    ax_ran = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
    ax_spa = fig.add_subplot(gs[1, 1], projection=ccrs.PlateCarree())
    ax_sum = fig.add_subplot(gs[:, 2])

    add_map_base(ax_dis, [99.7, 104.5, 1.05, 6.65])
    add_panel_label(ax_dis, "a")
    ax_dis.set_title("Random-CV disagreement", loc="left", pad=3)
    sc = ax_dis.scatter(
        disagree["longitude"],
        disagree["latitude"],
        s=14 + 36 * disagree["random_cv_error_rate"],
        c=disagree["random_cv_disagreement_rate"],
        cmap="viridis",
        vmin=0,
        vmax=max(0.625, disagree["random_cv_disagreement_rate"].max()),
        edgecolor="white",
        linewidth=0.20,
        alpha=0.88,
        transform=ccrs.PlateCarree(),
        zorder=8,
    )
    cax = inset_axes(ax_dis, width="4.5%", height="36%", loc="lower right", borderpad=0.85)
    cb = fig.colorbar(sc, cax=cax)
    cb.ax.set_ylabel("rate", fontsize=6)
    cb.ax.tick_params(labelsize=6, length=2)
    add_scale_bar(ax_dis, 100, lat=3.8)

    def plot_route_map(ax, subset: pd.DataFrame, title: str, label: str) -> None:
        add_map_base(ax, [99.7, 104.5, 1.05, 6.65], grid=False)
        add_panel_label(ax, label)
        ax.set_title(title, loc="left", pad=3)
        for route, g in subset.groupby("route"):
            ax.scatter(
                g["longitude"],
                g["latitude"],
                s=18 + 8 * g["set_size"].astype(float),
                color=ROUTE_COLORS.get(route, "#777777"),
                edgecolor="white",
                linewidth=0.25,
                alpha=0.90,
                transform=ccrs.PlateCarree(),
                label=ROUTE_LABELS.get(route, route),
                zorder=8,
            )

    ref_xy = disagree[["sample_id", "longitude", "latitude"]]
    trust_xy = trust.merge(ref_xy, on="sample_id", how="left")
    b2_random = trust_xy[(trust_xy["stack"] == "B2") & (trust_xy["split"] == "random")]
    b2_spatial = trust_xy[(trust_xy["stack"] == "B2") & (trust_xy["split"] == "spatial")]
    plot_route_map(ax_ran, b2_random, "B2 random routes", "b")
    plot_route_map(ax_spa, b2_spatial, "B2 q25 spatial routes", "c")
    add_scale_bar(ax_spa, 100, lat=3.8)

    add_panel_label(ax_sum, "d")
    summary = trust_xy[trust_xy["stack"].isin(["B2", "B3"])].groupby(["stack", "split", "route"]).size().rename("n").reset_index()
    totals = summary.groupby(["stack", "split"])["n"].transform("sum")
    summary["share"] = summary["n"] / totals
    positions = []
    labels = []
    bottom = np.zeros(4)
    combos = [("B2", "random"), ("B3", "random"), ("B2", "spatial"), ("B3", "spatial")]
    x = np.arange(len(combos))
    for route in ["low_risk_screening_only", "local_calibration_required", "manual_vhr_field_review"]:
        vals = []
        for stack, split in combos:
            row = summary[(summary["stack"] == stack) & (summary["split"] == split) & (summary["route"] == route)]
            vals.append(float(row["share"].iloc[0]) if not row.empty else 0)
        ax_sum.bar(x, vals, bottom=bottom, color=ROUTE_COLORS[route], edgecolor="white", linewidth=0.4, label=ROUTE_LABELS[route])
        bottom += vals
    ax_sum.set_xticks(x, [f"{a}\n{b}" for a, b in combos])
    ax_sum.tick_params(axis="x", labelsize=7, pad=2)
    ax_sum.set_ylim(0, 1)
    ax_sum.set_ylabel("case share")
    ax_sum.set_title("Routing burden", loc="left", pad=3)
    handles, labels = ax_sum.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.66, 0.02), ncol=3, frameon=False, handlelength=1.5, columnspacing=1.2)
    fig.suptitle("Trust routing converts uncertainty and transfer risk into review/calibration burden", x=0.02, y=0.995, ha="left", fontsize=11, fontweight="bold")
    return savefig(fig, "draft_Figure_8_trust_routing_disagreement")


def figure12_transfer_similarity(ref: pd.DataFrame, sim: pd.DataFrame) -> dict[str, str]:
    fig = plt.figure(figsize=(9.0, 4.85))
    gs = GridSpec(2, 3, width_ratios=[1.16, 1.18, 1.0], height_ratios=[1.0, 0.86], hspace=0.50, wspace=0.55)
    ax_map = fig.add_subplot(gs[:, 0], projection=ccrs.PlateCarree())
    ax_sc = fig.add_subplot(gs[:, 1])
    ax_dom = fig.add_subplot(gs[0, 2])
    ax_dist = fig.add_subplot(gs[1, 2])

    add_map_base(ax_map, [99.7, 104.5, 1.05, 6.65])
    add_panel_label(ax_map, "a")
    ax_map.set_title("Leave-region-out transfer regions", loc="left", pad=3)
    cent = ref.groupby("region_key").agg(longitude=("longitude", "mean"), latitude=("latitude", "mean"), n=("sample_id", "size")).reset_index()
    plot = sim.merge(cent, left_on="held_out_region", right_on="region_key", how="left")
    norm = mpl.colors.Normalize(vmin=plot["B3_RF_OA"].min(), vmax=plot["B3_RF_OA"].max())
    cmap = mpl.cm.viridis
    for _, row in plot.iterrows():
        ax_map.scatter(
            row["longitude"],
            row["latitude"],
            s=28 + row["n_test"] * 1.4,
            color=cmap(norm(row["B3_RF_OA"])),
            edgecolor=CLASS_COLORS.get(row["dominant_class_name"], "0.3"),
            linewidth=1.2,
            alpha=0.92,
            transform=ccrs.PlateCarree(),
            zorder=10,
        )
    texts = []
    short_names = {
        "advisor_vhr_cell_39_1": "cell39-1",
        "advisor_vhr_cell_39_2": "cell39-2",
        "advisor_vhr_cell_40_2": "cell40-2",
        "johor_negeri_pahang_rubber_belt": "rubber belt",
        "kedah_perlis_paddy_belt": "paddy belt",
        "study_area": "Johor core",
    }
    label_offsets = {
        "advisor_vhr_cell_39_2": (0.10, 0.22),
        "kedah_perlis_paddy_belt": (0.34, -0.16),
        "advisor_vhr_cell_40_2": (0.10, 0.08),
        "advisor_vhr_cell_39_1": (0.10, 0.05),
        "johor_negeri_pahang_rubber_belt": (0.12, 0.08),
        "study_area": (-0.50, 0.16),
    }
    for _, row in plot.iterrows():
        dx, dy = label_offsets.get(row["held_out_region"], (0.05, 0.05))
        ax_map.text(
            row["longitude"] + dx,
            row["latitude"] + dy,
            short_names.get(row["held_out_region"], row["held_out_region"]),
            transform=ccrs.PlateCarree(),
            fontsize=6.4,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.78, pad=0.4),
            zorder=12,
        )
    add_scale_bar(ax_map, 100, lat=3.8)
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    cax = inset_axes(ax_map, width="28%", height="4.5%", loc="lower right", borderpad=1.1)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.ax.set_title("B3 OA", fontsize=5, pad=1)
    cb.ax.tick_params(labelsize=6, length=2)

    add_panel_label(ax_sc, "b")
    facecolors = [CLASS_COLORS.get(name, "#777777") for name in plot["dominant_class_name"]]
    ax_sc.scatter(
        plot["mean_standardized_B2_nearest_train_distance"],
        plot["B3_RF_OA"],
        s=38 + plot["n_test"] * 1.2,
        color=facecolors,
        edgecolor="0.25",
        linewidth=0.5,
    )
    scatter_offsets = {
        "johor_negeri_pahang_rubber_belt": (0.10, -0.02),
        "kedah_perlis_paddy_belt": (-0.08, 0.02),
    }
    texts = []
    for _, row in plot.iterrows():
        dx, dy = scatter_offsets.get(row["held_out_region"], (0.015, 0.01))
        texts.append(ax_sc.text(row["mean_standardized_B2_nearest_train_distance"] + dx, row["B3_RF_OA"] + dy, short_names.get(row["held_out_region"], row["held_out_region"]), fontsize=6.5))
    adjust_text(texts, ax=ax_sc, arrowprops=dict(arrowstyle="-", color="0.45", lw=0.35), expand=(1.1, 1.2))
    ax_sc.set_xlabel("Mean nearest-training distance\nin standardized B2 feature space")
    ax_sc.set_ylabel("B3 RandomForest leave-region-out OA")
    ax_sc.set_title("Feature-space distance\nand transfer OA", loc="left", pad=3)
    ax_sc.set_xlim(plot["mean_standardized_B2_nearest_train_distance"].min() - 0.04, plot["mean_standardized_B2_nearest_train_distance"].max() + 0.10)
    ax_sc.set_ylim(plot["B3_RF_OA"].min() - 0.03, plot["B3_RF_OA"].max() + 0.04)
    class_handles = []
    for cls_name in ["oil_palm", "rubber", "paddy", "other_agri", "forest"]:
        if cls_name in set(plot["dominant_class_name"]):
            class_handles.append(Line2D([0], [0], marker="o", color="none", markerfacecolor=CLASS_COLORS[cls_name], markeredgecolor="0.3", markersize=5, label=cls_name.replace("_", " ")))
    # Class colors are repeated in panel c; removing the in-axis legend avoids label collisions.
    ax_sc.grid(True, color="0.88", linewidth=0.4)

    add_panel_label(ax_dom, "c")
    dom = plot.sort_values("dominant_class_fraction")
    y = np.arange(len(dom))
    ax_dom.barh(y, dom["dominant_class_fraction"], color=[CLASS_COLORS.get(c, "#777777") for c in dom["dominant_class_name"]], edgecolor="0.25", linewidth=0.4)
    ax_dom.set_yticks(y, [short_names.get(x, x) for x in dom["held_out_region"]])
    ax_dom.set_xlim(0, 1)
    ax_dom.set_xlabel("dominant class fraction")
    ax_dom.set_title("Class imbalance", loc="left", pad=3)

    add_panel_label(ax_dist, "d")
    dd = plot.sort_values("mean_geographic_nearest_train_distance_km")
    y = np.arange(len(dd))
    ax_dist.barh(y, dd["mean_geographic_nearest_train_distance_km"], color="#457B9D", edgecolor="0.25", linewidth=0.4)
    ax_dist.set_yticks(y, [short_names.get(x, x) for x in dd["held_out_region"]])
    ax_dist.set_xlabel("nearest-training distance (km)")
    ax_dist.set_title("Geographic isolation", loc="left", pad=3)
    fig.suptitle("Regional transfer is shaped by feature-space distance, geography, and class dominance", x=0.02, y=0.995, ha="left", fontsize=11, fontweight="bold")
    return savefig(fig, "draft_Figure_12_transfer_similarity_map")


def build_planar_risk_grid(disagree: pd.DataFrame, trust: pd.DataFrame) -> Path:
    """Compute figure-13 grid-cell means from sample-level diagnostics only."""
    work = disagree.copy()
    for col in ["longitude", "latitude", "random_cv_disagreement_rate", "strict_spatial_b3_rf_error_rate"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    trust_work = trust[trust["stack"].isin(["B2", "B3"]) & trust["split"].isin(["random", "spatial"])].copy()
    if trust_work.empty:
        burden = pd.DataFrame(columns=["sample_id", "trust_review_calibration_burden"])
    else:
        trust_work["requires_review_or_calibration"] = trust_work["route"].ne("low_risk_screening_only")
        burden = (
            trust_work.groupby("sample_id", as_index=False)
            .agg(
                trust_review_calibration_burden=("requires_review_or_calibration", "mean"),
                trust_route_cases=("requires_review_or_calibration", "size"),
            )
        )
    work = work.merge(burden, on="sample_id", how="left")

    lon_edges = np.arange(99.6, 104.81, 0.35)
    lat_edges = np.arange(1.0, 6.81, 0.35)
    metrics = [
        ("random_cv_disagreement_rate", "Random-CV disagreement"),
        ("strict_spatial_b3_rf_error_rate", "Strict-spatial B3 error"),
        ("trust_review_calibration_burden", "Trust-routing review/calibration burden"),
    ]
    rows = []
    for value_col, metric_label in metrics:
        sub = work[["sample_id", "longitude", "latitude", value_col]].copy()
        sub = sub.dropna(subset=["longitude", "latitude", value_col])
        if sub.empty:
            rows.append({
                "metric": metric_label,
                "cell_lon_min": "ERROR",
                "cell_lon_max": "ERROR",
                "cell_lat_min": "ERROR",
                "cell_lat_max": "ERROR",
                "n_samples": 0,
                "mean_value": "ERROR",
                "status": "ERROR",
                "reason": f"No finite samples for {value_col}",
            })
            continue
        sub["lon_bin"] = pd.cut(sub["longitude"], lon_edges, labels=False, include_lowest=True)
        sub["lat_bin"] = pd.cut(sub["latitude"], lat_edges, labels=False, include_lowest=True)
        sub = sub.dropna(subset=["lon_bin", "lat_bin"])
        grouped = sub.groupby(["lon_bin", "lat_bin"], as_index=False).agg(
            n_samples=("sample_id", "size"),
            mean_value=(value_col, "mean"),
        )
        for _, row in grouped.iterrows():
            lon_i = int(row["lon_bin"])
            lat_i = int(row["lat_bin"])
            rows.append({
                "metric": metric_label,
                "cell_lon_min": float(lon_edges[lon_i]),
                "cell_lon_max": float(lon_edges[lon_i + 1]),
                "cell_lat_min": float(lat_edges[lat_i]),
                "cell_lat_max": float(lat_edges[lat_i + 1]),
                "n_samples": int(row["n_samples"]),
                "mean_value": float(row["mean_value"]),
                "status": "OK",
                "reason": "",
            })

    grid = pd.DataFrame(rows)
    out_csv = OUT / f"figure13_planar_validation_risk_grid_{TAG}.csv"
    grid.to_csv(out_csv, index=False)
    return out_csv


def figure13_planar_validation_risk(disagree: pd.DataFrame, trust: pd.DataFrame) -> tuple[dict[str, str], str]:
    grid_path = build_planar_risk_grid(disagree, trust)
    grid = pd.read_csv(grid_path)
    grid = grid[grid["status"].eq("OK")].copy()
    grid["mean_value"] = pd.to_numeric(grid["mean_value"], errors="coerce")
    grid["n_samples"] = pd.to_numeric(grid["n_samples"], errors="coerce")

    fig = plt.figure(figsize=(8.2, 3.55))
    gs = GridSpec(1, 3, left=0.035, right=0.985, bottom=0.06, top=0.83, wspace=0.075)
    panels = [
        ("a", "Random-CV disagreement", "#F4A261", mpl.cm.Oranges, "mean disagreement"),
        ("b", "Strict-spatial B3 error", "#457B9D", mpl.cm.Blues, "mean error rate"),
        ("c", "Trust-routing burden", "#2A9D8F", mpl.cm.Greens, "mean burden"),
    ]
    for i, (label, metric, accent, cmap, cblabel) in enumerate(panels):
        ax = fig.add_subplot(gs[0, i], projection=ccrs.PlateCarree())
        add_map_base(ax, [99.7, 104.5, 1.05, 6.65], grid=(i == 0))
        add_panel_label(ax, label)
        ax.set_title(metric, loc="left", pad=3)
        metric_lookup = {
            "Trust-routing burden": "Trust-routing review/calibration burden",
        }
        sub = grid[grid["metric"].eq(metric_lookup.get(metric, metric))].copy()
        if sub.empty:
            ax.text(0.5, 0.5, "ERROR: no finite cells", transform=ax.transAxes, ha="center", va="center", fontsize=8)
            continue
        norm = mpl.colors.Normalize(vmin=0, vmax=1)
        for _, row in sub.iterrows():
            rect = Rectangle(
                (row["cell_lon_min"], row["cell_lat_min"]),
                row["cell_lon_max"] - row["cell_lon_min"],
                row["cell_lat_max"] - row["cell_lat_min"],
                transform=ccrs.PlateCarree(),
                facecolor=cmap(norm(row["mean_value"])),
                edgecolor="white",
                linewidth=0.18,
                alpha=min(0.95, 0.45 + 0.12 * math.log1p(row["n_samples"])),
                zorder=5,
            )
            ax.add_patch(rect)
        pts = disagree.dropna(subset=["longitude", "latitude"]).copy()
        ax.scatter(
            pts["longitude"],
            pts["latitude"],
            s=3.5,
            color="0.15",
            alpha=0.18,
            linewidth=0,
            transform=ccrs.PlateCarree(),
            zorder=8,
        )
        n_cells = int(len(sub))
        n_samples = int(sub["n_samples"].sum())
        ax.text(
            0.03,
            0.04,
            f"{n_cells} occupied cells; {n_samples} sample-metric records",
            transform=ax.transAxes,
            fontsize=6,
            color="0.20",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=1.5),
            zorder=30,
        )
        if i == 0:
            add_scale_bar(ax, 100, lat=3.8)
        if i == 2:
            add_north_arrow(ax, x=0.93, y=0.92)
        sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
        cax = inset_axes(ax, width="5%", height="32%", loc="lower right", borderpad=0.9)
        cb = fig.colorbar(sm, cax=cax)
        cb.ax.set_ylabel(cblabel, fontsize=6)
        cb.ax.tick_params(labelsize=6, length=2)
        for spine in ax.spines.values():
            spine.set_edgecolor(accent)
            spine.set_linewidth(0.45)

    fig.suptitle(
        "Planar sample-diagnostic surfaces locate disagreement, spatial failure, and review burden",
        x=0.02,
        y=0.98,
        ha="left",
        fontsize=10,
        fontweight="bold",
    )
    return savefig(fig, "draft_Figure_13_planar_validation_risk_map"), str(grid_path)


def iter_polygons_3d(geom):
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        yield geom
    elif geom.geom_type == "MultiPolygon":
        for child in geom.geoms:
            yield child
    elif hasattr(geom, "geoms"):
        for child in geom.geoms:
            yield from iter_polygons_3d(child)


def add_real_3d_map_base(ax, extent: list[float], zbase: float = -0.035) -> None:
    land_z = 0.0
    ocean = [[
        (extent[0], extent[2], zbase),
        (extent[1], extent[2], zbase),
        (extent[1], extent[3], zbase),
        (extent[0], extent[3], zbase),
    ]]
    ax.add_collection3d(
        Poly3DCollection(ocean, facecolors=(0.86, 0.94, 0.97, 0.68), edgecolors="none", zorder=0)
    )

    target = box(extent[0], extent[2], extent[1], extent[3])
    shp = shapereader.natural_earth(resolution="10m", category="cultural", name="admin_0_countries")
    countries = {"Malaysia", "Thailand", "Singapore", "Indonesia", "Brunei"}
    land_faces = []
    coast_lines = []
    for rec in shapereader.Reader(shp).records():
        attrs = rec.attributes
        name = attrs.get("NAME_EN") or attrs.get("ADMIN") or attrs.get("NAME_LONG") or attrs.get("NAME")
        if name not in countries:
            continue
        geom = rec.geometry
        if not geom.bounds or not geom.intersects(target):
            continue
        clipped = geom.intersection(target)
        for poly in iter_polygons_3d(clipped):
            poly = poly.simplify(0.006, preserve_topology=True)
            coords = list(poly.exterior.coords)
            if len(coords) < 4:
                continue
            land_faces.append([(float(x), float(y), land_z) for x, y in coords])
            coast_lines.append(coords)

    if land_faces:
        ax.add_collection3d(
            Poly3DCollection(
                land_faces,
                facecolors=(0.86, 0.82, 0.68, 0.98),
                edgecolors=(0.38, 0.38, 0.38, 0.75),
                linewidths=0.28,
                zorder=1,
            )
        )
    for coords in coast_lines:
        xs = [float(x) for x, _ in coords]
        ys = [float(y) for _, y in coords]
        ax.plot(xs, ys, [land_z + 0.006] * len(xs), color="#4B4B4B", lw=0.42, alpha=0.90, zorder=2)

    ax.plot(
        [extent[0], extent[1], extent[1], extent[0], extent[0]],
        [extent[2], extent[2], extent[3], extent[3], extent[2]],
        [land_z + 0.010] * 5,
        color="#333333",
        lw=0.55,
        zorder=3,
    )


def add_raised_diagnostic_surface(ax, sub: pd.DataFrame, cmap, norm, zbase: float = -0.035) -> None:
    top_faces = []
    shadow_faces = []
    top_colors = []
    shadow_colors = []
    for row in sub.itertuples(index=False):
        value = float(row.mean_value)
        z = 0.030 + 0.32 * max(0.0, min(1.0, value))
        x0 = float(row.cell_lon_min)
        x1 = float(row.cell_lon_max)
        y0 = float(row.cell_lat_min)
        y1 = float(row.cell_lat_max)
        pad_x = (x1 - x0) * 0.045
        pad_y = (y1 - y0) * 0.045
        face_xy = [
            (x0 + pad_x, y0 + pad_y),
            (x1 - pad_x, y0 + pad_y),
            (x1 - pad_x, y1 - pad_y),
            (x0 + pad_x, y1 - pad_y),
        ]
        top_faces.append([(x, y, z) for x, y in face_xy])
        shadow_faces.append([(x, y, zbase + 0.020) for x, y in face_xy])
        rgba = cmap(norm(value))
        top_colors.append((rgba[0], rgba[1], rgba[2], 0.94))
        shadow_colors.append((rgba[0], rgba[1], rgba[2], 0.26))

    if shadow_faces:
        ax.add_collection3d(
            Poly3DCollection(shadow_faces, facecolors=shadow_colors, edgecolors="none", zorder=4)
        )
    if top_faces:
        ax.add_collection3d(
            Poly3DCollection(
                top_faces,
                facecolors=top_colors,
                edgecolors=(1.0, 1.0, 1.0, 0.58),
                linewidths=0.16,
                zorder=8,
            )
        )


def figure13_3d_validation_risk(disagree: pd.DataFrame, trust: pd.DataFrame) -> tuple[dict[str, str], str]:
    grid_path = build_planar_risk_grid(disagree, trust)
    grid = pd.read_csv(grid_path)
    grid = grid[grid["status"].eq("OK")].copy()
    for col in ["cell_lon_min", "cell_lon_max", "cell_lat_min", "cell_lat_max", "mean_value", "n_samples"]:
        grid[col] = pd.to_numeric(grid[col], errors="coerce")
    grid = grid.dropna(subset=["cell_lon_min", "cell_lon_max", "cell_lat_min", "cell_lat_max", "mean_value"])

    fig = plt.figure(figsize=(8.5, 6.5))
    panels = [
        ("Random-CV disagreement", "a", "Random-CV disagreement", "YlOrRd"),
        ("Strict-spatial B3 error", "b", "Strict-spatial B3 error", "PuBu"),
        ("Trust-routing review/calibration burden", "c", "Review/calibration burden", "Greens"),
    ]
    extent = [99.55, 104.45, 1.05, 6.65]
    norm = mpl.colors.Normalize(vmin=0.0, vmax=1.0)

    panel_positions = [
        (0.035, 0.675, 0.91, 0.245),
        (0.035, 0.385, 0.91, 0.245),
        (0.035, 0.095, 0.91, 0.245),
    ]

    for i, (metric, panel, title, cmap_name) in enumerate(panels, start=1):
        ax = fig.add_axes(panel_positions[i - 1], projection="3d")
        sub = grid[grid["metric"].eq(metric)].copy()
        cmap = mpl.colormaps.get_cmap(cmap_name)
        if sub.empty:
            ax.text2D(0.08, 0.55, f"SKIPPED: no occupied cells for {metric}", transform=ax.transAxes, fontsize=8)
            continue

        add_real_3d_map_base(ax, extent)
        add_raised_diagnostic_surface(ax, sub, cmap, norm)

        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_zlim(-0.04, 0.42)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        ax.set_axis_off()
        ax.view_init(elev=30, azim=-66)
        try:
            ax.set_box_aspect((2.55, 1.08, 0.22), zoom=2.25)
        except TypeError:
            ax.set_box_aspect((2.55, 1.08, 0.22))
        ax.set_anchor("C")
        ax.text2D(0.01, 0.94, panel, transform=ax.transAxes, fontsize=10, fontweight="bold")
        ax.text2D(0.075, 0.945, title, transform=ax.transAxes, fontsize=8.1, fontweight="bold")
        ax.text2D(0.075, 0.845, f"{len(sub)} occupied cells", transform=ax.transAxes, fontsize=6.1, color="#333333")

        sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cax = fig.add_axes([panel_positions[i - 1][0] + 0.02, panel_positions[i - 1][1] + 0.015, 0.20, 0.014])
        cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
        cbar.set_label("mean", fontsize=6)
        cbar.ax.tick_params(labelsize=5, length=2)

    fig.suptitle(
        "Three-dimensional diagnostic map surfaces from verified sample cells",
        x=0.02,
        y=0.985,
        ha="left",
        fontsize=10,
        fontweight="bold",
    )
    fig.text(
        0.02,
        0.025,
        "Surface elevation encodes the computed occupied-cell mean from verified sample diagnostics; empty cells are not interpolated and no wall-to-wall accuracy estimate is implied.",
        fontsize=6.4,
        color="#333333",
    )
    return savefig(fig, "draft_Figure_13_3D_validation_risk_map"), str(grid_path)


def project_oblique(points, extent, shear=0.56, yscale=0.24):
    xmin, xmax, ymin, ymax = extent
    out = []
    for x, y in points:
        xx = (float(x) - xmin) + shear * (float(y) - ymin)
        yy = yscale * (float(y) - ymin)
        out.append((xx, yy))
    return out


def oblique_data_transform(extent, shear=0.56, yscale=0.24) -> Affine2D:
    xmin, xmax, ymin, ymax = extent
    return Affine2D.from_values(1.0, 0.0, shear, yscale, -xmin - shear * ymin, -yscale * ymin)


def load_figure13_basemap(extent: list[float]) -> tuple[np.ndarray | None, list[float] | None, str | None]:
    """Load a real shaded-relief basemap texture for the oblique Figure 13 panels."""
    png_path = OUT / f"figure13_esri_world_shaded_relief_basemap_{TAG}.png"
    meta_path = OUT / f"figure13_esri_world_shaded_relief_basemap_{TAG}.json"
    if png_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return np.asarray(Image.open(png_path).convert("RGBA")), meta["lonlat_extent"], str(png_path)

    try:
        image, web_extent = ctx.bounds2img(
            extent[0],
            extent[2],
            extent[1],
            extent[3],
            zoom=7,
            ll=True,
            source=ctx.providers.Esri.WorldShadedRelief,
            wait=0,
            max_retries=2,
        )
    except Exception as exc:
        print(f"WARN: Figure 13 shaded-relief basemap skipped: {type(exc).__name__}: {exc}")
        return None, None, None

    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    west, south = transformer.transform(web_extent[0], web_extent[2])
    east, north = transformer.transform(web_extent[1], web_extent[3])
    lonlat_extent = [float(west), float(east), float(south), float(north)]

    texture = Image.fromarray(image).convert("RGBA")
    # Keep the real relief visible, but make it light enough for diagnostic cells.
    rgb = texture.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(0.86)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.10)
    arr = np.asarray(rgb).astype(float)
    arr = np.clip(arr * 0.78 + 255.0 * 0.22, 0, 255).astype(np.uint8)
    alpha = np.full(arr.shape[:2] + (1,), 255, dtype=np.uint8)
    rgba = np.concatenate([arr, alpha], axis=2)
    Image.fromarray(rgba, mode="RGBA").save(png_path)
    meta = {
        "source": "Esri WorldShadedRelief via contextily",
        "requested_lonlat_extent": extent,
        "downloaded_web_mercator_extent": [float(v) for v in web_extent],
        "lonlat_extent": lonlat_extent,
        "zoom": 7,
        "sha256": sha256_file(png_path),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return rgba, lonlat_extent, str(png_path)


def add_oblique_polygon(ax, points, extent, **kwargs):
    poly = MplPolygon(project_oblique(points, extent), closed=True, **kwargs)
    ax.add_patch(poly)
    return poly


def add_perspective_map_base(
    ax,
    extent: list[float],
    basemap: np.ndarray | None = None,
    basemap_extent: list[float] | None = None,
) -> tuple[float, float, float, float]:
    xmin, xmax, ymin, ymax = extent
    corners = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    top = project_oblique(corners, extent)
    dx, dy = 0.30, -0.13
    lower = [(x + dx, y + dy) for x, y in top]

    ax.add_patch(MplPolygon(lower, closed=True, facecolor="#AAB9B9", edgecolor="none", alpha=0.54, zorder=0))
    side_1 = [top[0], top[1], lower[1], lower[0]]
    side_2 = [top[1], top[2], lower[2], lower[1]]
    side_3 = [top[2], top[3], lower[3], lower[2]]
    for face, color in [(side_1, "#DAE4E2"), (side_2, "#C7D3D3"), (side_3, "#EEF3F1")]:
        ax.add_patch(MplPolygon(face, closed=True, facecolor=color, edgecolor="#94A2A0", linewidth=0.38, zorder=1))
    top_poly = MplPolygon(top, closed=True, facecolor="#EDF4F2", edgecolor="#354242", linewidth=0.74, zorder=2)
    ax.add_patch(top_poly)

    if basemap is not None and basemap_extent is not None:
        image = ax.imshow(
            basemap,
            origin="upper",
            extent=basemap_extent,
            transform=oblique_data_transform(extent) + ax.transData,
            interpolation="bilinear",
            zorder=3,
            alpha=0.94,
        )
        image.set_clip_path(top_poly)
        ax.add_patch(MplPolygon(top, closed=True, facecolor=(1, 1, 1, 0), edgecolor="#354242", linewidth=0.74, zorder=7))

    target = box(xmin, ymin, xmax, ymax)
    shp = shapereader.natural_earth(resolution="10m", category="cultural", name="admin_0_countries")
    countries = {"Malaysia", "Thailand", "Singapore", "Indonesia", "Brunei"}
    for rec in shapereader.Reader(shp).records():
        attrs = rec.attributes
        name = attrs.get("NAME_EN") or attrs.get("ADMIN") or attrs.get("NAME_LONG") or attrs.get("NAME")
        if name not in countries:
            continue
        geom = rec.geometry
        if not geom.bounds or not geom.intersects(target):
            continue
        clipped = geom.intersection(target)
        for poly in iter_polygons_3d(clipped):
            poly = poly.simplify(0.006, preserve_topology=True)
            coords = list(poly.exterior.coords)
            if len(coords) < 4:
                continue
            add_oblique_polygon(
                ax,
                coords,
                extent,
                facecolor=(1, 1, 1, 0),
                edgecolor="#4F5A57",
                linewidth=0.42,
                zorder=8,
            )
            projected = project_oblique(coords, extent)
            ax.plot([p[0] for p in projected], [p[1] for p in projected], color="#4F5A57", lw=0.34, zorder=8.5)

    xs = [p[0] for p in top + lower]
    ys = [p[1] for p in top + lower]
    return min(xs), max(xs), min(ys), max(ys)


def add_oblique_diagnostic_cells(ax, sub: pd.DataFrame, extent: list[float], cmap, norm) -> None:
    for row in sub.sort_values(["cell_lat_min", "cell_lon_min"]).itertuples(index=False):
        value = float(row.mean_value)
        x0 = float(row.cell_lon_min)
        x1 = float(row.cell_lon_max)
        y0 = float(row.cell_lat_min)
        y1 = float(row.cell_lat_max)
        pad_x = (x1 - x0) * 0.045
        pad_y = (y1 - y0) * 0.045
        pts = [
            (x0 + pad_x, y0 + pad_y),
            (x1 - pad_x, y0 + pad_y),
            (x1 - pad_x, y1 - pad_y),
            (x0 + pad_x, y1 - pad_y),
        ]
        rgba = cmap(norm(value))
        add_oblique_polygon(
            ax,
            pts,
            extent,
            facecolor=(rgba[0], rgba[1], rgba[2], 0.82),
            edgecolor=(1, 1, 1, 0.56),
            linewidth=0.18,
            zorder=10 + 0.001 * float(row.cell_lat_min),
        )


def figure13_perspective_validation_map(disagree: pd.DataFrame, trust: pd.DataFrame) -> tuple[dict[str, str], str]:
    grid_path = build_planar_risk_grid(disagree, trust)
    grid = pd.read_csv(grid_path)
    grid = grid[grid["status"].eq("OK")].copy()
    for col in ["cell_lon_min", "cell_lon_max", "cell_lat_min", "cell_lat_max", "mean_value", "n_samples"]:
        grid[col] = pd.to_numeric(grid[col], errors="coerce")
    grid = grid.dropna(subset=["cell_lon_min", "cell_lon_max", "cell_lat_min", "cell_lat_max", "mean_value"])

    fig = plt.figure(figsize=(8.9, 6.25))
    panels = [
        ("Random-CV disagreement", "a", "Random-CV disagreement", "YlOrRd"),
        ("Strict-spatial B3 error", "b", "Strict-spatial B3 error", "PuBu"),
        ("Trust-routing review/calibration burden", "c", "Review/calibration burden", "Greens"),
    ]
    extent = [99.55, 104.45, 1.05, 6.65]
    norm = mpl.colors.Normalize(vmin=0.0, vmax=1.0)
    basemap, basemap_extent, _ = load_figure13_basemap(extent)
    panel_positions = [
        (0.028, 0.682, 0.948, 0.238),
        (0.028, 0.389, 0.948, 0.238),
        (0.028, 0.096, 0.948, 0.238),
    ]

    for i, (metric, panel, title, cmap_name) in enumerate(panels):
        ax = fig.add_axes(panel_positions[i])
        ax.set_aspect("equal")
        ax.axis("off")
        cmap = mpl.colormaps.get_cmap(cmap_name)
        sub = grid[grid["metric"].eq(metric)].copy()
        x0, x1, y0, y1 = add_perspective_map_base(ax, extent, basemap=basemap, basemap_extent=basemap_extent)
        if sub.empty:
            ax.text(0.1, 0.6, f"SKIPPED: no occupied cells for {metric}", fontsize=8)
        else:
            add_oblique_diagnostic_cells(ax, sub, extent, cmap, norm)
        ax.set_xlim(x0 - 0.28, x1 + 0.38)
        ax.set_ylim(y0 - 0.18, y1 + 0.30)
        ax.text(x0 - 0.19, y1 + 0.22, panel, fontsize=9.5, fontweight="bold", va="top")
        ax.text(x0 + 0.10, y1 + 0.22, title, fontsize=8.4, fontweight="bold", va="top")
        ax.text(x0 + 0.10, y1 + 0.06, f"{len(sub)} occupied cells", fontsize=5.9, color="#333333", va="top")
        sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cax = fig.add_axes([panel_positions[i][0] + 0.040, panel_positions[i][1] + 0.004, 0.205, 0.013])
        cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
        cbar.set_label("occupied-cell mean", fontsize=5.4, labelpad=1)
        cbar.ax.tick_params(labelsize=5.0, length=1.8, pad=1)

    fig.text(
        0.018,
        0.028,
        "Shaded-relief basemap is used as a real geographic texture; diagnostic colors are computed occupied-cell means only. Empty cells are not interpolated.",
        fontsize=5.7,
        color="#333333",
    )
    return savefig(fig, "draft_Figure_13_3D_validation_risk_map"), str(grid_path)


def main() -> int:
    setup_style()
    OUT.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(REF_PATH)
    pred = pd.read_csv(PRED_PATH)
    table3 = pd.read_csv(TABLE3_PATH)
    disagree = pd.read_csv(DISAGREE_PATH)
    trust = pd.read_csv(TRUST_PATH)
    sim = pd.read_csv(TRANSFER_SIM_PATH)

    outputs = {}
    outputs["Figure_2"] = figure2_reference_samples(ref)
    outputs["Figure_3"] = figure3_random_vs_spatial_accuracy(table3)
    outputs["Figure_7"] = figure7_spatial_errors(disagree)
    outputs["Figure_8"] = figure8_trust_routing(disagree, trust)
    outputs["Figure_12"] = figure12_transfer_similarity(ref, sim)
    outputs["Figure_13"], figure13_grid_path = figure13_perspective_validation_map(disagree, trust)

    basemap_path = OUT / f"figure13_esri_world_shaded_relief_basemap_{TAG}.png"
    basemap_meta_path = OUT / f"figure13_esri_world_shaded_relief_basemap_{TAG}.json"
    if basemap_path.exists() and basemap_meta_path.exists():
        basemap_info = {
            "status": "OK",
            "path": str(basemap_path),
            "sha256": sha256_file(basemap_path),
            "metadata": str(basemap_meta_path),
            "source": "Esri WorldShadedRelief via contextily",
        }
    else:
        basemap_info = {
            "status": "SKIPPED",
            "reason": "Basemap texture was not available; Figure 13 fell back to Natural Earth coastlines/boundaries.",
        }

    provenance = {
        "timestamp_tag": TAG,
        "status": "DRAFTS_CREATED_NOT_SUBMISSION_REPLACEMENTS",
        "script": str(Path(__file__).resolve()),
        "output_dir": str(OUT.resolve()),
        "inputs": {
            "reference_samples": {"path": str(REF_PATH), "sha256": sha256_file(REF_PATH), "rows": int(len(ref))},
            "predictions_by_fold": {"path": str(PRED_PATH), "sha256": sha256_file(PRED_PATH), "rows": int(len(pred))},
            "table3_accuracy_by_stack_split": {"path": str(TABLE3_PATH), "sha256": sha256_file(TABLE3_PATH), "rows": int(len(table3))},
            "sample_level_failure_disagreement": {"path": str(DISAGREE_PATH), "sha256": sha256_file(DISAGREE_PATH), "rows": int(len(disagree))},
            "trust_routing_point_assignments": {"path": str(TRUST_PATH), "sha256": sha256_file(TRUST_PATH), "rows": int(len(trust))},
            "region_transfer_similarity": {"path": str(TRANSFER_SIM_PATH), "sha256": sha256_file(TRANSFER_SIM_PATH), "rows": int(len(sim))},
            "figure13_shaded_relief_basemap": basemap_info,
        },
        "figure_claims": {
            "Figure_2": "The verified reference set is spatially clustered across a Johor core, a Kedah-Perlis paddy belt, a rubber belt, and small VHR extension cells.",
            "Figure_3": "Random cross-validation remains optimistic relative to strict q25 spatial validation across feature stacks.",
            "Figure_7": "Strict q25 spatial validation exposes class- and fold-specific failures rather than a uniform accuracy drop.",
            "Figure_8": "Trust routing converts disagreement, conformal set size, rubber-transfer risk, and q25 distance support into review/calibration burden.",
            "Figure_12": "Leave-region-out transfer varies with feature-space distance, geographic isolation, and dominant-class imbalance.",
            "Figure_13": "Oblique shaded-relief diagnostic maps show where random-CV disagreement, strict-spatial error, and trust-routing burden concentrate in occupied cells, without implying wall-to-wall map accuracy.",
        },
        "outputs": outputs,
        "derived_tables": {
            "figure13_planar_validation_risk_grid": {
                "path": figure13_grid_path,
                "sha256": sha256_file(Path(figure13_grid_path)),
                "rows": int(len(pd.read_csv(figure13_grid_path))),
            },
            "figure3_random_vs_spatial_accuracy_values": {
                "path": str(FIGURE3_VALUES_PATH),
                "sha256": sha256_file(FIGURE3_VALUES_PATH),
                "rows": int(len(pd.read_csv(FIGURE3_VALUES_PATH))),
                "provenance": str(FIGURE3_PROV_PATH),
            }
        },
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "library_versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": mpl.__version__,
            "contextily": ctx.__version__,
        },
    }
    (OUT / f"figure_redesign_draft_provenance_{TAG}.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(outputs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
