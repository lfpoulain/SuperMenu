# Foundry Local sous Windows

SuperMenu embarque le SDK Microsoft Foundry Local (paquet
`foundry-local-sdk-winml` 1.2.4). Il exécute les modèles Qwen3.5 4B ou 9B sur
votre PC, pour corriger, reformuler, résumer ou traduire sans clé API, sans
serveur, sans compte Microsoft ni abonnement.

## Mise en route

1. Installez SuperMenu pour Windows, [Stable](https://github.com/lfpoulain/SuperMenu/releases/latest)
   ou Bêta, sur Windows 11 24H2 ou plus récent.
2. Dans **Réglages > Texte**, choisissez **IA locale Microsoft — Foundry
   Local** comme moteur de texte.
3. Choisissez **Qwen3.5 4B — léger** (par défaut) ou **Qwen3.5 9B — qualité**.
4. Cliquez sur **Vérifier le modèle**. Cette étape prépare l’accélération
   matérielle : CUDA sur une carte NVIDIA, WebGPU sur les autres GPU, en
   réutilisant les composants déjà installés. La première préparation peut
   prendre quelques minutes. La taille du modèle, sa présence sur le disque et
   le matériel utilisé sont lus dans le catalogue Microsoft pour ce PC.
5. Si le modèle manque, cliquez sur **Télécharger le modèle**, puis sur
   **Enregistrer**.
6. Sélectionnez du texte et utilisez vos prompts habituels.

Le GPU est utilisé en priorité. Pour forcer le processeur, choisissez **CPU
uniquement** dans **Calcul local**, sous la section repliable **Matériel et
mémoire du modèle** (**Matériel du modèle** sans les fonctions avancées).

## Matériel et mémoire

- **Mémoire vive** : 16 Go conseillés pour le 4B, 24 Go pour le 9B. Ce sont
  des recommandations : le besoin réel dépend du matériel et de la variante.
- **Variantes** : le catalogue propose une variante par type de matériel. À
  titre d’exemple, en CPU : `qwen3.5-4b-generic-cpu:3` (3 085 Mo) et
  `qwen3.5-9b-generic-cpu:3` (5 569 Mo) ; avec CUDA :
  `qwen3.5-4b-cuda-gpu:3` (4 181 Mo) et `qwen3.5-9b-cuda-gpu:3` (7 144 Mo).
  Votre PC peut recevoir d’autres variantes et tailles.
- **NVIDIA** : le statut doit indiquer **GPU — CUDA (NVIDIA)**. Un modèle CPU
  déjà téléchargé ne remplace pas sa variante CUDA : téléchargez la variante
  GPU affichée, puis enregistrez. Les fichiers CPU restent utilisables avec
  **CPU uniquement**.
- **Échec de la préparation GPU** : le message propose de vérifier la
  connexion et le pilote, ou de choisir **CPU uniquement**. SuperMenu ne
  bascule jamais silencieusement sur le processeur.
- **Mémoire du modèle** : un seul modèle reste chargé. Il se décharge après
  cinq minutes d’inactivité. Avec les fonctions avancées
  (**Réglages > Application > Fonctions**), **Décharger le modèle texte
  après** propose aussi chaque requête, 1, 15 ou 30 minutes, ou la fermeture
  de SuperMenu, et **Décharger maintenant** libère la RAM ou la mémoire GPU
  sans supprimer les fichiers. Une requête en cours ou en attente n’est jamais
  interrompue par un déchargement.

## Limites

- Windows 11 24H2 ou plus récent, avec l’exécutable Windows x64. Le modèle et
  l’accélérateur disponibles dépendent du catalogue Microsoft et des pilotes.
- Internet est nécessaire pour télécharger les modèles et les composants
  matériels. Le traitement utilise ensuite les fichiers locaux ; le SDK peut
  rafraîchir son catalogue au démarrage ou utiliser celui en cache hors ligne.
- Le moteur Qwen traite uniquement du texte. La capture d’écran n’est pas
  disponible avec Foundry Local. La dictée se configure à part, dans
  **Réglages > Dictée** : OpenAI ou Nemotron 3.5 via Foundry Local (modèle
  distinct de 756 Mo).
- 16 000 caractères au plus par requête, et 24 000 octets UTF-8 pour garder de
  la place au contexte multilingue.
- La réponse est limitée à 2 048 tokens, ou 8 192 tokens raisonnement compris
  avec un prompt **Avec raisonnement**. Une réponse interrompue n’est jamais
  insérée.
- Le premier chargement prend plus de temps que les suivants.
- Les modèles sont stockés dans `%LOCALAPPDATA%\SuperMenu\Foundry\cache\models`.
  Ils ne sont pas inclus dans l’installateur et sont conservés entre les mises
  à jour. **Annuler** arrête un téléchargement, qui pourra être repris depuis
  les réglages.
- Aucune requête Foundry n’est transférée automatiquement à OpenAI ou à un
  autre serveur.

Les modèles Qwen3.5 sont publiés sous licence Apache 2.0 ; voir leurs fiches
[Qwen3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B) et
[Qwen3.5 9B](https://huggingface.co/Qwen/Qwen3.5-9B). Les composants Foundry
Local et leurs licences sont décrits dans
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).

## Délais et file d’attente

Les requêtes locales passent une par une. Pendant un téléchargement ou une
vérification, une requête en attente affiche « En attente de la fin du
téléchargement d’un modèle local… » (ou le message équivalent pour la
vérification), puis les étapes réelles dès qu’elle démarre.

Les délais portent sur l’inactivité : chaque progression les relance. Un
téléchargement qui avance n’est donc jamais coupé, et la préparation du
matériel ou le chargement à froid ne consomment pas le temps de génération.
Une génération dispose de 10 minutes sans progression, 40 minutes avec
raisonnement. Si un délai expire, le message indique l’opération concernée :
téléchargement qui ne progresse plus, vérification qui n’aboutit pas ou
génération trop longue.

## Fonctionnement interne

Le SDK s’exécute dans un processus enfant privé, sans fenêtre ni serveur HTTP.
Les textes passent par des pipes et ne figurent jamais dans les arguments du
processus. Les échanges avec ce worker passent par
`supermenu_core.utils.jsonl` (un objet JSON par ligne). Les paramètres du
fournisseur et du modèle sont capturés pour chaque client : modifier les
réglages ne perturbe pas les requêtes déjà envoyées. Chaque lancement crée un nouveau processus ; si l’ancien tarde à se
terminer, SuperMenu attend sa fin (15 secondes au plus) avant d’en démarrer un
autre, pour ne jamais garder deux modèles en mémoire GPU.

Le SDK 1.2.4 n’expose ni les variables du template Jinja ni la taille de
contexte au chargement. Avant le chargement, SuperMenu adapte donc une seule
fois son cache privé :

- choix de la branche Qwen `enable_thinking` par un message de contrôle privé,
  retiré par le template avant la tokenisation ;
- remplacement du test Jinja `is false`, non pris en charge par ORT GenAI
  0.14.1 ;
- limite de `search.max_length` à 32 768.

Les poids ne sont jamais modifiés. L’adaptation est atomique et idempotente ;
une variante sans template compatible est refusée. Un manifeste de modèle
illisible est ignoré. Le mode de raisonnement d’un prompt s’applique sans
modifier le template à chaque requête ni recharger le modèle. Avec
raisonnement, les paramètres d’échantillonnage suivent les
[recommandations Qwen](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices).

Le SDK n’expose que les modèles CPU tant que les fournisseurs d’exécution ne
sont pas enregistrés. Chaque processus prépare donc d’abord CUDA (prioritaire)
ou WebGPU avec `download_and_register_eps`, puis consulte les variantes. Les
composants téléchargés sont mis en cache par Microsoft : leur réactivation au
démarrage n’est pas un nouveau téléchargement des poids. La sélection donne la
priorité au GPU sur une variante CPU en cache et garde un objet de variante
distinct, pour décharger le modèle réellement en mémoire. Quand le catalogue
publie une nouvelle révision du même modèle, les poids déjà installés sont
réutilisés avec le matériel choisi.

Le déchargement appelle `model.unload()` dans le processus résident : le
gestionnaire Foundry, le catalogue et les fournisseurs GPU restent
initialisés. L’annulation d’une requête active, une erreur critique ou la
fermeture de SuperMenu arrêtent le processus. Les journaux consignent les
durées `runtime`, `hardware`, `load`, `generate` et `unload`, sans le texte
traité.

## Validation

Les tests automatisés couvrent la migration des réglages, le routage et la
conservation de la cible d’insertion, les changements de modèle, l’arrêt du
moteur, les délais, l’annulation, l’absence de téléchargement implicite, les
réponses interrompues, l’enregistrement CUDA, la priorité sur un cache CPU, le
choix CPU sans téléchargement GPU et la libération de l’ancienne variante.

Les builds Stable et Bêta exécutent aussi `SuperMenu.exe --foundry-smoke-test` :
l’exécutable final initialise les DLL natives embarquées et lit les deux
modèles du catalogue dans un processus enfant, en mode CPU, sans télécharger
de composant GPU ni de poids. L’inférence CUDA a été vérifiée manuellement sur
une carte NVIDIA, avec les deux modèles et les mêmes corrections et
traductions qu’en CPU.

Références : [Foundry Local (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/ai/foundry-local/get-started),
[SDK 1.2.4 sur PyPI](https://pypi.org/project/foundry-local-sdk-winml/1.2.4/).

Retour au [README Windows](../README.md) ou au
[guide d’utilisation](GUIDE_UTILISATION.md).
