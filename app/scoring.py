from __future__ import annotations

from typing import Any, Dict, List
from .cache import get_q

def hour_overlap(blocks1: List[Dict[str, str]], blocks2: List[Dict[str, str]]) -> float:
    def to_minutes(s: str) -> int:
        hh, mm = map(int, s.split(":"))
        return hh * 60 + mm
    minutes = 0
    for b1 in blocks1:
        s1, e1 = to_minutes(b1["start"]), to_minutes(b1["end"])
        for b2 in blocks2:
            s2, e2 = to_minutes(b2["start"]), to_minutes(b2["end"])
            minutes += max(0, min(e1, e2) - max(s1, s2))
    return minutes / 60.0

def jaccard(a: List[str], b: List[str]) -> float:
    A, B = set(a), set(b)
    return 0.0 if not A or not B else len(A & B) / len(A | B)

def score_interviewer(user: Dict[str, Any], query, itv: Dict[str, Any], redis_client) -> float:
    if query.language not in itv["languages"]:
        return float("-inf")

    ov = hour_overlap(user["availability_local"], itv["availability_local"])
    ov_pen = 0.0 if ov > 0 else -1.0

    cq = get_q(redis_client, itv["interviewer_id"])
    capacity_penalty = -2.0 if cq >= 8 else 0.0

    def budget_fit(rate: float, budget: float) -> float:
        return 0.5 if rate <= budget else -1.5 * ((rate - budget) / max(20.0, budget))

    def speed_fit(avg: float, sla: int) -> float:
        return 0.5 if avg <= sla else -0.3 * ((avg - sla) / max(10, sla))

    expertise_score = 2.0 * jaccard(query.topics, itv["expertise_tags"])
    domain_score = 1.5 * jaccard(user["domain_tags"], itv["expertise_tags"])
    budget_score = budget_fit(itv["rate_usd"], query.budget)
    speed_score = speed_fit(itv["avg_time_min"], query.sla_min)
    empathy_weight = 1.0 if query.sensitivity else 0.3
    empathy_score = empathy_weight * itv["empathy_score"]
    load_penalty = -0.08 * cq
    reliability_bns = 0.5 * itv["reliability"]

    return (
        2.0 * expertise_score
        + 1.0 * domain_score
        + budget_score
        + speed_score
        + empathy_score
        + reliability_bns
        + load_penalty
        + capacity_penalty
        + ov_pen
    )
