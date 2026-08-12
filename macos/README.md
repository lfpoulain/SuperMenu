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
