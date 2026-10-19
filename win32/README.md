# SuperMenu pour Windows

[![CI](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml/badge.svg)](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml)
![Plateforme](https://img.shields.io/badge/plateforme-Windows%2010%20%7C%2011-0078D4)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![Licence](https://img.shields.io/badge/licence-PolyForm%20Noncommercial%201.0.0-lightgrey)

SuperMenu amène l’IA dans toutes vos applications Windows. Sélectionnez un
texte, appuyez sur un raccourci et choisissez une action : corriger,
reformuler, résumer, traduire ou suivre une instruction libre. La réponse
s’affiche dans une fenêtre, d’où vous pouvez la copier ou l’insérer, ou
remplace directement la sélection.

Ce dossier contient l’application Windows : raccourcis globaux, presse-papiers,
insertion, capture d’écran, Foundry Local et installateur. Le client IA, les
prompts et les composants d’interface communs viennent du cœur partagé avec
macOS, [`shared/supermenu_core`](../shared/README.md).

## Fonctionnalités

**Toujours disponibles**

- menu des prompts au curseur, avec `Ctrl+²` par défaut ;
- mode personnalisé pour une instruction libre, avec `Ctrl+Alt+M` ;
- fenêtre de réponse avec **Réessayer**, **Copier**, **Voir le raisonnement**
  et **Insérer le texte** ;
- insertion directe : pour les prompts qui l’activent, la réponse remplace la
  sélection sans fenêtre intermédiaire ;
- prompts modifiables, réordonnables, importables et exportables, avec un
  raisonnement réglable pour chacun ;
- moteurs de texte : OpenAI (`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`,
  `gpt-5.4`), Ollama ou LM Studio (y compris les modèles partagés par LM Link),
  et l’IA locale Microsoft Foundry Local avec Qwen3.5 4B ou 9B, sans clé API,
  sur Windows 11 24H2 ou plus récent ([détails](docs/foundry-local.md)) ;
- thèmes sombre, clair ou automatique, mises à jour Stable ou Bêta.

**Fonctions avancées**, à activer

- modèle, fournisseur ou poste LM Link propre à chaque prompt ;
- raccourci direct par prompt ;
- durée de conservation en mémoire des modèles locaux (texte et voix).

**Fonctions expérimentales**, à activer

- prompts vocaux et menu vocal, avec `Ctrl+Alt+²` ;
- dictée en direct avec OpenAI GPT Live Transcribe (clé API et facturation
  OpenAI) ou avec Nemotron 3.5 via Foundry Local, sur le PC (modèle de 756 Mo) ;
- dictée instantanée par raccourci et test du micro ;
- capture et analyse d’écran, avec `Ctrl+Alt+&`.

Les deux interrupteurs se trouvent dans **Réglages > Application > Fonctions**.
Une nouvelle installation démarre avec les deux désactivés ; une mise à jour
depuis une version précédente les active tous les deux, pour ne retirer aucune
fonction déjà utilisée. Les désactiver masque ces fonctions sans supprimer
aucun réglage. Le [guide d’utilisation](docs/GUIDE_UTILISATION.md#fonctions-avancées-et-expérimentales)
détaille leur fonctionnement.

## Installation

Configuration requise : Windows 10 ou 11, 64 bits. Foundry Local demande
Windows 11 24H2 ou plus récent.

1. Téléchargez `SuperMenu_Setup.exe` depuis la
   [dernière release](https://github.com/lfpoulain/SuperMenu/releases/latest).
2. Lancez-le. L’installateur demande les droits administrateur, affiche la
   licence et propose deux options : un raccourci sur le Bureau et le
   démarrage avec Windows.
3. À la fin de l’installation, SuperMenu démarre et se place dans la zone de
   notification.

| Fichier | Usage |
|---|---|
| `SuperMenu_Setup.exe` | installateur, canal Stable (recommandé) |
| `SuperMenu.exe` | version portable, sans installation |
| `SuperMenu_Beta_Setup.exe` et `SuperMenu_Beta.exe` | canal Bêta, dans la release `beta` |
| `SHA256SUMS.txt` (Bêta : `SHA256SUMS-beta.txt`) | empreintes SHA-256 des fichiers publiés |

Les exécutables ne portent pas de signature Authenticode : Windows SmartScreen
peut afficher un avertissement au premier lancement. Pour vérifier un
téléchargement, comparez le résultat de
`Get-FileHash .\SuperMenu_Setup.exe` à la ligne correspondante de
`SHA256SUMS.txt`.

## Mises à jour

- Le canal (**Stable** ou **Bêta**) se choisit dans **Réglages > Application >
  Interface et mises à jour**, qui propose aussi **Vérifier les mises à
  jour**. Le menu de la zone de notification offre la même vérification, et la
  version installée vérifie discrètement au démarrage de SuperMenu, au plus
  une fois par jour.
- La Bêta est reconstruite automatiquement après chaque modification de `main`
  dont la CI réussit. Elle peut contenir des régressions.
- SuperMenu lit un petit manifeste publié avec la release, puis l’API GitHub
  en secours. L’installateur est téléchargé dans un dossier temporaire privé ;
  son empreinte SHA-256 est comparée à celle du manifeste, puis vérifiée de
  nouveau juste avant son lancement. Un fichier différent est supprimé et
  n’est jamais exécuté.
- L’installateur est lancé avec vos droits : Windows demande lui-même la
  confirmation administrateur. Après l’installation, SuperMenu redémarre avec
  vos droits habituels, jamais en administrateur.
- La version portable ne se met pas à jour elle-même : **Vérifier les mises
  à jour** signale une version plus récente et ouvre la page des
  téléchargements.
- La configuration, les prompts, les clés et les modèles locaux sont conservés.

## Premiers pas

1. Ouvrez la configuration : double-cliquez sur l’icône de la zone de
   notification, ou choisissez **Ouvrir SuperMenu** dans son menu.
2. Dans **Réglages > Texte**, choisissez le **Moteur de texte** : OpenAI avec
   votre clé API, Ollama / LM Studio avec l’adresse du serveur, ou
   **IA locale Microsoft — Foundry Local**, puis téléchargez un modèle Qwen.
   Cliquez sur **Enregistrer**.
3. Sélectionnez un texte dans n’importe quelle application, appuyez sur
   `Ctrl+²` et choisissez une action.

| Action | Raccourci par défaut | Disponible |
|---|---|---|
| Menu des prompts | `Ctrl+²` | toujours |
| Mode personnalisé | `Ctrl+Alt+M` | toujours |
| Menu vocal | `Ctrl+Alt+²` | avec les fonctions expérimentales |
| Capture d’écran | `Ctrl+Alt+&` | avec les fonctions expérimentales |
| Dictée instantanée | aucun | avec les fonctions expérimentales |
| Raccourci direct d’un prompt | aucun | avec les fonctions avancées |

`²` et `&` sont des touches du clavier AZERTY. Sur une autre disposition :

- sans touche `²` (QWERTY par exemple), `Ctrl+²` et `Ctrl+Alt+²` utilisent la
  touche située sous Échap : ``Ctrl+` `` et ``Ctrl+Alt+` `` en QWERTY ;
- quand `²` ne s’obtient qu’avec AltGr (QWERTZ allemand, AltGr+2), `Ctrl+²`
  utilise aussi la touche sous Échap (`Ctrl+^`), mais `Ctrl+Alt+²` reste
  `Ctrl+Alt+2`, c’est-à-dire AltGr+2 ;
- `&` suit la disposition : en QWERTY, `Ctrl+Alt+&` correspond à
  `Ctrl+Alt+Shift+7`.

Les réglages affichent toujours `Ctrl+²`. Tous les raccourcis se modifient dans
**Réglages > Raccourcis**.

## Données et confidentialité

| Élément | Emplacement |
|---|---|
| Configuration et prompts | `%USERPROFILE%\SuperMenu.ini` |
| Clé OpenAI et jeton d’endpoint | Gestionnaire d’identification Windows |
| Journaux | `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log` (`win32\logs\` depuis les sources) |
| Modèles locaux Foundry | `%LOCALAPPDATA%\SuperMenu\Foundry\cache\models` |

- La clé OpenAI et le jeton d’un endpoint privé sont stockés séparément et ne
  sont jamais envoyés à un autre fournisseur.
- Les journaux ne contiennent ni clé, ni texte sélectionné, ni instruction
  saisie, ni transcription.
- Aucun fichier audio n’est enregistré. Avec OpenAI, le son est transmis au
  service ; avec Nemotron, il reste sur le PC.
- À la désinstallation, une option supprime aussi la configuration, les
  journaux, les modèles locaux et les clés enregistrées.

## Développement

Prérequis : Windows 10 ou 11 64 bits, Python 3.11 ou 3.12 (la CI teste les
deux), Git. La construction de l’installateur demande aussi
[Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
git clone https://github.com/lfpoulain/SuperMenu.git
cd SuperMenu\win32
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

Lancez l’installation depuis `win32/` : `requirements.txt` installe le cœur
partagé `../shared` en mode éditable.

### Tests et vérifications

Les mêmes contrôles que la CI, depuis `win32/` :

```powershell
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
```

Les tests ne contactent aucun serveur réel. Pour qu’aucune fenêtre ne s’ouvre
pendant les tests Windows, définissez d’abord
`$env:QT_QPA_PLATFORM = "offscreen"` ; les tests du cœur partagé le font
d’eux-mêmes. Les modules de test propres à Windows qui ont un équivalent macOS
se terminent par `_win.py`.

### Construire l’exécutable et l’installateur

```powershell
pyinstaller --noconfirm --clean SuperMenu.spec
$smoke = Start-Process -FilePath dist\SuperMenu.exe -ArgumentList "--smoke-test" -Wait -PassThru
$smoke.ExitCode   # 0 attendu
iscc setup_supermenu.iss
```

PyInstaller écrit `dist\SuperMenu.exe` et `dist\third_party_licenses\`, la
liste des composants tiers embarqués. `iscc` produit `SuperMenu_Setup.exe`
dans `win32/`, avec la version lue dans `VERSION`.

### CI et publication

La CI (`.github/workflows/ci.yml`) teste le cœur partagé et Windows avec
Python 3.11 et 3.12, puis macOS avec Python 3.12 ; elle ne publie rien. La
Bêta roulante, reconstruite après chaque modification de `main`, et les
releases Stable, publiées sur un tag `vX.Y.Z`, sont produites par
`beta-release.yml` et `stable-release.yml`. Pour contribuer, lisez
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Documentation

- [Guide d’utilisation](docs/GUIDE_UTILISATION.md)
- [Foundry Local sous Windows](docs/foundry-local.md)
- [Architecture technique](docs/ARCHITECTURE.md)
- [Cœur partagé](../shared/README.md)
- [Journal des modifications](../CHANGELOG.md)
- [README principal](../README.md)

## Licence

SuperMenu est distribué sous licence
[PolyForm Noncommercial 1.0.0](../LICENSE), qui n’autorise que les usages non
commerciaux ; le texte de la licence fait foi. Les composants tiers embarqués
et leurs licences sont listés dans
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
