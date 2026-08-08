from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    config_file = LaunchConfiguration('config_file')
    dry_run = LaunchConfiguration('dry_run')
    time_limit = LaunchConfiguration('time_limit_sec')
    target_count = LaunchConfiguration('target_count')
    auto_grasp = LaunchConfiguration('auto_grasp_tweezer')
    auto_release = LaunchConfiguration('auto_release_tweezer')
    default_config = PathJoinSubstitution([
        FindPackageShare('dexterous_hand_competition'),
        'config',
        'bean_task.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('config_file', default_value=default_config),
        DeclareLaunchArgument('dry_run', default_value='true'),
        DeclareLaunchArgument('time_limit_sec', default_value='300.0'),
        DeclareLaunchArgument('target_count', default_value='0'),
        DeclareLaunchArgument('auto_grasp_tweezer', default_value='false'),
        DeclareLaunchArgument('auto_release_tweezer', default_value='false'),
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
                'config_file': config_file,
                'dry_run': ParameterValue(dry_run, value_type=bool),
                'time_limit_sec': ParameterValue(time_limit, value_type=float),
                'target_count': ParameterValue(target_count, value_type=int),
                'auto_grasp_tweezer': ParameterValue(
                    auto_grasp, value_type=bool
                ),
                'auto_release_tweezer': ParameterValue(
                    auto_release, value_type=bool
                ),
            }],
        ),
    ])
