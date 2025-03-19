@echo off
echo Installing BSC Token Sniper...

:: Create virtual environment
echo Creating Python virtual environment...
python -m venv venv

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

:: Install package
echo Installing BSC Token Sniper package...
pip install -e .

:: Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit the .env file with your own settings!
)

echo Installation complete!
echo Usage: python main.py --help
pause