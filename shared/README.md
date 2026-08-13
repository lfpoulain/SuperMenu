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

## Validation

Depuis `shared/`, avec les dépendances d'une application installées :

```bash
python -m pytest -q
python -m compileall -q supermenu_core
python -m flake8 supermenu_core tests --select=F,E9
```
