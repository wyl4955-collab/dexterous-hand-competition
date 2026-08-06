from dexterous_hand_competition.control.workspace_mapper import (
    WorkspaceMapper,
    WorkspacePoint,
)


def build_mapper(calibrated=True):
    points = {
        (0, 0): WorkspacePoint(0.0, 0.0, {'hover': {21: 0.0}}),
        (1, 0): WorkspacePoint(1.0, 0.0, {'hover': {21: 1.0}}),
        (0, 1): WorkspacePoint(0.0, 1.0, {'hover': {21: 1.0}}),
        (1, 1): WorkspacePoint(1.0, 1.0, {'hover': {21: 2.0}}),
    }
    return WorkspaceMapper([0.0, 1.0], [0.0, 1.0], points, calibrated)


def test_bilinear_center_value():
    result = build_mapper().map_table_to_joints(0.5, 0.5, 'hover')
    assert result is not None
    assert abs(result[21] - 1.0) < 1e-9


def test_workspace_does_not_extrapolate():
    assert build_mapper().map_table_to_joints(1.1, 0.5, 'hover') is None


def test_uncalibrated_workspace_is_blocked():
    assert build_mapper(False).map_table_to_joints(0.5, 0.5, 'hover') is None

