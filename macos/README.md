# SuperMenu pour macOS

[![CI](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml/badge.svg)](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml)
![Apple Silicon](https://img.shields.io/badge/architecture-Apple%20Silicon-000000?logo=apple)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Distribution](https://img.shields.io/badge/distribution-DMG%20notaris%C3%A9-success)
![Licence](https://img.shields.io/badge/licence-PolyForm%20Noncommercial%201.0.0-lightgrey)

SuperMenu pour macOS vit dans la barre des menus et travaille sur le texte de
n’importe quelle application. Sélectionnez un passage, appuyez sur un
raccourci et choisissez un prompt : la réponse de l’IA s’affiche, se copie ou
se réinsère dans l’application d’origine.

Ce dossier contient l’application macOS : intégrations AppKit, autorisations,
stockage, composants natifs Swift, tests et packaging. Le client IA, les
prompts et les composants d’interface communs viennent du cœur partagé avec
Windows, [`shared/supermenu_core`](../shared/README.md).

## Fonctionnalités

**Toujours disponibles**

- menu des prompts avec `Cmd+Shift+Space`, mode personnalisé avec
  `Cmd+Shift+M` ;
- lecture de la sélection par Accessibilité, avec repli prudent par le
  presse-papiers ;
- fenêtre de réponse avec **Réessayer**, **Copier**, **Voir le raisonnement**
  et **Insérer le texte**, ou insertion directe dans l’application d’origine ;
- moteurs de texte : OpenAI, Ollama ou LM Studio (y compris les modèles
  partagés par LM Link) et Apple Intelligence, local, sur macOS 26 ou plus
  récent ;
- prompts modifiables, réordonnables, importables et exportables, avec un
  raisonnement réglable pour chacun ;
- thèmes clair, sombre et automatique, mises à jour Stable ou Bêta vers le DMG
  Apple Silicon.

**Fonctions avancées**, à activer

- modèle, fournisseur ou poste LM Link propre à chaque prompt ;
- raccourci global propre à chaque prompt ;
- durée de conservation en mémoire du modèle vocal Apple Speech.

**Fonctions expérimentales**, à activer

- prompts vocaux, sous-menu **Voix** du menu des prompts et entrée **Dicter du
  texte…** de la barre des menus ;
- dictée en direct avec OpenAI GPT Live Transcribe (clé API et facturation
  OpenAI) ou Apple Speech, sur l’appareil, sous macOS 26 ou plus récent ;
- dictée instantanée par raccourci et test du micro.

Les deux interrupteurs se trouvent dans **Réglages > Application > Fonctions**.
Une nouvelle installation démarre avec les deux désactivés ; une mise à jour
depuis une version précédente les active tous les deux, pour ne retirer aucune
fonction déjà utilisée. Les désactiver masque ces fonctions sans supprimer
aucun réglage. Voir le
[guide d’utilisation](docs/GUIDE_UTILISATION.md#fonctions-avancées-et-expérimentales).

La capture d’écran est propre à Windows : SuperMenu ne demande pas
l’autorisation Enregistrement de l’écran sur Mac.

## Installation

Configuration requise : Mac Apple Silicon sous macOS 13 Ventura ou plus
récent. Les builds sont construits et testés sur macOS 14 et 15 ; Apple
Intelligence et Apple Speech demandent macOS 26 ou plus récent.

1. Ouvrez la [dernière release](https://github.com/lfpoulain/SuperMenu/releases/latest).
2. Téléchargez `SuperMenu-macOS-arm64.dmg` (Stable) ou, dans la release
   `beta`, `SuperMenu_Beta-macOS-arm64.dmg`.
3. Ouvrez le DMG et glissez `SuperMenu.app` dans **Applications**.
4. Lancez SuperMenu depuis `/Applications`.
5. Cliquez sur **Configurer Accessibilité…** et acceptez le dialogue de macOS.

Les DMG publiés sont signés avec un certificat Developer ID et notarisés par
Apple. Installez toujours les versions suivantes au même emplacement : macOS
reconnaît ainsi la même application et conserve l’autorisation Accessibilité.

## Autorisations

**Accessibilité** est la seule autorisation nécessaire au fonctionnement
courant. SuperMenu l’utilise pour :

- observer les raccourcis clavier globaux ;
- lire la sélection quand l’application l’expose ;
- envoyer `Cmd+C` et `Cmd+V` pour le repli par le presse-papiers et
  l’insertion.

Le premier clic sur **Configurer Accessibilité…** laisse macOS afficher son
dialogue. Si l’accès n’est toujours pas accordé, le bouton devient **Ouvrir
les réglages…**. Une fois l’autorisation accordée, SuperMenu recharge ses
raccourcis sans redémarrage, même si sa fenêtre a été fermée entre-temps.

Le **Microphone** n’est demandé qu’au lancement d’une dictée ou du test du
micro. SuperMenu ne demande pas **Surveillance de l’entrée**.

## Premiers pas

1. Cliquez sur l’icône de SuperMenu dans la barre des menus, puis sur
   **Ouvrir SuperMenu**.
2. Dans **Réglages > Texte**, choisissez le **Moteur de texte** : OpenAI avec
   votre clé API, Ollama / LM Studio avec l’adresse du serveur, ou
   **Apple Intelligence — local**. Cliquez sur **Enregistrer**.
3. Sélectionnez du texte dans Mail, Notes, Safari ou une autre application,
   appuyez sur `Cmd+Shift+Space` et choisissez un prompt.

L’icône de la barre des menus propose **Ouvrir SuperMenu**, **Afficher le
menu des prompts**, **Dicter du texte…** (fonctions expérimentales),
**Afficher la dernière réponse**, **Vérifier les mises à jour**,
**Autorisations macOS…** et **Quitter**.

## Données et confidentialité

```text
~/Library/Application Support/SuperMenu/SuperMenu.ini
~/Library/Logs/SuperMenu/supermenu.log
~/Library/Logs/SuperMenu/native-crash.log
```

- La configuration, clés API comprises, est lisible uniquement par votre
  compte (`0600`). SuperMenu n’utilise pas le Trousseau.
- Les journaux ne contiennent ni clé API, ni texte sélectionné, ni contenu de
  prompt, ni touche tapée.
- Avec Apple Intelligence et Apple Speech, le texte et la voix restent sur le
  Mac. Aucun fichier audio n’est enregistré.
- **Réglages > Application > Dossiers et diagnostic** ouvre le dossier de
  configuration et celui des journaux.

## Développer sur un Mac

Python 3.12 est la version de référence. Les composants natifs Apple
(Foundation Models et Apple Speech) se compilent avec Xcode 26 ou plus récent
et son SDK macOS 26. Sans eux, l’application fonctionne avec OpenAI, Ollama et
LM Studio.

```bash
git clone https://github.com/lfpoulain/SuperMenu.git
cd SuperMenu/macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
bash scripts/build_foundation_helper.sh   # facultatif : Apple Intelligence
bash scripts/build_speech_helper.sh       # facultatif : Apple Speech
python run.py
```

Lancez l’installation depuis `macos/` : `requirements.txt` installe le cœur
partagé `../shared` en mode éditable. En développement, macOS accorde
Accessibilité au processus qui exécute l’application (Terminal ou Python, par
exemple) ; un build installé l’accorde à `SuperMenu.app`.

### Tests et vérifications

Les mêmes contrôles que la CI, depuis `macos/` :

```bash
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
python run.py --smoke-test
```

Les tests utilisent des doublures pour AppKit, Quartz et le presse-papiers :
ils s’exécutent aussi hors macOS, certains étant alors ignorés. Les modules
de test qui ont un équivalent Windows se terminent par `_mac.py`.

### Construire un DMG

```bash
bash scripts/build_dmg.sh
```

Le script compile les composants natifs, construit l’application avec
PyInstaller, refuse un bundle qui contient un lien symbolique cassé, exécute
le smoke test, vérifie la présence des licences et écrit
`dist/SuperMenu-<version>-macOS-arm64.dmg`. Sans identité Developer ID,
il produit un paquet de développement, ni signé ni notarisé pour la
distribution. Les releases publiques
exigent la signature, le Hardened Runtime, la notarisation et l’agrafage des
tickets, assurés par les workflows de publication du dépôt : voir
[Packaging et notarisation](docs/ARCHITECTURE.md#packaging-et-notarisation).

## Organisation

```text
macos/
├── src/
│   ├── api/          # client texte partagé et Apple Foundation Models
│   ├── audio/        # moteurs de dictée (OpenAI, Apple Speech)
│   ├── config/       # réglages, version et canal
│   ├── ui/           # fenêtre de configuration, barre des menus, réponse
│   └── utils/        # AppKit, Accessibilité, raccourcis, sélection, insertion
├── native/           # composants Swift : Foundation Models et Apple Speech
├── docs/             # guide d’utilisation et architecture
├── resources/        # icônes
├── scripts/          # composants natifs, DMG, signature et notarisation
├── tests/
├── entitlements.plist
├── run.py            # point d’entrée (développement et bundle)
└── SuperMenu-macos.spec
```

## Documentation

- [Guide d’utilisation](docs/GUIDE_UTILISATION.md)
- [Architecture technique](docs/ARCHITECTURE.md)
- [Cœur partagé](../shared/README.md)
- [Contribuer](../CONTRIBUTING.md)
- [Journal des modifications](../CHANGELOG.md)
- [README principal](../README.md)

## Licence

SuperMenu est distribué sous licence
[PolyForm Noncommercial 1.0.0](../LICENSE), qui n’autorise que les usages non
commerciaux ; le texte de la licence fait foi. Les composants tiers embarqués
et leurs licences sont listés dans
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
