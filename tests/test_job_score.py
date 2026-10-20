import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.job_score import compute_match_score, score_band


def test_weighted_score():
    reqs = [
        {"filter_likelihood": "high", "meets": "yes"},
        {"filter_likelihood": "medium", "meets": "partly"},
        {"filter_likelihood": "low", "meets": "no"},
        {"filter_likelihood": "filler", "meets": "no"},
    ]
    assert compute_match_score(reqs) == 67


def test_all_filler_returns_none():
    assert compute_match_score([{"filter_likelihood": "filler", "meets": "yes"}]) is None
    assert compute_match_score([]) is None


def test_unknown_values_are_normalised():
    assert compute_match_score([{"filter_likelihood": "critical", "meets": None}]) == 0


def test_score_band_edges():
    assert score_band(70) == "blue"
    assert score_band(69) == "yellow"
    assert score_band(45) == "yellow"
    assert score_band(44) == "red"
