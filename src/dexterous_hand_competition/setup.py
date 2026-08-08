from glob import glob
from setuptools import find_packages, setup


package_name = 'dexterous_hand_competition'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Jinggong Zhiheng Team',
    maintainer_email='team@example.com',
    description='Autonomous tweezer bean-picking competition scaffold.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bean_scene_node = '
            'dexterous_hand_competition.vision.scene_node:main',
            'bean_task_node = '
            'dexterous_hand_competition.task.bean_task_node:main',
            'safety_monitor_node = '
            'dexterous_hand_competition.common.safety_monitor:main',
            'mock_scene_node = '
            'dexterous_hand_competition.tools.mock_scene_node:main',
            'powder_scene_node = '
            'dexterous_hand_competition.vision.powder_scene_node:main',
        ],
    },
)
