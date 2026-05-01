"""Generate a synthetic 50-page PBIR report for performance benchmarks.

Run manually:

    python tests/_gen_benchmark.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent / "fixtures" / "benchmark-report"
PAGES = 50
VISUALS_PER_PAGE = 12
TYPES = ["card", "actionButton", "tableEx", "shape", "slicer"]


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    pages_dir = ROOT / "definition" / "pages"
    pages_dir.mkdir(parents=True)

    (ROOT / "definition" / "version.json").write_text(
        json.dumps({"version": "4.0"}), encoding="utf-8"
    )

    for i in range(PAGES):
        page_id = f"page{i:03d}"
        page_dir = pages_dir / page_id
        page_dir.mkdir()
        (page_dir / "page.json").write_text(
            json.dumps(
                {
                    "name": page_id,
                    "displayName": f"Page {i:03d}",
                    "displayOption": "FitToWidth",
                    "height": 1500,
                    "width": 1280,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        visuals_dir = page_dir / "visuals"
        visuals_dir.mkdir()

        y = 10.0
        for j in range(VISUALS_PER_PAGE):
            vt = TYPES[j % len(TYPES)]
            vid = f"v{j:02d}_{vt}"
            v_dir = visuals_dir / vid
            v_dir.mkdir()
            (v_dir / "visual.json").write_text(
                json.dumps(
                    {
                        "name": vid,
                        "position": {
                            "x": 10,
                            "y": y,
                            "z": 1000 + j,
                            "height": 60,
                            "width": 200,
                            "tabOrder": j * 100,
                        },
                        "visual": {"visualType": vt},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            y += 70  # 60px height + 10px gap


if __name__ == "__main__":
    main()
    print(f"Wrote benchmark fixture to {ROOT}")
