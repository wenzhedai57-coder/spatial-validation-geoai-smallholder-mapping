from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

import compute_indicator_variogram_final_revision_20260612 as indicator
import select_practical_indicator_block_distance_20260612 as selector


ROOT = Path.cwd()
CONFIG = ROOT / "config_fold3_teacher_vhr_repair_20260613.yaml"
RESULTS_DIR = ROOT / "results_fold3_teacher_vhr_variogram_20260613"
FIGURES_DIR = ROOT / "figures_fold3_teacher_vhr_variogram_20260613"


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    ref_path = ROOT / config["reference_samples"]["file"]

    indicator.ROOT = ROOT
    indicator.REF_FILE = ref_path
    indicator.CONFIG_FILE = CONFIG
    indicator.RESULTS_DIR = RESULTS_DIR
    indicator.FIGURES_DIR = FIGURES_DIR
    indicator.main()

    selector.ROOT = ROOT
    selector.INDICATOR_SUMMARY = RESULTS_DIR / "variogram_indicator_summary.json"
    selector.REF_FILE = ref_path
    selector.OUT_DIR = RESULTS_DIR
    selector.K_FOLDS = int(config.get("cv", {}).get("k_folds", 4))
    selector.SEED = int(config.get("seeds", {}).get("global", 42))
    selector.main()

    renames = {
        "block_distance_practical_rule_candidates_20260612.csv": "block_distance_practical_rule_candidates_20260613.csv",
        "block_distance_practical_rule_summary_20260612.json": "block_distance_practical_rule_summary_20260613.json",
        "block_distance_practical_rule_20260612.md": "block_distance_practical_rule_20260613.md",
    }
    for src_name, dst_name in renames.items():
        src = RESULTS_DIR / src_name
        dst = RESULTS_DIR / dst_name
        if src.exists():
            shutil.copy2(src, dst)

    summary_path = RESULTS_DIR / "block_distance_practical_rule_summary_20260613.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["date_tag_normalized_for_fold3_teacher_vhr_rerun"] = True
        summary["config_file"] = str(CONFIG.relative_to(ROOT)).replace("//", "/")
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "/n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "OK",
                "config": str(CONFIG.relative_to(ROOT)).replace("//", "/"),
                "reference": str(ref_path.relative_to(ROOT)).replace("//", "/"),
                "results_dir": str(RESULTS_DIR.relative_to(ROOT)).replace("//", "/"),
                "figures_dir": str(FIGURES_DIR.relative_to(ROOT)).replace("//", "/"),
                "summary": str(summary_path.relative_to(ROOT)).replace("//", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
