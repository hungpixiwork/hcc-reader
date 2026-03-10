from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="hcc-reader",
    version="1.0.0",
    author="Pham Phu Nguyen Hung",
    author_email="hungphamphunguyen@gmail.com",
    description="Read MetaTrader 5 .hcc/.hc history files without MT5 terminal",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hungpixi/hcc-reader",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pandas>=1.5.0",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "hcc-reader=hcc_reader.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
)
