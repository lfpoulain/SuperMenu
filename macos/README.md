# SuperMenu macOS

Cette application est la composition macOS de SuperMenu. Elle utilise
`../shared/supermenu_core` pour le métier et les widgets Qt génériques, sans
jamais charger le sous-projet Windows. Les intégrations AppKit, les permissions,
le presse-papiers et l'insertion restent locales à `macos/src`.

```text
SuperMenu/
├── shared/supermenu_core/  # fournisseurs, modèles, prompts et UI commune
└── macos/
    ├── src/
    │   ├── api/       # configuration texte du client partagé
    │   ├── config/    # stockage et réglages propres au Mac
    │   ├── ui/        # composition et permissions
    │   └── utils/     # AppKit, raccourcis, cible et insertion
    ├── tests/
    ├── resources/
    ├── scripts/
    ├── run.py
    └── SuperMenu-macos.spec
```

## Lancer en développement sur un Mac

Python 3.12 est la version de référence pour la V1.

```bash
cd macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

L'installation doit être lancée depuis `macos/` : la première ligne de
`requirements.txt` installe alors le package local `../shared`.

Au premier lancement, autorisez le processus de développement (Terminal ou
Python) dans **Réglages Système > Confidentialité et sécurité >
Accessibilité** et **Surveillance de l’entrée**, puis relancez-le. Une fois
l’application packagée, c’est `SuperMenu.app` qu’il faudra autoriser. Ces deux
droits servent uniquement aux raccourcis globaux et aux commandes Copier/Coller.
Aucun droit Microphone ou Enregistrement de l’écran n’est utilisé.

Tous les raccourcis partagent deux moniteurs AppKit persistants : le moniteur
global reçoit les touches destinées aux autres applications et le moniteur
local couvre SuperMenu lorsqu’il est actif, conformément au fonctionnement
documenté par Apple. Modifier un raccourci met à jour les liaisons sans recréer
ces moniteurs. `pynput` reste limité aux commandes Copier/Coller.
L’enregistreur tient compte de l’inversion Command/Control appliquée par défaut
par Qt sur macOS : les noms affichés correspondent donc aux touches physiques.

L’affichage des fenêtres demande d’abord l’activation moderne et coopérative
d’AppKit. L’ancienne activation forcée n’est utilisée qu’en repli de
compatibilité si macOS n’a pas honoré la demande dans le délai attendu.

La version macOS n’utilise pas le Trousseau afin d’éviter ses demandes lors
des builds de test non signés. La clé OpenAI et l'éventuel jeton distinct d'un
endpoint personnalisé sont enregistrés dans
`~/Library/Application Support/SuperMenu/SuperMenu.ini`, dont l’accès est
limité au compte utilisateur. Elle devra être saisie une première fois après
le passage depuis une version qui utilisait le Trousseau.

## Diagnostic

Les journaux sont conservés dans `~/Library/Logs/SuperMenu`. Le fichier
`supermenu.log` trace le chemin complet d’un raccourci (événement AppKit,
détection, passage au thread Qt, activation macOS et affichage du menu) ainsi
que les erreurs Python.
`native-crash.log` conserve une trace des crashs natifs éventuels. Aucun de ces
fichiers ne contient la clé API, le texte sélectionné ou le contenu des prompts.

Le menu des prompts peut aussi être ouvert depuis l’icône SuperMenu dans la
barre des menus ou depuis **Paramètres > Test sans raccourci**. Ce chemin permet
de vérifier séparément l’affichage du menu et l’écoute du raccourci global.

Les doublons de raccourcis sont comparés après normalisation. Par exemple,
`Command+Shift+<` et `Cmd+Shift+<` sont considérés comme le même raccourci et le
second est refusé sans remplacer le premier.

## Valider la source

```bash
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
python run.py --smoke-test
```

Le workflow CI commun exécute ces validations sur macOS, puis construit aussi
un DMG de test. Une modification du cœur partagé doit donc rester compatible
avec les deux plateformes avant toute publication bêta.

## Construire le `.app` et le DMG

```bash
bash scripts/build_dmg.sh
```

Le résultat est écrit dans `dist/SuperMenu-<version>-macOS.dmg`. Le volume
contient `SuperMenu.app` et un raccourci vers `/Applications`, pour une
installation par glisser-déposer.

La première V1 est volontairement non signée. Pour une diffusion à des tiers,
la prochaine étape recommandée sera une signature Developer ID et une
notarisation Apple ; cela ne nécessite pas le Mac App Store et ne change pas
l’architecture de l’application.
