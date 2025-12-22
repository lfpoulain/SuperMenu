# Architecture technique de SuperMenu

Ce document détaille l'architecture technique de SuperMenu, expliquant comment les différents composants interagissent entre eux et comment l'application est structurée.

## Vue d'ensemble

SuperMenu est développé en Python avec le framework PySide6 (Qt) pour l'interface graphique. L'application utilise une architecture modulaire pour faciliter la maintenance et l'évolution du code.

```
SuperMenu/
├── src/                    # Code source principal
│   ├── __main__.py         # Point d'entrée
│   ├── main.py             # Classe principale de l'application
│   ├── api/                # Intégration avec les API externes
│   ├── audio/              # Gestion de l'audio et reconnaissance vocale
│   ├── config/             # Configuration et paramètres
│   ├── ui/                 # Interface utilisateur
│   └── utils/              # Utilitaires divers
├── requirements.txt        # Dépendances Python (développement)
├── run.py                  # Script de lancement (développement)
├── bin/                    # Binaries nécessaires (ex: ffmpeg.exe)
├── resources/              # Ressources UI (icônes, etc.)
├── dist/                   # Sortie PyInstaller (SuperMenu.exe)
└── setup_supermenu.iss     # Script d'installation Inno Setup
```

## Composants principaux

### 1. Point d'entrée et initialisation

- **run.py** : Script de lancement (ajoute la racine du projet au `sys.path` puis lance `src.main.SuperMenu`)
- **src/__main__.py** : Point d'entrée du package (lancement via `python -m src`)
- **src/main.py** : Classe `SuperMenu` qui initialise l'application, les raccourcis et les gestionnaires

En distribution, l'application est packagée en `SuperMenu.exe` (PyInstaller) et installée via Inno Setup. Les chemins de ressources (`resources/`, `bin/`) sont résolus depuis le dossier de l'exécutable en mode packagé.

### 2. Interface utilisateur (src/ui/)

- **main_window.py** : Fenêtre principale des paramètres
- **response_window.py** : Fenêtre d'affichage des réponses de l'API
- **prompt_dialog.py** : Dialogue de prompt personnalisé (texte et image)
- **screen_capture.py** : Capture d'écran (plein écran ou sélection de zone) utilisée par le flux "capture"
- **theme_manager.py** : Application du thème (sombre/clair/auto) via `pyqtdarktheme`

### 3. Utilitaires (src/utils/)

- **context_menu.py** : Gestion du menu contextuel
- **hotkey_manager.py** : Enregistrement et gestion des raccourcis clavier
- **logger.py** : Système de journalisation
- **loading_indicator.py** : Indicateur de chargement non bloquant

### 4. Configuration (src/config/)

- **settings.py** : Gestion des paramètres de l'application (via QSettings)

## Flux de données

### Menu contextuel

1. L'utilisateur sélectionne du texte dans une application
2. L'utilisateur appuie sur le raccourci clavier (par défaut: Ctrl+²)
3. `HotkeyManager` détecte le raccourci et déclenche `show_context_menu()`
4. `ContextMenuManager` récupère le texte sélectionné via diverses méthodes
5. `ContextMenuManager` affiche le menu contextuel avec les prompts configurés
6. L'utilisateur sélectionne une action
7. Le texte et le prompt sont envoyés à l'API OpenAI via `OpenAIClient`
8. La réponse est affichée dans `ResponseWindow` ou insérée directement

#### Fermeture automatique des menus (robuste)

Les menus (`QMenu.exec_`) sont affichés depuis un raccourci global. Les événements Qt de type "deactivate" peuvent être non fiables dans ce contexte. La fermeture automatique est donc assurée par un watchdog périodique côté `ContextMenuManager` :

- **Timer** : `QTimer` (intervalle ~200ms)
- **Suivi de focus Windows** : lecture du PID de la fenêtre au premier plan (`GetForegroundWindow` / `GetWindowThreadProcessId`)
- **PID owner** : PID capturé au moment de l'ouverture (application "propriétaire")
- **Période de grâce** : ~250ms après l'ouverture pour éviter une fermeture immédiate due aux changements de focus induits par le hotkey
- **Clic global** : détection du clic gauche via `GetAsyncKeyState(VK_LBUTTON)` et fermeture si clic extérieur au `menu.geometry()`

Le menu est fermé si :

- le PID au premier plan n'est ni celui de l'application propriétaire, ni celui de SuperMenu
- un clic gauche survient en dehors de la géométrie du menu (après la période de grâce)

### Reconnaissance vocale

1. L'utilisateur appuie sur le raccourci vocal (par défaut: Ctrl+Alt+²)
2. `VoiceRecognition` enregistre l'audio via le microphone
3. L'audio est transcrit en texte
4. Le texte transcrit est combiné avec le prompt vocal sélectionné
5. La requête est envoyée à l'API OpenAI
6. La réponse est affichée ou insérée selon la configuration

### Capture d'écran

1. L'utilisateur appuie sur le raccourci de capture (par défaut: Ctrl+Alt+&)
2. `ContextMenuManager` détermine le mode de capture via `Settings` :
   - `fullscreen`
   - `region`
   - `ask` (demande à chaque capture)
3. Si le mode est `ask`, un `QMenu` (même style que les autres menus) est affiché au curseur pour choisir le type de capture
4. `ContextMenuManager` déclenche la capture via `src/ui/screen_capture.py`
3. L'image est convertie en **data URL** (`data:image/...;base64,...`) puis le fichier temporaire est supprimé
4. Le prompt personnalisé est demandé via `PromptDialog`
5. La requête est envoyée à l'API (texte + image)
6. La réponse est affichée dans `ResponseWindow` (et le retry réutilise la data URL)

## Gestion des paramètres

La classe `Settings` dans `src/config/settings.py` gère tous les paramètres de l'application :

- Stockage des paramètres dans un fichier INI via `QSettings`
- Stockage sécurisé de la clé API via `keyring`
- Gestion des prompts textuels et vocaux
- Configuration des raccourcis clavier
- Paramètres du microphone
- Thème de l'application

Emplacements par défaut :

- **Configuration** : `%USERPROFILE%\SuperMenu.ini`
- **Logs** : `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`

## Système de thèmes

Le système de thèmes est implémenté via `src/ui/theme_manager.py` :

1. Thèmes disponibles : `dark`, `light`, `auto`
2. Application via `ThemeManager.apply_theme(app, theme)`
3. Stockage du thème sélectionné dans les paramètres (`Settings`)

## Extensibilité

L'architecture de SuperMenu a été conçue pour faciliter l'ajout de nouvelles fonctionnalités :

- **Nouveaux prompts** : Facilement ajoutables via l'interface utilisateur
- **Nouveaux thèmes** : Ajout possible en étendant `ThemeManager` (ou en ajoutant un nouveau gestionnaire)
- **Nouveaux modèles d'IA** : Support de différents modèles OpenAI, extensible à d'autres fournisseurs
- **Nouvelles actions** : Structure modulaire permettant l'ajout de nouvelles actions au menu contextuel

## Considérations techniques

### Gestion des erreurs

- Utilisation de blocs try/except pour capturer les erreurs
- Journalisation des erreurs via le module `logging`
- Messages d'erreur utilisateur via `QMessageBox`

### Performance

- Utilisation de `QTimer` pour les opérations asynchrones
- Gestion efficace des ressources (fermeture des connexions, libération de la mémoire)
- Optimisation des appels API (minimisation des requêtes)

### Sécurité

- Stockage sécurisé des clés API via `keyring`
- La clé API n'est pas loggée
- Nettoyage des fichiers temporaires SuperMenu (captures) limité au dossier temporaire

---

Ce document est destiné aux développeurs souhaitant comprendre l'architecture de SuperMenu ou contribuer au projet. Pour des informations sur l'utilisation de l'application, consultez le [Guide d'utilisation](GUIDE_UTILISATION.md).

- `OpenAIClient` (`src/api/openai_client.py`) : Gère toutes les communications avec l'API OpenAI. Il est responsable de la construction des requêtes, de l'envoi, et du traitement initial des réponses. Il est maintenant configuré dynamiquement avec le modèle sélectionné par l'utilisateur via `set_model()`.
- `Settings` (`src/config/settings.py`) : Charge et sauvegarde les configurations de l'utilisateur, y compris la clé API, le modèle OpenAI sélectionné, les prompts, les raccourcis, et le thème.
- `ContextMenuManager` (`src/utils/context_menu.py`) : Orchestre l'affichage du menu contextuel, la récupération du texte sélectionné, l'appel à `OpenAIClient` et l'affichage de la `ResponseWindow`. Il initialise et met à jour la configuration de `OpenAIClient` (clé API et modèle) en fonction des `Settings`.

### Flux de données (Exemple : Action sur Texte Sélectionné)

1.  L'utilisateur sélectionne du texte dans une application et appuie sur le raccourci clavier configuré.
2.  `HotkeyManager` détecte le raccourci et émet un signal.
3.  `SuperMenu` (dans `main.py`) reçoit ce signal et demande à `ContextMenuManager` d'afficher le menu.
4.  `ContextMenuManager` tente de récupérer le texte sélectionné.
5.  L'utilisateur choisit une action (un prompt) dans le menu contextuel.
6.  `ContextMenuManager` récupère le prompt correspondant depuis `Settings`.
7.  `ContextMenuManager` s'assure que son instance de `OpenAIClient` est configurée avec la clé API et le modèle actuels (provenant de `Settings`).
8.  `OpenAIClient` envoie la requête (texte sélectionné + prompt) à l'API OpenAI en utilisant le modèle configuré.
9.  `OpenAIClient` reçoit la réponse et émet un signal.
10. `ContextMenuManager` reçoit la réponse et l'affiche dans `ResponseWindow`.

### Flux de données (Exemple : Changement de Modèle OpenAI)

 1.  L'utilisateur ouvre la fenêtre `MainWindow` et va dans l'onglet "Modèles".
 2.  L'utilisateur sélectionne un nouveau modèle (ou active un endpoint personnalisé) puis enregistre.
 3.  `MainWindow` appelle `settings.set_model()` pour sauvegarder le nouveau modèle.
 4.  `MainWindow` appelle `context_menu_manager.update_client_config()`.
 5.  `ContextMenuManager` appelle `api_client.set_model()` et `api_client.set_api_key()` pour mettre à jour l'instance `OpenAIClient` avec les nouvelles valeurs des `Settings`.
 6.  Les requêtes suivantes utiliseront le nouveau modèle.
