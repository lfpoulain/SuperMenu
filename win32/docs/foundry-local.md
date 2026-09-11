# Foundry Local — Windows

SuperMenu embarque le SDK Microsoft Foundry Local WinML 1.2.4. Aucun serveur,
outil en ligne de commande, compte Microsoft ou abonnement IA n'est nécessaire.

## Utilisation

1. Installer la [version stable PC](https://github.com/lfpoulain/SuperMenu/releases/latest),
   ou choisir le canal Stable dans **Réglages > Application** puis rechercher une mise à jour.
2. Dans **Réglages > Texte**, choisir **IA locale Microsoft — Foundry Local**.
3. Cliquer sur **Vérifier**. Le GPU est utilisé en priorité ; ce choix peut se modifier
   dans **Matériel et détails du modèle**.
   Cette étape active CUDA sur NVIDIA (ou WebGPU sur les autres GPU), en réutilisant les composants déjà installés.
   Le premier téléchargement peut prendre quelques minutes. Choisir ensuite **Qwen3.5 4B** ou **Qwen3.5 9B**.
   La taille du téléchargement, sa présence sur le disque et le matériel
   d'exécution sont lus dans le catalogue Microsoft pour ce PC.
4. Si le modèle manque, cliquer sur **Télécharger le modèle**, puis **Enregistrer le moteur de texte**.
5. Sélectionner du texte et utiliser les actions habituelles de SuperMenu.

Le 4B est le choix par défaut. Prévoir 16 Go de RAM pour le 4B, 24 Go pour le 9B
(recommandations, la mémoire nécessaire varie selon le matériel et la sélection).
Sur le PC de validation CPU, les variantes du catalogue étaient
`qwen3.5-4b-generic-cpu:3` (3 085 Mo) et `qwen3.5-9b-generic-cpu:3` (5 569 Mo).
Les autres matériels peuvent recevoir des variantes et tailles différentes.

Sur NVIDIA, le statut doit indiquer **GPU — CUDA (NVIDIA)**. Un modèle CPU déjà
téléchargé ne remplace pas sa variante CUDA : télécharger la variante GPU affichée
puis enregistrer la configuration. Les fichiers CPU restent disponibles si l'on
choisit **CPU uniquement**. En cas d'échec de préparation GPU, le message propose
de vérifier la connexion/pilote ou de choisir CPU ; l'inférence ne bascule pas
silencieusement sur le CPU.

## Disponibilité et limites

- Cette intégration WinML vise Windows 11 24H2 ou plus récent, avec l'exécutable
  Windows x64. Le modèle et son accélérateur dépendent du catalogue et des pilotes.
- Internet est nécessaire pour télécharger les modèles et les composants
  matériels. L'inférence utilise ensuite les fichiers locaux ; le SDK peut
  rafraîchir son catalogue au démarrage ou reprendre le catalogue en cache hors ligne.
- Le moteur Qwen traite le texte : correction, reformulation, résumé et traduction.
  Les captures d'écran affichent un message de fonctionnalité non disponible.
  La transcription vocale se choisit dans **Réglages > Dictée** : OpenAI ou
  Foundry Local avec Nemotron 3.5 (modèle séparé d’environ 756 Mo).
- Jusqu'à 16 000 caractères par requête, avec une limite supplémentaire de
  24 000 octets UTF-8 pour préserver le contexte multilingue. La sortie est
  limitée à 2 048 tokens. Une réponse interrompue n'est jamais insérée dans le document.
- Le chargement initial prend plus de temps. Un seul modèle reste chargé ;
  le délai de déchargement est configurable dans les réglages (cinq minutes par défaut).
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

Le SDK expose seulement les modèles CPU tant que les fournisseurs d'exécution
ne sont pas enregistrés. Chaque processus prépare donc le fournisseur CUDA
(prioritaire) ou WebGPU avec `download_and_register_eps`, avant de consulter les
variantes. Le téléchargement des composants est mis en cache par Microsoft.
La sélection des variantes donne priorité au GPU devant le cache CPU, et conserve
un objet de variante distinct pour pouvoir décharger le modèle réellement en mémoire.

Validation locale du 9 septembre 2026 : les deux modèles corrigent
« Les enfant joue dans le jardin. » et traduisent
« Je serai disponible demain matin. » en anglais, sans raisonnement dans la sortie.
Les tests automatisés couvrent migration des réglages, routage et conservation
de la cible d'insertion, changements de modèle, arrêt du moteur, délai dépassé,
annulation, absence de téléchargement implicite et réponses interrompues.

Validation CUDA du 10 septembre 2026 sur RTX 4090, pilote 591.86 : les variantes
`qwen3.5-4b-cuda-gpu:3` (4 181 Mo) et `qwen3.5-9b-cuda-gpu:3` (7 144 Mo)
exécutent les mêmes corrections/traductions. La traduction de cette courte phrase
prend environ 0,17 s / 0,20 s une fois le modèle chargé (mesures ponctuelles).
Les régressions testent aussi l'enregistrement CUDA, la priorité sur un cache CPU,
le choix CPU sans téléchargement GPU et la libération de l'ancienne variante.

Les publications stable et bêta exigent également `SuperMenu.exe --foundry-smoke-test` :
initialisation des DLL natives embarquées et lecture des deux modèles du catalogue
depuis un processus enfant de l'exécutable final, en mode CPU sans télécharger
de composants GPU ni de poids en CI. L'inférence CUDA est vérifiée séparément
sur une machine disposant du matériel NVIDIA.

Références : [SDK Microsoft](https://learn.microsoft.com/en-us/windows/ai/foundry-local/get-started),
[SDK 1.2.4](https://pypi.org/project/foundry-local-sdk-winml/1.2.4/),
[Qwen3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B),
[Qwen3.5 9B](https://huggingface.co/Qwen/Qwen3.5-9B).
