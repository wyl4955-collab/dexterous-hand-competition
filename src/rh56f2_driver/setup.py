from setuptools import setup
setup(name='rh56f2_driver', version='0.1.0', packages=['rh56f2_driver'],
      data_files=[('share/rh56f2_driver', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': [
          'driver_node = rh56f2_driver.driver_node:main']})
