# Architecture technique de SuperMenu

Ce document détaille l'architecture technique de SuperMenu, expliquant comment les différents composants interagissent entre eux et comment l'application est structurée.

## Vue d'ensemble

SuperMenu est développé en Python avec PySide6. L'application Windows est une
composition : le métier multiplateforme vit dans `shared/supermenu_core`, tandis
que `win32/src` porte uniquement l'application et les intégrations Windows.

```
SuperMenu/
├── shared/supermenu_core/      # Cœur commun, sans API native
│   ├── api/                    # OpenAI, Ollama, LM Studio
│   ├── audio/                  # Capture Qt, dictée en direct, modèles résidents
│   ├── config/                 # Modèles et schémas de prompts
│   ├── ui/                     # Widgets Qt composables
│   └── utils/                  # Validateurs purs
└── win32/
    ├── src/
    │   ├── main.py             # Composition de l'application
    │   ├── api/                # Adaptateur multimodal du client
    │   ├── audio/              # Moteurs vocaux Windows et worker Nemotron
    │   ├── config/             # Persistance Windows
    │   ├── ui/                 # UI Windows et capture
    │   └── utils/              # Hotkeys, cible et presse-papiers
    ├── requirements*.txt
    ├── SuperMenu.spec
    └── setup_supermenu.iss
```

Règle de dépendance : `win32/src` peut importer `supermenu_core`, mais le cœur
partagé ne peut importer ni `src`, ni Win32, ni AppKit. Un test architectural
analyse tous ses imports pour garantir cette frontière.

## Composants principaux

### 1. Point d'entrée et initialisation

- **run.py** : Script de lancement (ajoute la racine du projet au `sys.path` puis lance `src.main.SuperMenu`)
- **src/__main__.py** : Point d'entrée du package (lancement via `python -m src`)
- **src/main.py** : Classe `SuperMenu` qui initialise l'application, les raccourcis et les gestionnaires

En distribution, l'application est packagée en `SuperMenu.exe` (PyInstaller)
et installée via Inno Setup. En mode one-file, les ressources sont résolues
depuis le répertoire d'extraction temporaire fourni par PyInstaller
(`sys._MEIPASS`).

### 2. Interface utilisateur

- **main_window.py** : Fenêtre principale des paramètres
- **`shared/.../response_window.py`** : comportement et rendu communs de la
  fenêtre de réponse ; `src/ui/response_window.py` ajoute la présentation Win32
  et l'insertion native.
- **`shared/.../prompt_dialog.py`** : dialogue Qt commun (texte et image).
- **screen_capture.py** : Capture d'écran (plein écran ou sélection de zone) utilisée par le flux "capture"
- **`shared/.../theme_manager.py`** : thème sombre/clair/auto.

### 3. Utilitaires (src/utils/)

- **context_menu.py** : Gestion du menu contextuel
- **hotkey_manager.py** : Enregistrement et gestion des raccourcis clavier
- **logger.py** : Système de journalisation
- **`shared/.../loading_indicator.py`** : indicateur non bloquant commun.

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

### 4. Configuration

- **`src/config/settings.py`** : persistance via QSettings et stockage sécurisé.
- **`shared/supermenu_core/config`** : catalogue OpenAI, options fournisseur et
  validation/migration des collections de prompts.

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
2. `ContextMenuManager` crée directement le `DictationSession` de `shared/supermenu_core/audio`, également utilisé sur Mac
3. La fenêtre partagée `RecordingDialog` indique la préparation du moteur ; le microphone ne démarre qu'une fois celui-ci prêt
4. `Microphone` capture via Qt Multimedia et convertit le flux en PCM mono : 24 kHz pour OpenAI GPT Live Transcribe, 16 kHz pour Foundry Local Nemotron
5. Les fragments audio sont transmis au moteur au fur et à mesure, sans fichier audio sur disque ; les signaux actualisent la transcription en direct
6. **Terminer**, ou la limite de cinq minutes de capture, arrête le microphone et finalise la transcription. **Annuler** libère la capture et ignore tout résultat tardif
7. L'action **Dicter** transmet le texte final à une `ResponseWindow` autonome, puis laisse l'utilisateur choisir **Copier** ou **Écrire**
8. Un prompt vocal combine la transcription avec son instruction et respecte son option `insert_directly`
9. Le service partagé `ResidentSpeechService` conserve le moteur local entre les dictées, avec une session distincte pour chacune et un déchargement après cinq minutes d'inactivité par défaut. Le délai est configurable ; le microphone reste fermé entre les dictées

`src/audio` contient uniquement les moteurs propres à Windows. Les délais de
copie et de collage résident dans `src/utils/clipboard_config.py`. Le microphone
est identifié par son ID Qt (`speech_microphone`) ; l'ancien index PortAudio est
retiré du fichier de configuration sans toucher aux préférences vocales actuelles.

La bibliothèque et l’éditeur des prompts vocaux utilisent désormais
`shared/supermenu_core/config/voice_prompts.py` et
`shared/supermenu_core/ui/voice_prompt_editor.py`, également utilisés sur Mac.
Les six ordres d’assemblage et l’inclusion facultative de la sélection gardent
leur format existant. L’import/export JSON est commun aux deux plateformes,
tandis que la capture de sélection et l’insertion restent dans `win32/src`.

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
- Moteur vocal, ID Qt du microphone, langues, contexte et délai de déchargement du modèle local
- Thème de l'application

Emplacements par défaut :

- **Configuration** : `%USERPROFILE%\SuperMenu.ini`
- **Logs** : `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`

## Système de thèmes

Le système de thèmes commun est implémenté via
`shared/supermenu_core/ui/theme_manager.py` :

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

- **CI** (`ci.yml`) : tests Windows sur Python 3.10 et 3.12, tests macOS
  sur Python 3.12 et construction d'un DMG de test pour les pull requests et
  les pushs sur `main`; aucune publication.
- **Beta** (`beta-release.yml`) : exécution après la réussite du workflow CI d'un push sur `main`, ou lancement manuel depuis `main`; version `VERSION-beta.RUN_NUMBER`, tag roulant `beta`, prérelease GitHub, installateur `SuperMenu_Beta_Setup.exe` et checksums SHA-256.
- **Stable** (`stable-release.yml`) : déclenchement uniquement par un tag exact `vMAJOR.MINOR.PATCH`; le tag doit correspondre à `VERSION`, la release n'est jamais remplacée et devient la release GitHub `Latest`.

L'updater télécharge en priorité le manifeste `update-stable.json` de la dernière release Stable ou `update-beta.json` du tag roulant Beta. Ces fichiers sont servis comme des artefacts GitHub classiques et n'utilisent pas le quota de l'API REST. Le manifeste est strictement validé (schéma, canal, version, type de release et tag) avant de construire l'URL exacte de l'installateur. Si le manifeste est absent, illisible ou momentanément inaccessible, l'updater utilise l'API GitHub comme solution de secours : `/releases/latest` pour Stable et le tag `beta` pour Beta.

Le choix du canal est conservé dans `QSettings`; un build beta neuf sélectionne Beta, tandis qu'un build stable sélectionne Stable. En cas de quota GitHub épuisé pendant le secours API, l'utilisateur reçoit un message compréhensible avec l'heure de réinitialisation et un lien vers les releases, au lieu de l'erreur HTTP brute.

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

- Stockage sécurisé et séparé de la clé OpenAI et du jeton d'endpoint via
  `keyring`
- Aucun credential n'est loggé ni envoyé à un autre fournisseur
- Nettoyage des fichiers temporaires SuperMenu (captures) limité au dossier temporaire

---

Ce document est destiné aux développeurs souhaitant comprendre l'architecture de SuperMenu ou contribuer au projet. Pour des informations sur l'utilisation de l'application, consultez le [Guide d'utilisation](GUIDE_UTILISATION.md).

- `OpenAIClient` (`shared/supermenu_core/api/openai_client.py`) : gère les
  requêtes, le raisonnement, les retries et la normalisation des réponses. Le
  mince adaptateur `src/api/openai_client.py` active les images pour la capture
  Windows. La clé OpenAI n'est jamais transmise implicitement à un endpoint
  personnalisé, qui peut recevoir son propre jeton explicitement configuré.
- `openai_models.py` / `Settings` : le catalogue partagé porte la source unique
  des modèles autorisés ; `Settings` valide, migre et persiste les choix propres
  à Windows.
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
