from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    dry_run = LaunchConfiguration('dry_run')
    time_limit = LaunchConfiguration('time_limit_sec')
    return LaunchDescription([
        DeclareLaunchArgument('dry_run', default_value='true'),
        DeclareLaunchArgument('time_limit_sec', default_value='300.0'),
        Node(
            package='dexterous_hand_competition',
            executable='safety_monitor_node',
            name='safety_monitor',
            output='screen',
            parameters=[{
                'dry_run': ParameterValue(dry_run, value_type=bool),
            }],
        ),
        Node(
            package='dexterous_hand_competition',
            executable='bean_task_node',
            name='bean_task_node',
            output='screen',
            parameters=[{
                'dry_run': ParameterValue(dry_run, value_type=bool),
                'time_limit_sec': ParameterValue(time_limit, value_type=float),
            }],
        ),
    ])

