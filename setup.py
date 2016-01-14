#!/usr/bin/env python3

# Prepare a release:
#
#  - git pull --rebase
#  - run tests: tox
#  - update VERSION in setup.py, fatoptimizer/__init__.py and doc/conf.py
#  - set release date in the changelog of README.rst
#  - git commit -a
#  - git push
#
# Release a new version:
#
#  - git tag VERSION
#  - git push --tags
#  - python3 setup.py register sdist upload
#
# After the release:
#
#  - set version to n+1
#  - git commit
#  - git push

VERSION = '0.1'

# put most of the code inside main() to be able to import setup.py in
# test_fatoptimizer.py, to ensure that VERSION is the same than
# fatoptimizer.__version__.
def main():
    CLASSIFIERS = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: C',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]

    from distutils.core import setup

    with open('README.rst') as f:
        long_description = f.read().strip()

    options = {
        'name': 'fatoptimizer',
        'version': VERSION,
        'license': 'MIT license',
        'description': 'Static optimizer specializing functions with guards for Python 3.6',
        'long_description': long_description,
        'url': 'https://github.com/haypo/fatoptimizer',
        'author': 'Victor Stinner',
        'author_email': 'victor.stinner@gmail.com',
        'classifiers': CLASSIFIERS,
        'packages': ['fatoptimizer'],
    }
    setup(**options)

if __name__ == '__main__':
    main()
