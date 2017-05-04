"""
flagpole
=====
Flagpole is a Flag arg parser to build out a dictionary with optional keys.
:copyright: (c) 2017 by Netflix, see AUTHORS for more
:license: Apache, see LICENSE for more details.
"""
from setuptools import setup
import os

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__)))

install_requires = []

tests_require = [
    'pytest',
    'mock'
]

docs_require = []

dev_require = []

setup(
    name='flagpole',
    version='1.0.1',
    author='Patrick Kelley',
    author_email='pkelley@netflix.com',
    url='https://github.com/monkeysecurity/flagpole',
    description='Flagpole is a Flag arg parser to build out a dictionary with optional keys.',
    long_description=open(os.path.join(ROOT, 'README.md')).read(),
    packages=['flagpole'],
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    extras_require={
        'tests': tests_require,
        'docs': docs_require,
        'dev': dev_require
    }
)