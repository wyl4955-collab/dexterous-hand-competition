"""Pure-Python dry-run adapters for C2 state-machine development."""

import math

from ..common.contracts import ActionResult


class DryRunArmAdapter:
    dry_run = True

    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def move_named_pose(
        self,
        name: str,
        timeout_sec: float = 10.0,
    ) -> ActionResult:
        self.calls.append(('move_named_pose', (name, timeout_sec)))
        return ActionResult.dry_run(f'would move arm to {name}')

    def move_to_joints(
        self,
        target: dict[int, float],
        duration_sec: float,
        timeout_sec: float,
    ) -> ActionResult:
        self.calls.append(
            ('move_to_joints', (dict(target), duration_sec, timeout_sec))
        )
        return ActionResult.dry_run(
            f'would move {len(target)} dry-run joints'
        )

    def stop_motion(self, reason: str):
        self.calls.append(('stop_motion', reason))


class DryRunHandAdapter:
    dry_run = True

    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def move_hand_pose(
        self,
        name: str,
        timeout_sec: float = 3.0,
    ) -> ActionResult:
        self.calls.append(('move_hand_pose', (name, timeout_sec)))
        return ActionResult.dry_run(f'would move hand to {name}')


class DryRunWorkspaceMapper:
    """Maps finite table points to synthetic joints; never use on hardware."""

    _LAYER_INDEX = {'hover': 0.0, 'pick': 1.0, 'lift': 2.0}

    def map_table_to_joints(
        self,
        x_m: float,
        y_m: float,
        layer: str,
    ) -> dict[int, float] | None:
        if layer not in self._LAYER_INDEX:
            return None
        if not math.isfinite(float(x_m)) or not math.isfinite(float(y_m)):
            return None
        return {1: float(x_m), 2: float(y_m), 3: self._LAYER_INDEX[layer]}
