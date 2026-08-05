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
├── requirements.txt        # Dépendances Python d'exécution
├── requirements-dev.txt    # Tests, qualité et construction
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

En distribution, l'application est packagée en `SuperMenu.exe` (PyInstaller) et installée via Inno Setup. En mode one-file, les chemins de ressources (`resources/`, `bin/`) sont résolus depuis le répertoire d'extraction temporaire fourni par PyInstaller (`sys._MEIPASS`).

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

#### Hotkeys (Windows)

Le module `src/utils/hotkey_manager.py` implémente les raccourcis globaux via l'API Win32 :

- Enregistrement/désenregistrement des hotkeys avec `RegisterHotKey` / `UnregisterHotKey`
- Réception des événements via `WM_HOTKEY`
- Intégration Qt via un `QAbstractNativeEventFilter` installé sur l'application (`QCoreApplication.installNativeEventFilter`)

Contraintes :

- Les modificateurs autorisés sont `Ctrl`, `Alt`, `Shift`
- La touche `Win` n'est pas autorisée
- Les raccourcis à une seule touche ne sont pas supportés
- Les touches de fonction Windows `F1` à `F24` sont traduites directement vers leurs codes virtuels Win32

Le dialogue d'enregistrement d'un raccourci (`HotkeyRecorderDialog`) capture les touches via les événements Qt (pas de hook clavier global).

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

### Raccourcis directs par prompt

Chaque prompt textuel peut porter un champ `hotkey`. `PromptHotkeyManager` enregistre dynamiquement toutes les combinaisons après les raccourcis principaux de l'application et émet l'identifiant du prompt concerné. `ContextMenuManager` capture alors la cible et la sélection, puis envoie la requête sans ouvrir de menu. Le champ `insert_directly` du prompt reste l'unique source de vérité : s'il est actif, `TextInserter` remplace la sélection uniquement si la fenêtre cible est toujours valide et un `SimpleLoadingIndicator` non activable signale l'envoi et la fin ; sinon, `ResponseWindow` est préparée et affichée normalement.

Les doublons entre prompts sont refusés par `Settings`. Les conflits Win32 sont détectés lors du réenregistrement et la modification du prompt est annulée sans désactiver ses autres réglages.

#### Affichage et fermeture automatique des menus

Les menus utilisent le `QMenu` natif sans drapeaux translucides ou sans bordure ajoutés. Ils sont ouverts avec `QMenu.exec()` depuis un raccourci global. Les événements Qt de type "deactivate" pouvant être non fiables dans ce contexte, la fermeture automatique est complétée par un watchdog périodique côté `ContextMenuManager` :

- **Timer** : `QTimer` (intervalle ~200ms)
- **Suivi de focus Windows** : lecture du PID de la fenêtre au premier plan (`GetForegroundWindow` / `GetWindowThreadProcessId`)
- **PID owner** : PID capturé au moment de l'ouverture (application "propriétaire")
- **Période de grâce** : ~250ms après l'ouverture pour éviter une fermeture immédiate due aux changements de focus induits par le hotkey
- **Clic global** : détection du clic gauche via `GetAsyncKeyState(VK_LBUTTON)` et fermeture si clic extérieur au `menu.geometry()`

Le menu est fermé si :

- le PID au premier plan n'est ni celui de l'application propriétaire, ni celui de SuperMenu
- un clic gauche survient en dehors de la géométrie du menu (après la période de grâce)

La fenêtre de résultat n'expose plus plusieurs moteurs expérimentaux. `ResponseWindow.present()` affiche d'abord la fenêtre avec Qt, puis tente un renforcement Win32 (`ShowWindow`, `SetWindowPos`, `BringWindowToTop`, `SetForegroundWindow`). Une erreur Win32 reste non bloquante puisque l'affichage Qt a déjà eu lieu.

### Reconnaissance vocale

1. L'utilisateur appuie sur le raccourci vocal (par défaut: Ctrl+Alt+²)
2. `VoiceRecognition` affiche `RecordingDialog`, qui expose la durée, la limite, l'annulation et les états de traitement
3. `AudioRecorder` capture en mono et produit un MP4/Opus, ou un WAV si FFmpeg est indisponible
4. `Transcriber` vérifie le format, la taille maximale de 25 Mo et appelle `/v1/audio/transcriptions` avec `gpt-transcribe`
5. Les champs OpenAI actuels sont utilisés : `languages`, `keywords` et `prompt`; la réponse JSON est lue via son champ `text`
6. L'encodage, le réseau et le nettoyage restent hors du thread Qt; des signaux mettent l'interface à jour
7. L'action **Écrire à la voix** transmet la transcription à une `ResponseWindow` autonome, sans ancienne requête réessayable, puis laisse l'utilisateur choisir **Copier** ou **Écrire**
8. Un prompt vocal combine la transcription avec son instruction et respecte son option `insert_directly`
9. Les fichiers audio temporaires et les ressources PyAudio sont nettoyés dans tous les chemins de sortie

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
- Paramètres du microphone et indices GPT Transcribe
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

## CI, versions et canaux de publication

Le fichier `VERSION` contient la prochaine version stable sous la forme `MAJOR.MINOR.PATCH`. Les workflows injectent la version et le canal dans `src/config/build_info.py` avant le packaging :

- **CI** (`ci.yml`) : tests sur Python 3.10 et 3.12 pour les pull requests et les pushs sur `main`; aucune publication.
- **Beta** (`beta-release.yml`) : exécution après la réussite du workflow CI d'un push sur `main`, ou lancement manuel depuis `main`; version `VERSION-beta.RUN_NUMBER`, tag roulant `beta`, prérelease GitHub, installateur `SuperMenu_Beta_Setup.exe` et checksums SHA-256.
- **Stable** (`stable-release.yml`) : déclenchement uniquement par un tag exact `vMAJOR.MINOR.PATCH`; le tag doit correspondre à `VERSION`, la release n'est jamais remplacée et devient la release GitHub `Latest`.

L'updater interroge `/releases/latest` pour Stable, ce qui exclut les préversions, et le tag `beta` pour Beta. Il vérifie également que la release beta est bien marquée comme prérelease et attend un nom d'installateur différent par canal. Le choix est conservé dans `QSettings`; un build beta neuf sélectionne Beta, tandis qu'un build stable sélectionne Stable.

Lors d'une publication Stable, le tag technique historique `nightly` reçoit temporairement les artefacts Stable sous leurs anciens noms afin que les installations existantes migrent vers le nouvel updater et sélectionnent Stable. La Beta ne modifie jamais ce tag. Il ne représente plus un canal et n'est plus proposé dans l'interface.

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

- `OpenAIClient` (`src/api/openai_client.py`) : Gère les requêtes mono-tour, leur envoi et le traitement initial des réponses. OpenAI utilise Chat Completions avec les capacités déclarées du modèle. LM Studio utilise prioritairement `/api/v1/chat`, lit `/api/v1/models` pour traduire le raisonnement selon le modèle et retombe sur `/v1/chat/completions` si l'API native n'est pas disponible. Ollama lit `/api/show`, utilise des booléens pour les modèles hybrides et les niveaux documentés pour GPT‑OSS. Les sorties `message`, `reasoning` et `thinking` sont normalisées sans perdre une réponse placée dans le mauvais canal par le template du modèle.
- `openai_models.py` / `Settings` (`src/config/`) : Le module pur `openai_models.py` porte la source unique des modèles OpenAI autorisés, de leurs efforts et de leurs valeurs par défaut, sans effet de bord Qt ou journalisation. `Settings` gère uniquement leur validation, leur migration et leur persistance; les efforts OpenAI et endpoint local sont enregistrés séparément.
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
 2.  L'utilisateur sélectionne un nouveau modèle et son effort de raisonnement (ou active un endpoint personnalisé) puis enregistre.
 3.  `MainWindow` sauvegarde le modèle et les efforts OpenAI/local dans des réglages distincts. `Settings` valide le choix contre la matrice de capacités et migre les anciens identifiants par rôle.
 4.  `MainWindow` appelle `context_menu_manager.update_client_config()`.
 5.  `ContextMenuManager` appelle `api_client.set_model()` et `api_client.set_api_key()` pour mettre à jour l'instance `OpenAIClient` avec les nouvelles valeurs des `Settings`.
 6.  Les requêtes suivantes utiliseront le nouveau modèle.
