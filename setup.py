#!/usr/bin/env python3

# Copyright (c) Juptyer Development Team.
# Distributed under the terms of the Modified BSD License.

#-----------------------------------------------------------------------------
# Minimal Python version sanity check (from IPython/Jupyterhub)
#-----------------------------------------------------------------------------
from __future__ import print_function

import os
import sys

v = sys.version_info
if v[:2] < (3,3):
    error = "ERROR: Jupyter Hub requires Python version 3.3 or above."
    print(error, file=sys.stderr)
    sys.exit(1)


if os.name in ('nt', 'dos'):
    error = "ERROR: Windows is not supported"
    print(error, file=sys.stderr)


from setuptools import setup

pjoin = os.path.join
here = os.path.abspath(os.path.dirname(__file__))

# Get the current package version.
version_ns = {}

from setuptools.command.bdist_egg import bdist_egg
class bdist_egg_disabled(bdist_egg):
    """Disabled version of bdist_egg
    Prevents setup.py install from performing setuptools' default easy_install,
    which it should never ever do.
    """
    def run(self):
        sys.exit("Aborting implicit building of eggs. Use `pip install .` to install from source.")

setup_args = dict(
    name                = 'remotesingularityspawner',
    packages            = ['remotesingularityspawner'],
    version             = "0.0.3",
    description         = """RemoteSingularitySpawner: A custom spawner for Jupyterhub in singularity container.""",
    long_description    = "",
    author              = "xinping fan",
    author_email        = "897488736@qq.com",
    url                 = "https://github.com/fanxinping/remotesingularityspawner",
    download_url        = "https://github.com/fanxinping/remotesingularityspawner/archive/v0.0.2.tar.gz",
    license             = "BSD",
    platforms           = "Linux, Mac OS X",
    keywords            = ['Interactive', 'Interpreter', 'Shell', 'Web'],
    classifiers         = [
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    install_requires = [
        'paramiko'],
    entry_points={
        'jupyterhub.spawners': [
            'remote-singularity-spawner = remotesingularityspawner:RemoteSingularitySpawner'
        ],
    },
    cmdclass = {
        'bdist_egg': bdist_egg if 'bdist_egg' in sys.argv else bdist_egg_disabled,
    }
)


def main():
    setup(**setup_args)

if __name__ == '__main__':
    main()
