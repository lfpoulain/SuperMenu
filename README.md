# SuperMenu

SuperMenu est désormais organisé en deux applications autonomes. Elles suivent
la même séparation métier, mais ne partagent aucun code d’exécution :

- [`win32/`](win32/) : application Windows historique, avec ses dépendances,
  ses tests et son installateur Inno Setup ;
- [`macos/`](macos/) : adaptation macOS indépendante, avec ses dépendances,
  ses tests et son image disque DMG.

Chaque sous-projet contient son propre point d’entrée, son fichier `VERSION`,
ses ressources et les couches `api/`, `config/`, `ui/` et `utils/`.

La version macOS est volontairement limitée aux fonctions texte. Elle ne
contient ni transcription, ni enregistrement, ni capture d’écran. Consultez
[`macos/README.md`](macos/README.md) pour la lancer ou construire le DMG, et
[`macos/ROADMAP.md`](macos/ROADMAP.md) pour suivre la V1.
