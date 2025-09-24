import setuptools
import os

# Read metadata from __init__.py
about = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'src', 'uPttTerm', '__init__.py'), 'r', encoding='utf-8') as f:
    exec(f.read(), about)


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name=about['__name__'],
    version=about['__version__'],
    author=about['__author__'],
    author_email="pttcodingman@gmail.com",
    description="A TUI application for real-time chat on PTT via its built-in private message system.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/uPtt-messenger/uPttTerm",  # Replace with your repository URL
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "uptt=uPttTerm.app:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License", # You can change this to your license
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