"""Timer-driven task orchestrator.

The scaffold simulates state transitions in dry-run mode. Real mode remains
locked until the verified arm, hand, safety and scene adapters are connected.
"""

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

from competition_interfaces.msg import Scene, TaskState

from .fsm import BeanTaskFsm, BeanTaskState


class BeanTaskNode(Node):
    def __init__(self):
        super().__init__('bean_task_node')
        self.declare_parameter('dry_run', True)
        self.declare_parameter('time_limit_sec', 300.0)
        self.declare_parameter('scene_timeout_sec', 0.5)
        self.dry_run = bool(self.get_parameter('dry_run').value)
        self.time_limit_sec = float(self.get_parameter('time_limit_sec').value)
        self.scene_timeout_sec = float(
            self.get_parameter('scene_timeout_sec').value
        )

        self.fsm = BeanTaskFsm()
        self.task_started_sec = 0.0
        self.beans_confirmed = 0
        self.latest_scene = None
        self.latest_scene_received_sec = 0.0
        self.safety_ok = self.dry_run

        self.state_pub = self.create_publisher(
            TaskState, '/bean_task/state', 10
        )
        self.scene_sub = self.create_subscription(
            Scene, '/bean_task/scene', self._scene_callback, 10
        )
        self.safety_sub = self.create_subscription(
            Bool, '/bean_task/safety_ok', self._safety_callback, 10
        )
        self.start_srv = self.create_service(
            Trigger, '/bean_task/start', self._start_callback
        )
        self.stop_srv = self.create_service(
            Trigger, '/bean_task/stop', self._stop_callback
        )
        self.create_timer(0.1, self._tick)
        self.create_timer(0.2, self._publish_state)

        if self.dry_run:
            self.get_logger().warning('Task node is running in dry-run mode')
        else:
            self.get_logger().error(
                'Real mode is not connected to verified robot adapters yet'
            )

    def _scene_callback(self, message: Scene):
        self.latest_scene = message
        self.latest_scene_received_sec = time.monotonic()

    def _safety_callback(self, message: Bool):
        self.safety_ok = bool(message.data)
        if not self.safety_ok and self.fsm.state not in (
            BeanTaskState.WAIT_START,
            BeanTaskState.ERROR_LOCK,
        ):
            self.fsm.transition(
                BeanTaskState.ERROR_LOCK, 'safety monitor became unsafe'
            )

    def _start_callback(self, request, response):
        _ = request
        if self.fsm.state != BeanTaskState.WAIT_START:
            response.success = False
            response.message = f'task is already in {self.fsm.state.name}'
            return response
        if not self.safety_ok:
            response.success = False
            response.message = 'safety monitor is not clear'
            return response
        if not self.dry_run:
            response.success = False
            response.message = 'real robot adapters are not implemented'
            return response

        self.task_started_sec = time.monotonic()
        self.beans_confirmed = 0
        self.fsm.transition(BeanTaskState.CHECK_SYSTEM)
        response.success = True
        response.message = 'dry-run task started'
        return response

    def _stop_callback(self, request, response):
        _ = request
        self.fsm.transition(BeanTaskState.SAFE_FINISH)
        response.success = True
        response.message = 'stop requested; no new task actions will start'
        return response

    def _scene_is_fresh(self) -> bool:
        return (
            self.latest_scene is not None
            and time.monotonic() - self.latest_scene_received_sec
            <= self.scene_timeout_sec
        )

    def _elapsed(self) -> float:
        if self.task_started_sec <= 0.0:
            return 0.0
        return time.monotonic() - self.task_started_sec

    def _tick(self):
        state = self.fsm.state
        if state in (
            BeanTaskState.WAIT_START,
            BeanTaskState.DONE,
            BeanTaskState.ERROR_LOCK,
        ):
            return
        if not self.safety_ok:
            self.fsm.transition(BeanTaskState.ERROR_LOCK, 'safety is not clear')
            return
        if self._elapsed() >= self.time_limit_sec:
            self.fsm.transition(BeanTaskState.SAFE_FINISH)
            return

        # This sequence is deliberately a dry-run scaffold. Replace each
        # transition with calls to the frozen public A/B/C interfaces.
        if state == BeanTaskState.CHECK_SYSTEM:
            self.fsm.transition(BeanTaskState.GRASP_TWEEZER)
        elif state == BeanTaskState.GRASP_TWEEZER:
            self.fsm.transition(BeanTaskState.VERIFY_TWEEZER)
        elif state == BeanTaskState.VERIFY_TWEEZER:
            self.fsm.transition(BeanTaskState.WAIT_SCENE)
        elif state == BeanTaskState.WAIT_SCENE:
            if self._scene_is_fresh() and self.latest_scene.valid:
                self.fsm.transition(BeanTaskState.SELECT_BEAN)
        elif state == BeanTaskState.SELECT_BEAN:
            if not self._scene_is_fresh() or not self.latest_scene.beans:
                self.fsm.transition(BeanTaskState.WAIT_SCENE)
            else:
                self.fsm.transition(BeanTaskState.MOVE_HOVER)
        elif state == BeanTaskState.MOVE_HOVER:
            self.fsm.transition(BeanTaskState.VISUAL_REFINE)
        elif state == BeanTaskState.VISUAL_REFINE:
            self.fsm.transition(BeanTaskState.DESCEND)
        elif state == BeanTaskState.DESCEND:
            self.fsm.transition(BeanTaskState.SQUEEZE)
        elif state == BeanTaskState.SQUEEZE:
            self.fsm.transition(BeanTaskState.LIFT)
        elif state == BeanTaskState.LIFT:
            self.fsm.transition(BeanTaskState.VERIFY_PICK)
        elif state == BeanTaskState.VERIFY_PICK:
            self.fsm.transition(BeanTaskState.MOVE_TARGET)
        elif state == BeanTaskState.MOVE_TARGET:
            self.fsm.transition(BeanTaskState.RELEASE_BEAN)
        elif state == BeanTaskState.RELEASE_BEAN:
            self.fsm.transition(BeanTaskState.VERIFY_DROP)
        elif state == BeanTaskState.VERIFY_DROP:
            self.beans_confirmed += 1
            self.fsm.transition(BeanTaskState.WAIT_SCENE)
        elif state == BeanTaskState.SAFE_FINISH:
            self.fsm.transition(BeanTaskState.DONE)

    def _publish_state(self):
        message = TaskState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.task_name = 'tweezer_bean_picking'
        message.state_name = self.fsm.state.name
        message.state_code = int(self.fsm.state)
        message.elapsed_sec = float(self._elapsed())
        message.remaining_sec = float(
            max(0.0, self.time_limit_sec - self._elapsed())
        )
        message.beans_confirmed = int(self.beans_confirmed)
        message.last_error = self.fsm.last_error
        self.state_pub.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = BeanTaskNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

