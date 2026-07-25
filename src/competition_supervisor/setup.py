from setuptools import setup
setup(name='competition_supervisor', version='0.1.0', packages=['competition_supervisor'],
      data_files=[('share/competition_supervisor', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': [
          'supervisor = competition_supervisor.supervisor:main']})
