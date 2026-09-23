def rank_candidates(scores):
    """Sort candidates by forward_score descending."""
    valid = [s for s in scores if s.get("forward_score", 0) > 0]
    return sorted(valid, key=lambda x: x["forward_score"], reverse=True)


def classify_attribution(ranked):
    """
    Three-outcome logic:
      STRONG       - top score clearly above others
      INCONCLUSIVE - top two scores very close
      INSUFFICIENT - no candidate meets minimum threshold
    """
    if not ranked:
        return {"outcome": "INSUFFICIENT",
                "reason": "No candidates scored"}

    top = ranked[0]["forward_score"]

    if top < 0.4:
        return {"outcome": "INSUFFICIENT",
                "reason": f"Top score {top:.2f} below threshold"}

    if len(ranked) >= 2:
        gap = ranked[0]["forward_score"] - ranked[1]["forward_score"]
        if gap < 0.1:
            return {"outcome": "INCONCLUSIVE",
                    "reason": f"Top two scores within {gap:.2f}"}

    return {"outcome": "STRONG",
            "reason": f"Top score {top:.2f}"}