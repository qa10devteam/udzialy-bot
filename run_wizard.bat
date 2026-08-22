@echo off
chcp 65001 >nul
echo Uruchamianie kreatora konfiguracji...
"%~dp0python\pythonw.exe" "%~dp0config_wizard.pyw"
if errorlevel 1 (
    echo.
    echo Proba z python.exe...
    "%~dp0python\python.exe" "%~dp0config_wizard.pyw"
)
