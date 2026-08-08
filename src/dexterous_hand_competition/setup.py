from glob import glob
from setuptools import find_packages, setup


package_name = 'dexterous_hand_competition'


setup(
    name=package_name,
    version='0.2.0',
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
    description='Safety-first autonomous tweezer bean-picking task engine.',
    license='Apache-2.0',
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
        ],
    },
)
