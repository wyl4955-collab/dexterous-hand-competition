from dexterous_hand_competition.common.contracts import BeanCandidate
from dexterous_hand_competition.task.target_manager import TargetManager


def candidate(target_id, confidence=0.9, edge=50.0, neighbor=50.0):
    return BeanCandidate(
        target_id=target_id,
        u=100.0,
        v=100.0,
        table_x_m=0.4,
        table_y_m=-0.2,
        confidence=confidence,
        edge_distance_px=edge,
        nearest_neighbor_px=neighbor,
    )


def test_select_prefers_confident_isolated_target():
    manager = TargetManager()
    selected = manager.select([
        candidate(1, confidence=0.6, edge=20.0, neighbor=20.0),
        candidate(2, confidence=0.95, edge=80.0, neighbor=100.0),
    ])
    assert selected.target_id == 2


def test_failed_target_is_temporarily_blacklisted_then_expires():
    now = [10.0]
    manager = TargetManager(
        max_retries=2,
        blacklist_ttl_sec=5.0,
        clock=lambda: now[0],
    )
    assert not manager.mark_failure(1)
    assert manager.mark_failure(1)
    assert manager.is_blacklisted(1)
    assert manager.select([candidate(1)]) is None

    now[0] += 5.1
    assert not manager.is_blacklisted(1)
    assert manager.select([candidate(1)]).target_id == 1


def test_success_clears_failure_history():
    manager = TargetManager(max_retries=2)
    manager.mark_failure(7)
    assert manager.failure_count(7) == 1
    manager.mark_success(7)
    assert manager.failure_count(7) == 0
