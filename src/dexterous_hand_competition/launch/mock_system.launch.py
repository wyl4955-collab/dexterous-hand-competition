from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='dexterous_hand_competition',
            executable='safety_monitor_node',
            name='safety_monitor',
            output='screen',
            parameters=[{'dry_run': True}],
        ),
        Node(
            package='dexterous_hand_competition',
            executable='mock_scene_node',
            name='mock_scene_node',
            output='screen',
        ),
        Node(
            package='dexterous_hand_competition',
            executable='bean_task_node',
            name='bean_task_node',
            output='screen',
            parameters=[{'dry_run': True, 'time_limit_sec': 30.0}],
        ),
    ])

