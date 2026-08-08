"""Ranks soybean candidates by pickability.

Does not import ROS types — works on plain dict/list input so it can be
unit-tested without a ROS installation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoredTarget:
    """A bean candidate with a composite pickability score."""

    target_id: int
    u: float
    v: float
    x_m: float
    y_m: float
    confidence: float
    edge_distance_px: float
    nearest_neighbor_px: float
    failure_count: int
    score: float


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rank_candidates(
    beans: list[dict],
    workspace_center: tuple[float, float] = (0.0, 0.0),
    failure_map: dict[int, int] | None = None,
) -> list[ScoredTarget]:
    """Score every candidate and return them sorted best-first.

    Weights are chosen so that safe, isolated beans rank highest:
      - edge distance (avoid container walls)   — 0.30
      - nearest-neighbour distance (isolation)  — 0.25
      - workspace centrality                    — 0.15
      - detection confidence                    — 0.15
      - failure count penalty                   — 0.15

    Args:
        beans: list of dicts with keys id, u, v, x_m, y_m, confidence,
               edge_distance_px, nearest_neighbor_px.
        workspace_center: (cx_m, cy_m) of the preferred picking zone.
        failure_map: {target_id: consecutive_failures}.

    Returns:
        Candidates ordered by descending score.
    """
    if failure_map is None:
        failure_map = {}

    scored = []
    for bean in beans:
        edge = _safe_float(bean.get('edge_distance_px', 0))
        nn = _safe_float(bean.get('nearest_neighbor_px', 9999))
        x = _safe_float(bean.get('x_m', 0))
        y = _safe_float(bean.get('y_m', 0))
        conf = _safe_float(bean.get('confidence', 0.5))
        tid = int(bean.get('id', bean.get('target_id', 0)))
        failures = int(failure_map.get(tid, 0))

        # Normalise components to roughly [0, 1].
        edge_score = min(1.0, edge / 200.0)
        iso_score = min(1.0, nn / 100.0)
        dist_to_center = (
            (x - workspace_center[0]) ** 2 + (y - workspace_center[1]) ** 2
        ) ** 0.5
        center_score = max(0.0, 1.0 - dist_to_center / 0.15)
        fail_penalty = min(1.0, failures * 0.25)

        score = (
            0.30 * edge_score
            + 0.25 * iso_score
            + 0.15 * center_score
            + 0.15 * conf
            - 0.15 * fail_penalty
        )

        scored.append(
            ScoredTarget(
                target_id=tid,
                u=_safe_float(bean.get('u', 0)),
                v=_safe_float(bean.get('v', 0)),
                x_m=x,
                y_m=y,
                confidence=conf,
                edge_distance_px=edge,
                nearest_neighbor_px=nn,
                failure_count=failures,
                score=score,
            )
        )

    scored.sort(key=lambda t: t.score, reverse=True)
    return scored


def select_best(
    beans: list[dict],
    workspace_center: tuple[float, float] = (0.0, 0.0),
    failure_map: dict[int, int] | None = None,
    min_score: float = 0.1,
) -> ScoredTarget | None:
    """Return the single best candidate, or None if none meet the threshold."""
    ranked = rank_candidates(beans, workspace_center, failure_map)
    if not ranked or ranked[0].score < min_score:
        return None
    return ranked[0]
