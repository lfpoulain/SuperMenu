# SuperMenu

SuperMenu est une application Windows (Python + PySide6) qui affiche un menu contextuel piloté par raccourci clavier pour exécuter rapidement des actions IA sur :

- du texte sélectionné
- de la dictée (reconnaissance vocale)
- une capture d'écran

Liens :

- Dépôt : https://github.com/lfpoulain/SuperMenu
- Releases : https://github.com/lfpoulain/SuperMenu/releases

## Fonctionnalités

- Menu contextuel sur texte sélectionné (prompts configurables)
- Fermeture automatique des menus contextuels (clic extérieur / changement de fenêtre)
- Prompts vocaux (dictée + prompt + option d'inclure le texte sélectionné)
- Capture d'écran + envoi à l'IA (avec prompt)
- Insertion directe dans l'application active (optionnelle)
- Choix du modèle :
  - OpenAI (`gpt-5.2`, `gpt-5.1`,`gpt-4.1-mini`)
  - Endpoint compatible OpenAI (ex : Ollama) + modèle libre
- Raccourcis configurables (menu, voix, capture)
- Thèmes (via `ThemeManager`) : sombre, clair, automatique
- Stockage sécurisé de la clé API via `keyring` (la clé n'est pas écrite dans les fichiers de configuration)

## Installation (recommandée)

1. Télécharge l'installateur depuis la page des releases (canal nightly) :
   - https://github.com/lfpoulain/SuperMenu/releases/tag/nightly
2. Lance `SuperMenu_Setup.exe`.
3. Lance SuperMenu depuis le menu Démarrer.

## Mise à jour

Deux options :

- **Depuis l'application** : onglet "À propos" -> "Vérifier les mises à jour" (télécharge et lance l'installateur).
- **Manuellement** : retélécharger `SuperMenu_Setup.exe` (nightly) et le relancer par-dessus l'installation existante.

## Désinstallation

Lors de la désinstallation, SuperMenu est fermé automatiquement si nécessaire.
Une question te propose de supprimer aussi les données utilisateur (logs et configuration).

## Configuration & logs

- **Configuration** : `%USERPROFILE%\SuperMenu.ini`
- **Logs** : `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`

## Utilisation rapide

### Raccourcis clavier par défaut

Ils sont configurables dans l'onglet "Réglages".

- **Ctrl+²** : menu contextuel sur texte sélectionné
- **Ctrl+Alt+²** : prompt vocal
- **Ctrl+Shift+²** : capture d'écran

### Menu contextuel

1. Sélectionne du texte
2. Appuie sur le raccourci
3. Choisis l'action

Le menu se ferme automatiquement si tu cliques en dehors ou si tu changes de fenêtre.

## Développement

Prérequis :

- Windows 10/11
- Python 3.10+ recommandé

Installation :

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Build local (PyInstaller) :

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean SuperMenu.spec
```

Build local (Inno Setup) :

- Compile `setup_supermenu.iss` avec Inno Setup (`iscc`).

## Documentation

- `docs/GUIDE_UTILISATION.md`
- `docs/ARCHITECTURE.md`

## Licence

2025 LFPoulain - Tous droits réservés
