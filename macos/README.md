# SuperMenu pour macOS

[![macOS CI](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml/badge.svg)](https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml)
![Apple Silicon](https://img.shields.io/badge/architecture-Apple%20Silicon-000000?logo=apple)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Distribution](https://img.shields.io/badge/distribution-DMG%20notari%C3%A9-success)

SuperMenu pour macOS est une application de barre des menus dédiée au travail
sur du texte. Elle lit la sélection de l’application active, propose les
prompts configurés, interroge OpenAI ou un endpoint local et peut réinsérer la
réponse dans la cible d’origine. Sur macOS 26+, la bêta propose aussi le modèle
local Apple Intelligence via Foundation Models.

Cette composition est indépendante de Windows : elle possède ses intégrations
AppKit, ses permissions, son stockage, ses tests et son packaging. La logique
métier et les composants Qt génériques proviennent de `../shared`.

## Ce que propose la version macOS

- menu universel de prompts avec `Cmd+Shift+Space` par défaut ;
- mode personnalisé avec `Cmd+Shift+M` ;
- raccourcis globaux attribuables à des prompts individuels ;
- lecture du texte sélectionné et restauration prudente du presse-papiers ;
- réponse affichée, copiée ou réinsérée dans l’application d’origine ;
- OpenAI, Ollama, LM Studio et Apple Intelligence local (bêta, macOS 26+) ;
- prompts modifiables, réordonnables, importables et exportables ;
- thèmes clair, sombre et automatique ;
- mises à jour Stable/Beta dirigées vers le DMG Apple Silicon exact.

La bêta inclut la dictée en direct via OpenAI ou Apple Speech sur macOS 26+.
Le moteur vocal se choisit indépendamment du moteur de texte, dans
**Paramètres > Dictée** : sélectionnez le moteur, vérifiez sa
disponibilité, téléchargez le modèle de langue Apple si nécessaire puis enregistrez.
Apple Speech est le framework de reconnaissance vocale ; Foundation Models reste
le moteur de génération de texte. La dictée Apple fonctionne sur l’appareil.
OpenAI utilise GPT Live Transcribe, une clé API et la facturation OpenAI.

Les paramètres sont répartis en **Texte**, **Dictée**, **Raccourcis** et
**Application**, avec les options avancées repliées. Dans Dictée, **Tester le
micro** vérifie l’entrée choisie pendant cinq secondes sans conserver ni
transmettre d’audio. La préparation distingue la vérification, le téléchargement
éventuel et le chargement en mémoire du modèle installé.

L’accès au microphone est demandé au lancement d’une dictée ou du test du micro.
Ouvrez **Dicter du texte…** dans le menu de barre des menus ou dans le menu des
prompts. Le texte et le niveau du microphone apparaissent en direct. **Terminer**
arrête le microphone et ouvre le résultat à copier ou à insérer ; **Annuler**
interrompt la capture et le moteur. Durée maximale : cinq minutes par dictée.
La composition macOS ne propose pas de capture d’écran.

## Installer l’application

1. Ouvrez les [releases SuperMenu](https://github.com/lfpoulain/SuperMenu/releases).
2. Téléchargez `SuperMenu-macOS-arm64.dmg` pour Stable ou
   `SuperMenu_Beta-macOS-arm64.dmg` pour Beta.
3. Ouvrez le DMG et glissez `SuperMenu.app` dans `/Applications`.
4. Lancez SuperMenu depuis `/Applications`.
5. Cliquez sur **Configurer Accessibilité…** et acceptez le dialogue macOS.

Les DMG publiés sont signés avec Developer ID, notariés par Apple et destinés
aux Mac Apple Silicon. Installer les versions suivantes au même emplacement
permet à macOS de reconnaître la même application et de conserver normalement
l’autorisation Accessibilité.

Le [guide d’utilisation](docs/GUIDE_UTILISATION.md) détaille l’installation,
les paramètres, les prompts, les mises à jour et le dépannage.

## Autorisation macOS

SuperMenu utilise uniquement **Accessibilité** pour :

- observer les raccourcis clavier globaux ;
- lire la sélection via l’API d’accessibilité lorsqu’elle est disponible ;
- émettre les commandes Copier/Coller nécessaires au chemin de repli.

Le premier clic sur **Configurer Accessibilité…** laisse macOS présenter son
dialogue natif. Si l’accès n’est toujours pas accordé, le bouton devient
**Ouvrir les réglages…**. Une fois la permission activée, SuperMenu recharge ses
moniteurs sans exiger un redémarrage dans le fonctionnement normal.

## Utilisation rapide

1. Sélectionnez du texte dans Mail, Notes, Safari, un éditeur ou une autre
   application.
2. Appuyez sur `Cmd+Shift+Space`.
3. Choisissez un prompt.
4. Dans la fenêtre de réponse, utilisez **Copier**, **Écrire** ou
   **Réessayer**.

Un prompt peut aussi activer **Insérer directement la réponse dans
l’application cible**. Dans ce cas, SuperMenu affiche un indicateur près du
curseur et réinsère la réponse sans ouvrir la fenêtre de résultat.

## Configuration et diagnostic

La fenêtre de configuration contient trois onglets :

- **Prompts** : catalogue, ordre, instructions, insertion directe et raccourcis ;
- **Paramètres** : fournisseur IA, modèles, raccourcis, permission, thème et
  canal de mise à jour ;
- **À propos** : version, mise à jour, dossier de configuration, journaux et
  releases.

Les fichiers utilisateur se trouvent ici :

```text
~/Library/Application Support/SuperMenu/SuperMenu.ini
~/Library/Logs/SuperMenu/supermenu.log
~/Library/Logs/SuperMenu/native-crash.log
```

La configuration est limitée au compte utilisateur (`0600`). Les journaux ne
contiennent ni clé API, ni texte sélectionné, ni contenu de prompt.

## Développer sur un Mac

Python 3.12 est la version de référence. Pour compiler le composant Apple ou un
DMG, utilisez Xcode 26+ avec son SDK macOS 26+. Les autres fournisseurs restent
utilisables sur les versions de macOS antérieures prises en charge.

```bash
cd macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
bash scripts/build_foundation_helper.sh
python run.py
```

L’installation doit être lancée depuis `macos/`, car `requirements.txt`
référence le package local `../shared`.

En développement, macOS autorise le processus qui exécute l’application — par
exemple Terminal ou Python — tandis qu’un build installé autorise
`SuperMenu.app`.

### Validation locale

```bash
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
python run.py --smoke-test
```

### Construire un DMG de développement

```bash
bash scripts/build_dmg.sh
```

Le résultat est écrit dans :

```text
dist/SuperMenu-<version>-macOS-arm64.dmg
```

Sans identité Developer ID, le script produit un paquet de développement. Les
releases publiques exigent au contraire la signature, le Hardened Runtime, la
notarisation et l’agrafage des tickets au `.app` puis au DMG. La procédure est
documentée dans [SIGNING.md](SIGNING.md).

## Organisation

```text
macos/
├── src/
│   ├── api/          # adaptation texte du client IA partagé
│   ├── config/       # réglages, versions et stockage macOS
│   ├── ui/           # fenêtre de configuration et compositions Qt
│   └── utils/        # AppKit, permissions, raccourcis, sélection et insertion
├── docs/             # guides utilisateur et architecture
├── resources/        # icônes et ressources du bundle
├── scripts/          # build, signature et notarisation
├── tests/            # tests fonctionnels et garde-fous de distribution
├── run.py             # point d’entrée développement / bundle
└── SuperMenu-macos.spec
```

Pour comprendre les flux AppKit, la cible d’insertion, les attentes
asynchrones et les frontières avec le cœur partagé, consultez
[l’architecture macOS](docs/ARCHITECTURE.md).

## Documentation macOS

- [Guide d’utilisation](docs/GUIDE_UTILISATION.md)
- [Architecture technique](docs/ARCHITECTURE.md)
- [Signature et notarisation](SIGNING.md)
- [Roadmap historique de la V1](ROADMAP.md)

Retour au [README principal](../README.md).
