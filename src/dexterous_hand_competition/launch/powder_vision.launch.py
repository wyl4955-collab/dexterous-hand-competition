from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    default_config = PathJoinSubstitution(
        [FindPackageShare('dexterous_hand_competition'), 'config', 'powder_vision.yaml']
    )
    return LaunchDescription([
        DeclareLaunchArgument('config_path', default_value=default_config),
        Node(
            package='dexterous_hand_competition',
            executable='powder_scene_node',
            name='powder_scene_node',
            output='screen',
            parameters=[{'config_path': LaunchConfiguration('config_path')}],
        ),
    ])
