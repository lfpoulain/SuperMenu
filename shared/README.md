# SuperMenu Core

`supermenu_core` contient le code exécuté à l’identique par les applications
Windows ([`win32/`](../win32/README.md)) et macOS
([`macos/`](../macos/README.md)) : client IA, modèles, prompts, dictée en
direct et composants d’interface Qt. Ce n’est pas une bibliothèque publiée :
chaque application l’installe en mode éditable depuis son propre
`requirements.txt` (`-e ../shared`).

## Règles

- Le cœur n’importe rien depuis `win32/src` ou `macos/src`, ni API propre à un
  système : Win32 (`win32api`, `winreg`, `ctypes.windll`…), AppKit et PyObjC,
  `foundry_local`. Le test `tests/test_architecture.py` analyse tous les
  imports, y compris `importlib.import_module` et `__import__`, et n’autorise
  que la bibliothèque standard portable et une liste fermée de dépendances
  (PySide6, requests, websocket-client, pyqtdarktheme).
- Les intégrations natives (raccourcis globaux, presse-papiers, activation des
  fenêtres, autorisations, moteurs vocaux natifs, capture et installation)
  restent dans les applications. Les classes qui ont besoin du système
  exposent des hooks ou des signaux, complétés par un adaptateur de
  plateforme.
- Le cœur évite les branchements `sys.platform`. Les rares qui subsistent
  concernent des libellés et la disponibilité des moteurs vocaux
  (`audio/settings.py`, `ui/speech_settings.py`, `ui/microphone_test.py`,
  `ui/model_catalog.py`) ; un nouveau comportement propre à un système passe
  par un hook.
- Le client garde deux secrets distincts : la clé OpenAI n’est envoyée qu’à
  OpenAI, et le jeton d’un endpoint personnalisé est fourni explicitement par
  l’adaptateur de plateforme.

## Modules

### `api/` : fournisseurs et modèles

- `openai_client.py` : `OpenAIClient`, utilisé pour OpenAI, Ollama, LM Studio
  et les serveurs compatibles OpenAI. Il gère le raisonnement, les reprises
  (erreurs de connexion, 429 et 5xx), les signaux scopés par `request_id` et
  la normalisation des réponses. Une réponse tronquée est détectée pour tous
  les fournisseurs (`finish_reason`, `done_reason` d’Ollama,
  `incomplete_details`) et produit une erreur adaptée au fournisseur au lieu
  d’un texte incomplet. Une génération lente n’est pas relancée : une seule
  attente de 180 s (300 s avec LM Studio). Les capacités des modèles sondées
  auprès d’Ollama et de LM Studio sont partagées entre clients pendant 300 s
  (`clear_capabilities_cache()`) et sondées de nouveau 30 s après un échec.
  Un texte sélectionné n’est jamais lu comme un chemin de fichier.
- `lmstudio_transport.py` : exécution explicite sur le poste local ou sur un
  poste LM Link.
- `lmstudio_provenance.py` : lecture seule des métadonnées LM Link (WebSocket
  vers LM Studio), facultative pour la découverte des modèles.
- `model_capabilities.py` : aides partagées entre le client des modèles
  locaux et ses réglages.

### `config/` : réglages et prompts

- `openai_models.py` : catalogue des modèles OpenAI proposés, leurs niveaux de
  raisonnement et la migration des anciens identifiants.
- `prompts.py` : prompts par défaut, schéma, migrations et validation. En
  lecture, `repair_prompt_collection` répare chaque entrée invalide avec ses
  valeurs par défaut ou l’écarte, sans effacer les autres ; seule une racine
  qui n’est pas un objet JSON reste une erreur. L’écriture et l’import
  restent en validation stricte, avec des messages qui nomment le prompt.
- `prompt_restore.py` : restauration des prompts d’origine et copies de
  sauvegarde. Les cinq dernières copies de chaque bibliothèque sont gardées
  dans `prompts_backups` et `voice_prompts_backups`, avec leur date et leur
  motif (restauration, import, réparation, retour à une copie), sans doublon.
  `restore_prompt_backup` remet la copie désignée par `next_prompt_backup` :
  la première copie plus ancienne que la liste actuelle, en ignorant les
  copies identiques à cette liste ou illisibles. Chaque nouvel appel remonte
  donc d’une copie. La liste remplacée est gardée en copie.
  `sync_settings_or_raise` détecte un échec d’écriture de la configuration et
  annule l’opération en mémoire.
- `prompt_transfer.py` : import et export JSON communs (`text_prompts` et
  `voice_prompts`). Les anciens fichiers Mac avec `prompts` restent acceptés,
  et une collection absente du fichier est conservée. Les deux collections
  sont validées avant toute écriture ; le fichier est lu en UTF-8, avec ou
  sans BOM. `endpoint` et `endpoint_type` ne sont ni exportés ni importés :
  le moteur (`provider`), le modèle et le poste LM Link d’un prompt sont
  conservés. Un fichier importé peut donc désigner OpenAI ou un moteur local,
  mais jamais un serveur autre que celui des réglages Texte.
- `model_target.py` : modèle choisi par prompt. Un choix « LM Studio /
  Ollama » suit toujours le serveur des réglages Texte : les adresses
  laissées par d’anciennes versions sont ignorées à l’exécution et retirées à
  la lecture (`without_server`). Le cœur n’importe pas le catalogue Foundry
  Local de Windows : `register_foundry_models()` est appelé par
  `win32/src/config/foundry_models.py`, et `registered_foundry_models()` le
  relit pour l’éditeur et le routage. Sans enregistrement (macOS), aucun
  modèle Foundry n’est proposé.
- `feature_modes.py` : interrupteurs « Fonctions avancées » et « Fonctions
  expérimentales », décrits plus bas.
- `prompt_reasoning.py` : mode de raisonnement d’un prompt (réglage du moteur,
  sans, avec), indépendant de l’affichage de la trace.
- `model_memory.py` : choix de conservation des modèles locaux en mémoire
  (après chaque usage, 1, 5, 15 ou 30 minutes, à la fermeture ; cinq minutes
  par défaut).
- `voice_prompts.py` : bibliothèque vocale, options et assemblage des six
  ordres instruction / dictée / sélection.
- `provider_settings.py` : réglages communs des fournisseurs.

### `audio/` : dictée en direct

- `microphone.py` : capture Qt Multimedia en fragments PCM bornés, sans
  fichier audio.
- `session.py` : `DictationSession` ne démarre la capture qu’une fois le
  moteur prêt et ignore tout résultat tardif.
- `dictation_flow.py` : `PlainDictationSession` garde le résultat simple dans
  la fenêtre de transcription, avec correction facultative par un client
  texte isolé ; fermeture, annulation et erreurs empêchent tout collage
  tardif. Le mode de raisonnement de la correction est lu au moment de
  l’insertion.
- `dictation_shortcut.py` : transitions appui/relâchement de la dictée
  instantanée, sans répétition. Windows observe la libération de la
  combinaison pendant l’appui ; macOS réutilise ses moniteurs AppKit.
- `backends.py` et `resident.py` : transports asynchrones vers OpenAI et vers
  les workers vocaux locaux. `ResidentSpeechService` garde un worker par
  application avec une session isolée par dictée. Le délai de préparation est
  réarmé à chaque progression, pour ne jamais couper un téléchargement ou
  l’activation du GPU. Si le worker échoue pendant qu’une dictée attend la
  fin de la précédente, cette dictée repart sur un worker neuf.
- `settings.py` : réglages vocaux, indépendants du moteur de texte.

### `ui/` : composants Qt

- Fenêtres : `configuration_shell.py`, `response_window.py` (avec un état
  d’erreur qui désactive l’insertion), `prompt_dialog.py`,
  `dictation_dialog.py`, `about_page.py` (version, licence et composants
  tiers).
- Réglages : `settings_panel.py` (navigation, `Disclosure`, formulaires
  défilants), `application_settings.py` (thème, canal de mise à jour,
  `FeatureModeSettings`), `speech_settings.py`, `dictation_settings.py`,
  `shortcut_settings.py`, `microphone_test.py`, `model_catalog.py`.
- Prompts : `text_prompt_form.py`, `voice_prompt_editor.py`,
  `prompt_model.py`, `prompt_reasoning.py`, `prompt_restore.py`,
  `page_actions.py` (**Réinitialiser**, **Tout restaurer…**, **Revenir à la
  copie…**, **Enregistrer**), `voice_menu.py`.
- Socle : `theme_manager.py` et `theme_styles.py` (palette, états et couleurs
  de statut ; les fenêtres ne définissent pas de styles locaux), `controls.py`
  (`ChoiceBox`, `Menu`, `PlainTextEdit`, `populate_prompt_menu`),
  `loading_indicator.py`, `safe_dialogs.py`, `confirmations.py`,
  `verification_status.py`, `window_header.py`.
- Requêtes : `request_coordinator.py` (`PromptRequestCoordinator`) porte le
  cycle de vie des requêtes des deux menus contextuels : identifiant par
  requête, client dédié aux prompts liés à un modèle, seule la dernière
  requête met à jour la fenêtre de réponse, relance, changement de client et
  fermeture. Chaque plateforme fournit sa fabrique de clients, son insertion
  directe (collage natif, réponse conservée quand l’insertion est refusée),
  le signalement d’un échec et ses libellés (`RequestFeedback`) ; capture,
  menus et dictée restent dans son `ContextMenuManager`.

Les textes venant d’un serveur ou d’un prompt sont affichés en texte brut :
`SafeDialogs` force le format texte et tronque un message trop long,
l’aperçu de `PromptDialog` et les instructions utilisent `setPlainText`, et
l’indicateur de chargement n’interprète pas le HTML. Les boutons utilisent
`variant="primary"` ou `variant="danger"`, et les changements d’état passent
par `set_ui_property` pour repeindre immédiatement.

### `utils/`

- `thinking.py` : sépare la réponse visible du raisonnement, y compris une
  balise `</think>` sans balise ouvrante ; une balise citée au milieu d’une
  phrase reste du texte.
- `validators.py` : validation des URL (noms sans point, IPv6, domaines
  `.internal`, ports) et des noms de modèles.

## Fonctions avancées et expérimentales

`config/feature_modes.py` définit deux interrupteurs indépendants, réglés dans
**Réglages > Application > Fonctions** par `FeatureModeSettings` :

| Interrupteur | Clé | Fonctions |
|---|---|---|
| Fonctions avancées | `advanced_features_enabled` | modèle, fournisseur ou poste LM Link par prompt ; raccourci direct par prompt ; conservation des modèles locaux en mémoire |
| Fonctions expérimentales | `experimental_features_enabled` | prompts vocaux, dictée instantanée, réglages de la dictée, test du micro ; capture et analyse d’écran sous Windows |

- **Valeurs initiales** : `FeatureModesSettingsMixin.has_saved_preferences()`
  regarde, avant toute écriture de défaut, si une version précédente a déjà
  enregistré `hotkey`, `prompts`, `model`, `theme` ou `update_channel`.
  `initialize_feature_modes()` écrit alors les interrupteurs absents :
  activés pour une installation existante, désactivés pour une nouvelle
  (`NEW_INSTALL_ENABLED = False`). Un choix déjà enregistré n’est jamais
  remplacé.
- **Lecture au moment de l’usage** : `advanced_enabled()`,
  `experimental_enabled()`, `effective_model_target()`,
  `effective_text_idle_seconds()` et `effective_speech_idle_seconds()` relisent
  le réglage à chaque appel, sans cache. Sans les fonctions avancées, un
  prompt utilise le réglage général (`{}`) et les modèles locaux se
  déchargent après cinq minutes. Un objet de réglages sans cette API garde le
  comportement d’avant les interrupteurs : tout est actif.
- **Aucune suppression** : désactiver une fonction la masque et l’ignore ; les
  prompts, raccourcis et délais restent stockés et l’import/export conserve
  tous les champs. Les raccourcis concernés sont filtrés à leur
  enregistrement par chaque plateforme.
- `prompts_with_model_target()` compte les prompts qui ont leur propre
  modèle, pour que `FeatureModeSettings` demande confirmation avant de
  désactiver les fonctions avancées.

Les points de contrôle propres à chaque plateforme sont décrits dans
[l’architecture Windows](../win32/docs/ARCHITECTURE.md#fonctions-avancées-et-expérimentales)
et [l’architecture macOS](../macos/docs/ARCHITECTURE.md#fonctions-avancées-et-expérimentales).

## Tests et outils

Les tests du cœur s’exécutent depuis une application, avec ses dépendances
installées, comme dans la CI :

```bash
cd win32        # ou macos
python -m compileall -q ../shared/supermenu_core
python -m pytest -q ../shared/tests
python -m flake8 ../shared/supermenu_core ../shared/tests --select=F,E9
```

Les tests Qt du cœur s’exécutent sans affichage (`QT_QPA_PLATFORM=offscreen`,
défini par `tests/conftest.py`) et ne contactent aucun serveur réel. Les noms
des modules de test sont uniques dans tout le dépôt.

Pour régénérer les captures des composants dans les deux thèmes, avec des
données d’exemple uniquement, lancez depuis la racine du dépôt :

```bash
python shared/tools/preview_ui.py
```

Les images sont écrites dans `build/ui-preview/`, ignoré par git.

## Licence

Le cœur partagé fait partie de SuperMenu et suit la même licence,
[PolyForm Noncommercial 1.0.0](../LICENSE) (`PolyForm-Noncommercial-1.0.0`
dans `pyproject.toml`). Les composants tiers sont listés dans
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
