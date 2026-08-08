from dexterous_hand_competition.common.contracts import (
    BeanCandidate,
    ResultCode,
)
from dexterous_hand_competition.skills.tweezer_skills import TweezerSkills
from dexterous_hand_competition.tools.mock_robot import (
    DryRunArmAdapter,
    DryRunHandAdapter,
    DryRunWorkspaceMapper,
)


def bean():
    return BeanCandidate(
        target_id=4,
        u=640.0,
        v=360.0,
        table_x_m=0.45,
        table_y_m=-0.20,
        confidence=0.99,
        edge_distance_px=100.0,
        nearest_neighbor_px=100.0,
    )


def build_skills(safety=lambda: True):
    arm = DryRunArmAdapter()
    hand = DryRunHandAdapter()
    skills = TweezerSkills(
        arm,
        hand,
        DryRunWorkspaceMapper(),
        safety_check=safety,
        hand_feedback_check=lambda: True,
        tweezer_verifier=lambda: True,
    )
    return skills, arm, hand


def test_grasp_tweezer_uses_public_sequence():
    skills, arm, hand = build_skills()
    result = skills.grasp_tweezer()
    assert result.ok
    assert result.code == ResultCode.DRY_RUN
    assert [call[1][0] for call in hand.calls] == [
        'tweezers_pregrasp',
        'tweezers_hold',
    ]
    assert [call[1][0] for call in arm.calls] == [
        'tweezer_pregrasp',
        'tweezer_grasp',
    ]


def test_safety_latch_blocks_commands():
    skills, arm, hand = build_skills(safety=lambda: False)
    result = skills.squeeze_bean()
    assert not result.ok
    assert result.code == ResultCode.SAFETY_LOCKED
    assert arm.calls == []
    assert hand.calls == []


def test_workspace_layers_are_delegated_to_mapper_and_arm():
    skills, arm, _ = build_skills()
    assert skills.move_hover(bean()).ok
    assert skills.descend(bean()).ok
    assert skills.lift(bean()).ok
    layers = [call[1][0][3] for call in arm.calls]
    assert layers == [0.0, 1.0, 2.0]


def test_releasing_bean_does_not_release_tool():
    skills, _, hand = build_skills()
    assert skills.release_bean().ok
    assert hand.calls[0][1][0] == 'tweezers_release'
    assert all(call[1][0] != 'release_tool' for call in hand.calls)


def test_missing_tweezer_verifier_is_not_assumed_successful():
    skills = TweezerSkills(
        DryRunArmAdapter(),
        DryRunHandAdapter(),
        DryRunWorkspaceMapper(),
        hand_feedback_check=lambda: True,
    )
    result = skills.ensure_tweezer_held()
    assert not result.ok
    assert result.code == ResultCode.ADAPTER_MISSING


def test_missing_candidate_is_rejected_without_calling_adapter():
    skills, arm, _ = build_skills()
    result = skills.move_hover(None)
    assert not result.ok
    assert result.code == ResultCode.VISION_INVALID
    assert arm.calls == []
