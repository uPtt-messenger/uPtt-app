import setuptools
import os

# Read metadata from __init__.py
about = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'src', 'uPtt', '__init__.py'), 'r', encoding='utf-8') as f:
    exec(f.read(), about)


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name=about['__name__'],
    version=about['__version__'],
    author=about['__author__'],
    author_email=about['__author_email__'],
    description=about['__description__'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=about['__url__'],
    license=about['__license__'],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    package_data={
        "uPtt.ui": ["assets/*"],
    },
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "uptt=uPtt.app:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
    ],
    python_requires=">=3.8",
)
