"""Deterministic match score from a job analysis' ranked requirements."""
from typing import List, Optional

WEIGHTS = {"high": 3, "medium": 2, "low": 1, "filler": 0}
CREDIT = {"yes": 1.0, "partly": 0.5, "no": 0.0}


def compute_match_score(requirements: List[dict]) -> Optional[int]:
    total_weight = 0
    earned = 0.0
    for req in requirements:
        weight = WEIGHTS.get(req.get("filter_likelihood"), WEIGHTS["low"])
        total_weight += weight
        earned += weight * CREDIT.get(req.get("meets"), CREDIT["no"])
    if total_weight == 0:
        return None
    return round(100 * earned / total_weight)


def score_band(score: int) -> str:
    if score >= 70:
        return "blue"
    if score >= 45:
        return "yellow"
    return "red"
