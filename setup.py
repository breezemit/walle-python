#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="walle",
    version="0.2.0",
    author="Walle Team",
    description="A GitLab-based release automation tool that generates release notes and changelogs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "python-gitlab>=3.15.0",
        "click>=8.0.0",
        "pydantic>=1.10.0",
        "pydantic-settings>=2.0.0",
        "python-dateutil>=2.8.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "walle=walle.cli.main:main",
        ],
    },
)