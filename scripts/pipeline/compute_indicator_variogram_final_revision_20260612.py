from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REF_FILE = ROOT / "data" / "reference_samples_DAI_WENZHE_ADVISOR_VHR_ACCEPTED_95_CLEANED_20260612.csv"
CONFIG_FILE = ROOT / "config_advisor_vhr_repair_20260612.yaml"
RESULTS_DIR = ROOT / "results_final_revision_20260612"
FIGURES_DIR = ROOT / "figures_final_revision_20260612"

N_BINS = 12
MAX_PAIR_COUNT = 250_000
SILL_FRACTION = 0.95
RANDOM_SEED = 42
MIN_CLASS_COUNT = 30


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def config_hash() -> str:
    if CONFIG_FILE.exists():
        return sha256_file(CONFIG_FILE)
    return "CONFIG_MISSING"


def parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def project_lonlat_to_meters(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mean_lat = float(np.nanmean(lat))
    x = lon * 111_320.0 * math.cos(math.radians(mean_lat))
    y = lat * 110_574.0
    return np.column_stack([x, y])


def provenance(timestamp: str, status: str, reason: str = "") -> dict[str, Any]:
    return {
        "timestamp_utc": timestamp,
        "config_hash": config_hash(),
        "input_files": str(REF_FILE.relative_to(ROOT)).replace("//", "/"),
        "input_sha256": sha256_file(REF_FILE) if REF_FILE.exists() else "MISSING",
        "random_seed": RANDOM_SEED,
        "status": status,
        "reason": reason,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def compute_for_class(
    timestamp: str,
    work: pd.DataFrame,
    coords: np.ndarray,
    class_code: Any,
    class_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    z = (work["class_code"].astype(str) == str(class_code)).astype(float).to_numpy()
    n = len(work)
    n_positive = int(np.sum(z == 1.0))
    n_negative = int(np.sum(z == 0.0))
    total_pairs = n * (n - 1) // 2

    base = {
        "class_code": class_code,
        "class_name": class_name,
        "indicator_variable": f"is_{class_name}",
        "n_samples": n,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "total_pair_count": total_pairs,
        "n_bins": N_BINS,
        "sill_fraction_for_range": SILL_FRACTION,
        "min_class_count": MIN_CLASS_COUNT,
        "method": "one_vs_rest_binary_indicator_empirical_variogram",
        "projection_note": "Equirectangular lon-lat-to-meter approximation using sample mean latitude; used only for block-distance diagnostic.",
    }

    if n < 3:
        reason = "SKIPPED: fewer than 3 verified samples with coordinates."
        return [], {**provenance(timestamp, "SKIPPED", reason), **base}
    if n_positive < MIN_CLASS_COUNT:
        reason = "SKIPPED: positive class count below configured min_class_count."
        return [], {**provenance(timestamp, "SKIPPED", reason), **base}
    if n_negative < MIN_CLASS_COUNT:
        reason = "SKIPPED: one-vs-rest negative count below configured min_class_count."
        return [], {**provenance(timestamp, "SKIPPED", reason), **base}

    if total_pairs <= MAX_PAIR_COUNT:
        i_idx, j_idx = np.triu_indices(n, k=1)
    else:
        rng = np.random.default_rng(RANDOM_SEED)
        i_idx = rng.integers(0, n, size=MAX_PAIR_COUNT)
        j_idx = rng.integers(0, n, size=MAX_PAIR_COUNT)
        keep = i_idx != j_idx
        i_idx = i_idx[keep]
        j_idx = j_idx[keep]

    distances = np.linalg.norm(coords[i_idx] - coords[j_idx], axis=1)
    semivar = 0.5 * (z[i_idx] - z[j_idx]) ** 2
    keep = np.isfinite(distances) & np.isfinite(semivar) & (distances > 0)
    distances = distances[keep]
    semivar = semivar[keep]

    if len(distances) < N_BINS:
        reason = "SKIPPED: too few positive-distance pairs for configured bins."
        return [], {**provenance(timestamp, "SKIPPED", reason), **base, "pair_count_used": int(len(distances))}

    edges = np.linspace(0, float(np.nanmax(distances)), N_BINS + 1)
    rows: list[dict[str, Any]] = []
    mids: list[float] = []
    gammas: list[float] = []
    for idx in range(N_BINS):
        lo = float(edges[idx])
        hi = float(edges[idx + 1])
        in_bin = (distances >= lo) & (distances < hi if idx < N_BINS - 1 else distances <= hi)
        if not np.any(in_bin):
            continue
        gamma = float(np.nanmean(semivar[in_bin]))
        midpoint = float((lo + hi) / 2.0)
        mids.append(midpoint)
        gammas.append(gamma)
        row = {
            **provenance(timestamp, "OK", ""),
            **base,
            "bin": idx + 1,
            "distance_low_m": lo,
            "distance_high_m": hi,
            "distance_midpoint_m": midpoint,
            "semivariance": gamma,
            "pair_count": int(np.sum(in_bin)),
            "pair_count_used": int(len(distances)),
        }
        rows.append(row)

    if not gammas or max(gammas) <= 0:
        reason = "SKIPPED: empirical sill is zero or unavailable for this indicator."
        return rows, {**provenance(timestamp, "SKIPPED", reason), **base, "pair_count_used": int(len(distances))}

    sill = float(max(gammas))
    threshold = SILL_FRACTION * sill
    chosen_range = None
    for midpoint, gamma in zip(mids, gammas):
        if gamma >= threshold:
            chosen_range = float(midpoint)
            break
    if chosen_range is None:
        chosen_range = float(mids[-1])

    for row in rows:
        row["sill"] = sill
        row["range_threshold"] = threshold
        row["chosen_range_m"] = chosen_range

    summary = {
        **provenance(timestamp, "OK", ""),
        **base,
        "pair_count_used": int(len(distances)),
        "sill": sill,
        "range_threshold": threshold,
        "chosen_range_m": chosen_range,
    }
    return rows, summary


def make_plot_with_pillow(bin_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], error: Exception) -> str:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        return f"SKIPPED: matplotlib unavailable ({type(error).__name__}: {error}); Pillow fallback unavailable ({type(exc).__name__}: {exc})."

    ok_ranges = {str(row["class_code"]): row for row in summary_rows if row.get("status") == "OK"}
    if not ok_ranges:
        return "SKIPPED: no OK class ranges to plot."

    width, height = 1400, 850
    left, right, top, bottom = 110, 330, 80, 110
    plot_w = width - left - right
    plot_h = height - top - bottom
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]

    all_x = [float(row["distance_midpoint_m"]) / 1000.0 for row in bin_rows if row.get("distance_midpoint_m") not in ("", None)]
    all_y = [float(row["semivariance"]) for row in bin_rows if row.get("semivariance") not in ("", None)]
    if not all_x or not all_y:
        return "SKIPPED: no plottable bin rows."
    x_max = max(all_x)
    y_max = max(all_y)
    if x_max <= 0 or y_max <= 0:
        return "SKIPPED: non-positive plotting extent."

    def sx(x: float) -> int:
        return int(left + (x / x_max) * plot_w)

    def sy(y: float) -> int:
        return int(top + plot_h - (y / y_max) * plot_h)

    draw.line((left, top, left, top + plot_h), fill="black", width=2)
    draw.line((left, top + plot_h, left + plot_w, top + plot_h), fill="black", width=2)
    draw.text((left, 25), "One-vs-rest indicator variograms for verified reference classes", fill="black", font=font)
    draw.text((left + 360, height - 45), "Pair distance midpoint (km)", fill="black", font=font)
    draw.text((left, top - 28), "Empirical semivariance", fill="black", font=font)

    for tick in range(6):
        x_val = x_max * tick / 5
        x_pos = sx(x_val)
        draw.line((x_pos, top + plot_h, x_pos, top + plot_h + 8), fill="black", width=1)
        draw.text((x_pos - 22, top + plot_h + 14), f"{x_val:.0f}", fill="black", font=font)
        y_val = y_max * tick / 5
        y_pos = sy(y_val)
        draw.line((left - 8, y_pos, left, y_pos), fill="black", width=1)
        draw.text((left - 78, y_pos - 6), f"{y_val:.3f}", fill="black", font=font)

    for idx, (class_code, summary) in enumerate(ok_ranges.items()):
        color = colors[idx % len(colors)]
        cls_rows = [row for row in bin_rows if str(row.get("class_code")) == class_code]
        cls_rows = sorted(cls_rows, key=lambda r: int(r["bin"]))
        points = [(sx(float(row["distance_midpoint_m"]) / 1000.0), sy(float(row["semivariance"]))) for row in cls_rows]
        if len(points) >= 2:
            draw.line(points, fill=color, width=3)
        for x, y in points:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color, outline=color)
        range_x = sx(float(summary["chosen_range_m"]) / 1000.0)
        for y in range(top, top + plot_h, 18):
            draw.line((range_x, y, range_x, min(y + 9, top + plot_h)), fill=color, width=1)
        legend_y = top + idx * 38
        legend_x = left + plot_w + 35
        draw.rectangle((legend_x, legend_y + 5, legend_x + 24, legend_y + 20), fill=color)
        draw.text(
            (legend_x + 34, legend_y),
            f"{summary['class_name']} range={float(summary['chosen_range_m']) / 1000.0:.1f} km",
            fill="black",
            font=font,
        )

    out = FIGURES_DIR / "variogram_indicator_ranges.png"
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out.relative_to(ROOT)).replace("//", "/") + " (Pillow fallback; matplotlib unavailable)"


def make_plot(bin_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> str:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        return make_plot_with_pillow(bin_rows, summary_rows, exc)

    try:
        ok_ranges = {str(row["class_code"]): row for row in summary_rows if row.get("status") == "OK"}
        if not ok_ranges:
            return "SKIPPED: no OK class ranges to plot."

        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(8.8, 5.2), dpi=180)
        for class_code, summary in ok_ranges.items():
            cls_rows = [row for row in bin_rows if str(row.get("class_code")) == class_code]
            cls_rows = sorted(cls_rows, key=lambda r: int(r["bin"]))
            xs = [float(row["distance_midpoint_m"]) / 1000.0 for row in cls_rows]
            ys = [float(row["semivariance"]) for row in cls_rows]
            ax.plot(xs, ys, marker="o", linewidth=1.6, label=str(summary["class_name"]))
            ax.axvline(float(summary["chosen_range_m"]) / 1000.0, linestyle=":", linewidth=0.8, alpha=0.5)

        ax.set_xlabel("Pair distance midpoint (km)")
        ax.set_ylabel("Empirical semivariance")
        ax.set_title("One-vs-rest indicator variograms for verified reference classes")
        ax.grid(True, linewidth=0.3, alpha=0.5)
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        out = FIGURES_DIR / "variogram_indicator_ranges.png"
        fig.savefig(out)
        plt.close(fig)
        return str(out.relative_to(ROOT)).replace("//", "/")
    except Exception as exc:
        return make_plot_with_pillow(bin_rows, summary_rows, exc)


def write_decision_memo(timestamp: str, summary: dict[str, Any]) -> None:
    path = RESULTS_DIR / "block_distance_decision_20260612.md"
    ok_rows = [row for row in summary["class_ranges"] if row["status"] == "OK"]
    lines = [
        "# Final-revision block-distance diagnostic",
        "",
        f"Timestamp UTC: `{timestamp}`",
        "",
        "## Purpose",
        "",
        "This memo records a one-vs-rest indicator variogram diagnostic computed from the cleaned 619-row verified reference table. It is added because the previous 95.1 km distance was derived from a nominal `class_code` variogram and should not be treated as an ecological range or a design-based map-accuracy scale.",
        "",
        "## Input",
        "",
        f"- Reference file: `{summary['reference_file']}`",
        f"- Reference SHA-256: `{summary['reference_sha256']}`",
        f"- Config file: `{summary['config_file']}`",
        f"- Config SHA-256: `{summary['config_hash']}`",
        f"- Verified rows used: `{summary['verified_rows']}`",
        f"- Random seed: `{RANDOM_SEED}`",
        "",
        "## Class-specific indicator ranges",
        "",
        "| class_code | class_name | status | n_positive | n_negative | chosen_range_km | reason |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for row in summary["class_ranges"]:
        range_km = ""
        if row.get("chosen_range_m") not in ("", None):
            range_km = f"{float(row['chosen_range_m']) / 1000.0:.3f}"
        lines.append(
            f"| {row['class_code']} | {row['class_name']} | {row['status']} | "
            f"{row['n_positive']} | {row['n_negative']} | {range_km} | {row.get('reason', '')} |"
        )
    lines.extend(["", "## Decision rule", ""])
    if ok_rows:
        lines.extend(
            [
                f"- Suggested conservative replacement block distance, if the analysis is rerun from this diagnostic: `{summary['suggested_block_distance_m']:.6f}` m (`{summary['suggested_block_distance_km']:.3f}` km).",
                "- Rule: maximum OK one-vs-rest indicator range across configured classes.",
                "- Rationale: this is conservative across class-specific spatial structures and avoids treating the nominal multi-class code as a continuous variable.",
            ]
        )
    else:
        lines.append("- No replacement block distance is selected because no class-specific indicator variogram returned `OK`.")
    lines.extend(
        [
            "",
            "## Submission consequence",
            "",
            "This diagnostic does **not** update Table 3-12 or any figure by itself. If this replacement block distance is adopted, the spatial CV, leakage audit, conformal random/spatial reporting, Moran's I, transfer outputs, figures, manuscript tables, manifest, and checksums must be regenerated. Until that rerun exists, the current manuscript results remain tied to the older 95.1 km stress-test distance and should be treated as `MAJOR_REVISION_FIRST`, not final submission-ready evidence.",
            "",
            "## Output files",
            "",
            "- `results_final_revision_20260612/variogram_indicator_bins.csv`",
            "- `results_final_revision_20260612/variogram_indicator_ranges.csv`",
            "- `results_final_revision_20260612/variogram_indicator_summary.json`",
            "- `figures_final_revision_20260612/variogram_indicator_ranges.png`",
        ]
    )
    path.write_text("/n".join(lines) + "/n", encoding="utf-8")


def main() -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    if not REF_FILE.exists():
        row = provenance(timestamp, "ERROR", "Missing cleaned reference CSV.")
        write_csv(RESULTS_DIR / "variogram_indicator_ranges.csv", [row], list(row.keys()))
        print("ERROR: Missing cleaned reference CSV.")
        return

    ref = pd.read_csv(REF_FILE)
    required = ["sample_id", "longitude", "latitude", "class_code", "class_name", "verified"]
    missing = [col for col in required if col not in ref.columns]
    if missing:
        row = provenance(timestamp, "ERROR", "Missing required columns: " + ", ".join(missing))
        write_csv(RESULTS_DIR / "variogram_indicator_ranges.csv", [row], list(row.keys()))
        print("ERROR: Missing required columns: " + ", ".join(missing))
        return

    work = ref[parse_bool(ref["verified"])].copy()
    work = work.dropna(subset=["longitude", "latitude", "class_code", "class_name"]).copy()
    work["longitude"] = work["longitude"].astype(float)
    work["latitude"] = work["latitude"].astype(float)
    work["class_code"] = work["class_code"].astype(str)
    coords = project_lonlat_to_meters(work["longitude"].to_numpy(), work["latitude"].to_numpy())

    class_table = (
        work.groupby(["class_code", "class_name"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values("class_code", key=lambda s: s.astype(float))
    )

    bin_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for _, cls in class_table.iterrows():
        rows, summary = compute_for_class(timestamp, work, coords, cls["class_code"], str(cls["class_name"]))
        bin_rows.extend(rows)
        summary_rows.append(summary)

    bin_fields = [
        "timestamp_utc",
        "config_hash",
        "input_files",
        "input_sha256",
        "random_seed",
        "status",
        "reason",
        "class_code",
        "class_name",
        "indicator_variable",
        "n_samples",
        "n_positive",
        "n_negative",
        "total_pair_count",
        "pair_count_used",
        "n_bins",
        "bin",
        "distance_low_m",
        "distance_high_m",
        "distance_midpoint_m",
        "semivariance",
        "pair_count",
        "sill",
        "sill_fraction_for_range",
        "range_threshold",
        "chosen_range_m",
        "min_class_count",
        "method",
        "projection_note",
    ]
    range_fields = [field for field in bin_fields if field not in {"bin", "distance_low_m", "distance_high_m", "distance_midpoint_m", "semivariance", "pair_count"}]
    write_csv(RESULTS_DIR / "variogram_indicator_bins.csv", bin_rows, bin_fields)
    write_csv(RESULTS_DIR / "variogram_indicator_ranges.csv", summary_rows, range_fields)

    ok_rows = [row for row in summary_rows if row["status"] == "OK"]
    suggested = max(float(row["chosen_range_m"]) for row in ok_rows) if ok_rows else None
    plot_status = make_plot(bin_rows, summary_rows)
    summary = {
        "timestamp_utc": timestamp,
        "status": "OK" if ok_rows else "SKIPPED",
        "reference_file": str(REF_FILE.relative_to(ROOT)).replace("//", "/"),
        "reference_sha256": sha256_file(REF_FILE),
        "config_file": str(CONFIG_FILE.relative_to(ROOT)).replace("//", "/") if CONFIG_FILE.exists() else "MISSING",
        "config_hash": config_hash(),
        "random_seed": RANDOM_SEED,
        "verified_rows": int(len(work)),
        "method": "one_vs_rest_binary_indicator_empirical_variogram",
        "n_bins": N_BINS,
        "sill_fraction_for_range": SILL_FRACTION,
        "min_class_count": MIN_CLASS_COUNT,
        "class_ranges": summary_rows,
        "block_distance_rule": "max_ok_one_vs_rest_indicator_range",
        "suggested_block_distance_m": suggested,
        "suggested_block_distance_km": suggested / 1000.0 if suggested is not None else None,
        "plot_status": plot_status,
        "requires_full_spatial_rerun_before_manuscript_tables_can_use_this_distance": True,
    }
    (RESULTS_DIR / "variogram_indicator_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_decision_memo(timestamp, summary)
    print(json.dumps({k: summary[k] for k in ["status", "verified_rows", "suggested_block_distance_m", "suggested_block_distance_km", "plot_status"]}, indent=2))


if __name__ == "__main__":
    main()
