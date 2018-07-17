import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='asyncio_bus_timetable',
    version="0.0.1",
    author="Tim Richardson",
    author_email="tim@tim-richardson.net",
    description="Simple, beginner aiohttp project fetching PTV bus times",
    long_description='long_description',
    long_description_content_type="text/markdown",
    url="https://github.com/timrichardson/asyncio_bus_timetable",
    packages=setuptools.find_packages(),
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)