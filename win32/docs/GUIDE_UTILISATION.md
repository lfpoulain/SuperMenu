# Guide d’utilisation de SuperMenu pour Windows

Ce guide explique comment installer, configurer et utiliser SuperMenu sous
Windows, puis comment résoudre les problèmes courants. Pour une présentation
rapide, consultez le [README Windows](../README.md).

## Sommaire

1. [Présentation](#présentation)
2. [Installation](#installation)
3. [La fenêtre de configuration](#la-fenêtre-de-configuration)
4. [Choisir le moteur de texte](#choisir-le-moteur-de-texte)
5. [Fonctions avancées et expérimentales](#fonctions-avancées-et-expérimentales)
6. [Raccourcis clavier](#raccourcis-clavier)
7. [Utilisation quotidienne](#utilisation-quotidienne)
8. [Presse-papiers et applications particulières](#presse-papiers-et-applications-particulières)
9. [Gérer les prompts](#gérer-les-prompts)
10. [Voix et dictée](#voix-et-dictée)
11. [Capture d’écran](#capture-décran)
12. [Apparence](#apparence)
13. [Mises à jour](#mises-à-jour)
14. [Données et confidentialité](#données-et-confidentialité)
15. [Dépannage](#dépannage)
16. [Désinstallation](#désinstallation)

## Présentation

SuperMenu fonctionne en arrière-plan, depuis la zone de notification. Il
traite le texte sélectionné dans n’importe quelle application : vous appuyez
sur un raccourci, choisissez un prompt (une instruction enregistrée, comme
« Corriger » ou « Traduire en anglais »), et la réponse de l’IA s’affiche ou
remplace la sélection.

Les fonctions de base sont toujours disponibles. Deux groupes de fonctions
s’activent séparément : les **fonctions avancées** (modèle et raccourci par
prompt, mémoire des modèles locaux) et les **fonctions expérimentales** (voix,
dictée, capture d’écran). Voir
[Fonctions avancées et expérimentales](#fonctions-avancées-et-expérimentales).

## Installation

### Configuration requise

- Windows 10 ou 11, 64 bits ;
- pour OpenAI : une clé API OpenAI, l’usage étant facturé par OpenAI ;
- pour Ollama ou LM Studio : un serveur accessible depuis le PC ;
- pour Foundry Local : Windows 11 24H2 ou plus récent ; 16 Go de RAM sont
  conseillés pour Qwen3.5 4B et 24 Go pour Qwen3.5 9B.

### Installateur

1. Téléchargez `SuperMenu_Setup.exe` depuis la
   [dernière release](https://github.com/lfpoulain/SuperMenu/releases/latest)
   (`SuperMenu_Beta_Setup.exe` pour le canal Bêta).
2. Lancez-le et acceptez la demande d’autorisation de Windows.
3. Acceptez la licence, puis choisissez si besoin un raccourci sur le Bureau
   et **Démarrer SuperMenu avec Windows**.
4. À la fin, SuperMenu démarre et son icône apparaît dans la zone de
   notification.

Un installateur peut être lancé par-dessus une installation existante : la
configuration, les prompts, les clés et les modèles locaux sont conservés.

Les exécutables ne portent pas de signature Authenticode : Windows SmartScreen
peut afficher un avertissement. Pour vérifier un fichier, comparez le résultat
de `Get-FileHash .\SuperMenu_Setup.exe` à la ligne correspondante de
`SHA256SUMS.txt`, publié dans la même release.

### Version portable

`SuperMenu.exe` (ou `SuperMenu_Beta.exe`) fonctionne sans installation. Il
utilise les mêmes emplacements de configuration et de journaux que la version
installée. Il ne se met pas à jour lui-même : **Vérifier les mises à jour**
signale une version plus récente et propose d’ouvrir la page des
téléchargements.

### Une seule instance

Un seul SuperMenu fonctionne à la fois par session Windows. Lancer
l’application alors qu’elle tourne déjà affiche simplement sa fenêtre de
configuration.

## La fenêtre de configuration

Pour l’ouvrir, double-cliquez sur l’icône de la zone de notification ou
choisissez **Ouvrir SuperMenu** dans son menu. Fermer la fenêtre laisse
SuperMenu actif ; **Quitter**, dans le menu de l’icône, l’arrête.

La fenêtre comporte quatre onglets :

- **Prompts** : liste des prompts textuels et éditeur ;
- **Voix** : prompts vocaux (fonctions expérimentales) ;
- **Réglages**, en quatre rubriques :
  - **Texte** : moteur de texte et modèle ;
  - **Dictée** : microphone et moteur de transcription (fonctions
    expérimentales) ;
  - **Raccourcis** : raccourcis globaux, dictée instantanée et mode de capture
    d’écran ;
  - **Application** : thème, canal de mise à jour, interrupteurs **Fonctions**,
    fenêtre de correction, import et export des prompts, dossiers et
    réinitialisation ;
- **À propos** : version, licence et lien vers les versions publiées.

Les options rarement utiles sont regroupées dans des sections repliables, comme
**Options avancées**. **Enregistrer** valide les rubriques Texte et Dictée,
**Appliquer** la rubrique Application ; un raccourci global s’applique dès
qu’il est défini.

## Choisir le moteur de texte

Dans **Réglages > Texte**, la liste **Moteur de texte** propose trois choix.
Cliquez sur **Enregistrer** après chaque modification. Les nouvelles requêtes
utilisent aussitôt la nouvelle configuration ; une requête déjà en cours
termine avec l’ancienne.

### OpenAI

1. Collez votre **Clé API**.
2. Choisissez le **Modèle** : `gpt-5.6-sol` (qualité maximale, par défaut),
   `gpt-5.6-terra` (équilibre entre qualité et coût), `gpt-5.6-luna` (rapide
   et économique) ou `gpt-5.4`.
3. Dans **Options avancées**, réglez si besoin le **Raisonnement** : `none`,
   `low`, `medium`, `high`, `xhigh` ou `max` pour GPT-5.6 ; les mêmes niveaux
   sauf `max` pour GPT-5.4.

Les anciens identifiants de modèles sont convertis automatiquement : anciens
modèles phares vers Sol, variantes mini vers Terra, variantes nano vers Luna.

### Ollama / LM Studio

1. Saisissez l’**URL de l’endpoint**, par exemple `http://localhost:11434`
   pour Ollama.
2. Dans **Options avancées**, choisissez le **Type d’endpoint** (**Ollama** ou
   **LM Studio / Bionic**), un éventuel **Jeton de l’endpoint** et le réglage
   **Raisonnement / think**, adapté aux capacités annoncées par le modèle.
   Choisissez **LM Studio / Bionic** pour LM Studio, Bionic ou tout autre
   serveur compatible OpenAI, et **Ollama** pour un serveur Ollama.
3. Choisissez le **Modèle**, ou cliquez sur **Actualiser** pour interroger le
   serveur. Vous pouvez aussi saisir un nom de modèle.

Avec LM Studio, SuperMenu utilise l’API native du serveur, avec un repli
compatible OpenAI pour les anciennes versions. Une adresse saisie avec
`/api/v1` fonctionne aussi. Les modèles partagés par d’autres postes via
**LM Link** apparaissent avec leur provenance, par exemple « Sur … (LM Link) » ;
**Nommer ce poste distant…** leur donne un nom lisible.

Avec Ollama, SuperMenu lit les capacités du modèle. Qwen 3 et DeepSeek
reçoivent l’interrupteur `think` ; GPT-OSS reçoit toujours un niveau (`low`,
`medium` ou `high`), car son raisonnement ne peut pas être désactivé : le choix
`none` envoie `low` et masque la trace. Un modèle sans raisonnement ne reçoit
aucun paramètre superflu.

Le jeton de l’endpoint est distinct de la clé OpenAI. La clé OpenAI n’est
jamais envoyée à un autre serveur.

### IA locale Microsoft — Foundry Local

Foundry Local exécute Qwen3.5 4B ou 9B sur le PC, sans clé API ni serveur. La
préparation se fait en trois temps : **Vérifier le modèle**, **Télécharger le
modèle** si nécessaire, puis **Enregistrer**. Configuration, limites et
mémoire du modèle : voir [Foundry Local sous Windows](foundry-local.md).

### Réponses interrompues et délais

Si le serveur coupe une réponse avant la fin (limite de longueur ou de
contexte), SuperMenu affiche une erreur qui indique quoi changer, par exemple
augmenter la taille de contexte du modèle dans LM Studio. Une réponse
incomplète n’est jamais insérée.

Une génération lente n’est pas relancée : SuperMenu attend jusqu’à trois
minutes (cinq avec LM Studio), puis affiche un message clair. Les erreurs de
connexion et les surcharges momentanées du serveur sont retentées
automatiquement.

## Fonctions avancées et expérimentales

SuperMenu affiche l’essentiel par défaut. Dans **Réglages > Application >
Fonctions**, deux interrupteurs indépendants ajoutent des fonctions. Cochez ou
décochez, puis cliquez sur **Appliquer** : le changement est immédiat, sans
redémarrage.

**Fonctions avancées**

- modèle, fournisseur ou poste LM Link choisi pour chaque prompt, textuel ou
  vocal ;
- raccourci direct par prompt ;
- durée de conservation en mémoire du modèle texte Foundry Local et du modèle
  vocal Nemotron.

Quand elles sont désactivées, chaque prompt utilise le moteur et le modèle
des réglages **Texte**, les raccourcis de prompts ne sont pas enregistrés auprès de Windows
et les modèles locaux se déchargent après cinq minutes d’inactivité. Le
raisonnement par prompt reste toujours disponible.

**Fonctions expérimentales**

- onglet **Voix** (prompts vocaux), menu vocal et son raccourci ;
- dictée instantanée ;
- rubrique **Dictée** : moteur de transcription, microphone et test du micro ;
- capture et analyse d’écran : raccourci et mode de capture.

Quand elles sont désactivées, ces éléments sont masqués et leurs raccourcis
ne sont pas réservés auprès de Windows. Une vérification du moteur vocal ou un test du
micro en cours s’arrête, et le modèle vocal inactif est déchargé.

**Valeurs initiales.** Une nouvelle installation démarre avec les deux
interrupteurs désactivés. Une mise à jour depuis une version précédente les
active tous les deux : aucune fonction déjà utilisée ne disparaît.

**Rien n’est supprimé.** Prompts vocaux, raccourcis, modèles choisis par
prompt et délais de déchargement sont conservés, restent dans l’export des
prompts et réapparaissent tels quels à la réactivation. Si des prompts ont
leur propre modèle, SuperMenu demande confirmation avant de désactiver les
fonctions avancées, car ils utiliseront alors le moteur des réglages Texte,
éventuellement en ligne.

Si un raccourci ne peut pas être réactivé après **Appliquer**, une alerte
**Raccourcis inactifs** les énumère ; choisissez-en un autre dans **Réglages >
Raccourcis** ou dans l’onglet **Prompts**.

## Raccourcis clavier

### Valeurs par défaut

| Action | Raccourci | Disponible |
|---|---|---|
| Menu des prompts | `Ctrl+²` | toujours |
| Mode personnalisé | `Ctrl+Alt+M` | toujours |
| Menu vocal | `Ctrl+Alt+²` | fonctions expérimentales |
| Capture d’écran | `Ctrl+Alt+&` | fonctions expérimentales |
| Dictée instantanée | aucun | fonctions expérimentales |
| Raccourci direct d’un prompt | aucun | fonctions avancées |

Pour modifier un raccourci, ouvrez **Réglages > Raccourcis**, cliquez sur
**Définir** et appuyez sur la combinaison voulue. Pendant l’enregistrement,
les autres raccourcis de SuperMenu sont libérés ; une combinaison déjà prise
par un autre raccourci de SuperMenu est refusée. **Afficher le menu des
prompts** teste le menu sans passer par le raccourci global.

### Règles

- Un raccourci combine au moins un modificateur (`Ctrl`, `Alt` ou `Shift`) et
  une touche. La touche `Win` n’est pas acceptée.
- `Shift` seul ne convient qu’aux touches `F1` à `F24`. Une lettre, un
  chiffre, un symbole, Espace, Entrée ou une flèche doit être combiné avec
  `Ctrl` ou `Alt` : Windows réserve la combinaison dans toutes les
  applications, et `Shift+K` empêcherait de taper un K majuscule.
- La majuscule d’une lettre n’ajoute pas `Shift` : `Ctrl+Alt+C` se tape avec
  Ctrl, Alt et C.
- Une combinaison déjà utilisée par Windows ou par une autre application ne
  peut pas être enregistrée.

### Dispositions de clavier

`²` et `&` sont des touches du clavier AZERTY. Sur une autre disposition :

- sans touche `²` (QWERTY par exemple), `Ctrl+²` et `Ctrl+Alt+²` utilisent la
  touche physique située sous Échap : ``Ctrl+` `` et ``Ctrl+Alt+` `` en
  QWERTY ;
- quand `²` ne s’obtient qu’avec AltGr (QWERTZ allemand, AltGr+2), `Ctrl+²`
  utilise aussi la touche sous Échap (`Ctrl+^`), tandis que `Ctrl+Alt+²` reste
  `Ctrl+Alt+2`, c’est-à-dire AltGr+2 ;
- les autres caractères suivent la disposition active : en QWERTY,
  `Ctrl+Alt+&` correspond à `Ctrl+Alt+Shift+7`.

Les réglages affichent toujours le raccourci tel qu’il a été enregistré, par
exemple `Ctrl+²`. Si vous changez souvent de disposition, préférez une
combinaison de lettres, comme `Ctrl+Alt+M`.

### Raccourcis inactifs

Un raccourci que Windows refuse reste enregistré mais inactif :

- au démarrage, une notification liste les raccourcis principaux inactifs et
  le nombre de raccourcis de prompts concernés ;
- dans **Réglages > Raccourcis**, il apparaît suivi de « (inactif) », et
  l’infobulle donne la raison ;
- après **Appliquer**, l’alerte **Raccourcis inactifs** les énumère.

Choisissez alors une autre combinaison.

## Utilisation quotidienne

### Menu des prompts

1. Sélectionnez du texte dans n’importe quelle application.
2. Appuyez sur `Ctrl+²`.
3. Choisissez un prompt dans le menu affiché au curseur.
4. La réponse s’affiche dans la fenêtre de réponse, ou remplace la sélection
   si le prompt utilise l’insertion directe.

Si aucun texte n’a pu être lu, les prompts sont grisés ; **Mode
personnalisé…** reste disponible. Le menu se ferme si vous cliquez ailleurs
ou changez de fenêtre.

Avant de copier la sélection, SuperMenu attend que vous relâchiez Shift, Alt
et Win (et aussi Ctrl pour un raccourci de prompt), deux secondes au plus.
Sinon, l’application recevrait une autre combinaison, comme `Ctrl+Alt+C`. Si
les touches restent enfoncées, le message « Relâchez les touches puis
réessayez » s’affiche ; si la fenêtre active change pendant l’attente, le
raccourci est ignoré.

### Fenêtre de réponse

- **Réessayer** renvoie la même requête, avec le même modèle et le même
  raisonnement ;
- **Copier** place la réponse dans le presse-papiers ;
- **Voir le raisonnement** affiche ou masque le raisonnement renvoyé par un
  modèle compatible ;
- **Insérer le texte** colle la réponse dans l’application d’où la requête
  est partie.

En cas d’échec, la fenêtre affiche « Échec de la requête » et le message
d’erreur : **Copier** et **Réessayer** restent disponibles, **Insérer le
texte** est désactivé.

Pour retrouver la dernière réponse, choisissez **Afficher la dernière
réponse** dans le menu de l’icône, ou **Ouvrir la fenêtre de correction** dans
**Réglages > Application > Fenêtre de correction**.

### Insertion directe

Un prompt dont l’option **Insérer le résultat sans ouvrir la fenêtre de
réponse** est cochée remplace directement la sélection. Un petit indicateur
près du curseur confirme l’envoi et la progression.

Au lancement, SuperMenu mémorise la fenêtre et le champ actifs. Au moment de
coller, il réactive cette fenêtre et vérifie qu’elle appartient toujours à la
même application et que le même champ a le focus. Sinon, l’insertion est
annulée et la réponse n’est pas perdue : elle s’affiche dans la fenêtre de
réponse, avec **Réessayer** et **Insérer le texte**, ou elle est copiée dans
le presse-papiers si cette fenêtre attend déjà une autre réponse. Un message
indique où la retrouver. Une réponse n’est jamais collée dans une fenêtre
devenue active entre-temps, ni quand aucune fenêtre cible n’avait été
mémorisée au lancement.

Pour obtenir un texte prêt à insérer, rédigez le prompt pour qu’il renvoie
seulement le résultat, sans explication.

### Mode personnalisé

Appuyez sur `Ctrl+Alt+M` ou choisissez **Mode personnalisé…** dans le menu.
Une boîte de dialogue montre la sélection éventuelle, telle qu’elle sera
envoyée, et vous permet de saisir une instruction libre, par exemple
« Transforme ces notes en liste d’actions ».

### Raccourcis directs par prompt

Disponibles avec les [fonctions avancées](#fonctions-avancées-et-expérimentales).

1. Dans l’onglet **Prompts**, sélectionnez un prompt.
2. À côté de **Raccourci direct**, cliquez sur **Définir** et appuyez sur la
   combinaison voulue, puis enregistrez le prompt.
3. Sélectionnez du texte dans une application et appuyez sur ce raccourci.

Le prompt démarre sans afficher le menu et respecte son option d’insertion
directe. Deux prompts ne peuvent pas partager une combinaison. En cas de
conflit avec Windows, une autre application ou un raccourci principal de
SuperMenu, la modification est refusée et l’ancien réglage est conservé.

## Presse-papiers et applications particulières

SuperMenu lit la sélection en simulant une copie et insère une réponse en
simulant un collage.

- **Votre presse-papiers est préservé.** Avant de copier ou de coller,
  SuperMenu sauvegarde son contenu avec tous ses formats (texte, texte mis en
  forme, images). Il le restaure ensuite, seulement si personne ne l’a modifié
  entre-temps.
- **Historique et cloud.** Les écritures internes de SuperMenu (le marqueur de
  copie et la réponse à coller) sont exclues de l’historique `Win+V` et de la
  synchronisation du presse-papiers dans le cloud. Votre propre contenu,
  restauré, y revient comme avant.
- **Toutes les dispositions.** La copie et le collage utilisent les touches
  physiques C et V : ils fonctionnent aussi avec un clavier cyrillique, grec
  ou hébreu.
- **Terminaux.** Les consoles Windows et Windows Terminal reçoivent
  `Ctrl+Insert`, puis `Ctrl+Shift+C` si nécessaire. mintty (Git Bash), PuTTY,
  KiTTY et WezTerm ne reçoivent que `Ctrl+Insert`. Aucun de ces terminaux ne
  reçoit `Ctrl+C`, qui interromprait le programme en cours. Le terminal
  intégré de VS Code ne se distingue pas de l’éditeur et reçoit `Ctrl+C` :
  sélectionnez toujours du texte avant d’appeler SuperMenu dans ce terminal.
- **Bureau à distance, Citrix et VMware.** SuperMenu attend plus longtemps
  avant de restaurer le presse-papiers, le temps que la session distante lise
  la réponse à coller.
- **Pas d’accès aux fichiers.** Un texte sélectionné qui ressemble à un chemin
  de fichier reste du texte : SuperMenu ne l’ouvre jamais.

## Gérer les prompts

### Modifier un prompt

L’onglet **Prompts** affiche la liste à gauche et l’éditeur à droite. Le champ
**Rechercher un prompt…** filtre la liste, et l’ordre se change par
glisser-déposer : c’est celui du menu. **Ajouter** crée un prompt,
**Supprimer** en retire un après confirmation.

Champs d’un prompt :

- **Nom** : libellé affiché dans le menu ;
- **Instructions** : texte envoyé au modèle avec la sélection, conservé tel
  quel, balises HTML ou XML comprises ;
- **Modèle de texte pour ce prompt** : fonctions avancées, voir plus bas ;
- **Raisonnement (si disponible)** : voir plus bas ;
- **Message pendant le traitement** : texte affiché pendant l’attente ;
- **Insérer le résultat sans ouvrir la fenêtre de réponse** : insertion
  directe ;
- **Raccourci direct** : fonctions avancées.

Cliquez sur **Enregistrer** pour valider le prompt.

### Raisonnement par prompt

**Raisonnement (si disponible)** propose trois choix :

- **Réglage du moteur** : comportement des réglages Texte ;
- **Sans raisonnement** : réponse plus rapide, adaptée à « Corriger » ;
- **Avec raisonnement** : adapté à une analyse ou à une extraction de chiffres.

Ce choix agit sur OpenAI, Ollama, LM Studio et Foundry Local (Qwen3.5), selon
les capacités du modèle ; certains modèles, comme GPT-OSS, imposent un
raisonnement minimal. Il est enregistré avec le prompt, conservé à l’export
et réutilisé par **Réessayer**. L’affichage du raisonnement suit le mode
réellement demandé. Le raisonnement peut allonger le traitement ; l’insertion
conserve uniquement la réponse finale.

### Modèle par prompt

Disponible avec les [fonctions avancées](#fonctions-avancées-et-expérimentales).
**Modèle de texte pour ce prompt** propose :

- **Utiliser le réglage général** (par défaut) ;
- **LM Studio / Ollama — serveur configuré** : un modèle, et éventuellement
  un poste LM Link, du serveur défini dans **Réglages > Texte** ;
- **OpenAI** : un des modèles OpenAI ;
- **Foundry Local — sur ce PC** : Qwen3.5 4B ou 9B.

Un prompt LM Studio / Ollama suit toujours le serveur des réglages Texte : son
adresse n’est pas enregistrée dans le prompt. **Actualiser** interroge le
serveur actuel, et un poste LM Link ne peut être choisi que si ce serveur est
LM Studio. Le niveau de raisonnement OpenAI des réglages Texte n’est jamais
modifié par le modèle choisi pour un prompt.

### Réinitialiser, restaurer, revenir à une copie

- **Réinitialiser** rétablit le prompt d’origine sélectionné, après
  confirmation.
- **Tout restaurer…** remplace la liste de l’onglet (Prompts ou Voix) par les
  prompts d’origine, après confirmation. Les prompts personnels sont retirés ;
  les réglages des moteurs ne changent pas.
- **Revenir à la copie…** remet la copie précédente de la liste, après
  confirmation ; le message indique sa date, son origine et le nombre de
  prompts. La liste remplacée est elle-même gardée en copie. Chaque nouvel
  usage remonte d’une copie, jusqu’à la plus ancienne des cinq conservées.

SuperMenu garde les cinq dernières copies de chaque liste. Une copie est
faite avant une restauration, un import ou une réinitialisation de tous les
paramètres, et lorsqu’une configuration partiellement illisible est lue. Ces
copies sont stockées dans le fichier de configuration (`prompts_backups` et
`voice_prompts_backups`).

Une entrée illisible dans la configuration n’efface jamais les autres
prompts : elle est réparée avec des valeurs par défaut ou écartée, et une
copie de la liste d’origine est conservée. Si la configuration ne peut pas
être écrite (fichier en lecture seule ou disque plein), un import ou une
restauration est annulé avec un message, sans rien modifier.

### Importer et exporter

**Importer** et **Exporter** se trouvent sous la liste des onglets Prompts et
Voix, ainsi que dans **Réglages > Application > Importer ou exporter les
prompts**. Un seul fichier JSON contient les prompts textuels et vocaux ; il
s’échange entre Windows et macOS.

- L’import vérifie tout le fichier avant d’écrire. Une erreur nomme le prompt
  concerné et ne modifie rien. Un prompt sans instruction est accepté comme
  brouillon. Les fichiers UTF-8, avec ou sans BOM, sont acceptés.
- Une copie de vos prompts est gardée avant l’import (voir **Revenir à la
  copie…**).
- **Aucune adresse de serveur n’est échangée.** L’export n’en contient pas et
  l’import ignore celles qu’un fichier contiendrait : un prompt LM Studio /
  Ollama importé utilise votre serveur des réglages Texte, avec votre jeton.
  Le moteur, le modèle et le poste LM Link de chaque prompt sont repris. Un
  fichier importé ne peut donc viser que les moteurs déjà configurés dans vos
  réglages. Avec les fonctions avancées, un prompt importé peut toutefois
  utiliser OpenAI si votre clé est enregistrée, même si votre moteur Texte est
  local : vérifiez le modèle des prompts importés.

## Voix et dictée

Disponibles avec les [fonctions expérimentales](#fonctions-avancées-et-expérimentales).
Le moteur de transcription se choisit indépendamment du moteur de texte.

### Régler la dictée

Dans **Réglages > Dictée** :

1. Choisissez le **Microphone** (**Actualiser** relit la liste), puis cliquez
   sur **Tester le micro** : le niveau s’affiche pendant cinq secondes, sans
   enregistrement ni envoi d’audio.
2. Choisissez le **Moteur de transcription** :
   - **OpenAI · en ligne** : GPT Live Transcribe, avec votre clé OpenAI ;
     l’audio est envoyé à OpenAI et facturé selon votre usage ;
   - **Nemotron 3.5 · sur ce PC** : Foundry Local, votre voix reste sur le PC ;
     le modèle de 756 Mo se télécharge une fois.
3. Choisissez la **Langue**. OpenAI accepte plusieurs langues attendues ;
   Nemotron accepte une langue ou la détection automatique.
4. Avec Nemotron, cliquez sur **Vérifier le moteur**, puis sur **Télécharger
   le modèle** si nécessaire. La préparation affiche chaque étape :
   vérification des fichiers, activation du GPU, téléchargement, puis
   chargement en mémoire.
5. Cliquez sur **Enregistrer**. Tant que la page diffère des réglages
   enregistrés, « Modifications non enregistrées » s’affiche.

**Options avancées** contient le **Calcul local** (**Automatique — CUDA en
priorité** ou **CPU uniquement**), le vocabulaire et le contexte facultatifs
pour OpenAI et, avec les fonctions avancées, la mémoire du modèle vocal. Les
mots-clés doivent rester courts et correspondre à des termes susceptibles
d’être prononcés.

### Dicter du texte

1. Appuyez sur `Ctrl+Alt+²` et choisissez **Dicter du texte…**.
2. Attendez **À l’écoute** avant de parler. La préparation du moteur ne compte
   pas dans la durée de dictée.
3. Le texte apparaît pendant que vous parlez, avec le niveau du microphone.
4. **Terminer** arrête le microphone et finalise la transcription ;
   **Annuler** abandonne la dictée.
5. Le texte final reste dans la même fenêtre : retouchez-le si besoin, puis
   cliquez sur **Copier** ou **Insérer**.

Une dictée dure au plus cinq minutes. Aucun fichier audio n’est enregistré.

### Après la dictée

Dans **Réglages > Dictée > Après la dictée**, deux options indépendantes :

- **Coller automatiquement quand la dictée se termine** ;
- **Corriger avec le moteur de texte avant d’insérer** : le bouton devient
  **Corriger et insérer**.

La correction utilise le raisonnement du prompt « Corriger » et, avec les
fonctions avancées, le modèle choisi pour ce prompt ; sinon, le moteur et le
modèle des réglages Texte. Si la correction échoue, votre dictée est
conservée et rien n’est collé. Ces options ne changent pas les prompts
vocaux.

### Prompts vocaux

Un prompt vocal applique une instruction au texte dicté, par exemple
« Résume ». L’onglet **Voix** les crée et les modifie, avec les mêmes champs
que les prompts textuels et deux options :

- **Inclure le texte sélectionné dans la requête vocale** ;
- **Ordre des éléments** : ordre de l’instruction, de la dictée et de la
  sélection.

Changer de prompt avec des modifications en cours demande s’il faut
**Enregistrer**, **Ignorer** ou **Annuler**.

Pour lancer un prompt vocal, appuyez sur `Ctrl+Alt+²` et choisissez-le dans le
menu vocal. **Prompt vocal personnalisé…** dicte une instruction ponctuelle.
La transcription est ensuite traitée par le moteur de texte, selon les options
du prompt.

### Dictée instantanée

Dans **Réglages > Raccourcis > Dictée instantanée**, cliquez sur **Définir**
pour choisir un raccourci, aucun n’étant défini au départ. Il lance une dictée
depuis l’application où vous écrivez, sans passer par le menu. Deux modes :

- **Appuyer une fois — arrêter avec Terminer** ;
- **Maintenir pour parler — relâcher pour terminer**.

Attendez **À l’écoute** avant de parler. Relâcher le raccourci pendant la
préparation annule le démarrage.

### Mémoire du modèle vocal

Le modèle Nemotron reste en mémoire entre deux dictées, puis se décharge après
cinq minutes d’inactivité. Avec les
[fonctions avancées](#fonctions-avancées-et-expérimentales), **Options
avancées** propose **Décharger le modèle vocal après** (chaque dictée, 1, 5,
15 ou 30 minutes d’inactivité, ou à la fermeture de SuperMenu) et **Décharger
maintenant**, qui libère la mémoire sans supprimer le modèle téléchargé. Le
microphone reste arrêté entre les dictées.

## Capture d’écran

Disponible avec les [fonctions expérimentales](#fonctions-avancées-et-expérimentales).

1. Appuyez sur `Ctrl+Alt+&`.
2. SuperMenu capture l’image selon le mode choisi.
3. Saisissez une instruction, par exemple « Décris cette image » ou « Extrais
   le texte ».
4. La réponse s’affiche dans la fenêtre de réponse ; **Réessayer** réutilise
   la même image.

Le mode se règle dans **Réglages > Raccourcis > Capture d’écran**, puis
**Enregistrer le mode de capture** :

- **Plein écran** : l’écran principal ;
- **Sélection de zone** : sur l’écran où se trouve le curseur, au pixel près,
  y compris avec une mise à l’échelle de 125 ou 150 % ;
- **Demander à chaque capture** : un menu au curseur propose les deux choix.

La fenêtre de réponse est masquée pendant la capture. L’image est envoyée au
moteur de texte : choisissez un modèle qui accepte les images, comme les
modèles OpenAI. Foundry Local ne traite pas les images. Le fichier temporaire
de la capture est supprimé aussitôt après sa conversion.

## Apparence

Dans **Réglages > Application > Interface et mises à jour**, choisissez le
**Thème** (**Sombre**, **Clair** ou **Automatique (Système)**), puis cliquez
sur **Appliquer**. Le thème change immédiatement.

## Mises à jour

- **Stable** : versions validées, recommandées pour un usage quotidien.
- **Bêta** : version reconstruite automatiquement après chaque modification
  de `main` dont la CI réussit ; elle permet de tester les nouveautés et peut
  contenir des régressions.

Le **Canal de mise à jour** se choisit dans **Réglages > Application >
Interface et mises à jour** et s’enregistre immédiatement. **Vérifier les
mises à jour**, sur cette page ou dans le menu de l’icône, lance une
vérification. La version installée vérifie aussi discrètement au démarrage de
SuperMenu, au plus une fois par jour, et ne se manifeste que si une mise à
jour existe.

Quand une version plus récente existe, SuperMenu propose de la télécharger :

1. L’installateur est téléchargé dans un dossier temporaire privé.
2. Son empreinte SHA-256 est comparée à celle publiée avec la release. Un
   fichier différent est supprimé et refusé.
3. SuperMenu demande s’il faut lancer l’installation, vérifie l’empreinte une
   dernière fois, lance l’installateur et se ferme.
4. Windows demande la confirmation administrateur. Après l’installation,
   SuperMenu redémarre avec vos droits habituels, jamais en administrateur.

Si une nouvelle Bêta paraît pendant le téléchargement, le fichier obtenu est
supprimé : relancez **Vérifier les mises à jour**. Si GitHub limite
temporairement les requêtes, le message indique l’heure de reprise et un lien
vers les releases.

## Données et confidentialité

| Élément | Emplacement |
|---|---|
| Configuration et prompts | `%USERPROFILE%\SuperMenu.ini` |
| Clé OpenAI et jeton d’endpoint | Gestionnaire d’identification Windows |
| Journaux | `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log` |
| Modèles Foundry Local | `%LOCALAPPDATA%\SuperMenu\Foundry\cache\models` |

**Réglages > Application > Dossiers et diagnostic** ouvre le dossier de
configuration et celui des journaux. Le journal est limité à 1 Mo, avec trois
archives. Il ne contient ni clé, ni texte sélectionné, ni instruction saisie,
ni transcription.

Le texte et les images sont envoyés uniquement au moteur choisi. Avec Foundry
Local et Nemotron, tout reste sur le PC ; aucune requête n’est transférée
automatiquement à un autre fournisseur.

## Dépannage

### Le menu n’apparaît pas

1. Vérifiez que l’icône de SuperMenu est dans la zone de notification.
2. Ouvrez **Réglages > Raccourcis** : un raccourci suivi de « (inactif) » est
   refusé par Windows ou pris par une autre application. Choisissez-en un
   autre.
3. Cliquez sur **Afficher le menu des prompts** pour tester sans raccourci.
4. Sur un clavier non AZERTY, voir
   [Dispositions de clavier](#dispositions-de-clavier).

### Les prompts sont grisés

SuperMenu n’a lu aucun texte. Vérifiez que la sélection est active, que
l’application autorise la copie et que vous avez relâché les touches du
raccourci. Le **Mode personnalisé…** reste utilisable sans sélection.

### « Insertion annulée »

La fenêtre ou le champ cible a changé avant le collage. La réponse se trouve
dans la fenêtre de réponse ou dans le presse-papiers, comme l’indique le
message. Évitez de changer de fenêtre pendant une insertion directe.

### Erreurs du moteur de texte

- OpenAI : vérifiez la clé API, la connexion et le crédit du compte, ou
  essayez un autre modèle.
- Ollama ou LM Studio : vérifiez que le serveur est démarré, l’URL, le type
  d’endpoint et le jeton, puis cliquez sur **Actualiser**.
- Réponse interrompue : suivez le conseil du message, par exemple réduire le
  texte, augmenter le contexte du modèle ou choisir **Sans raisonnement**.

### Dictée

1. Dans **Réglages > Dictée**, choisissez le microphone et cliquez sur
   **Tester le micro**. Sans niveau, vérifiez l’autorisation Microphone de
   Windows et essayez une autre entrée.
2. Avec OpenAI, vérifiez la clé et la connexion. Avec Nemotron, cliquez sur
   **Vérifier le moteur** et téléchargez les éléments manquants.
3. Un modèle déchargé se recharge sans nouveau téléchargement.
4. Enregistrez les réglages, puis attendez **À l’écoute** avant de parler.

Si la rubrique **Dictée** n’apparaît pas, activez les
[fonctions expérimentales](#fonctions-avancées-et-expérimentales).

### Mise à jour refusée

Un message indiquant que l’installateur ne correspond pas (ou plus) à
l’empreinte publiée signifie que le fichier téléchargé diffère de celui de la
release : il est supprimé sans être lancé. Réessayez plus tard ou
téléchargez l’installateur depuis la page des releases.

### Journaux

Ouvrez **Réglages > Application > Dossiers et diagnostic > Ouvrir le dossier
des journaux**. Les erreurs inattendues y sont consignées, ainsi que les
étapes du traitement et leur durée.

## Désinstallation

Désinstallez SuperMenu depuis les Paramètres de Windows. SuperMenu est fermé
automatiquement si nécessaire. Le programme de désinstallation demande s’il
faut aussi supprimer vos données : configuration, journaux, modèles locaux et
clés API enregistrées.

Retour au [README Windows](../README.md) ou au
[README principal](../../README.md).
