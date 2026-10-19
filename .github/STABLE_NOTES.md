## Nouveautés de SuperMenu 1.3.0

Version Stable recommandée pour une utilisation quotidienne, pour Windows (exécutable portable et installateur) et pour Mac Apple Silicon (DMG signé Developer ID et notarisé par Apple).

- **Fonctions avancées et expérimentales** : deux interrupteurs dans Réglages > Application > Fonctions. Les fonctions avancées regroupent le modèle et le raccourci propres à chaque prompt et la conservation des modèles locaux en mémoire ; les fonctions expérimentales, les prompts vocaux, la dictée et, sous Windows, la capture d’écran. Les deux sont activés après une mise à jour et désactivés sur une nouvelle installation ; les désactiver masque les fonctions sans supprimer aucun réglage.
- **Prompts** : modèle, fournisseur ou poste LM Link propre à chaque prompt, raisonnement réglable prompt par prompt, « Tout restaurer… » pour revenir aux prompts d’origine et « Revenir à la copie… » pour rétablir une version précédente. Une entrée invalide n’efface plus la bibliothèque.
- **Fiabilité** : une réponse coupée par le fournisseur affiche une erreur au lieu d’être insérée, le presse-papiers est mieux préservé, les raccourcis attendent le relâchement des touches, la capture d’écran est exacte en multi-écran et Foundry Local se recharge plus vite.
- **Sécurité** : un fichier de prompts importé ne peut plus envoyer votre texte vers un serveur absent de vos réglages, le texte collé est exclu de l’historique du presse-papiers et le texte traité n’apparaît plus dans les journaux.
- **Mises à jour vérifiées** : sous Windows, l’installateur est contrôlé par son empreinte SHA-256 avant d’être lancé et SuperMenu ne redémarre plus en administrateur. Chaque fichier de la release est accompagné d’une attestation de provenance signée par GitHub.
- **Licence** : SuperMenu est désormais distribué sous PolyForm Noncommercial 1.0.0 ; l’usage non commercial reste libre. Ce qui a été publié auparavant (releases jusqu’à v1.2.1, soit macOS 1.2.8, et bêtas précédentes) reste disponible sous CC BY-NC 4.0.
- **Documentation** revue et complétée : README en français et en anglais, guides d’utilisation Windows et Mac, guide de contribution et politique de sécurité.

Les prompts, réglages et modèles déjà téléchargés sont conservés. Sous Windows, un raccourci Maj+touche (hors F1 à F24) est désormais refusé et signalé comme inactif : choisissez-en un autre. Sur Mac, un nouveau raccourci doit comporter Cmd ou Ctrl ; un ancien raccourci sans l’un d’eux reste actif, mais il est conseillé de le remplacer.
