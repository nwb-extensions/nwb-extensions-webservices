#!/usr/bin/env python
from setuptools import setup, find_packages


def main():
    skw = dict(
        name='nwb-extensions-webservices',
        version='1.0',
        author='Ryan Ly',
        author_email='nwbextensions@gmail.com',
        url='https://github.com/nwb-extensions/nwb-extensions-webservices',
        # entry_points=dict(console_scripts=[
        #                    'conda_forge_webservices.linting = conda_forge_webservices.linting:main']),
        packages=find_packages(),
        include_package_data=True,
        )
    setup(**skw)


if __name__ == '__main__':
    main()
