from setuptools import setup
setup(name='competition_vision', version='0.1.0', packages=['competition_vision'],
      data_files=[('share/competition_vision', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': [
          'perception_node = competition_vision.perception_node:main']})
