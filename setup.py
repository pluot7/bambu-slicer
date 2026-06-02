from setuptools import setup, find_packages

# Read long description from README
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="bambu-slicer",
    version="1.0.0",
    description="Precise filament weight extraction via BambuStudio CLI slicing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your@email.com",
    url="https://github.com/YOUR_USERNAME/bambu-slicer",
    packages=find_packages(),
    package_data={
        "bambu_slicer": ["py.typed"],
    },
    data_files=[("", ["bambu_template.3mf"])],
    install_requires=[],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "bambu-slicer=bambu_slicer.slicer:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Manufacturing",
        "Topic :: Scientific/Engineering :: 3D Printing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="bambu-studio 3d-printing slicer filament-weight gcode bambulab p1p",
)
