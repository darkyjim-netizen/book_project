@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo Project Python environment is missing. Run: py -3.12 -m venv .venv
    popd
    exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000 %*
set "BOOKBOOK_BACKEND_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %BOOKBOOK_BACKEND_EXIT_CODE%
