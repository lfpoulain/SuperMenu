# SuperMenu

[![CI](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml/badge.svg)](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/lfpoulain/SuperMenu?display_name=tag&sort=semver)](https://github.com/lfpoulain/SuperMenu/releases)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows)
![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-000000?logo=apple)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
[![License](https://img.shields.io/badge/licence-CC%20BY--NC%204.0-lightgrey)](LICENSE)

SuperMenu place l’IA dans les applications où vous travaillez déjà. Sélectionnez
du texte, utilisez un raccourci global, choisissez une action — corriger,
reformuler, résumer, traduire ou votre propre prompt — puis copiez ou réinsérez
la réponse sans changer de contexte.

Le projet fournit deux applications de bureau séparées, une pour Windows et une
pour macOS, réunies autour d’un cœur métier Python commun. Chaque plateforme
conserve ses intégrations natives, ses dépendances, ses tests et son packaging.

## Fonctionnalités

- menu de prompts accessible par raccourci global ;
- prompts modifiables, réordonnables, importables et exportables ;
- raccourcis directs attribuables à des prompts individuels ;
- mode personnalisé pour écrire une instruction libre ;
- fenêtre de réponse avec **Réessayer**, **Copier**, **Écrire** et affichage
  optionnel du raisonnement ;
- OpenAI, Ollama / LM Studio et moteurs natifs Apple / Microsoft ;
- thèmes clair, sombre et automatique ;
- canaux de mise à jour Stable et Beta via GitHub Releases.

### Différences entre plateformes

| Capacité | Windows | macOS |
|---|---:|---:|
| Texte sélectionné et prompts personnalisés | Oui | Oui |
| Insertion directe dans l’application cible | Oui | Oui |
| OpenAI, Ollama et LM Studio | Oui | Oui |
| Apple Intelligence local | Non | macOS 26+ |
| Texte local avec Foundry / Qwen3.5 | Windows 11 24H2+ | Non |
| Prompts vocaux et raccourci de dictée instantanée | Oui | Oui |
| Raccourcis globaux et raccourcis par prompt | Win32 | AppKit |
| Transcription audio en direct | OpenAI ou Foundry Local / Nemotron 3.5 | OpenAI ou Apple Speech (macOS 26+) |
| Capture et analyse d’écran | Oui | Non |
| Distribution | EXE portable + installateur | DMG Apple Silicon |
| Mise à jour intégrée | Installateur correspondant au canal | DMG correspondant au canal |

La version macOS partage le texte et la dictée avec Windows, tout en gardant
ses intégrations natives. Le microphone est demandé uniquement pour la dictée
ou son test. La capture d’écran reste propre à Windows ; macOS ne demande
ni Enregistrement de l’écran ni Surveillance de l’entrée.

## Installation

Les versions Stable et Beta sont regroupées sur la page
[GitHub Releases](https://github.com/lfpoulain/SuperMenu/releases).

### Windows

1. Téléchargez `SuperMenu_Setup.exe` pour Stable ou
   `SuperMenu_Beta_Setup.exe` pour Beta.
2. Exécutez l’installateur.
3. SuperMenu démarre dans la zone de notification Windows.

Une version portable, `SuperMenu.exe` ou `SuperMenu_Beta.exe`, est également
publiée.

### macOS

1. Téléchargez `SuperMenu-macOS-arm64.dmg` pour Stable ou
   `SuperMenu_Beta-macOS-arm64.dmg` pour Beta.
2. Ouvrez le DMG et glissez `SuperMenu.app` dans `/Applications`.
3. Lancez l’application puis accordez **Accessibilité** lorsque macOS le
   demande.

Les DMG publics sont signés avec Developer ID, notariés par Apple et destinés
aux Mac Apple Silicon. Consultez le [guide macOS](macos/docs/GUIDE_UTILISATION.md)
pour le premier lancement et les autorisations.

## Utilisation en trois étapes

1. Sélectionnez du texte dans votre application courante.
2. Ouvrez SuperMenu avec le raccourci principal.
3. Choisissez un prompt, puis utilisez **Copier** ou **Écrire** pour renvoyer la
   réponse vers l’application capturée.

Les raccourcis par défaut sont :

| Action | Windows | macOS |
|---|---|---|
| Menu principal | `Ctrl+²` | `Cmd+Shift+Space` |
| Mode personnalisé | `Ctrl+Alt+M` | `Cmd+Shift+M` |

Tous les raccourcis sont modifiables dans les paramètres.

## Documentation

| Sujet | Windows | macOS |
|---|---|---|
| Présentation de la plateforme | [README](win32/README.md) | [README](macos/README.md) |
| Guide d’utilisation | [Guide Windows](win32/docs/GUIDE_UTILISATION.md) | [Guide macOS](macos/docs/GUIDE_UTILISATION.md) |
| Architecture technique | [Architecture Windows](win32/docs/ARCHITECTURE.md) | [Architecture macOS](macos/docs/ARCHITECTURE.md) |
| Signature et distribution | — | [Signature et notarisation](macos/SIGNING.md) |

## Organisation du dépôt

```text
SuperMenu/
├── shared/
│   └── supermenu_core/       # métier, fournisseurs IA et composants Qt communs
├── win32/                    # application et intégrations natives Windows
│   ├── src/
│   ├── docs/
│   └── tests/
├── macos/                    # application et intégrations natives macOS
│   ├── src/
│   ├── docs/
│   ├── scripts/
│   └── tests/
└── .github/workflows/        # CI, Beta roulante et releases Stable
```

`shared/supermenu_core` contient le client IA, les capacités des modèles, le
catalogue de prompts, les validateurs et les composants Qt réutilisables. Il
n’importe jamais AppKit, Win32, `macos/src` ou `win32/src`.

Les couches de plateforme possèdent l’amorçage de l’application, les
raccourcis globaux, le presse-papiers, la capture de la cible, l’insertion, les
permissions, le stockage et le packaging. Cette séparation permet d’adapter
chaque OS sans accumuler de conditions de plateforme dans une application
unique.

## Développement

### Windows

Python 3.11 minimum (SDK Foundry Local) ; Python 3.12 recommandé et utilisé
pour les versions publiées.

```powershell
cd win32
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

### macOS

```bash
cd macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

L’installation doit être lancée depuis le sous-projet choisi : son fichier
`requirements.txt` installe le package local `../shared`.

### Validation

Depuis `win32/` ou `macos/` :

```text
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
```

macOS possède en plus un smoke test natif :

```bash
python run.py --smoke-test
```

## CI, versions et releases

- **CI** valide le cœur partagé et Windows sous Python 3.11/3.12, valide macOS
  sous Python 3.12, puis construit un DMG de contrôle.
- **Beta** démarre après une CI réussie sur `main`. Windows et macOS sont
  construits en parallèle ; la prerelease roulante `beta` n’est remplacée que
  si les deux plateformes réussissent.
- **Stable** démarre lors du push d’un tag `vMAJOR.MINOR.PATCH` correspondant à
  `win32/VERSION`. La release est créée comme version stable immuable.

`win32/VERSION` et `macos/VERSION` sont indépendants. Une même release GitHub
peut donc transporter deux numéros d’application et utilise des manifestes
distincts :

| Canal | Windows | macOS |
|---|---|---|
| Stable | `update-stable.json` | `update-macos-stable.json` |
| Beta | `update-beta.json` | `update-macos-beta.json` |

Ces petits fichiers JSON indiquent à chaque updater la version, le canal, le
tag et l’asset attendu. Ils empêchent notamment macOS de choisir un EXE et
Windows de choisir un DMG.

## Données et sécurité

- Les contenus sont envoyés uniquement au fournisseur configuré par
  l’utilisateur.
- Les journaux n’enregistrent ni clé API, ni sélection, ni contenu de prompt.
- Windows utilise le stockage sécurisé de la plateforme pour les secrets.
- macOS stocke sa configuration dans un fichier utilisateur protégé par les
  permissions du compte, afin d’éviter les dialogues Trousseau des builds de
  test.
- Les releases macOS publiques exigent signature Developer ID et notarisation ;
  le workflow refuse de publier un DMG incomplet ou non signé.

## Licence

SuperMenu est distribué sous licence
[Creative Commons Attribution-NonCommercial 4.0 International](LICENSE).
Le partage et l’adaptation sont autorisés avec attribution ; l’utilisation
commerciale est interdite.
