# Architecture technique de SuperMenu pour Windows

Ce document décrit l’organisation de l’application Windows, ses frontières
avec le cœur partagé, les flux principaux et la chaîne de distribution. Il
s’adresse aux contributeurs ; l’utilisation est décrite dans le
[guide d’utilisation](GUIDE_UTILISATION.md).

## Vue d’ensemble

SuperMenu est écrit en Python avec PySide6 (Qt 6). L’application Windows est
une composition : le métier commun aux deux plateformes vit dans
`shared/supermenu_core`, et `win32/src` ne contient que l’application et les
intégrations propres à Windows.

```text
SuperMenu/
├── shared/supermenu_core/      # cœur commun, sans API native
│   ├── api/                    # client OpenAI, Ollama, LM Studio et LM Link
│   ├── audio/                  # capture Qt, dictée, modèles vocaux résidents
│   ├── config/                 # modèles, prompts, fonctions avancées/expérimentales
│   ├── ui/                     # fenêtres et widgets Qt communs
│   └── utils/                  # validateurs et traitement du raisonnement
└── win32/
    ├── run.py                  # point d’entrée (sources et exécutable)
    ├── src/
    │   ├── main.py             # classe SuperMenu : démarrage, instance unique
    │   ├── api/                # adaptateur du client, Foundry Local (texte)
    │   ├── audio/              # moteurs vocaux Windows, worker Nemotron
    │   ├── config/             # Settings (QSettings + keyring), catalogue Foundry
    │   ├── ui/                 # fenêtre principale, réponse, capture, Foundry
    │   └── utils/              # raccourcis, menu, presse-papiers, insertion, updater
    ├── tests/
    ├── requirements.txt        # dépendances épinglées, dont ../shared en éditable
    ├── SuperMenu.spec          # build PyInstaller
    └── setup_supermenu.iss     # installateur Inno Setup
```

**Règle de dépendance** : `win32/src` peut importer `supermenu_core`, jamais
l’inverse. Le cœur n’importe ni `src`, ni Win32 (`win32api`, `winreg`,
`ctypes.windll`…), ni AppKit, ni `foundry_local`. Le test
`shared/tests/test_architecture.py` analyse tous les imports du cœur, y
compris `importlib.import_module` et `__import__`, et n’autorise que la
bibliothèque standard portable et une liste fermée de dépendances.

## Composants

### Démarrage

- `run.py` ajoute la racine de `win32/` au `sys.path`, installe la
  journalisation des exceptions non gérées sur le chemin graphique, puis lance
  `src.main.SuperMenu`. Il accepte aussi les modes `--smoke-test`,
  `--foundry-smoke-test`, `--microphone-smoke-test` et les modes worker
  (`--foundry-worker`, `--speech-worker`).
- `src/main.py` crée l’application, les gestionnaires de raccourcis, le
  `ContextMenuManager` et la `MainWindow`, puis termine le démarrage par
  `_finish_startup`. Les raccourcis principaux sont enregistrés avant ceux des
  prompts, pour qu’un prompt ne prenne jamais un raccourci principal.
- Un échec de démarrage est consigné avec sa trace, puis expliqué dans une
  boîte de dialogue minimale (jamais en mode smoke test ou worker).

En distribution, l’application est un exécutable PyInstaller « one-file »
(`SuperMenu.exe`) installé par Inno Setup. Les ressources sont résolues depuis
le dossier d’extraction de PyInstaller (`sys._MEIPASS`) par
`src/utils/paths.py`.

### Instance unique

L’instance unique repose sur un mutex nommé, `Local\SuperMenuSingleInstance`
(`CreateMutexW`), propre à la session Windows. Un `QLocalServer` nommé avec
l’identifiant de session sert seulement au message « show » envoyé par une
seconde instance. Si l’instance existante ne répond pas (redémarrage ou mise à
jour en cours), la nouvelle attend jusqu’à cinq secondes que le mutex soit
libéré. Si le mutex est inutilisable, le démarrage n’est jamais bloqué. À la
fermeture, le mutex est libéré juste après les raccourcis, pour qu’une
instance relancée les retrouve libres.

### Interface

- `src/ui/main_window.py` : fenêtre de configuration (onglets Prompts, Voix,
  Réglages, À propos), icône de la zone de notification, page Application
  (thème, fonctions avancées et expérimentales), réinitialisation et mises à
  jour. Ses rubriques sont des mixins : `main_window_prompts.py` (prompts
  texte et vocaux), `main_window_settings.py` (fournisseur, modèles, capture)
  et `main_window_hotkeys.py` (raccourcis). `background_worker.py` exécute les
  requêtes bloquantes hors du thread Qt. Les pages communes viennent de
  `supermenu_core.ui` (`ConfigurationShell`, `SettingsPanel`,
  `TextPromptForm`, `VoicePromptEditor`, `SpeechSettingsWidget`,
  `ApplicationSettings`, `FeatureModeSettings`, `AboutPage`…).
- `src/ui/foundry_settings.py` : réglages Foundry Local du moteur de texte.
- `src/ui/response_window.py` : ajoute à la fenêtre de réponse commune la
  présentation Win32 et l’insertion native. La fenêtre s’affiche d’abord avec
  Qt, puis un renforcement Win32 (`ShowWindow`, `SetWindowPos`,
  `BringWindowToTop`, `SetForegroundWindow`) la ramène au premier plan ; un
  échec Win32 reste sans conséquence.
- `src/ui/screen_capture.py` : capture plein écran ou de zone.
- Le thème (sombre, clair, automatique) est appliqué à toute l’application par
  `supermenu_core.ui.theme_manager.ThemeManager` ; les fenêtres ne définissent
  pas de styles locaux.

### Configuration

`src/config/settings.py` (`Settings`) persiste les réglages dans un fichier INI
via `QSettings` (`%USERPROFILE%\SuperMenu.ini`). La clé OpenAI et le jeton
d’endpoint sont stockés séparément avec `keyring`, dans le Gestionnaire
d’identification Windows. `Settings` valide et migre les modèles, les
prompts, les raccourcis, les réglages vocaux et le délai de déchargement des
modèles locaux, et porte les interrupteurs des fonctions avancées et
expérimentales.

Les collections de prompts passent par le schéma partagé
(`supermenu_core.config.prompts`). En lecture, une entrée invalide est
réparée ou écartée sans effacer les autres, et la valeur brute est copiée
dans `prompts_backups` ou `voice_prompts_backups` (cinq copies au plus). En
écriture et à l’import, la validation est stricte. `reset_to_defaults` garde
aussi une copie des deux bibliothèques. `src/config/foundry_models.py` déclare
le catalogue Foundry (`FOUNDRY_MODELS`) et l’enregistre dans le cœur avec
`register_foundry_models()`.

## Fonctions avancées et expérimentales

Les interrupteurs `advanced_features_enabled` et
`experimental_features_enabled` sont définis dans
`shared/supermenu_core/config/feature_modes.py` (`FeatureModesSettingsMixin`,
hérité par `Settings`).

- **Création** : `Settings.__init__` appelle `has_saved_preferences()` avant
  d’écrire le moindre défaut. Si le fichier INI contient déjà un réglage d’une
  version précédente (`hotkey`, `prompts`, `model`, `theme` ou
  `update_channel`), les deux interrupteurs sont créés activés ; sinon,
  désactivés. Un choix existant n’est jamais remplacé, et `reset_to_defaults`
  ne les modifie pas.
- **Règle** : lire au moment de l’usage, filtrer à l’enregistrement, ne jamais
  supprimer. Les fonctions `advanced_enabled()`, `experimental_enabled()`,
  `effective_model_target()`, `effective_text_idle_seconds()` et
  `effective_speech_idle_seconds()` relisent le réglage à chaque appel. Aucun
  réglage stocké n’est réécrit à cause d’un interrupteur.

Points de contrôle :

- `HotkeyManager.register_hotkey` ne réserve pas les raccourcis du menu vocal,
  de la capture et de la dictée instantanée sans les fonctions
  expérimentales. C’est un succès sans erreur : aucun « raccourci inactif »
  n’est signalé. `PromptHotkeyManager.refresh_hotkeys` n’enregistre aucun
  raccourci de prompt sans les fonctions avancées.
- `ContextMenuManager` vérifie l’interrupteur à chaque point d’entrée (menu
  vocal, actions vocales, dictée instantanée, capture, raccourci de prompt) :
  un `WM_HOTKEY` déjà en file après la désactivation est ignoré, et
  **Réessayer** refuse une ancienne requête d’image. `_send_request` applique
  `effective_model_target` : sans les fonctions avancées, chaque prompt
  utilise le client des réglages Texte.
- `FoundrySettingsWidget`, `FoundryClient` et `create_speech_backend`
  appliquent `effective_text_idle_seconds` et `effective_speech_idle_seconds`
  (cinq minutes sans les fonctions avancées).
- `MainWindow._apply_feature_visibility` masque l’onglet Voix, la rubrique
  Dictée, les raccourcis expérimentaux, le groupe Capture d’écran, les lignes
  de modèle et de raccourci des prompts et la mémoire des modèles, sans
  jamais retirer de widget : les index restent stables.
- `MainWindow.apply_feature_modes`, relié à `FeatureModeSettings.modes_changed`
  et déclenché par **Appliquer**, libère les raccourcis de prompts,
  réenregistre les raccourcis expérimentaux si leur interrupteur a changé,
  puis les raccourcis de prompts, dans l’ordre du démarrage. Il applique les
  délais de déchargement aux services en cours et, à la désactivation des
  fonctions expérimentales, arrête la vérification vocale et le test du micro
  et décharge le modèle vocal inactif. Les raccourcis qui ne peuvent pas être
  repris sont listés dans l’alerte **Raccourcis inactifs**.

L’import et l’export des prompts conservent toujours tous les champs, que les
fonctions soient actives ou non.

## Raccourcis globaux

`src/utils/hotkey_manager.py` implémente les raccourcis avec l’API Win32 :

- `RegisterHotKey` / `UnregisterHotKey`, réception de `WM_HOTKEY` par un
  `QAbstractNativeEventFilter` installé sur l’application ;
- un `HotkeyManager` par raccourci principal (menu, mode personnalisé, menu
  vocal, capture, dictée instantanée) et un `PromptHotkeyManager` pour les
  raccourcis des prompts ;
- `HotkeyRecorderDialog` capture la combinaison avec les événements Qt, sans
  hook clavier global. Pendant l’enregistrement, tous les raccourcis de
  SuperMenu sont libérés, puis réenregistrés avant d’appliquer le nouveau :
  un conflit avec un autre raccourci de SuperMenu est donc refusé.

Règles de `_parse_hotkey_to_win32` :

- modificateurs `Ctrl`, `Alt` et `Shift` ; `Win` est refusé, comme un
  raccourci sans modificateur ;
- `Shift` seul n’est accepté qu’avec `F1` à `F24` : `RegisterHotKey` réserve
  la combinaison dans tout le système, et `Shift+K` empêcherait de taper un K
  majuscule ailleurs ;
- une lettre majuscule n’ajoute pas `Shift` ;
- un caractère est converti en touche virtuelle par `VkKeyScanW` dans la
  disposition active, et les modificateurs qu’il exige sont ajoutés (`&` en
  QWERTY donne `Shift+7`).

Repli pour `²` : quand la disposition active n’a pas de `²`, ou ne l’obtient
qu’avec AltGr alors que le raccourci ne contient pas déjà `Ctrl+Alt`, le
raccourci utilise la touche physique située sous Échap (code de balayage
`0x29`, converti par `MapVirtualKeyW` et limité aux touches `VK_OEM_*`). Ainsi
`Ctrl+²` devient ``Ctrl+` `` en QWERTY et `Ctrl+^` en QWERTZ, au lieu de
`Ctrl+Alt+2` qui entrerait en conflit avec le raccourci vocal. Un `Ctrl+Alt+²`
garde son sens sur QWERTZ (`Ctrl+Alt+2`, soit AltGr+2). Sur AZERTY, rien ne
change. Le libellé enregistré reste `²` et le journal nomme la touche
réellement réservée.

Chaque `HotkeyManager` expose `last_error`, `feature_name` et le signal
`registration_failed`. Au démarrage, `_report_hotkey_failures` affiche une
notification listant les raccourcis principaux inactifs et le nombre de
raccourcis de prompts concernés. L’onglet Raccourcis affiche « (inactif) »
avec la raison en infobulle.

## Flux principaux

### Menu des prompts

1. `HotkeyManager` reçoit le raccourci et appelle `ContextMenuManager.show_menu()`.
2. `PasteTarget.capture()` mémorise la fenêtre au premier plan, son processus
   et le contrôle qui a le focus. Une fenêtre de SuperMenu n’est jamais prise
   pour cible.
3. `_when_hotkey_released` attend le relâchement de Shift, Alt et Win (aussi
   Ctrl pour un raccourci de prompt), en sondant toutes les 20 ms pendant
   deux secondes au plus, sans bloquer la boucle Qt. Si la fenêtre active
   change pendant l’attente, rien n’est lu ; un nouveau raccourci remplace
   celui en attente.
4. `_try_get_selected_text` copie la sélection (voir plus bas) puis
   `populate_prompt_menu` construit le menu ; les prompts sont désactivés si
   aucun texte n’a été lu.
5. Le prompt choisi est envoyé au client IA avec un `request_id`.
6. La réponse s’affiche dans `ResponseWindow` ou est insérée directement.

Le menu est un `QMenu` natif ouvert par `exec()`. Les événements de
désactivation n’étant pas fiables depuis un raccourci global, un watchdog
(`QTimer` d’environ 200 ms) le ferme si la fenêtre au premier plan n’appartient
ni à l’application d’origine ni à SuperMenu, ou si un clic gauche survient hors
du menu (`GetAsyncKeyState`), après une période de grâce d’environ 250 ms.

### Raccourcis directs par prompt

Chaque prompt textuel peut porter un champ `hotkey`. `PromptHotkeyManager`
enregistre ces combinaisons après les raccourcis principaux et émet
l’identifiant du prompt. `ContextMenuManager.run_prompt_hotkey` capture la
cible et la sélection, puis envoie la requête sans menu. Le champ
`insert_directly` du prompt décide de l’affichage. Les doublons entre prompts
sont refusés par `Settings` ; un conflit Win32 annule la modification sans
toucher aux autres réglages du prompt.

### Copie et collage synthétiques

- Ctrl+C et Ctrl+V sont envoyés avec les codes virtuels `VK_C` et `VK_V`
  (`KeyCode.from_vk`), indépendants de la disposition : pas de paquet
  `KEYEVENTF_UNICODE` sur un clavier cyrillique, grec ou hébreu.
- `_copy_shortcuts_for` choisit la copie selon la classe de la fenêtre :
  `ConsoleWindowClass` et `CASCADIA_HOSTING_WINDOW_CLASS` (Windows Terminal)
  reçoivent Ctrl+Insert puis Ctrl+Shift+C ; mintty, PuTTY, KiTTY et WezTerm ne
  reçoivent que Ctrl+Insert ; les autres fenêtres reçoivent Ctrl+C. ConEmu et
  Cmder copient une sélection avec Ctrl+C et restent donc dans le cas
  général. Le terminal intégré de VS Code ne se distingue pas de l’éditeur
  (`Chrome_WidgetWin_1`).
- Quand SuperMenu est lui-même au premier plan, la lecture de sélection ne
  touche pas au presse-papiers.
- `ClipboardManager.capture_snapshot` clone tous les formats annoncés, images
  comprises (via `imageData()` pour `application/x-qt-image`), et
  `restore_if_unchanged` ne restaure que si le presse-papiers contient encore
  la valeur écrite par SuperMenu.
- Les écritures internes (sentinelle de copie, réponse à coller) passent par
  `set_text(..., transient=True)`, qui ajoute
  `ExcludeClipboardContentFromMonitorProcessing`,
  `CanIncludeInClipboardHistory` et `CanUploadToCloudClipboard` à 0 : elles
  n’entrent ni dans l’historique `Win+V` ni dans le presse-papiers cloud. Le
  contenu de l’utilisateur est restauré tel qu’il a été capturé.
- `PasteTarget.is_remote_session()` reconnaît Bureau à distance
  (`TscShellContainerClass`, `RAIL_WINDOW`), Citrix et VMware : la restauration
  attend alors `CLIPBOARD_REMOTE_RESTORE_DELAY` (1,5 s) au lieu du délai
  normal. Les délais sont définis dans `src/utils/clipboard_config.py`.

### Insertion

`TextInserter` colle la réponse dans la cible capturée.
`PasteTarget.activate_and_verify()` réactive la fenêtre, puis exige le même
processus et le même contrôle focalisé qu’au lancement ; sinon l’insertion est
annulée. Pour une insertion directe :

- sans cible capturée au lancement, rien n’est collé : la réponse est affichée
  avec le message « Aucune fenêtre cible n’était disponible au lancement » ;
- une insertion refusée passe par `_keep_refused_direct_response`, qui
  affiche la réponse dans `ResponseWindow` avec le prompt, le contenu, le
  modèle et le raisonnement d’origine (**Réessayer** et **Insérer le texte**
  fonctionnent), ou la copie dans le presse-papiers si la fenêtre attend
  déjà une autre réponse.

Seul le bouton **Insérer le texte** peut capturer la fenêtre active au
moment du clic quand aucune cible n’est connue.

### Requêtes et clients IA

Le cycle de vie des requêtes est commun aux deux plateformes :
`ContextMenuManager` hérite de
`supermenu_core.ui.request_coordinator.PromptRequestCoordinator` et ne
fournit que la fabrique de clients, l’insertion directe (collage natif,
réponse conservée quand l’insertion est refusée), le signalement d’un échec
et ses libellés.

`ContextMenuManager` crée le client IA à partir des `Settings`
(`_create_api_client`) et le recrée quand les réglages changent
(`update_client_config`, qui vide aussi le cache partagé des capacités des
modèles). L’ancien client est retiré dès qu’il n’a plus de requête en cours.
Un prompt qui choisit son propre modèle reçoit un client dédié. Les requêtes
sont suivies par `request_id` avec des signaux scopés ; `send_request_sync`,
`process_request` et les signaux non scopés ne sont gardés que pour
compatibilité.

Le client commun (`supermenu_core.api.openai_client.OpenAIClient`) gère le
raisonnement, les reprises, la détection des réponses tronquées pour tous les
fournisseurs et le masquage des blocs de raisonnement ; les charges utiles
et la lecture des réponses de chaque fournisseur sont dans
`supermenu_core.api.providers`. L’adaptateur
`src/api/openai_client.py` active les images pour la capture d’écran ; un
chemin de fichier présent dans la sélection reste du texte. Foundry Local
passe par `src/api/foundry_client.py` (`FoundryService`, `FoundryClient`) et
un worker dans un processus enfant (`src/api/foundry_worker.py`), décrits dans
[foundry-local.md](foundry-local.md).

Une erreur de requête appelle `ResponseWindow.set_error` : statut d’échec,
**Insérer le texte** désactivé, **Copier** et **Réessayer** disponibles.

### Voix et dictée

1. Le raccourci vocal ouvre le menu vocal commun (`populate_voice_menu`) :
   **Dicter du texte…**, prompts vocaux, **Prompt vocal personnalisé…**.
2. `ContextMenuManager` crée un `DictationSession` du cœur partagé, également
   utilisé sur macOS, ou un `PlainDictationSession` pour la dictée simple.
3. `RecordingDialog` affiche la préparation ; le microphone ne s’ouvre qu’une
   fois le moteur prêt.
4. `Microphone` capture avec Qt Multimedia et convertit le flux en PCM mono :
   24 kHz pour OpenAI GPT Live Transcribe, 16 kHz pour Nemotron. Les fragments
   sont transmis au fil de l’eau, sans fichier audio.
5. **Terminer** ou la limite de cinq minutes arrête le microphone et finalise ;
   **Annuler** libère la capture et ignore tout résultat tardif.
6. La dictée simple garde son texte dans la même fenêtre (**Copier**,
   **Insérer**), avec correction facultative par le moteur de texte. Le mode
   de raisonnement de la correction est lu à l’insertion dans le prompt
   « Corriger ». Un prompt vocal combine la transcription avec son instruction
   et respecte son option `insert_directly`.
7. `ResidentSpeechService` garde le moteur local entre les dictées, avec une
   session distincte pour chacune, et le décharge après le délai choisi. Le
   délai de préparation est réarmé à chaque progression, pour ne jamais
   couper un téléchargement ou l’activation du GPU.

`src/audio/speech_backend.py` crée le moteur (OpenAI ou Nemotron) et
`src/audio/foundry_speech_worker.py` exécute Nemotron dans un processus
enfant. Le microphone est identifié par son ID Qt (`speech_microphone`).
La bibliothèque et l’éditeur des prompts vocaux
(`supermenu_core.config.voice_prompts`, `supermenu_core.ui.voice_prompt_editor`)
sont partagés avec macOS ; la capture de sélection et l’insertion restent dans
`win32/src`.

### Capture d’écran

1. Le raccourci de capture déclenche `ContextMenuManager`, qui lit le mode :
   `fullscreen`, `region` ou `ask` (menu au curseur).
2. `ResponseWindow` est masquée pendant la capture ; un filtre d’événements
   empêche de réafficher une fenêtre fermée entre-temps.
3. `screen_capture.py` capture l’écran principal (`ImageGrab.grab()`) ou la
   zone choisie. La sélection de zone s’affiche sur l’écran du curseur et la
   zone est capturée par `QScreen.grabWindow` sur cet écran : l’image est en
   pixels physiques, exacte à toutes les mises à l’échelle et sur un écran
   secondaire de coordonnées négatives.
4. L’image est convertie en data URL (`data:image/...;base64,...`), puis le
   fichier temporaire est supprimé.
5. `PromptDialog` demande l’instruction, la requête (texte et image) est
   envoyée, et la réponse s’affiche ; **Réessayer** réutilise la data URL.

## Mises à jour

`src/utils/updater.py` lit d’abord le manifeste `update-stable.json` de la
dernière release Stable ou `update-beta.json` du tag roulant `beta`. Ces
fichiers sont des assets de release : ils ne consomment pas le quota de l’API
REST GitHub. Le manifeste est strictement validé (schéma, canal, version,
type de release, tag, nom de l’asset et empreinte `sha256`). S’il est absent
ou illisible, l’updater interroge l’API GitHub (`/releases/latest` pour
Stable, le tag `beta` pour Bêta) ; un quota épuisé produit un message avec
l’heure de réinitialisation.

Téléchargement et lancement :

- `download_verified_installer` supprime les dossiers de téléchargements
  précédents, télécharge dans un dossier `tempfile.mkdtemp` au nom
  imprévisible, protégé contre les chemins relatifs, et calcule le SHA-256 au
  fil du flux. Une divergence supprime le dossier et lève
  `UpdateIntegrityError`, ou `UpdateSupersededError` si une nouvelle Bêta a
  été publiée entre-temps. Un ancien manifeste sans empreinte est accepté,
  avec un avertissement dans le journal.
- `verify_installer_sha256` revérifie le fichier juste avant `ShellExecuteW`,
  ce qui ferme la fenêtre entre la confirmation et l’exécution.
- L’installateur est lancé avec le verbe `open`, pas `runas` : le chargeur
  Inno Setup demande lui-même l’élévation et l’entrée `postinstall` relance
  SuperMenu avec les droits de l’utilisateur. Un refus (`SE_ERR_ACCESSDENIED`)
  laisse SuperMenu ouvert, sans seconde invite.
- La version portable (`_is_portable_build`) n’est jamais notifiée en
  arrière-plan ; une vérification manuelle propose la page des
  téléchargements.
- Les workers de vérification et de téléchargement héritent de
  `_BackgroundWorker` : un `QObject` dont `run()` s’exécute dans un
  `threading.Thread` démon. Quitter pendant une requête ne provoque plus
  d’arrêt brutal.

Le canal est conservé dans `QSettings` ; un build Bêta neuf sélectionne Bêta,
un build Stable sélectionne Stable. La version comparée est celle de
l’exécutable (`APP_VERSION`), ou celle du registre pour une exécution depuis
les sources.

## Journalisation et diagnostic

`src/utils/logger.py` écrit dans `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`
pour un exécutable, ou `win32/logs/supermenu.log` depuis les sources, avec une
rotation de 1 Mo et trois archives. Depuis les sources, la variable
`SUPERMENU_LOG_DIR` remplace ce dossier : `tests/conftest.py` la fait pointer
vers un dossier temporaire. `install_crash_reporting()` pose
`sys.excepthook` et `threading.excepthook`, pour que les exceptions des slots
Qt et des threads arrivent dans le journal sans arrêter l’application. Aucune
sortie console n’est créée quand `sys.stderr` vaut `None` (exécutable
fenêtré). Le texte sélectionné, les instructions saisies et les
transcriptions ne sont jamais journalisés, même en DEBUG : seule leur longueur
l’est.

## Distribution

- `SuperMenu.spec` construit `dist\SuperMenu.exe` et appelle
  `tools/collect_third_party_licenses.py`, qui écrit
  `dist\third_party_licenses\` (avec `INDEX.txt`). Un composant sans fichier de
  licence produit un avertissement, jamais un échec. Les DLL ICU trouvées dans
  le `PATH` sont écartées, ainsi que des fichiers collectés par les hooks Qt
  mais jamais utilisés : Qt Virtual Keyboard (GPL-3.0 ou licence
  commerciale), Qt Pdf et `opengl32sw.dll` (Mesa).
- `setup_supermenu.iss` installe dans `Program Files\SuperMenu` l’exécutable,
  `LICENSE.txt`, `THIRD_PARTY_NOTICES.md`, `licenses\` et
  `third_party_licenses\`, avec l’éditeur LFPoulain. Les tâches facultatives
  créent un raccourci sur le Bureau et un démarrage avec Windows. La
  désinstallation ferme SuperMenu et peut supprimer
  `%LOCALAPPDATA%\SuperMenu`, `%USERPROFILE%\SuperMenu.ini` et les clés
  enregistrées (`CredDeleteW` sur les entrées créées par `keyring`).
- `src/config/build_info.py` reçoit la version et le canal injectés par les
  workflows avant le packaging.

## CI, versions et canaux

`win32/VERSION` contient la prochaine version Stable (`MAJOR.MINOR.PATCH`).

- **CI** (`ci.yml`) : compilation, tests et lint critique pour Windows sous
  Python 3.11 et 3.12, macOS sous Python 3.12, puis construction d’un DMG de
  contrôle ; aucune publication.
- **Bêta** (`beta-release.yml`) : après la réussite de la CI d’un push sur
  `main` du dépôt, ou lancement manuel sur `main`. Version
  `VERSION-beta.RUN_NUMBER`, tag roulant `beta`, prérelease GitHub,
  `SuperMenu_Beta.exe`, `SuperMenu_Beta_Setup.exe`, manifestes et
  `SHA256SUMS-beta.txt`. Les fichiers sont remplacés un par un, manifestes en
  dernier.
- **Stable** (`stable-release.yml`) : déclenchée uniquement par un tag
  `vMAJOR.MINOR.PATCH` égal à `VERSION`, et seulement si
  `.github/STABLE_NOTES.md` cite la version. La release est publiée une seule
  fois, jamais réécrite par le workflow, et devient la release `Latest`.

Les workflows Bêta et Stable exécutent `SuperMenu.exe --smoke-test` et
`--foundry-smoke-test` sur l’exécutable construit, avant de produire
l’installateur. La procédure complète est décrite dans
[docs/RELEASING.md](../../docs/RELEASING.md).

## Tests

Les tests vivent dans `win32/tests` et s’exécutent depuis `win32/`, après ceux
du cœur (`python -m pytest ../shared/tests`, puis `python -m pytest tests`).

- Les noms de modules sont uniques entre `shared/tests`, `win32/tests` et
  `macos/tests`. Un module Windows qui a un équivalent macOS se termine par
  `_win.py`. `test_prompt_model_routing_win.py` et
  `test_prompt_model_routing_mac.py` sont volontairement identiques et
  doivent le rester.
- `conftest.py` exécute les tests comme une installation mise à jour (les deux
  interrupteurs actifs) ; les tests d’une nouvelle installation remettent
  `feature_modes.NEW_INSTALL_ENABLED` à `False`.
- Après chaque test, `conftest.py` lance le ramasse-miettes et détruit les
  objets Qt en attente de `deleteLater()`. Un test qui crée une fenêtre de
  configuration doit la fermer et appeler `deleteLater()`.
- Un test ne contacte jamais de serveur réel. Par exemple, la provenance
  LM Link (une connexion WebSocket au serveur LM Studio) est remplacée par un
  faux `lmstudio_provenance.fetch_provenance` qui renvoie `([], [])`.

## Règles d’évolution

- Le métier commun va dans `shared/supermenu_core`, sans branchement
  `sys.platform` ajouté ; les API Windows restent dans `win32/src`.
- Une attente de focus ou de presse-papiers est bornée et ne bloque pas la
  boucle Qt.
- Toute insertion revalide sa `PasteTarget` ; une réponse refusée reste
  accessible.
- Une fonction soumise à un interrupteur est vérifiée au moment de l’usage et
  ne supprime jamais de réglage.
- Un nouvel asset de release a un nom déterministe, une entrée de manifeste et
  une empreinte SHA-256.

Retour au [README Windows](../README.md) ou au
[README principal](../../README.md).
