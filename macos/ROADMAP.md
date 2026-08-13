# Roadmap macOS V1

## Terminé dans la première implémentation

- [x] Isoler les intégrations natives de `win32/` et `macos/`.
- [x] Mutualiser le client IA, les modèles, les prompts et les widgets Qt
  génériques dans `shared/supermenu_core`.
- [x] Retirer transcription, enregistrement et capture d’écran du code macOS.
- [x] Remplacer les raccourcis système par une implémentation `pynput`/macOS.
- [x] Remplacer la gestion de fenêtre cible par AppKit.
- [x] Utiliser `Cmd+C` et `Cmd+V` avec restauration du presse-papiers.
- [x] Contrôler Accessibilité et Surveillance de l’entrée.
- [x] Adapter réglages, prompts, menu-bar et mises à jour au Mac.
- [x] Stocker la configuration dans `~/Library/Application Support/SuperMenu`.
- [x] Stocker les journaux dans `~/Library/Logs/SuperMenu`.
- [x] Préparer la construction native `.app` et le DMG glisser-déposer.
- [x] Ajouter les tests macOS et une CI commune aux deux plateformes.

## Validation V1 sur un vrai Mac

- [ ] Installer les dépendances et exécuter les tests sur Apple Silicon.
- [ ] Vérifier les demandes Accessibilité et Surveillance de l’entrée.
- [ ] Tester le raccourci principal dans TextEdit, Safari, Mail et Notes.
- [ ] Tester le menu de prompts, le mode personnalisé et les raccourcis directs.
- [ ] Tester l’insertion directe et la restauration du presse-papiers.
- [ ] Tester le retour vers l’application cible après une réponse asynchrone.
- [ ] Vérifier OpenAI, Ollama puis LM Studio.
- [ ] Construire le DMG, installer par glisser-déposer et relancer depuis
  `/Applications`.
- [ ] Corriger les écarts observés et figer la V1.

## Après la V1 fonctionnelle

- [ ] Ajouter la signature Developer ID et la notarisation pour la diffusion.
- [ ] Tester séparément un build Intel si ce matériel doit être supporté.
- [ ] Publier le DMG dans le workflow de release choisi.
