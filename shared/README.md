# SuperMenu Core

`supermenu_core` contient le code exécuté de manière identique par les
applications macOS et Windows. Il ne doit importer aucun module depuis
`macos/src` ou `win32/src` et ne doit dépendre d'aucune API propre à un système
d'exploitation.

Les intégrations natives (raccourcis globaux, presse-papiers, activation des
fenêtres, permissions, audio, capture et installation) restent dans les
sous-projets de plateforme.

## Modules

- `api/` : client fournisseur, formats multimodaux et capacités des modèles ;
- `config/` : catalogue OpenAI, options fournisseur et schéma des prompts ;
- `ui/` : thème, dialogues, indicateur et fenêtre de réponse composable ;
- `utils/` : validateurs sans état.

Les classes UI qui ont besoin du système exposent des hooks et sont complétées
par un adaptateur dans `macos/src` ou `win32/src`. Aucun branchement
`sys.platform` n'est autorisé dans le cœur.

Le client conserve deux credentials distincts : la clé OpenAI n'est envoyée
qu'à OpenAI, tandis qu'un éventuel jeton d'endpoint personnalisé doit être
fourni explicitement par l'adaptateur de plateforme.

## Composants d'interface

- `config/voice_prompts.py` partage la bibliothèque vocale, ses options et
  l’assemblage des six ordres instruction/dictée/sélection. Les deux plateformes
  utilisent `ui/voice_prompt_editor.py` et `ui/voice_menu.py` ; les lecteurs de
  sélection, les cibles d’insertion et le cycle de vie natif restent dans leur
  composition respective. Le traitement du texte utilise le fournisseur IA
  choisi indépendamment du moteur de reconnaissance vocale.
- `config/prompt_transfer.py` partage l’import/export JSON des collections
  `text_prompts` et `voice_prompts`. Les anciens fichiers Mac avec `prompts`
  restent acceptés ; une collection absente est conservée. Les deux collections
  sont validées avant toute écriture.
- `ui/theme_styles.py` centralise la palette d'origine, les états de sélection,
  les surfaces et les couleurs de statut. `ThemeManager` applique le thème à
  toute l'application ; les fenêtres ne définissent pas de styles locaux.
- `ui/controls.py` fournit `ChoiceBox` pour les listes déroulantes, `Menu` pour
  les menus et leurs sous-menus, et `populate_prompt_menu` pour conserver le même
  ordre et les mêmes règles d'activation sur Windows et macOS.
- `ui/settings_panel.py` fournit la navigation des réglages, `Disclosure`,
  `form_layout` et `scrollable_form`. Les formulaires restent accessibles en
  petit format et avec une taille de texte agrandie.
- Les boutons utilisent `variant="primary"` ou `variant="danger"` ; les
  changements de statut passent par `set_ui_property` pour repeindre les
  composants immédiatement.

Pour régénérer les captures des composants en clair et en sombre, lancer
`python tools/preview_ui.py` depuis `shared/`. Les images sont enregistrées dans
`build/ui-preview/` à la racine du dépôt, avec des données d'exemple uniquement.

## Validation

Depuis `shared/`, avec les dépendances d'une application installées :

```bash
python -m pytest -q
python -m compileall -q supermenu_core
python -m flake8 supermenu_core tests --select=F,E9
```

### Dictée instantanée et livraison du texte

`audio/dictation_flow.py` réutilise `DictationSession` pour garder le résultat
simple dans la fenêtre de transcription. La correction utilise un client texte
isolé avec des signaux de requête identifiés ; fermeture, annulation et erreurs
empêchent tout collage tardif. Les adaptateurs natifs conservent la cible de
collage et reçoivent un prédicat d’annulation pour leurs étapes asynchrones.

`audio/dictation_shortcut.py` partage les transitions appui/relâchement et bloque
les répétitions. Windows conserve RegisterHotKey et observe la libération de la
combinaison uniquement pendant l’appui ; Mac réutilise ses moniteurs AppKit avec
KeyUp/FlagsChanged. `ui/dictation_settings.py` partage les options d’écoute et de
livraison. `config/model_memory.py` centralise les choix de rétention ; le service
texte Foundry protège les requêtes actives et en attente avant tout déchargement.
