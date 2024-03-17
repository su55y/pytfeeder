#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name="pytfeeder",
    author="su55y",
    version="1.1",
    url="https://github.com/su55y/pytfeeder",
    description="---",
    long_description="---",
    packages=find_packages(".", exclude=["tests", "tests.*", "examples"]),
    install_requires=[],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3 :: Only",
    ],
    entry_points={
        "console_scripts": [
            "pytfeeder = pytfeeder.entry_points.run_pytfeeder:run",
            "pytfeeder-rofi = pytfeeder.entry_points.run_pytfeeder_rofi:run",
        ]
    },
)
