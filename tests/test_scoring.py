"""Tests for bull.scoring"""

from __future__ import annotations

from bull.models.signal import PatternMatch
from bull.scoring import score_patterns


def _pat(name: str, strength: float = 1.0) -> PatternMatch:
    return PatternMatch(name=name, strength=strength, description="test")


def _detectors() -> list[tuple]:
    """Minimal detector list (fn name → pattern name mapping)."""

    class FakeFn:
        def __init__(self, name: str) -> None:
            self.__name__ = name

    return [
        (FakeFn("bullish_engulfing"), 3.0),
        (FakeFn("golden_cross"), 2.5),
        (FakeFn("rsi_oversold_bounce"), 2.0),
    ]


class TestScorePatterns:
    def test_all_matched_at_full_strength_returns_10(self) -> None:
        detectors = _detectors()
        matched = [
            _pat("Bullish Engulfing"),
            _pat("Golden Cross"),
            _pat("Rsi Oversold Bounce"),
        ]
        score = score_patterns(matched, detectors)
        assert score == 10.0

    def test_no_match_returns_zero(self) -> None:
        score = score_patterns([], _detectors())
        assert score == 0.0

    def test_partial_match_between_0_and_10(self) -> None:
        detectors = _detectors()
        matched = [_pat("Bullish Engulfing", strength=0.5)]
        score = score_patterns(matched, detectors)
        assert 0 < score < 10

    def test_score_scales_with_strength(self) -> None:
        detectors = _detectors()
        high = score_patterns([_pat("Bullish Engulfing", 1.0)], detectors)
        low = score_patterns([_pat("Bullish Engulfing", 0.2)], detectors)
        assert high > low

    def test_higher_weight_detector_scores_higher(self) -> None:
        detectors = _detectors()
        # golden_cross weight=2.5, rsi_oversold_bounce weight=2.0
        score_gc = score_patterns([_pat("Golden Cross")], detectors)
        score_rsi = score_patterns([_pat("Rsi Oversold Bounce")], detectors)
        assert score_gc > score_rsi
