# Contribuer à SuperMenu

Merci de votre intérêt pour SuperMenu ! Ce guide explique comment préparer un
environnement de développement, valider vos changements et proposer une
contribution.

- Une question de sécurité ? Ne l’ouvrez pas en public : suivez la
  [politique de sécurité](SECURITY.md).
- Les échanges sur le projet suivent le [code de conduite](CODE_OF_CONDUCT.md).

## Licence des contributions

SuperMenu est distribué sous licence
[PolyForm Noncommercial 1.0.0](LICENSE).

En proposant une contribution (code, documentation, traduction, ressource),
vous confirmez avoir le droit de la soumettre : il s’agit de votre propre
travail, ou d’un contenu dont la licence permet cette diffusion. Vous acceptez
aussi :

1. qu’elle soit distribuée sous la licence du projet, PolyForm Noncommercial
   1.0.0 ;
2. d’accorder en plus au mainteneur du projet (LFPoulain) une licence
   mondiale, gratuite, non exclusive, perpétuelle et irrévocable pour
   utiliser, reproduire, modifier et distribuer votre contribution sous
   d’autres conditions, y compris commerciales, et pour en accorder des
   sous-licences.

Vous restez titulaire de vos droits sur votre contribution. Cette licence
supplémentaire permet au mainteneur de continuer à proposer des accords
séparés pour l’usage commercial de SuperMenu, ou de changer un jour la licence
du projet, sans devoir obtenir l’accord de chaque contributeur. Si vous ne
pouvez pas l’accorder (par exemple pour du code repris d’un autre projet),
signalez-le dans la pull request.

## Organisation du dépôt

```text
shared/supermenu_core/   cœur commun : fournisseurs IA, prompts, validateurs, composants Qt
win32/                   application Windows : Win32, presse-papiers, Foundry Local, installateur
macos/                   application macOS : AppKit, Accessibilité, helpers Swift, DMG
.github/workflows/       CI, bêta roulante et releases Stable
```

**Règle d’architecture** : `shared/` n’importe jamais de code de plateforme
(AppKit, PyObjC, pywin32, `winreg`, `foundry_local`, `win32/src`,
`macos/src`…). Le test `shared/tests/test_architecture.py` le vérifie et
n’autorise qu’une courte liste de dépendances tierces dans le cœur. Ce qui
dépend du système (raccourcis globaux, presse-papiers, fenêtre cible,
insertion, permissions, stockage, packaging) reste dans `win32/` ou `macos/`.

## Préparer l’environnement

L’installation se lance toujours depuis le sous-projet choisi : son fichier
`requirements.txt` installe le paquet local `../shared` en mode éditable.

### Windows

Windows 10 ou 11, Python 3.11 minimum (exigé par le SDK Foundry Local) ;
Python 3.12 est recommandé et sert aux versions publiées. Foundry Local
fonctionne sous Windows 11 24H2 ou plus récent.

```powershell
cd win32
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

### macOS

Mac Apple Silicon et Python 3.12. Les composants Apple Foundation Models et
Apple Speech demandent Xcode 26+ avec le SDK macOS 26+ ; les autres
fournisseurs fonctionnent sans eux.

```bash
cd macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
bash scripts/build_foundation_helper.sh   # facultatif : Apple Foundation Models
bash scripts/build_speech_helper.sh       # facultatif : Apple Speech
python run.py
```

En développement, macOS demande l’autorisation **Accessibilité** pour le
processus qui lance l’application (Terminal, votre éditeur ou Python), et non
pour `SuperMenu.app`.

## Tester et vérifier

Depuis `win32/` ou `macos/`, lancez les mêmes contrôles que la CI :

```text
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
```

Sur macOS, ajoutez le smoke test natif :

```bash
python run.py --smoke-test
```

Les tests Qt peuvent tourner sans affichage avec la variable
`QT_QPA_PLATFORM=offscreen`, comme dans la CI macOS. Les tests ne doivent
dépendre ni du réseau, ni d’une vraie clé API, ni d’un micro : utilisez les
faux objets et les serveurs locaux déjà présents dans les suites.

Si vous ne disposez que d’une plateforme, lancez au moins la suite partagée et
celle de votre système : la CI exécute les deux plateformes sur chaque pull
request.

Pour construire un exécutable localement :

- Windows : `pyinstaller --noconfirm --clean SuperMenu.spec`, puis, dans
  PowerShell,
  `(Start-Process -FilePath dist\SuperMenu.exe -ArgumentList "--smoke-test" -Wait -PassThru).ExitCode`,
  qui doit afficher `0` ;
- macOS : `bash scripts/build_dmg.sh` produit un DMG de développement non
  signé (voir [macos/SIGNING.md](macos/SIGNING.md) pour la signature).

## Style et règles de code

- Suivez le style du fichier que vous modifiez. `black` est installé avec les
  dépendances de développement mais n’est pas imposé : ne reformatez pas un
  fichier existant en entier, cela noierait votre changement dans le diff.
- Seules les erreurs `flake8 --select=F,E9` bloquent la CI ; évitez tout de
  même d’ajouter de nouveaux avertissements.
- Le code doit fonctionner avec Python 3.11 et 3.12.
- Les textes de l’interface sont en français et vouvoient l’utilisateur.
- Les journaux ne contiennent jamais de clé API, de texte sélectionné, de
  contenu de prompt ni de transcription : journalisez au plus une longueur.
- Ne bloquez pas le thread Qt (`sleep`, attente réseau, boîte de dialogue
  modale dans un rappel) : utilisez des signaux, des minuteurs ou un thread.
- Les réglages (`SuperMenu.ini`) et les bibliothèques de prompts existants
  doivent rester lisibles après votre changement. Une donnée invalide est
  réparée ou ignorée, jamais effacée en silence.
- Une fonction réservée aux **fonctions avancées** ou **expérimentales** se
  contrôle avec `advanced_enabled()` ou `experimental_enabled()`
  (`shared/supermenu_core/config/feature_modes.py`), lus au moment de
  l’usage. Quand l’interrupteur est désactivé, la fonction est masquée et
  ignorée, mais ses réglages ne sont jamais supprimés.
- Les dépendances sont épinglées à une version exacte. Un ajout ou une mise à
  jour de dépendance se discute d’abord dans une issue et fait l’objet d’une
  pull request dédiée.
- Messages de commit courts, en anglais, à l’impératif (par exemple
  `Fix clipboard restore after direct insertion`).

## Proposer une modification

1. **Ouvrez d’abord une issue** pour une nouvelle fonction ou un changement de
   comportement, afin de valider l’idée avant d’écrire le code. Une petite
   correction évidente peut partir directement en pull request.
2. Créez une branche à partir de `main` dans votre fork.
3. Gardez la pull request **petite et ciblée** : un sujet par pull request,
   sans reformatage ni refactorisation sans rapport.
4. **Ajoutez des tests** : un correctif est accompagné d’un test qui échoue
   sans lui ; une nouvelle fonction est couverte par des tests.
5. Mettez à jour la documentation concernée (guides d’utilisation,
   `ARCHITECTURE.md`) et ajoutez une ligne dans la section « Non publié » de
   [CHANGELOG.md](CHANGELOG.md) si le changement est visible pour
   l’utilisateur.
6. Ne modifiez ni `win32/VERSION`, ni `macos/VERSION`, ni les notes de release
   (`.github/BETA_NOTES.md`, `.github/STABLE_NOTES.md`) : le mainteneur s’en
   charge au moment de publier (voir [docs/RELEASING.md](docs/RELEASING.md)).
7. Ouvrez la pull request en remplissant le modèle proposé, puis attendez que
   la CI soit verte.

## CI et forks

Une pull request ouverte depuis un fork déclenche la CI : tests Windows
(Python 3.11 et 3.12), tests macOS et construction d’un DMG. GitHub ne
transmet pas les secrets du dépôt à une pull request venant d’un fork : ce DMG
est donc **non signé**, joint au run sous le nom
`SuperMenu-macOS-arm64-unsigned-test` et réservé aux essais. Pour une première
contribution, GitHub peut demander au mainteneur d’approuver l’exécution de la
CI.

Aucune release n’est publiée depuis une pull request ou un fork. La bêta
roulante et les versions Stable ne sont construites que depuis `main` et les
tags du dépôt principal. Dans votre propre fork, les workflows **Beta Release**
et **Stable Release** échouent faute de secrets Apple et ne publient rien ; vous
pouvez les désactiver dans l’onglet **Actions** de votre fork.
