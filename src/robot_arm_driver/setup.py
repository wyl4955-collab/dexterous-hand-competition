from setuptools import setup

package_name = 'robot_arm_driver'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/arm_bringup.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
)
