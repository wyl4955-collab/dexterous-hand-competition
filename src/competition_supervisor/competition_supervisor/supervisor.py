#!/usr/bin/env python3
"""
Competition Supervisor — the ONLY high-level node.
Creates Primitives, powder/bean FSMs internally. All share this node's ROS2 handle.
"""
import time
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from competition_interfaces.msg import HandCommand
from manipulation_skills.primitives import Primitives
from powder_weighing.powder_fsm import PowderWeighingFSM
from bean_picking.bean_fsm import BeanPickingFSM


class Supervisor(Node):
    def __init__(self):
        super().__init__('competition_supervisor')
        self.declare_parameter('tasks', ['powder_weighing', 'bean_picking'])
        self.declare_parameter('match_timeout', 300.0)

        # Create primitives using this node's publisher
        self.p = Primitives(self)

        # Create FSMs (plain objects, they subscribe via this node)
        self.powder = PowderWeighingFSM(self, self.p)
        self.bean = BeanPickingFSM(self, self.p)

        # State
        self.running = False
        self.estop = False
        self.estop_pub = self.create_publisher(HandCommand, '/hand/command', 10)

        # Services
        self.create_service(Trigger, '/competition/start', self._start)
        self.create_service(Trigger, '/competition/stop', self._stop)
        self.create_service(Trigger, '/competition/estop', self._estop)

        self.get_logger().info('Supervisor ready — call /competition/start to begin')

    def _start(self, req, resp):
        if self.running:
            resp.success = False; resp.message = 'Already running'; return resp

        # Pre-match: calibrate force sensors
        self.get_logger().info('Calibrating force sensors (ensure hand is empty!)')
        self.p.release()
        time.sleep(1)

        self.running = True; self.estop = False
        t0 = time.time(); score = 0
        tasks = self.get_parameter('tasks').value

        self.get_logger().info(f'🏁 MATCH STARTED: {tasks}')

        for name in tasks:
            if self.estop: break
            elapsed = time.time()-t0
            if elapsed > self.get_parameter('match_timeout').value: break

            self.get_logger().info(f'▶ Task: {name}')
            try:
                if name == 'powder_weighing':
                    r = self.powder.execute(target=5.00, tolerance=0.05, timeout=120)
                    score += 100 if r['success'] else 0
                elif name == 'bean_picking':
                    r = self.bean.execute(count=3, timeout=120)
                    done = r.get('beans_done', 0)
                    score += int(done/3*100) if done > 0 else 0
            except Exception as e:
                self.get_logger().error(f'Task {name} error: {e}')

        self.running = False
        elapsed = time.time()-t0
        self.get_logger().info(f'🏁 MATCH DONE: {score}pts in {elapsed:.1f}s')
        resp.success = True
        resp.message = f'Score:{score} Time:{elapsed:.1f}s'
        return resp

    def _stop(self, req, resp):
        self.running = False
        resp.success = True; resp.message = 'Stopped'; return resp

    def _estop(self, req, resp):
        self.estop = True; self.running = False
        cmd = HandCommand()
        cmd.force_thresholds = [10]*6; cmd.speeds = [4000]*6
        self.estop_pub.publish(cmd)
        resp.success = True; resp.message = 'ESTOP'; return resp


def main():
    rclpy.init()
    rclpy.spin(Supervisor())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
