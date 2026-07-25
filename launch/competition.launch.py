"""
Master launch file — starts all competition nodes.
Usage: ros2 launch competition.launch.py
       ros2 launch competition.launch.py mock_arm:=true hand_port:=/dev/ttyUSB1
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    hand_port = LaunchConfiguration('hand_port', default='/dev/ttyUSB0')
    scale_port = LaunchConfiguration('scale_port', default='/dev/ttyUSB1')
    mock_arm = LaunchConfiguration('mock_arm', default='true')

    return LaunchDescription([
        DeclareLaunchArgument('hand_port', default_value='/dev/ttyUSB0'),
        DeclareLaunchArgument('scale_port', default_value='/dev/ttyUSB1'),
        DeclareLaunchArgument('mock_arm', default_value='true'),

        LogInfo(msg=['=== Starting Competition System ===']),

        # 1. Hand driver
        Node(
            package='rh56f2_driver', executable='driver_node',
            name='rh56f2_driver',
            parameters=[{'port': hand_port, 'hand_id': 1, 'baudrate': 115200, 'rate': 50}],
            output='screen',
        ),

        # 2. Perception (vision + scale)
        Node(
            package='competition_vision', executable='perception_node',
            name='perception_node',
            parameters=[{'scale_port': scale_port, 'fps': 20}],
            output='screen',
        ),

        # 3. Competition supervisor (creates FSMs internally)
        Node(
            package='competition_supervisor', executable='supervisor',
            name='competition_supervisor',
            parameters=[{'tasks': ['powder_weighing', 'bean_picking']}],
            output='screen',
        ),

        LogInfo(msg=['=== All nodes launched ===']),
        LogInfo(msg=['Call: ros2 service call /competition/start std_srvs/srv/Trigger "{}"']),
    ])
