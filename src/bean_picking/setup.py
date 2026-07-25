from setuptools import setup
setup(name='bean_picking', version='0.1.0', packages=['bean_picking'],
      data_files=[('share/bean_picking', ['package.xml'])],
      install_requires=['setuptools'], zip_safe=True, entry_points={'console_scripts':[]})
