"""Unit tests for pbir_validator.gui.export (T019)."""

from __future__ import annotations

import csv
import json

from pbir_validator.gui import export


HEADERS = ("page", "from_type", "to_type", "expected_px", "actual_px")
ROWS = [
    ("Page 1", "card", "table", 16, 12.0),
    ("Page 2", "slicer", "card", 8, 10.0),
]


def test_write_csv_round_trip(tmp_path):
    out = tmp_path / "out.csv"
    export.write_csv(HEADERS, ROWS, out)

    with out.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    assert rows[0] == list(HEADERS)
    assert rows[1] == ["Page 1", "card", "table", "16", "12.0"]
    assert rows[2] == ["Page 2", "slicer", "card", "8", "10.0"]


def test_write_csv_handles_none_values(tmp_path):
    out = tmp_path / "out.csv"
    export.write_csv(("a", "b"), [(None, "x")], out)
    with out.open(encoding="utf-8") as fh:
        text = fh.read()
    assert ",x" in text  # the None became empty string


def test_write_json_round_trip(tmp_path):
    out = tmp_path / "out.json"
    export.write_json(HEADERS, ROWS, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == [
        {
            "page": "Page 1",
            "from_type": "card",
            "to_type": "table",
            "expected_px": 16,
            "actual_px": 12.0,
        },
        {
            "page": "Page 2",
            "from_type": "slicer",
            "to_type": "card",
            "expected_px": 8,
            "actual_px": 10.0,
        },
    ]


def test_write_json_is_indented_for_diff_friendliness(tmp_path):
    out = tmp_path / "out.json"
    export.write_json(("a", "b"), [(1, 2)], out)
    text = out.read_text(encoding="utf-8")
    assert "\n  " in text  # indent=2
