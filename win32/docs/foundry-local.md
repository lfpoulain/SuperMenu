# Foundry Local — bêta Windows

SuperMenu embarque le SDK Microsoft Foundry Local WinML 1.2.4. Aucun serveur,
outil en ligne de commande, compte Microsoft ou abonnement IA n'est nécessaire.

## Utilisation

1. Installer la [bêta PC](https://github.com/lfpoulain/SuperMenu/releases/tag/beta),
   ou choisir le canal Beta dans À propos puis rechercher une mise à jour.
2. Dans **Réglages > Moteur IA**, choisir **IA locale Microsoft — Foundry Local**.
3. Cliquer sur **Vérifier**, puis sélectionner **Qwen3.5 4B** ou **Qwen3.5 9B**.
   La taille du téléchargement, sa présence sur le disque et le matériel
   d'exécution sont lus dans le catalogue Microsoft pour ce PC.
4. Cliquer sur **Télécharger le modèle**, puis **Enregistrer la configuration**.
5. Sélectionner du texte et utiliser les actions habituelles de SuperMenu.

Le 4B est le choix par défaut. Prévoir 16 Go de RAM pour le 4B, 24 Go pour le 9B
(recommandations, la mémoire nécessaire varie selon le matériel et la sélection).
Sur le PC de validation CPU, les variantes du catalogue étaient
`qwen3.5-4b-generic-cpu:3` (3 085 Mo) et `qwen3.5-9b-generic-cpu:3` (5 569 Mo).
Les autres matériels peuvent recevoir des variantes et tailles différentes.

## Disponibilité et limites

- Cette intégration WinML vise Windows 11 24H2 ou plus récent, avec l'exécutable
  Windows x64. Le modèle et son accélérateur dépendent du catalogue et des pilotes.
- Internet est nécessaire pour télécharger les modèles et les composants
  matériels. L'inférence utilise ensuite les fichiers locaux ; le SDK peut
  rafraîchir son catalogue au démarrage ou reprendre le catalogue en cache hors ligne.
- Cette bêta traite le texte : correction, reformulation, résumé et traduction.
  Les captures d'écran affichent un message de fonctionnalité non disponible.
  La transcription vocale continue d'utiliser l'API OpenAI.
- Jusqu'à 16 000 caractères par requête, avec une limite supplémentaire de
  24 000 octets UTF-8 pour préserver le contexte multilingue. La sortie est
  limitée à 2 048 tokens. Une réponse interrompue n'est jamais insérée dans le document.
- Le chargement initial prend plus de temps. Un seul modèle reste chargé ;
  le moteur est arrêté après cinq minutes d'inactivité pour libérer la mémoire.
- Les modèles sont stockés dans `%LOCALAPPDATA%\SuperMenu\Foundry\cache\models`.
  Ils ne sont pas inclus dans l'installateur. Le bouton Annuler arrête l'opération ;
  un téléchargement incomplet peut être repris depuis les réglages.
- Aucune requête Foundry n'est automatiquement transférée à OpenAI ou à un endpoint.

## Détails de validation et maintenance

Le SDK s'exécute dans un processus enfant privé, sans fenêtre ni serveur HTTP.
Les textes passent par des pipes et ne figurent pas dans les arguments du
processus. Les paramètres du fournisseur et du modèle sont capturés pour chaque
client : une modification des réglages préserve les requêtes déjà envoyées.

Le SDK 1.2.4 n'expose ni les variables du template Jinja, ni la taille de contexte
au chargement. Avant chargement, SuperMenu adapte uniquement son cache privé :
activation de la branche Qwen `enable_thinking = false`, remplacement du test
Jinja `is false` non pris en charge par ORT GenAI 0.14.1 et limite de
`search.max_length` à 32 768. Les poids restent inchangés. L'adaptation est
atomique et idempotente. Les variantes sans template compatible sont refusées.

Validation locale du 9 septembre 2026 : les deux modèles corrigent
« Les enfant joue dans le jardin. » et traduisent
« Je serai disponible demain matin. » en anglais, sans raisonnement dans la sortie.
Les tests automatisés couvrent migration des réglages, routage et conservation
de la cible d'insertion, changements de modèle, arrêt du moteur, délai dépassé,
annulation, absence de téléchargement implicite et réponses interrompues.

La publication bêta exige également `SuperMenu.exe --foundry-smoke-test` :
initialisation des DLL natives embarquées et lecture des deux modèles du catalogue
depuis un processus enfant de l'exécutable final, sans télécharger les poids en CI.

Références : [SDK Microsoft](https://learn.microsoft.com/en-us/windows/ai/foundry-local/get-started),
[SDK 1.2.4](https://pypi.org/project/foundry-local-sdk-winml/1.2.4/),
[Qwen3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B),
[Qwen3.5 9B](https://huggingface.co/Qwen/Qwen3.5-9B).
