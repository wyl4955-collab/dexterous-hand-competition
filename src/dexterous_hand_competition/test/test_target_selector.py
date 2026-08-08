from dexterous_hand_competition.vision.target_selector import (
    rank_candidates,
    select_best,
)


def make_bean(tid, x_m, y_m, edge=100.0, nn=100.0, conf=0.8):
    return {
        'id': tid,
        'u': 320.0 + tid * 10,
        'v': 240.0 + tid * 10,
        'x_m': x_m,
        'y_m': y_m,
        'confidence': conf,
        'edge_distance_px': edge,
        'nearest_neighbor_px': nn,
    }


class TestRankCandidates:
    def test_single_bean_returns_one(self):
        beans = [make_bean(1, 0.4, -0.2)]
        ranked = rank_candidates(beans)
        assert len(ranked) == 1
        assert ranked[0].target_id == 1

    def test_edge_bean_ranks_lower_than_center(self):
        edge_bean = make_bean(1, 0.4, -0.2, edge=10.0)   # near wall
        center_bean = make_bean(2, 0.4, -0.2, edge=150.0)  # safe
        ranked = rank_candidates([edge_bean, center_bean])
        assert ranked[0].target_id == 2

    def test_isolated_bean_ranks_higher(self):
        crowded = make_bean(1, 0.4, -0.2, nn=10.0)
        isolated = make_bean(2, 0.4, -0.2, nn=200.0)
        ranked = rank_candidates([crowded, isolated])
        assert ranked[0].target_id == 2

    def test_failure_penalty_reduces_score(self):
        clean = make_bean(1, 0.4, -0.2)
        failed = make_bean(2, 0.4, -0.2)
        ranked = rank_candidates([clean, failed], failure_map={2: 4})
        assert ranked[0].target_id == 1

    def test_far_from_workspace_center_ranks_lower(self):
        near = make_bean(1, 0.42, -0.19)
        far = make_bean(2, 0.55, -0.35)
        ranked = rank_candidates([far, near], workspace_center=(0.42, -0.20))
        assert ranked[0].target_id == 1


class TestSelectBest:
    def test_selects_highest_scored(self):
        beans = [
            make_bean(1, 0.4, -0.2, edge=20.0),
            make_bean(2, 0.4, -0.2, edge=150.0),
        ]
        best = select_best(beans)
        assert best is not None
        assert best.target_id == 2

    def test_returns_none_when_empty(self):
        assert select_best([]) is None

    def test_returns_none_below_min_score(self):
        beans = [make_bean(1, 0.4, -0.2, edge=5.0, nn=5.0, conf=0.1)]
        assert select_best(beans, min_score=0.5) is None
