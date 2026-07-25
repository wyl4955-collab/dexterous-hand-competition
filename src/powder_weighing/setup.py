from setuptools import setup
setup(name='powder_weighing', version='0.1.0', packages=['powder_weighing'],
      data_files=[('share/powder_weighing', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': ['powder_fsm = powder_weighing.powder_fsm:main']})
