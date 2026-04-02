"""
JSON reporter — writes structured scan results to stdout or a file.
"""

from __future__ import annotations

import dataclasses
import json
import math
import sys
from pathlib import Path
from typing import Any

from bull.models.signal import ScanResult


class JsonReporter:
    """Serialise a ``ScanResult`` to JSON."""

    def __init__(self, output_path: Path | None = None) -> None:
        """
        Parameters
        ----------
        output_path:
            If provided, write JSON to this file.  Otherwise write to stdout.
        """
        self._output_path = output_path

    def render(self, result: ScanResult) -> None:
        payload = _to_dict(result)
        text = json.dumps(payload, indent=2, default=_default)
        if self._output_path:
            self._output_path.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text + "\n")


# ─────────────────────────── serialisation helpers ──────────────────────────


def _to_dict(obj: Any) -> Any:  # noqa: ANN401
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _default(obj: Any) -> Any:  # noqa: ANN401
    """Custom JSON encoder for types json can't handle by default."""
    import datetime

    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, float) and math.isnan(obj):
        return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
