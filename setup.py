from setuptools import setup


setup(
    name="open-finance-br-cli",
    version="0.1.0",
    description="CLI Python para consumir APIs padronizadas do Open Finance Brasil.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=["openfinance"],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "openfinance=openfinance.cli:main",
        ],
    },
)
