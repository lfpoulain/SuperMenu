# Journal des modifications

Les évolutions notables de SuperMenu sont consignées dans ce fichier.

Le format s’inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
et les numéros suivent le [versionnage sémantique](https://semver.org/lang/fr/).
Chaque entrée correspond à une release Stable, nommée d’après la version
Windows (`win32/VERSION`) ; la version macOS (`macos/VERSION`) a son propre
numéro, indiqué à côté. Les bêtas roulantes ne sont pas détaillées une par une.

## [Non publié]

## [1.3.0] - 2026-10-19

macOS : 1.3.0.

### Nouveautés

- Deux interrupteurs indépendants dans **Réglages > Application > Fonctions** : **Fonctions avancées** et **Fonctions expérimentales**, appliqués sans redémarrer.
- Fonctions avancées : modèle, fournisseur ou poste LM Link propre à chaque prompt, raccourcis directs par prompt, durée de conservation des modèles locaux en mémoire.
- Fonctions expérimentales : prompts vocaux, dictée instantanée, rubrique **Dictée** et test du micro, et sous Windows la capture et l’analyse d’écran.
- Une nouvelle installation démarre avec les deux interrupteurs désactivés ; une mise à jour les active tous les deux pour ne retirer aucune fonction déjà utilisée.
- Désactiver une fonction la masque sans rien supprimer ; SuperMenu demande confirmation si des prompts ont leur propre modèle.
- Choix du moteur et du modèle pour chaque prompt, texte ou vocal, le réglage général restant la valeur par défaut (fonctions avancées).
- LM Studio : copies locales et copies LM Link d’un même modèle distinguées, exécution sur le poste choisi et postes distants renommables.
- LM Studio : modèles chargés à la demande ; les instances ainsi créées sont libérées après cinq minutes d’inactivité.
- Raisonnement réglable pour chaque prompt (réglage du moteur, sans raisonnement, avec raisonnement), conservé à l’export et par **Réessayer**.
- La correction de la dictée suit le prompt « Corriger » : son mode de raisonnement et, avec les fonctions avancées, son modèle.
- **Tout restaurer…** remet les prompts d’origine dans les onglets Prompts et Voix.
- **Revenir à la copie…** rétablit une version précédente de la bibliothèque de prompts ; chaque nouvel usage remonte d’une copie, parmi les cinq conservées avant chaque restauration, import ou réparation.
- Foundry Local garde son moteur initialisé entre deux chargements de modèle et réutilise les poids déjà installés quand le catalogue publie une nouvelle révision.
- Raccourcis refusés par le système signalés après **Appliquer** ; sous Windows, aussi au démarrage et dans la rubrique **Raccourcis** (mention « inactif »).
- Rubrique Dictée et éditeur de prompts vocaux : modifications non enregistrées signalées, avec confirmation avant de changer de prompt.

### Sécurité

- Windows : l’installateur de mise à jour est vérifié avec l’empreinte SHA-256 publiée, téléchargé dans un dossier temporaire privé et revérifié juste avant son lancement ; un fichier différent est refusé.
- Windows : après une mise à jour, SuperMenu n’est plus relancé avec les droits administrateur.
- Un fichier de prompts importé ne peut plus envoyer votre texte vers un serveur absent de vos réglages : les adresses de serveur sont retirées à l’import, ignorées à l’exécution et absentes de l’export. Le moteur choisi par un prompt, par exemple OpenAI, reste repris.
- Le texte sélectionné n’est plus jamais interprété comme un chemin de fichier image.
- Une réponse à insertion directe n’est plus collée dans la fenêtre active par défaut quand aucune cible n’a été capturée ; macOS annule aussi l’insertion si une autre fenêtre de l’application cible est devenue active.
- Le texte sélectionné, le prompt saisi et les transcriptions n’apparaissent plus dans les journaux, même en mode débogage ; macOS ne journalise plus les touches observées par le moniteur de raccourcis.
- Messages d’erreur, statuts et aperçus affichés en texte brut : une page d’erreur HTML renvoyée par un serveur ne peut plus injecter de liens ni de mise en forme.
- Le texte collé par SuperMenu est exclu de l’historique du presse-papiers et de sa synchronisation (Win+V et cloud sous Windows, gestionnaires d’historique et presse-papiers universel sous macOS).
- Windows : la désinstallation avec suppression des données efface aussi les clés API enregistrées.
- Publication de la bêta réservée aux pushes sur `main` du dépôt : une pull request venant d’un fork ne peut plus déclencher de build signé.
- Chaque fichier publié avec une release est accompagné d’une attestation de provenance signée par GitHub, vérifiable avec `gh attestation verify` (voir « Vérifier un téléchargement » dans le README).

### Corrections

- Réponses tronquées détectées pour tous les fournisseurs (OpenAI, Ollama, LM Studio, serveurs compatibles OpenAI) : une erreur s’affiche au lieu d’insérer un texte incomplet.
- OpenAI : limite de sortie relevée pour les longues réponses.
- Une génération lente n’est plus relancée trois fois : une seule attente plus longue, puis un message clair.
- LM Studio : une adresse saisie avec `/api/v1` fonctionne.
- Raisonnement : les balises `</think>` sans balise ouvrante sont reconnues, et une balise citée dans le texte ne coupe plus la réponse.
- L’affichage du raisonnement suit le mode réellement demandé par le prompt.
- Capacités des modèles Ollama et LM Studio : nouvelle tentative après un échec temporaire, nouvelle détection après l’enregistrement des réglages.
- Validation des adresses de serveur (noms sans point, IPv6, domaines `.internal`) et des noms de modèles (`@q4_k_m`) corrigée.
- L’effort de raisonnement OpenAI global n’est plus modifié par un prompt ou par la simple consultation d’un autre modèle.
- Les prompts LM Studio et Ollama suivent toujours le serveur des réglages Texte ; **Actualiser** interroge le serveur actuel.
- Une entrée invalide dans la bibliothèque de prompts n’efface plus les autres prompts : elle est réparée ou écartée, et une copie est conservée.
- Import de prompts : brouillons à instruction vide acceptés, fichiers UTF-8 avec BOM acceptés, erreurs qui nomment le prompt concerné.
- Un échec d’écriture de la configuration pendant un import ou une restauration est signalé et annulé.
- macOS : un raccourci en double n’efface plus en silence celui d’un autre prompt.
- Windows : la liste des prompts se met à jour après un import ou une réinitialisation.
- Windows : images et autres formats du presse-papiers restaurés après une copie ou une insertion.
- Windows : SuperMenu attend le relâchement des touches de modification avant de copier la sélection (menu, mode personnalisé, raccourcis de prompt).
- Windows : copier-coller fiable avec les dispositions cyrillique, grecque ou hébraïque.
- Windows : sur un clavier non AZERTY, `Ctrl+²` utilise la touche située sous Échap et n’entre plus en conflit avec le raccourci vocal.
- Windows : plus de Ctrl+C intempestif dans mintty (Git Bash), PuTTY, KiTTY et WezTerm.
- Windows : collage fiable via Bureau à distance, Citrix et VMware.
- Une réponse à insertion directe refusée reste disponible dans la fenêtre de réponse (avec **Réessayer** et **Insérer le texte**) ou dans le presse-papiers.
- Fenêtre de réponse : état d’erreur clair, bouton d’insertion désactivé après un échec.
- L’indicateur de progression ne disparaît plus avant la fin du traitement.
- Les instructions de prompt contenant des balises HTML ou XML sont conservées telles quelles.
- Windows : pendant l’enregistrement d’un raccourci, les autres raccourcis de SuperMenu sont libérés, et un conflit est refusé.
- Windows : un seul SuperMenu à la fois, y compris pendant un redémarrage ou une mise à jour.
- Windows : les erreurs inattendues sont consignées dans le journal, et un échec de démarrage est expliqué dans une boîte de dialogue.
- Windows : capture de zone exacte en multi-écran et avec une mise à l’échelle de 125 ou 150 % ; la fenêtre de réponse est masquée pendant la capture.
- Windows : la version portable n’annonce plus une mise à jour à chaque vérification.
- Quitter pendant une vérification ou un téléchargement de mise à jour ne provoque plus de plantage.
- macOS : l’enregistreur de raccourcis accepte Option+touche et Cmd+Maj+touche.
- macOS : le statut « Raccourcis globaux actifs » n’apparaît plus sans l’autorisation Accessibilité, et l’autorisation est détectée même fenêtre fermée.
- macOS : barre des menus gérée directement par AppKit, ce qui évite un plantage sous macOS 27.
- macOS : une application figée ne bloque plus SuperMenu plusieurs secondes.
- macOS : l’application cible garde le premier plan pendant une insertion directe et le retrouve après un message d’erreur.
- macOS : une erreur tardive d’une requête remplacée n’ouvre plus de boîte de dialogue.
- macOS : message clair, « Réinstallez SuperMenu », si le composant vocal Apple manque.
- Dictée : le téléchargement d’un modèle vocal ou d’un pilote GPU n’est plus interrompu par le délai de préparation.
- Dictée Nemotron : messages d’erreur utiles, et dictée en attente relancée après un arrêt du moteur vocal.
- Dictée OpenAI : « Connexion à OpenAI impossible » quand le serveur refuse la connexion.
- Modifier la clé API n’interrompt plus le téléchargement ou la vérification d’un moteur vocal local.
- Foundry Local : un téléchargement qui progresse n’est plus interrompu, une génération avec raisonnement dispose d’un délai plus long, et chaque délai dépassé a son propre message.
- Foundry Local : une requête en attente indique qu’un téléchargement de modèle est en cours.
- Foundry Local : redémarrage du moteur fiable, sans jamais garder deux modèles en mémoire.

### Changements

- Licence : SuperMenu passe de CC BY-NC 4.0 à [PolyForm Noncommercial 1.0.0](LICENSE). L’usage non commercial reste libre. Tout ce qui a été publié avant ce changement reste disponible sous CC BY-NC 4.0 : les releases jusqu’à v1.2.1 (Windows 1.2.1, macOS 1.2.8), leur code source (tags `v1.2.0` et `v1.2.1`) et les bêtas publiées jusque-là.
- Windows : un raccourci « Maj + touche » est refusé, sauf avec F1 à F24, car il bloquait la saisie des majuscules.
- macOS : un nouveau raccourci doit comporter Cmd ou Ctrl, sauf avec F1 à F24 ; un raccourci sans Cmd ni Ctrl enregistré par une version précédente reste actif. Cmd+A, C, V, X et Z sont réservés.
- Les prompts n’enregistrent plus l’adresse du serveur LM Studio ou Ollama ; les anciennes adresses sont retirées automatiquement.
- macOS : l’application déclare macOS 13 comme version minimale, celle qu’exige Qt 6.11.
- Les applications n’incluent plus Qt Virtual Keyboard, Qt Pdf ni, sous Windows, le rendu OpenGL logiciel de Mesa, que SuperMenu n’utilise pas.
- La rubrique **À propos** indique la licence et renvoie vers la liste des composants tiers. Les applications et l’installateur Windows incluent la licence, les avis des composants tiers et leurs textes de licence ; l’installateur présente aussi les conditions des composants Microsoft de Foundry Local.
- Documentation réécrite : README en français et en anglais, guides d’utilisation et d’architecture Windows et macOS, guide de contribution, politique de sécurité et code de conduite.

### Interne

- Code commun réorganisé (cycle de vie des requêtes, contrat des réglages, fenêtres principales découpées par rubrique, modules par fournisseur, règles de mise à jour partagées) et publication renforcée (contrôles de version avant chaque bêta ou Stable, DMG de contrôle non signé en CI, actions épinglées, attestations de provenance).

## [1.2.1] - 2026-09-11

macOS : 1.2.8 (première version Stable macOS).

### Nouveautés

- Application macOS pour Mac Apple Silicon, distribuée en DMG signé Developer ID et notarisé par Apple, avec mise à jour intégrée Stable et Bêta.
- Cœur commun aux applications Windows et macOS : prompts, fournisseurs IA et interface.
- IA locale sous Windows : Foundry Local avec Qwen3.5 4B et 9B, accélération CUDA prioritaire sur les GPU NVIDIA compatibles.
- IA locale sur Mac : Apple Foundation Models sur les Mac compatibles avec macOS 26+.
- Dictée en direct avec OpenAI, Nemotron via Foundry Local sous Windows, ou Apple Speech sur Mac.
- Raccourci de dictée instantanée (appui maintenu ou simple), copie et insertion depuis la fenêtre de transcription, collage automatique et correction préalable facultative.
- Prompts vocaux partagés entre Mac et Windows.
- Modèles locaux conservés en mémoire, avec délai d’inactivité configurable et déchargement manuel.
- Réglages du raisonnement adaptés aux capacités des modèles locaux et appliqués immédiatement.

### Changements

- Interface Mac et PC harmonisée : réglages par rubrique, retours visuels de préparation des modèles, fenêtre plus haute.
- La dictée en direct remplace l’ancienne transcription d’enregistrements audio.
- Ancien canal de mise à jour « nightly » retiré : seuls les canaux Stable et Bêta subsistent.

### Corrections

- Ouverture du microphone corrigée.
- Redémarrage de Foundry Local corrigé.

## [1.2.0] - 2026-08-05

Première release du canal Stable, pour Windows. Les versions précédentes ne
sont pas détaillées ici.

### Nouveautés

- Menu de prompts ouvert par raccourci global (`Ctrl+²`) sur le texte sélectionné : corriger, reformuler, résumer, traduire, expliquer.
- Insertion directe de la réponse à la place de la sélection, et raccourci propre à chaque prompt.
- Prompts personnalisables et mode personnalisé direct (`Ctrl+Alt+M`).
- Commandes vocales (`Ctrl+Alt+²`) transcrites par OpenAI, avec vocabulaire et contexte personnalisables.
- Capture et analyse d’écran (`Ctrl+Alt+&`) : plein écran, zone ou choix à chaque fois.
- OpenAI, Ollama et LM Studio, avec réglage du raisonnement selon le modèle.
- Thèmes clair, sombre et automatique.
- Clé API conservée dans le stockage sécurisé de Windows.
- Canaux de mise à jour Stable et Bêta via GitHub Releases, avec migration des installations de l’ancien canal « nightly » vers Stable.

[Non publié]: https://github.com/lfpoulain/SuperMenu/compare/v1.3.0...main
[1.3.0]: https://github.com/lfpoulain/SuperMenu/releases/tag/v1.3.0
[1.2.1]: https://github.com/lfpoulain/SuperMenu/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/lfpoulain/SuperMenu/releases/tag/v1.2.0
