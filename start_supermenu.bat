@echo off
echo Démarrage de SuperMenu...

REM Chemin complet vers l'environnement virtuel
set VENV_DIR=%~dp0venv
set PYTHON=%VENV_DIR%\Scripts\python.exe

REM Vérifier si l'environnement virtuel existe
if not exist "%VENV_DIR%" (
    echo L'environnement virtuel n'existe pas. Veuillez exécuter install.bat d'abord.
    pause
    exit /b 1
)

REM Créer un script VBS pour lancer l'application en arrière-plan
echo Set WshShell = CreateObject("WScript.Shell") > "%TEMP%\start_supermenu_hidden.vbs"
echo WshShell.CurrentDirectory = "%~dp0" >> "%TEMP%\start_supermenu_hidden.vbs"
echo WshShell.Run "cmd /c call ""%VENV_DIR%\Scripts\activate.bat"" && ""%PYTHON%"" ""%~dp0run.py""", 0, False >> "%TEMP%\start_supermenu_hidden.vbs"

REM Exécuter le script VBS
start "" "%TEMP%\start_supermenu_hidden.vbs"

echo SuperMenu a été lancé en arrière-plan.
echo Vous pouvez fermer cette fenêtre.
