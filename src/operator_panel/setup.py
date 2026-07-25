from setuptools import setup
setup(name='operator_panel', version='0.1.0', packages=['operator_panel'],
      data_files=[('share/operator_panel', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts':[]})
