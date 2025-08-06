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
├── venv/                   # Environnement virtuel Python
├── requirements.txt        # Dépendances Python
├── run.py                  # Script de lancement
└── setup_supermenu.iss     # Script d'installation Inno Setup
```

## Composants principaux

### 1. Point d'entrée et initialisation

- **run.py** : Script de lancement qui initialise l'application
- **src/__main__.py** : Point d'entrée du package qui instancie la classe principale
- **src/main.py** : Classe SuperMenu qui initialise l'application, les raccourcis et les gestionnaires

### 2. Interface utilisateur (src/ui/)

- **main_window.py** : Fenêtre principale des paramètres
- **response_window.py** : Fenêtre d'affichage des réponses de l'API
- **prompt_dialog.py** : Dialogue pour les prompts personnalisés
- **screenshot_dialog.py** : Interface de capture d'écran
- **screen_capture.py** : Fonctionnalités de capture d'écran
- **style.py** : Gestion des thèmes et styles de l'application

### 3. Utilitaires (src/utils/)

- **context_menu.py** : Gestion du menu contextuel
- **hotkey_manager.py** : Enregistrement et gestion des raccourcis clavier
- **logger.py** : Système de journalisation
- **screenshot_tool.py** : Outil de capture d'écran

### 4. Configuration (src/config/)

- **settings.py** : Gestion des paramètres de l'application (via QSettings)

### 5. API (src/api/)

- **openai_client.py** : Client pour l'API OpenAI

### 6. Audio (src/audio/)

- **voice_recognition.py** : Reconnaissance vocale
- **text_inserter.py** : Insertion de texte dans les applications

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

### Reconnaissance vocale

1. L'utilisateur appuie sur le raccourci vocal (par défaut: Ctrl+Alt+²)
2. `VoiceRecognition` enregistre l'audio via le microphone
3. L'audio est transcrit en texte
4. Le texte transcrit est combiné avec le prompt vocal sélectionné
5. La requête est envoyée à l'API OpenAI
6. La réponse est affichée ou insérée selon la configuration

### Capture d'écran

1. L'utilisateur appuie sur le raccourci de capture (par défaut: Ctrl+Shift+²)
2. `ScreenshotDialog` permet à l'utilisateur de sélectionner une zone de l'écran
3. L'image capturée est enregistrée temporairement
4. Un menu contextuel spécifique aux images est affiché
5. L'utilisateur sélectionne une action
6. L'image et le prompt sont envoyés à l'API OpenAI
7. La réponse est affichée dans `ResponseWindow`

## Gestion des paramètres

La classe `Settings` dans `src/config/settings.py` gère tous les paramètres de l'application :

- Stockage des paramètres dans un fichier INI via `QSettings`
- Stockage sécurisé de la clé API via `keyring`
- Gestion des prompts textuels et vocaux
- Configuration des raccourcis clavier
- Paramètres du microphone
- Thème de l'application

## Système de thèmes

Le système de thèmes est implémenté dans `src/ui/style.py` :

1. Définition des palettes de couleurs (DARK_PALETTE, BEE_PALETTE)
2. Création de styles CSS pour chaque thème
3. Application du thème via `apply_theme(app, theme)`
4. Stockage du thème sélectionné dans les paramètres

## Extensibilité

L'architecture de SuperMenu a été conçue pour faciliter l'ajout de nouvelles fonctionnalités :

- **Nouveaux prompts** : Facilement ajoutables via l'interface utilisateur
- **Nouveaux thèmes** : Ajout possible en définissant une nouvelle palette et un style CSS
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
- Pas de stockage en clair des informations sensibles
- Utilisation de fichiers temporaires avec nettoyage automatique

---

Ce document est destiné aux développeurs souhaitant comprendre l'architecture de SuperMenu ou contribuer au projet. Pour des informations sur l'utilisation de l'application, consultez le [Guide d'utilisation](GUIDE_UTILISATION.md).

### Utilisation dynamique des modèles OpenAI

- `OpenAIClient` (`src/api/openai_client.py`) : Gère toutes les communications avec l'API OpenAI pour les requêtes texte et image. Il est responsable de la construction des requêtes, de l'envoi, et du traitement initial des réponses. Il est maintenant configuré dynamiquement avec le modèle et l'URL de base sélectionnés par l'utilisateur. La transcription audio utilise séparément l'API OpenAI standard.
- `Settings` (`src/config/settings.py`) : Charge et sauvegarde les configurations de l'utilisateur, y compris la clé API, l'URL de base de l'API, le modèle OpenAI sélectionné, les prompts, les raccourcis et le thème.
- `ContextMenuManager` (`src/utils/context_menu.py`) : Orchestre l'affichage du menu contextuel, la récupération du texte sélectionné, l'appel à `OpenAIClient` et l'affichage de la `ResponseWindow`. Il initialise et met à jour la configuration de `OpenAIClient` (clé API, modèle et URL) en fonction des `Settings`.

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

1.  L'utilisateur ouvre la fenêtre `MainWindow` et va dans l'onglet "Général".
2.  L'utilisateur sélectionne ou saisit un nouveau modèle compatible dans la liste déroulante puis clique sur "Enregistrer la clé et le modèle".
3.  `MainWindow` appelle `settings.set_model()` pour sauvegarder le nouveau modèle.
4.  `MainWindow` appelle `context_menu_manager.update_client_config()`.
5.  `ContextMenuManager` appelle `api_client.set_model()` et `api_client.set_api_key()` pour mettre à jour l'instance `OpenAIClient` avec les nouvelles valeurs des `Settings`.
6.  Les requêtes suivantes utiliseront le nouveau modèle.
