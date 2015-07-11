#!/usr/bin/env python
# vim: fileencoding=utf-8 tw=100 expandtab ts=4 sw=4 :
#
# (c) 2015 ActivKonnect

import os
import codecs
from distutils.core import setup


with codecs.open(os.path.join(os.path.dirname(__file__), 'README.rst'), 'r') as readme:
    README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='castor',
    version='0.1.0',
    scripts=['bin/castor'],
    packages=['castor'],
    package_dir={'': 'src'},
    include_package_data=True,
    license='WTFPL',
    description='Assemble Git repos into a deployable tree of code.',
    long_description=README,
    url='https://github.com/ActivKonnect/castor',
    author='Rémy Sanchez',
    author_email='remy.sanchez@activkonnect.com',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: Other/Proprietary License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ]
)
