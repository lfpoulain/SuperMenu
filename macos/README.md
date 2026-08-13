# SuperMenu macOS

Cette application est une adaptation macOS autonome de SuperMenu. Son code ne
charge aucun module du sous-projet Windows. L’organisation métier reste la même :

```text
macos/
├── src/
│   ├── api/       # appels OpenAI, Ollama et LM Studio
│   ├── config/    # modèles, prompts et réglages persistants
│   ├── ui/        # configuration, saisie et réponse
│   └── utils/     # raccourcis, presse-papiers, permissions et insertion
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

Au premier lancement, autorisez le processus de développement (Terminal ou
Python) dans **Réglages Système > Confidentialité et sécurité >
Accessibilité** et **Surveillance de l’entrée**, puis relancez-le. Une fois
l’application packagée, c’est `SuperMenu.app` qu’il faudra autoriser. Ces deux
droits servent uniquement aux raccourcis globaux et aux commandes Copier/Coller.
Aucun droit Microphone ou Enregistrement de l’écran n’est utilisé.

Tous les raccourcis partagent un seul écouteur macOS persistant. Modifier un
raccourci ou revérifier les autorisations met à jour ses liaisons sans arrêter
ni recréer le tap clavier natif. SuperMenu s’appuie directement sur le listener
macOS standard de `pynput`, sans surcharger ses callbacks Darwin privés.
L’enregistreur tient compte de l’inversion Command/Control appliquée par défaut
par Qt sur macOS : les noms affichés correspondent donc aux touches physiques.

L’affichage des fenêtres demande d’abord l’activation moderne et coopérative
d’AppKit. L’ancienne activation forcée n’est utilisée qu’en repli de
compatibilité si macOS n’a pas honoré la demande dans le délai attendu.

La version macOS n’utilise pas le Trousseau afin d’éviter ses demandes lors
des builds de test non signés. La clé API est enregistrée dans
`~/Library/Application Support/SuperMenu/SuperMenu.ini`, dont l’accès est
limité au compte utilisateur. Elle devra être saisie une première fois après
le passage depuis une version qui utilisait le Trousseau.

## Diagnostic

Les journaux sont conservés dans `~/Library/Logs/SuperMenu`. Le fichier
`supermenu.log` trace le chemin complet d’un raccourci (détection, passage au
thread Qt, activation macOS et affichage du menu) ainsi que les erreurs Python.
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
python -m compileall -q src run.py
python -m pytest -q
python -m flake8 src tests run.py --select=F,E9
python run.py --smoke-test
```

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
