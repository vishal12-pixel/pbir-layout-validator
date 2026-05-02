"""CSV / JSON export for ResultTable rows (FR-013a).

Pure stdlib. No Tk imports — independently unit-testable.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Sequence


def _table_to_csv_bytes(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
) -> bytes:
    """Render headers + rows to UTF-8 CSV bytes.

    Used by both the per-tab Export button (via :func:`write_csv`) and the
    new ZIP-of-CSVs aggregator in :mod:`pbir_validator.gui.controllers`
    so per-tab parity is structural, not duplicated. Empty-row tables
    still emit the header line.
    """
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow(["" if v is None else str(v) for v in row])
    return buf.getvalue().encode("utf-8")


def write_csv(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    path: Path | str,
) -> None:
    """Write ``rows`` to ``path`` as UTF-8 CSV with ``headers`` on the first line.

    Header order in the file matches ``headers`` exactly. Values are rendered
    via ``str()``; ``None`` becomes the empty string so Excel doesn't show
    "None".
    """
    path = Path(path)
    path.write_bytes(_table_to_csv_bytes(headers, rows))


def write_json(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    path: Path | str,
) -> None:
    """Write ``rows`` to ``path`` as a JSON array of objects keyed by header.

    Output is ``indent=2`` UTF-8 with stable key order for diff-friendliness.
    """
    path = Path(path)
    payload = [
        {h: ("" if v is None else v) for h, v in zip(headers, row)}
        for row in rows
    ]
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
