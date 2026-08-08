"""ROS 2 C2 orchestrator for autonomous tweezer bean picking.

The node is executable end-to-end with synthetic adapters in ``dry_run``.
Real mode intentionally refuses to start until verified A/C1 adapters are
injected.  Pick and drop counters require target-ID confirmations published by
the vision side; state transitions alone never increment the score.
"""

from dataclasses import replace
from pathlib import Path
import threading
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.callback_groups import (
    MutuallyExclusiveCallbackGroup,
    ReentrantCallbackGroup,
)
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool, UInt32
from std_srvs.srv import Trigger

from competition_interfaces.msg import Scene, TaskState

from ..common.config_loader import load_yaml
from ..common.contracts import ActionResult, BeanCandidate, ResultCode
from ..skills.tweezer_skills import TweezerSkills
from ..tools.mock_robot import (
    DryRunArmAdapter,
    DryRunHandAdapter,
    DryRunWorkspaceMapper,
)
from .fsm import BeanTaskFsm, BeanTaskState
from .settings import BeanTaskSettings
from .target_manager import TargetManager


class BeanTaskNode(Node):
    def __init__(self, skills: TweezerSkills | None = None):
        super().__init__('bean_task_node')
        self._lock = threading.RLock()
        self._io_group = ReentrantCallbackGroup()
        self._tick_group = MutuallyExclusiveCallbackGroup()

        default_config = self._default_config_path()
        self.declare_parameter('config_file', str(default_config))
        config_path = str(self.get_parameter('config_file').value)
        configured = BeanTaskSettings.from_mapping(load_yaml(config_path))

        self.declare_parameter('dry_run', configured.dry_run)
        self.declare_parameter('time_limit_sec', configured.time_limit_sec)
        self.declare_parameter('target_count', configured.target_count)
        self.declare_parameter(
            'scene_timeout_sec', configured.scene_timeout_sec
        )
        self.declare_parameter(
            'auto_grasp_tweezer', configured.auto_grasp_tweezer
        )
        self.declare_parameter(
            'auto_release_tweezer', configured.auto_release_tweezer
        )
        self.settings = replace(
            configured,
            dry_run=bool(self.get_parameter('dry_run').value),
            time_limit_sec=float(
                self.get_parameter('time_limit_sec').value
            ),
            target_count=int(self.get_parameter('target_count').value),
            scene_timeout_sec=float(
                self.get_parameter('scene_timeout_sec').value
            ),
            auto_grasp_tweezer=bool(
                self.get_parameter('auto_grasp_tweezer').value
            ),
            auto_release_tweezer=bool(
                self.get_parameter('auto_release_tweezer').value
            ),
        )
        self.settings.validate()

        self.fsm = BeanTaskFsm(self.settings.state_timeouts_sec)
        self.targets = TargetManager(
            max_retries=self.settings.max_pick_retries,
            blacklist_ttl_sec=self.settings.blacklist_ttl_sec,
            min_confidence=self.settings.min_target_confidence,
        )
        self.task_started_sec = 0.0
        self.beans_confirmed = 0
        self.latest_scene: Scene | None = None
        self.latest_scene_received_sec = 0.0
        self.safety_ok = self.settings.dry_run
        self.vision_ok = self.settings.dry_run
        self.stop_requested = False
        self.current_target: BeanCandidate | None = None
        self.pick_confirmation = (0, 0.0)
        self.drop_confirmation = (0, 0.0)
        self.selection_not_before_sec = 0.0
        self.last_event = 'waiting for start'
        self._action_in_progress = False

        if skills is not None:
            self.skills = skills
            self.adapters_ready = True
        elif self.settings.dry_run:
            self.skills = TweezerSkills(
                DryRunArmAdapter(),
                DryRunHandAdapter(),
                DryRunWorkspaceMapper(),
                safety_check=self._commands_allowed,
                hand_feedback_check=lambda: True,
                tweezer_verifier=lambda: True,
            )
            self.adapters_ready = True
        else:
            self.skills = None
            self.adapters_ready = False

        self.state_pub = self.create_publisher(
            TaskState, '/bean_task/state', 10
        )
        self.active_target_pub = self.create_publisher(
            UInt32, '/bean_task/active_target_id', 10
        )
        self.create_subscription(
            Scene,
            '/bean_task/scene',
            self._scene_callback,
            10,
            callback_group=self._io_group,
        )
        self.create_subscription(
            Bool,
            '/bean_task/safety_ok',
            self._safety_callback,
            10,
            callback_group=self._io_group,
        )
        self.create_subscription(
            Bool,
            '/bean_task/vision_health',
            self._vision_health_callback,
            10,
            callback_group=self._io_group,
        )
        self.create_subscription(
            UInt32,
            '/bean_task/pick_confirmed_id',
            self._pick_confirmation_callback,
            10,
            callback_group=self._io_group,
        )
        self.create_subscription(
            UInt32,
            '/bean_task/drop_confirmed_id',
            self._drop_confirmation_callback,
            10,
            callback_group=self._io_group,
        )
        self.create_service(
            Trigger,
            '/bean_task/start',
            self._start_callback,
            callback_group=self._io_group,
        )
        self.create_service(
            Trigger,
            '/bean_task/stop',
            self._stop_callback,
            callback_group=self._io_group,
        )
        self.create_service(
            Trigger,
            '/bean_task/reset',
            self._reset_callback,
            callback_group=self._io_group,
        )
        self.create_timer(
            self.settings.tick_period_sec,
            self._tick,
            callback_group=self._tick_group,
        )
        self.create_timer(
            self.settings.state_publish_period_sec,
            self._publish_state,
            callback_group=self._io_group,
        )

        if self.settings.dry_run:
            self.get_logger().warning(
                'C2 task node uses synthetic dry-run robot adapters'
            )
        elif not self.adapters_ready:
            self.get_logger().error(
                'Real mode locked: inject verified A/C1 adapters before start'
            )

    @staticmethod
    def _default_config_path() -> Path:
        try:
            share = Path(
                get_package_share_directory('dexterous_hand_competition')
            )
            candidate = share / 'config' / 'bean_task.yaml'
            if candidate.is_file():
                return candidate
        except Exception:
            pass
        package_root = Path(__file__).resolve().parents[2]
        return package_root / 'config' / 'bean_task.yaml'

    def _commands_allowed(self) -> bool:
        with self._lock:
            return (
                self.safety_ok
                and self.vision_ok
                and not self.stop_requested
                and self.fsm.state != BeanTaskState.ERROR_LOCK
            )

    def _scene_callback(self, message: Scene):
        with self._lock:
            self.latest_scene = message
            self.latest_scene_received_sec = time.monotonic()

    def _safety_callback(self, message: Bool):
        should_lock = False
        with self._lock:
            self.safety_ok = bool(message.data)
            should_lock = (
                not self.safety_ok
                and self.fsm.state
                not in (
                    BeanTaskState.WAIT_START,
                    BeanTaskState.DONE,
                    BeanTaskState.ERROR_LOCK,
                )
            )
        if should_lock:
            if self.skills is not None:
                self.skills.halt('safety monitor became unsafe')
            self._lock_error('safety monitor became unsafe')

    def _vision_health_callback(self, message: Bool):
        should_lock = False
        with self._lock:
            self.vision_ok = bool(message.data)
            should_lock = (
                not self.vision_ok
                and self.fsm.state
                not in (
                    BeanTaskState.WAIT_START,
                    BeanTaskState.DONE,
                    BeanTaskState.ERROR_LOCK,
                )
            )
        if should_lock:
            if self.skills is not None:
                self.skills.halt('vision health became false')
            self._lock_error('vision health became false')

    def _pick_confirmation_callback(self, message: UInt32):
        with self._lock:
            self.pick_confirmation = (int(message.data), time.monotonic())

    def _drop_confirmation_callback(self, message: UInt32):
        with self._lock:
            self.drop_confirmation = (int(message.data), time.monotonic())

    def _start_callback(self, request, response):
        _ = request
        with self._lock:
            if self.fsm.state != BeanTaskState.WAIT_START:
                response.success = False
                response.message = f'task is in {self.fsm.state.name}'
                return response
            if not self.safety_ok:
                response.success = False
                response.message = 'safety monitor is not clear'
                return response
            if not self.vision_ok:
                response.success = False
                response.message = 'vision health is not clear'
                return response
            if not self.adapters_ready or self.skills is None:
                response.success = False
                response.message = 'verified robot adapters are not connected'
                return response

            self.task_started_sec = time.monotonic()
            self.beans_confirmed = 0
            self.stop_requested = False
            self.current_target = None
            self.pick_confirmation = (0, 0.0)
            self.drop_confirmation = (0, 0.0)
            self.selection_not_before_sec = 0.0
            self.targets.reset()
        self._transition(BeanTaskState.CHECK_SYSTEM, 'start service accepted')
        response.success = True
        response.message = (
            'dry-run task started'
            if self.settings.dry_run
            else 'bean-picking task started'
        )
        return response

    def _stop_callback(self, request, response):
        _ = request
        with self._lock:
            state = self.fsm.state
            if state == BeanTaskState.WAIT_START:
                response.success = True
                response.message = 'task is already idle'
                return response
            if state in (BeanTaskState.DONE, BeanTaskState.ERROR_LOCK):
                response.success = False
                response.message = f'task is already in {state.name}'
                return response
            self.stop_requested = True
        if self.skills is not None:
            self.skills.halt('manual stop requested')
        self._transition(
            BeanTaskState.SAFE_FINISH,
            'manual stop: hold position and issue no new task commands',
        )
        response.success = True
        response.message = 'manual stop latched; no new actions will start'
        return response

    def _reset_callback(self, request, response):
        _ = request
        with self._lock:
            if self.fsm.state not in (
                BeanTaskState.DONE,
                BeanTaskState.ERROR_LOCK,
            ):
                response.success = False
                response.message = 'reset is allowed only from DONE/ERROR_LOCK'
                return response
            if not self.safety_ok:
                response.success = False
                response.message = (
                    'inspect robot and clear safety before reset'
                )
                return response
            if not self.vision_ok:
                response.success = False
                response.message = 'restore vision health before reset'
                return response
            self.fsm.reset()
            self.stop_requested = False
            self.task_started_sec = 0.0
            self.current_target = None
            self.last_event = 'manual reset complete'
            self.targets.reset()
        self._publish_active_target()
        response.success = True
        response.message = 'task reset to WAIT_START'
        return response

    def _scene_is_fresh(self) -> bool:
        with self._lock:
            return (
                self.latest_scene is not None
                and time.monotonic() - self.latest_scene_received_sec
                <= self.settings.scene_timeout_sec
            )

    def _elapsed(self) -> float:
        with self._lock:
            started = self.task_started_sec
        return 0.0 if started <= 0.0 else time.monotonic() - started

    def _remaining(self) -> float:
        return max(0.0, self.settings.time_limit_sec - self._elapsed())

    @staticmethod
    def _to_candidates(scene: Scene) -> list[BeanCandidate]:
        return [
            BeanCandidate(
                target_id=int(bean.id),
                u=float(bean.u),
                v=float(bean.v),
                table_x_m=float(bean.table_position.x),
                table_y_m=float(bean.table_position.y),
                confidence=float(bean.confidence),
                edge_distance_px=float(bean.edge_distance_px),
                nearest_neighbor_px=float(bean.nearest_neighbor_px),
                failure_count=int(bean.failure_count),
            )
            for bean in scene.beans
            if int(bean.id) != 0
        ]

    def _latest_candidates(self) -> list[BeanCandidate]:
        with self._lock:
            scene = self.latest_scene
        return [] if scene is None else self._to_candidates(scene)

    def _matching_target(self) -> BeanCandidate | None:
        with self._lock:
            target = self.current_target
        if target is None or not self._scene_is_fresh():
            return None
        return next(
            (
                candidate
                for candidate in self._latest_candidates()
                if candidate.target_id == target.target_id
            ),
            None,
        )

    def _confirmation_matches(self, pick: bool) -> bool:
        with self._lock:
            target = self.current_target
            target_id, stamp = (
                self.pick_confirmation if pick else self.drop_confirmation
            )
            entered = self.fsm.state_entered_sec
        return (
            target is not None
            and target_id == target.target_id
            and stamp >= entered
        )

    def _transition(
        self,
        new_state: BeanTaskState,
        reason: str = '',
        error: str = '',
    ):
        with self._lock:
            previous = self.fsm.state
            try:
                self.fsm.transition(new_state, reason=reason, error=error)
            except ValueError as exc:
                self.get_logger().error(str(exc))
                if previous not in (
                    BeanTaskState.DONE,
                    BeanTaskState.ERROR_LOCK,
                ):
                    self.fsm.transition(
                        BeanTaskState.ERROR_LOCK,
                        error=f'FSM contract violation: {exc}',
                    )
                return
            self.last_event = reason or error or new_state.name
        self.get_logger().info(
            f'{previous.name} -> {new_state.name}: {self.last_event}'
        )

    def _lock_error(self, reason: str):
        with self._lock:
            if self.fsm.state in (
                BeanTaskState.DONE,
                BeanTaskState.ERROR_LOCK,
            ):
                return
        self._transition(BeanTaskState.ERROR_LOCK, error=reason)
        self.get_logger().error(reason)

    def _execute_action(
        self,
        expected_state: BeanTaskState,
        label: str,
        action,
        success_state: BeanTaskState,
    ):
        if self.skills is None:
            self._lock_error('skill adapter is unavailable')
            return
        result: ActionResult = action()
        with self._lock:
            if self.fsm.state != expected_state:
                return
            stopped = self.stop_requested
            safe = self.safety_ok
        if result.ok:
            self._transition(success_state, f'{label}: {result.message}')
            return
        if stopped:
            self._transition(
                BeanTaskState.SAFE_FINISH,
                'manual stop acknowledged',
            )
        elif not safe or result.code == ResultCode.SAFETY_LOCKED:
            self._lock_error(f'{label}: safety locked: {result.message}')
        else:
            self._lock_error(
                f'{label} failed [{result.code.name}]: {result.message}'
            )

    def _normal_finish(self, reason: str, allow_tool_return: bool):
        next_state = (
            BeanTaskState.RETURN_TWEEZER
            if allow_tool_return and self.settings.auto_release_tweezer
            else BeanTaskState.SAFE_FINISH
        )
        self._transition(next_state, reason)

    def _handle_state_timeout(self, state: BeanTaskState):
        if state == BeanTaskState.VERIFY_PICK:
            self._transition(
                BeanTaskState.RECOVER_PICK,
                'pick confirmation timed out',
            )
        elif state == BeanTaskState.VERIFY_DROP:
            self._transition(
                BeanTaskState.RECOVER_DROP,
                'drop confirmation timed out; bean not counted',
            )
        elif state == BeanTaskState.WAIT_SCENE:
            self._lock_error('fresh calibrated vision scene timed out')
        else:
            self._lock_error(
                f'state {state.name} timed out after '
                f'{self.fsm.state_age_sec():.2f}s'
            )

    def _tick(self):
        with self._lock:
            state = self.fsm.state
            if state in (
                BeanTaskState.WAIT_START,
                BeanTaskState.DONE,
                BeanTaskState.ERROR_LOCK,
            ):
                return
            if self._action_in_progress:
                return
            if not self.safety_ok:
                pass
            elif not self.vision_ok:
                self._lock_error('vision health is not clear')
                return
            elif self.stop_requested and state != BeanTaskState.SAFE_FINISH:
                self._transition(
                    BeanTaskState.SAFE_FINISH, 'manual stop acknowledged'
                )
                return
            elif self._elapsed() >= self.settings.time_limit_sec:
                self._normal_finish(
                    'task time limit reached', allow_tool_return=False
                )
                return
            elif self.fsm.timed_out():
                self._handle_state_timeout(state)
                return
            self._action_in_progress = True

        try:
            if not self.safety_ok:
                self._lock_error('safety is not clear')
            else:
                self._advance(state)
        finally:
            with self._lock:
                self._action_in_progress = False

    def _advance(self, state: BeanTaskState):
        if state == BeanTaskState.CHECK_SYSTEM:
            if not self.adapters_ready or self.skills is None:
                self._lock_error('verified adapters are not ready')
            elif not self.vision_ok:
                return
            else:
                next_state = (
                    BeanTaskState.GRASP_TWEEZER
                    if self.settings.auto_grasp_tweezer
                    else BeanTaskState.VERIFY_TWEEZER
                )
                self._transition(next_state, 'system and safety checks passed')

        elif state == BeanTaskState.GRASP_TWEEZER:
            self._execute_action(
                state,
                'grasp tweezer',
                self.skills.grasp_tweezer,
                BeanTaskState.VERIFY_TWEEZER,
            )

        elif state == BeanTaskState.VERIFY_TWEEZER:
            self._execute_action(
                state,
                'verify tweezer',
                self.skills.ensure_tweezer_held,
                BeanTaskState.WAIT_SCENE,
            )

        elif state == BeanTaskState.WAIT_SCENE:
            if time.monotonic() < self.selection_not_before_sec:
                return
            if not self._scene_is_fresh():
                return
            with self._lock:
                scene = self.latest_scene
            if scene is None or not scene.valid or not scene.calibrated:
                return
            candidates = self._to_candidates(scene)
            if not candidates:
                self._normal_finish('no beans remain', allow_tool_return=True)
            elif (
                self._remaining()
                <= self.settings.stop_new_pick_remaining_sec
            ):
                self._normal_finish(
                    'insufficient time for another safe pick',
                    allow_tool_return=True,
                )
            else:
                self._transition(
                    BeanTaskState.SELECT_BEAN, 'fresh scene ready'
                )

        elif state == BeanTaskState.SELECT_BEAN:
            if not self._scene_is_fresh():
                self._transition(
                    BeanTaskState.WAIT_SCENE, 'scene became stale'
                )
                return
            candidate = self.targets.select(self._latest_candidates())
            if candidate is None:
                self.selection_not_before_sec = (
                    time.monotonic() + self.settings.retry_wait_sec
                )
                self._transition(
                    BeanTaskState.WAIT_SCENE,
                    'all visible targets are invalid or temporarily '
                    'blacklisted',
                )
                return
            with self._lock:
                self.current_target = candidate
            self._publish_active_target()
            self._transition(
                BeanTaskState.MOVE_HOVER,
                f'selected bean {candidate.target_id}',
            )

        elif state == BeanTaskState.MOVE_HOVER:
            target = self.current_target
            self._execute_action(
                state,
                'move hover',
                lambda: self.skills.move_hover(target),
                BeanTaskState.VISUAL_REFINE,
            )

        elif state == BeanTaskState.VISUAL_REFINE:
            refined = self._matching_target()
            if refined is None:
                target = self.current_target
                if target is not None:
                    self.targets.mark_failure(target.target_id)
                self._clear_current_target()
                self._transition(
                    BeanTaskState.WAIT_SCENE,
                    'selected bean disappeared before descent',
                )
                return
            with self._lock:
                self.current_target = refined
            self._execute_action(
                state,
                'visual refine',
                lambda: self.skills.visual_refine(refined),
                BeanTaskState.DESCEND,
            )

        elif state == BeanTaskState.DESCEND:
            target = self.current_target
            self._execute_action(
                state,
                'descend',
                lambda: self.skills.descend(target),
                BeanTaskState.SQUEEZE,
            )

        elif state == BeanTaskState.SQUEEZE:
            with self._lock:
                self.pick_confirmation = (0, 0.0)
            self._execute_action(
                state,
                'squeeze bean',
                self.skills.squeeze_bean,
                BeanTaskState.LIFT,
            )

        elif state == BeanTaskState.LIFT:
            target = self.current_target
            self._execute_action(
                state,
                'lift',
                lambda: self.skills.lift(target),
                BeanTaskState.VERIFY_PICK,
            )

        elif state == BeanTaskState.VERIFY_PICK:
            if self._confirmation_matches(pick=True):
                self._transition(
                    BeanTaskState.MOVE_TARGET,
                    f'vision confirmed pick of bean '
                    f'{self.current_target.target_id}',
                )

        elif state == BeanTaskState.RECOVER_PICK:
            target = self.current_target
            if target is None:
                self._lock_error('pick recovery has no active target')
                return
            result = self.skills.recover_failed_pick(target)
            if not result.ok:
                self._lock_error(f'pick recovery failed: {result.message}')
                return
            blacklisted = self.targets.mark_failure(target.target_id)
            suffix = ' and blacklisted' if blacklisted else ''
            self._clear_current_target()
            self._transition(
                BeanTaskState.WAIT_SCENE,
                f'pick recovery complete{suffix}',
            )

        elif state == BeanTaskState.MOVE_TARGET:
            self._execute_action(
                state,
                'move target',
                self.skills.move_to_target,
                BeanTaskState.RELEASE_BEAN,
            )

        elif state == BeanTaskState.RELEASE_BEAN:
            with self._lock:
                self.drop_confirmation = (0, 0.0)
            self._execute_action(
                state,
                'release bean',
                self.skills.release_bean,
                BeanTaskState.VERIFY_DROP,
            )

        elif state == BeanTaskState.VERIFY_DROP:
            if not self._confirmation_matches(pick=False):
                return
            target = self.current_target
            if target is None:
                self._lock_error('drop confirmation has no active target')
                return
            with self._lock:
                self.beans_confirmed += 1
                count = self.beans_confirmed
            self.targets.mark_success(target.target_id)
            self._clear_current_target()
            if (
                self.settings.target_count > 0
                and count >= self.settings.target_count
            ):
                self._normal_finish(
                    f'target count {count} reached', allow_tool_return=True
                )
            else:
                self._transition(
                    BeanTaskState.WAIT_SCENE,
                    f'vision confirmed bean {target.target_id}; total={count}',
                )

        elif state == BeanTaskState.RECOVER_DROP:
            target = self.current_target
            if target is not None:
                self.targets.mark_failure(target.target_id)
            self._clear_current_target()
            self._transition(
                BeanTaskState.WAIT_SCENE,
                'unconfirmed drop recorded without increasing count',
            )

        elif state == BeanTaskState.RETURN_TWEEZER:
            self._execute_action(
                state,
                'return tweezer',
                self.skills.release_tweezer,
                BeanTaskState.SAFE_FINISH,
            )

        elif state == BeanTaskState.SAFE_FINISH:
            if self.stop_requested:
                self._transition(
                    BeanTaskState.DONE,
                    'manual stop complete; robot remains held',
                )
            else:
                self._execute_action(
                    state,
                    'safe finish',
                    self.skills.safe_finish,
                    BeanTaskState.DONE,
                )

    def _clear_current_target(self):
        with self._lock:
            self.current_target = None
            self.pick_confirmation = (0, 0.0)
            self.drop_confirmation = (0, 0.0)
        self._publish_active_target()

    def _publish_active_target(self):
        with self._lock:
            target = self.current_target
        message = UInt32()
        message.data = 0 if target is None else int(target.target_id)
        self.active_target_pub.publish(message)

    def _publish_state(self):
        with self._lock:
            state = self.fsm.state
            last_error = self.fsm.last_error
            beans_confirmed = self.beans_confirmed
        message = TaskState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.task_name = 'tweezer_bean_picking'
        message.state_name = state.name
        message.state_code = int(state)
        message.elapsed_sec = float(self._elapsed())
        message.remaining_sec = float(self._remaining())
        message.beans_confirmed = int(beans_confirmed)
        message.last_error = last_error
        self.state_pub.publish(message)
        self._publish_active_target()


def main(args=None):
    rclpy.init(args=args)
    node = BeanTaskNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
