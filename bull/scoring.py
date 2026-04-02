"""
Composite signal scoring.

``score_patterns`` converts a list of ``PatternMatch`` objects and their
associated weights into a single float score on a 0–10 scale.

Formula
-------
For each matched pattern with weight *w* and strength *s* (0–1):

    contribution = w * s

The raw sum is normalised to [0, 10] using the theoretical maximum
(all patterns matched at full strength).
"""

from __future__ import annotations

from bull.models.signal import PatternMatch


def score_patterns(
    matched: list[PatternMatch],
    detectors: list[tuple],
) -> float:
    """
    Compute a [0, 10] composite score.

    Parameters
    ----------
    matched:
        Patterns that were detected.
    detectors:
        Full (detector_fn, weight) list for the current mode — used to
        compute the theoretical maximum so scores are comparable across modes.

    Returns
    -------
    float
        Score in [0, 10].
    """
    if not matched or not detectors:
        return 0.0

    # Map pattern name → weight via the detectors list
    weight_map: dict[str, float] = {}
    max_raw = 0.0
    for fn, w in detectors:
        name = _detector_name(fn)
        weight_map[name] = w
        max_raw += w  # theoretical max if all patterns hit at strength 1.0

    raw = sum(
        weight_map.get(p.name, 1.0) * p.strength
        for p in matched
    )

    return round(min(10.0, (raw / max_raw) * 10.0), 3) if max_raw > 0 else 0.0


def _detector_name(fn: object) -> str:
    """Derive the expected PatternMatch.name from a detector function."""
    # Pattern functions return PatternMatch with a fixed name — we derive it
    # from the function name by converting snake_case → Title Case with spaces.
    name = getattr(fn, "__name__", "")
    return name.replace("_", " ").title()
