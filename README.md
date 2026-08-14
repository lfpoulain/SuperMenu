# SuperMenu

SuperMenu est une application de bureau Python/PySide6 disponible sous Windows
et macOS. Les deux applications utilisent désormais un cœur commun afin que la
logique métier, les fournisseurs IA et les composants Qt génériques évoluent
une seule fois.

```text
SuperMenu/
├── shared/supermenu_core/  # logique et UI réellement multiplateformes
├── macos/                 # composition et intégrations natives macOS
├── win32/                 # composition et intégrations natives Windows
└── .github/workflows/     # validation croisée et publications
```

## Frontières de l'architecture

Le package `supermenu_core` contient notamment :

- le client OpenAI, Ollama et LM Studio ;
- les capacités et migrations des modèles ;
- le schéma de validation des prompts ;
- le dialogue de prompt et la base de la fenêtre de réponse ;
- les thèmes, validateurs, dialogues sûrs et indicateurs de chargement.

Les raccourcis globaux, le presse-papiers, l'activation des applications, les
permissions, l'insertion de texte et l'installation restent propres à chaque
OS. L'audio et la capture d'écran sont pour le moment des fonctionnalités
Windows. Le cœur partagé n'importe jamais `macos/src`, `win32/src`, AppKit ou
Win32.

## Développement

Chaque application conserve son environnement et ses dépendances de
plateforme. Le package local partagé est installé automatiquement par son
fichier `requirements.txt` ; les commandes d'installation doivent donc être
lancées depuis le sous-projet concerné.

Windows :

```powershell
cd win32
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python run.py
```

macOS :

```bash
cd macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python run.py
```

Validation complète depuis chacun des sous-projets :

```text
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m compileall -q ../shared/supermenu_core src run.py
```

Les détails d'exécution et de packaging se trouvent dans
[`macos/README.md`](macos/README.md) et [`win32/README.md`](win32/README.md).

## CI et versions

Le workflow `CI` valide le cœur partagé sous Windows (Python 3.10 et 3.12),
macOS (Python 3.12), puis construit un DMG de test. Lorsque les secrets Apple
sont configurés, ce DMG est signé avec Developer ID, notarié et validé avant
son chargement comme artifact.

Après la réussite de `CI` sur `main`, le workflow `Beta Release` construit en
parallèle les exécutables Windows et le DMG Apple Silicon, puis remplace la
prérelease roulante `beta` uniquement si les deux builds réussissent. Le
workflow `Stable Release`, déclenché par un tag `vMAJOR.MINOR.PATCH` conforme à
`win32/VERSION`, publie les mêmes formats dans une release stable immuable.
Les DMG de release exigent les cinq secrets Apple : aucun paquet macOS non
signé ou non notarié ne peut être publié par ces workflows.

`macos/VERSION` et `win32/VERSION` restent indépendants : une modification du
cœur commun ne force pas les deux applications à partager le même numéro. Les
manifestes de mise à jour sont donc propres à chaque plateforme, même si les
binaires sont regroupés dans une seule release GitHub.

## Licence

Voir [`LICENSE`](LICENSE).
