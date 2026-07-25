"""
Master launch file — starts ALL competition nodes.

Usage:
  ros2 launch competition_bringup.launch.py
  ros2 launch competition_bringup.launch.py hand_port:=/dev/ttyUSB1
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace


def generate_launch_description():
    # ── Arguments ──
    hand_port = LaunchConfiguration('hand_port', default='/dev/ttyUSB0')
    hand_id = LaunchConfiguration('hand_id', default='1')
    scale_port = LaunchConfiguration('scale_port', default='/dev/ttyUSB1')
    camera_id = LaunchConfiguration('camera_id', default='0')
    mock_arm = LaunchConfiguration('mock_arm', default='true')

    args = [
        DeclareLaunchArgument('hand_port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('hand_id', default_value='1'),
        DeclareLaunchArgument('scale_port', default_value='/dev/ttyUSB1'),
        DeclareLaunchArgument('camera_id', default_value='0'),
        DeclareLaunchArgument('mock_arm', default_value='true',
                              description='Use mock arm for development'),
    ]

    # ── Nodes ──
    nodes = [
        # 1. Camera driver (RealSense or USB)
        # Node(
        #     package='realsense2_camera', executable='realsense2_camera_node',
        #     name='camera', namespace='camera',
        #     parameters=[{'enable_color': True, 'color_width': 1280, 'color_height': 720,
        #                  'color_fps': 30.0}],
        # ),

        # 2. Hand driver (RH56F2 over RS485)
        Node(
            package='rh56f2_driver', executable='rh56f2_driver_node',
            name='rh56f2_driver',
            parameters=[{
                'port': hand_port,
                'hand_id': hand_id,
                'baudrate': 115200,
                'update_rate': 50,
            }],
            output='screen',
        ),

        # 3. Vision perception node
        Node(
            package='competition_vision', executable='perception_node',
            name='perception_node',
            parameters=[{
                'camera_topic': '/camera/color/image_raw',
                'scale_port': scale_port,
                'scale_baudrate': 9600,
                'publish_debug': True,
            }],
            output='screen',
        ),

        # 4. Competition supervisor
        Node(
            package='competition_supervisor', executable='supervisor_node',
            name='competition_supervisor',
            parameters=[{
                'tasks': ['powder_weighing', 'bean_picking'],
                'match_timeout': 300.0,
            }],
            output='screen',
        ),

        # 5. Operator panel (curses UI)
        Node(
            package='operator_panel', executable='panel_node',
            name='operator_panel',
            output='screen',
            prefix='xterm -e',  # launch in separate terminal
        ),
    ]

    return LaunchDescription([
        *args,
        LogInfo(msg=['=== Competition System Starting ===']),
        LogInfo(msg=['Hand port: ', hand_port]),
        LogInfo(msg=['Scale port: ', scale_port]),
        LogInfo(msg=['Mock arm: ', mock_arm]),
        *nodes,
        LogInfo(msg=['=== All nodes launched ===']),
    ])
