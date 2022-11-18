#!/usr/bin/env python
from setuptools import setup, find_packages
setup(
    name='cgwebpy',
    version='1.0.1',
    author='Andrea Cattaneo',
    author_email='andrea.cattaneo@infoesse.it',
    description='cgroup manager for LAMP users',
    packages = find_packages(),
    install_requires=[
        'systemd-python', # optional
    ],
    entry_points={
        'console_scripts': [
            'cgwebpy = cgwebpy.main:main'
        ]
    }
)