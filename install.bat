@echo off
echo Installation de SuperMenu...

REM Vérifier si Python est installé
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python n'est pas installé. Veuillez installer Python 3.8 ou supérieur.
    exit /b 1
)

REM Créer l'environnement virtuel
echo Création de l'environnement virtuel...
python -m venv venv

REM Activer l'environnement virtuel et installer les dépendances
echo Installation des dépendances...
call venv\Scripts\activate
pip install -r requirements.txt

echo Installation terminée avec succès!
echo Pour lancer l'application, utilisez start_supermenu.bat
pause
