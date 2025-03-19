from setuptools import setup, find_packages

setup(
    name="bsc_token_sniper",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "web3>=5.31.1",
        "python-dotenv>=0.20.0",
        "requests>=2.28.0",
        "pandas>=1.4.2",
    ],
    entry_points={
        "console_scripts": [
            "bsc-sniper=main:main",
        ],
    },
    author="4lphA",
    author_email="danci.nelu@gmail.com",
    description="A modular and secure token sniper for Binance Smart Chain",
    keywords="blockchain, crypto, binance, smart chain, trading, bot",
    url="https://github.com/4lphA2023/BSC_Sniping",
    classifiers=[
        "Development Status :: 3 - 4lphA",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.7",
)