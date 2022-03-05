"""Python package setup."""
import setuptools

with open("README.md", "r", encoding="UTF-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="asyncio-paho",
    version="0.1.0",
    author="Tore Amundsen",
    author_email="tore@amundsen.org",
    description="A Paho MQTT client supporting asyncio loop without additional setup.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/toreamun/asyncio-paho",
    packages=["asyncio-paho"],
    package_data={"asyncio-paho": ["py.typed"]},
    keywords=[
        "paho",
        "mqtt",
        "asyncio",
    ],
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    install_requires=["paho-mqtt~=1.6"],
)
