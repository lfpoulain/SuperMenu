## Description

<!-- Que change cette pull request, et pourquoi ? Liez l’issue concernée, par exemple « Corrige #123 ». -->

## Type de changement

- [ ] Correction de bug
- [ ] Nouvelle fonction (discutée dans une issue)
- [ ] Documentation
- [ ] Autre :

## Parties concernées

- [ ] Cœur partagé (`shared/`)
- [ ] Windows (`win32/`)
- [ ] macOS (`macos/`)
- [ ] CI ou publication (`.github/`)

## Tests

<!-- Commandes lancées, tests ajoutés et essais manuels : système, fournisseur IA, application cible. -->

- [ ] `python -m pytest -q ../shared/tests` et `python -m pytest -q tests` passent depuis `win32/` et/ou `macos/`.
- [ ] `python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9` ne signale rien.
- [ ] Un test couvre la correction ou la nouvelle fonction.
- [ ] J’ai essayé le changement dans l’application.

## Vérifications

- [ ] `shared/` n’importe aucun code propre à Windows ou à macOS.
- [ ] Les textes de l’interface sont en français.
- [ ] Ni le code, ni les tests, ni les journaux ne contiennent de clé API, de chemin personnel ou de texte de l’utilisateur.
- [ ] Les réglages et bibliothèques de prompts existants restent lisibles, sans perte de données.
- [ ] Une fonction avancée ou expérimentale est masquée et ignorée quand son interrupteur est désactivé, sans effacer ses réglages.
- [ ] La documentation et la section « Non publié » de `CHANGELOG.md` sont à jour si le changement est visible.
- [ ] Je n’ai modifié ni `win32/VERSION`, ni `macos/VERSION`, ni les notes de release (`.github/BETA_NOTES.md`, `.github/STABLE_NOTES.md`).

## Licence

- [ ] J’ai le droit de soumettre cette contribution. Je la soumets sous la licence du projet (PolyForm Noncommercial 1.0.0) et j’accorde au mainteneur la licence supplémentaire décrite dans [CONTRIBUTING.md](https://github.com/lfpoulain/SuperMenu/blob/main/CONTRIBUTING.md#licence-des-contributions), qui lui permet de la distribuer sous d’autres conditions, y compris commerciales.
