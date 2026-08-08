from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    bean_count = LaunchConfiguration('bean_count')
    time_limit = LaunchConfiguration('time_limit_sec')
    default_config = PathJoinSubstitution([
        FindPackageShare('dexterous_hand_competition'),
        'config',
        'bean_task.yaml',
    ])
    return LaunchDescription([
        DeclareLaunchArgument('bean_count', default_value='3'),
        DeclareLaunchArgument('time_limit_sec', default_value='30.0'),
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
            parameters=[{
                'bean_count': ParameterValue(bean_count, value_type=int),
            }],
        ),
        Node(
            package='dexterous_hand_competition',
            executable='bean_task_node',
            name='bean_task_node',
            output='screen',
            parameters=[{
                'config_file': default_config,
                'dry_run': True,
                'time_limit_sec': ParameterValue(time_limit, value_type=float),
                'target_count': ParameterValue(bean_count, value_type=int),
                'auto_grasp_tweezer': True,
                'auto_release_tweezer': True,
            }],
        ),
    ])
