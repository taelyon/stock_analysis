@echo off
title stock_db update

:retry
ping -n 1 www.google.com > nul
if %errorlevel%==0 (
    echo Internet connection is available.
    rem 다음에 실행할 명령을 여기에 넣으세요. 예: start firefox.exe

    cd C:\myPackage\stock\Investar
    C:\Users\BOK\AppData\Local\Programs\Python\Python312\python DBUpdater_new.py
    cmd.exe

) else (
    echo Internet connection is not available. Waiting for 60 seconds before retrying...
    timeout /t 10
    goto retry
)
pause
