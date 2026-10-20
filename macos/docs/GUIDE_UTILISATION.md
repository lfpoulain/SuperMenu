# Guide d’utilisation de SuperMenu pour macOS

Ce guide explique comment installer, configurer et utiliser SuperMenu sur
Mac, puis comment résoudre les problèmes courants. Pour une présentation
rapide, consultez le [README macOS](../README.md).

## Sommaire

- [Compatibilité](#compatibilité)
- [Installation](#installation)
- [Premier lancement et Accessibilité](#premier-lancement-et-accessibilité)
- [La fenêtre de configuration](#la-fenêtre-de-configuration)
- [Choisir le moteur de texte](#choisir-le-moteur-de-texte)
- [Fonctions avancées et expérimentales](#fonctions-avancées-et-expérimentales)
- [Configurer les raccourcis](#configurer-les-raccourcis)
- [Utilisation quotidienne](#utilisation-quotidienne)
- [Gérer les prompts](#gérer-les-prompts)
- [Voix et dictée](#voix-et-dictée)
- [Barre des menus et apparence](#barre-des-menus-et-apparence)
- [Mises à jour](#mises-à-jour)
- [Données et confidentialité](#données-et-confidentialité)
- [Dépannage](#dépannage)
- [Désinstallation](#désinstallation)

## Compatibilité

- Mac **Apple Silicon** uniquement. Le nom de chaque DMG contient `arm64`
  pour éviter une installation sur un Mac Intel.
- macOS 13 Ventura ou plus récent, version minimale de Qt 6.11. Les builds
  sont construits et testés sur macOS 14 et 15. Apple Intelligence
  (moteur de texte local) et Apple Speech (dictée locale) demandent macOS 26
  ou plus récent.
- La dictée demande l’autorisation Microphone. La capture d’écran est propre à
  Windows : SuperMenu ne demande pas l’autorisation Enregistrement de l’écran.

## Installation

### Choisir un canal

- **Stable** : version recommandée pour un usage quotidien ;
- **Bêta** : version reconstruite automatiquement après chaque modification
  de `main` dont la CI réussit. Elle permet de tester les nouveautés et peut
  contenir des régressions.

| Canal | Fichier à télécharger |
|---|---|
| Stable | `SuperMenu-macOS-arm64.dmg`, dans la [dernière release](https://github.com/lfpoulain/SuperMenu/releases/latest) |
| Bêta | `SuperMenu_Beta-macOS-arm64.dmg`, dans la release `beta` des [releases](https://github.com/lfpoulain/SuperMenu/releases) |

### Installer le DMG

1. Téléchargez le fichier du canal choisi.
2. Ouvrez le DMG.
3. Glissez `SuperMenu.app` sur le raccourci **Applications**.
4. Éjectez le volume SuperMenu.
5. Lancez l’application depuis `/Applications`.

Les releases publiques sont signées avec un certificat Developer ID et
notarisées par Apple : Gatekeeper reconnaît l’éditeur sans exiger **Ouvrir
quand même**.

Pour les mises à jour, remplacez toujours l’application au même
emplacement. L’identifiant de l’application et l’identité de signature
restent ainsi stables, ce qui aide macOS à conserver l’autorisation
Accessibilité.

## Premier lancement et Accessibilité

Tant qu’Accessibilité n’est pas accordée, SuperMenu ouvre au démarrage sa
fenêtre de configuration sur **Réglages > Application**, où se trouve la
section **Autorisations macOS**. Il le fait aussi quand un raccourci
enregistré est refusé, pour le signaler. Sinon, il reste discrètement dans la
barre des menus.

1. Cliquez sur **Configurer Accessibilité…**.
2. Acceptez le dialogue de macOS indiquant que SuperMenu souhaite contrôler
   l’ordinateur.
3. Activez SuperMenu dans **Réglages Système > Confidentialité et sécurité >
   Accessibilité** si macOS ouvre cette liste.
4. Revenez dans SuperMenu et cliquez sur **Revérifier** si l’état ne s’est pas
   encore actualisé.

Le premier clic laisse macOS présenter son propre dialogue. Si l’autorisation
reste absente, le bouton devient **Ouvrir les réglages…**, pour ne pas
empiler le dialogue système et la fenêtre des réglages.

Une autorisation accordée recharge les raccourcis sans redémarrage, même si
vous avez fermé la fenêtre de SuperMenu entre-temps. **Quitter pour
appliquer** reste disponible si macOS tarde à propager le nouvel état.

L’état affiché est fiable : « Raccourcis globaux actifs » n’apparaît que si
l’autorisation est accordée. Sinon, « Raccourcis inactifs : autorisez
Accessibilité » rappelle ce qui manque.

### Pourquoi cette autorisation ?

Accessibilité sert à :

- recevoir les raccourcis globaux quand vous travaillez dans une autre
  application ;
- lire directement la sélection quand l’application l’expose ;
- envoyer `Cmd+C` et `Cmd+V` quand le passage par le presse-papiers est
  nécessaire.

SuperMenu ne demande pas **Surveillance de l’entrée** : l’ajouter
manuellement n’apporte rien.

## La fenêtre de configuration

Pour l’ouvrir, cliquez sur l’icône de la barre des menus, puis sur **Ouvrir
SuperMenu**. Fermer la fenêtre laisse SuperMenu actif dans la barre des menus.

La fenêtre comporte quatre onglets :

- **Prompts** : liste des prompts textuels et éditeur ;
- **Voix** : prompts vocaux (fonctions expérimentales) ;
- **Réglages**, en quatre rubriques :
  - **Texte** : moteur de texte et modèle ;
  - **Dictée** : microphone et moteur de transcription (fonctions
    expérimentales) ;
  - **Raccourcis** : menu principal, mode personnalisé et dictée instantanée ;
  - **Application** : thème, canal de mise à jour, interrupteurs **Fonctions**,
    autorisations macOS, dossiers et diagnostic ;
- **À propos** : version, licence et lien vers les versions publiées.

Les options rarement utiles sont regroupées dans des sections repliables, comme
**Plus d’options**. **Enregistrer** valide les rubriques Texte et Dictée,
**Appliquer** la rubrique Application ; un raccourci global s’applique dès
qu’il est défini.

## Choisir le moteur de texte

Dans **Réglages > Texte**, la liste **Moteur de texte** propose trois choix.
Cliquez sur **Enregistrer** après chaque modification. Les nouvelles requêtes
utilisent aussitôt la nouvelle configuration ; une requête déjà en cours
termine avec l’ancienne.

### OpenAI

1. Collez votre **Clé API**.
2. Choisissez le **Modèle** : `gpt-5.6-sol` (par défaut), `gpt-5.6-terra`,
   `gpt-5.6-luna` ou `gpt-5.4`.
3. Dans **Plus d’options**, réglez si besoin le **Raisonnement** proposé
   pour ce modèle.

### Ollama / LM Studio

1. Saisissez l’URL de l’endpoint, par exemple `http://localhost:11434` pour
   Ollama.
2. Dans **Plus d’options**, choisissez le type d’endpoint (**Ollama** ou
   **LM Studio / Bionic**), un éventuel jeton et le réglage **Raisonnement /
   think**, adapté aux capacités du modèle. Choisissez **LM Studio / Bionic**
   pour LM Studio, Bionic ou tout autre serveur compatible OpenAI, et
   **Ollama** pour un serveur Ollama.
3. Choisissez le modèle, ou cliquez sur **Actualiser** pour interroger le
   serveur. Vous pouvez aussi saisir un nom de modèle.

Avec LM Studio, les modèles partagés par d’autres postes via **LM Link**
apparaissent avec leur provenance ; **Nommer ce poste distant…** leur donne un
nom lisible. Une adresse saisie avec `/api/v1` fonctionne aussi.

La clé OpenAI et le jeton d’endpoint sont deux réglages séparés : la clé
OpenAI n’est jamais envoyée à un autre serveur.

### Apple Intelligence — local

Sur un Mac Apple Silicon sous macOS 26 ou plus récent :

1. Activez Apple Intelligence dans **Réglages Système > Apple Intelligence et
   Siri** et attendez la fin du téléchargement du modèle. Le bouton **Ouvrir
   les réglages Apple Intelligence** y mène directement.
2. Choisissez **Apple Intelligence — local** comme moteur de texte.
3. Cliquez sur **Vérifier la disponibilité** : l’état doit indiquer **Prêt à
   utiliser**.
4. Cliquez sur **Enregistrer**, puis testez une correction ou un résumé sur un
   court passage.

Le traitement s’exécute sur le Mac, sans clé API ni serveur. Les réglages des
autres moteurs sont conservés. Une erreur Apple est affichée telle quelle : la
demande n’est jamais envoyée automatiquement à un autre moteur.

Le modèle a une capacité de contexte limitée et peut refuser certaines
demandes. Si le texte est trop long, sélectionnez un passage plus court. Ce
moteur ne propose pas de niveau de raisonnement.

### Réponses interrompues

Si le serveur coupe une réponse avant la fin (limite de longueur ou de
contexte), SuperMenu affiche une erreur qui indique quoi changer, par exemple
augmenter la taille de contexte du modèle dans LM Studio. Une réponse
incomplète n’est jamais insérée.

## Fonctions avancées et expérimentales

SuperMenu affiche l’essentiel par défaut. Deux interrupteurs indépendants se
trouvent dans **Réglages > Application > Fonctions** ; cochez-les ou
décochez-les, puis cliquez sur **Appliquer**. Les onglets, rubriques, entrées
de menu et raccourcis concernés apparaissent ou disparaissent aussitôt, sans
redémarrer.

**Fonctions avancées**

- choix du modèle, du fournisseur ou du poste LM Link pour chaque prompt,
  textuel ou vocal ;
- raccourci global propre à chaque prompt ;
- durée de conservation du modèle vocal local (Apple Speech).

Quand elles sont désactivées, chaque prompt utilise le moteur et le modèle
des réglages **Texte**, y compris pour la correction de la dictée, les raccourcis de
prompts sont inactifs et le modèle vocal est déchargé après cinq minutes
d’inactivité. Le raisonnement de chaque prompt reste toujours réglable.

**Fonctions expérimentales**

- onglet **Voix** (prompts vocaux) et sous-menu **Voix** du menu des prompts ;
- entrée **Dicter du texte…** de la barre des menus ;
- dictée instantanée et son raccourci ;
- rubrique **Dictée** des réglages et test du micro.

Quand elles sont désactivées, aucun de ces éléments n’est affiché et le
raccourci de dictée instantanée n’est pas enregistré. Une vérification du moteur vocal ou un test
du micro en cours s’arrête, et le modèle vocal inactif est déchargé.

**Valeurs initiales.** Une nouvelle installation démarre avec les deux
interrupteurs désactivés. Une mise à jour depuis une version précédente les
active tous les deux, afin de ne retirer aucune fonction déjà utilisée.

**Rien n’est supprimé.** Modèles choisis, raccourcis, prompts vocaux et
réglages de dictée sont conservés et réapparaissent tels quels à la
réactivation. Si des prompts ont leur propre modèle, SuperMenu demande
confirmation avant de désactiver les fonctions avancées, car ils utiliseront
alors le moteur des réglages Texte, éventuellement en ligne. L’export et
l’import des prompts conservent toujours tous les champs.

Si un raccourci ne peut pas être réactivé après **Appliquer**, par exemple
parce qu’un prompt utilise la même combinaison que la dictée instantanée, une
seule alerte **Raccourcis inactifs** les énumère. Seul le prompt concerné
reste inactif ; il se réactive dès que l’un des deux raccourcis change.

## Configurer les raccourcis

| Action | Raccourci par défaut | Disponible |
|---|---|---|
| Menu des prompts | `Cmd+Shift+Space` | toujours |
| Mode personnalisé | `Cmd+Shift+M` | toujours |
| Dictée instantanée | aucun | fonctions expérimentales |
| Raccourci d’un prompt | aucun | fonctions avancées |

Pour modifier un raccourci :

1. ouvrez **Réglages > Raccourcis** ;
2. cliquez sur **Définir** à côté du raccourci ;
3. appuyez sur la combinaison souhaitée et validez.

SuperMenu normalise les noms des touches : `Command+Shift+<` et
`Cmd+Shift+<` représentent la même combinaison. L’enregistreur lit la touche
physique : `Cmd+Option+K` est enregistré comme tel, et non avec le caractère
spécial que produit Option. Une combinaison déjà utilisée par SuperMenu est
refusée au lieu de remplacer silencieusement un autre raccourci.

Règles :

- Une lettre, un chiffre, un symbole, Espace, Entrée ou une flèche doit être
  combiné avec `Cmd` ou `Ctrl`. SuperMenu observe le clavier sans intercepter
  la frappe : `Shift+K` ou `Option+Espace` seraient aussi tapés dans
  l’application active. `Shift` ou `Option` seuls restent possibles avec `F1`
  à `F24`.
- Sont réservés : toute combinaison avec `Cmd` et `Q`, `Cmd+H`, `Cmd+M`,
  `Cmd+W`, `Cmd+Space` (Spotlight) et `Cmd+A`, `Cmd+C`, `Cmd+V`, `Cmd+X`,
  `Cmd+Z`.
- Un raccourci sans `Cmd` ni `Ctrl` enregistré par une version précédente
  continue de fonctionner ; le journal conseille de le remplacer. Une
  nouvelle combinaison doit respecter la règle. Les combinaisons réservées
  ci-dessus sont refusées et signalées, même enregistrées par une version
  précédente.

**Afficher le menu des prompts** teste tout le flux sans utiliser le raccourci
global : il aide à distinguer un problème d’écoute clavier d’un problème de
sélection ou d’affichage.

## Utilisation quotidienne

### Ouvrir le menu des prompts

1. Sélectionnez du texte dans l’application courante.
2. Appuyez sur `Cmd+Shift+Space`.
3. Choisissez une action dans le menu affiché près du pointeur.
4. Attendez la réponse.

Les prompts sont désactivés si aucune sélection n’a pu être lue ; **Mode
personnalisé…** reste disponible. Avec les fonctions expérimentales, le menu
contient aussi le sous-menu **Voix**.

SuperMenu mémorise l’application cible avant de passer au premier plan. Pour
un prompt à insertion directe, il lui rend le premier plan dès votre choix,
pendant le traitement.

### Utiliser un raccourci de prompt

Disponible avec les [fonctions avancées](#fonctions-avancées-et-expérimentales).
Un prompt peut posséder sa propre combinaison globale, définie dans l’onglet
**Prompts** avec **Définir** à côté de **Raccourci direct**. Ce raccourci :

1. capture l’application active ;
2. lit la sélection ;
3. lance directement le prompt, sans afficher le menu.

Si aucun texte n’est sélectionné, l’indicateur **Aucun texte sélectionné**
apparaît près du curseur.

### Mode personnalisé

Appuyez sur `Cmd+Shift+M` ou choisissez **Mode personnalisé…** dans le menu.
Une boîte de dialogue montre la sélection éventuelle, telle qu’elle sera
envoyée, et vous permet de saisir une instruction libre :

- « Réécris ce message avec un ton plus chaleureux » ;
- « Transforme ces notes en liste d’actions » ;
- « Explique ce code à un débutant ».

### Fenêtre de réponse

- **Réessayer** renvoie la même requête, avec le même modèle et le même
  raisonnement ;
- **Copier** place la réponse dans le presse-papiers ;
- **Voir le raisonnement** affiche ou masque le raisonnement renvoyé par un
  modèle compatible ;
- **Insérer le texte** réactive l’application capturée et y colle la réponse.

En cas d’échec, la fenêtre affiche « Échec de la requête » et le message
d’erreur : **Copier** et **Réessayer** restent disponibles, **Insérer le
texte** est désactivé.

### Insertion directe

Lorsqu’un prompt active **Insérer le résultat sans ouvrir la fenêtre de
réponse**, un indicateur près du curseur affiche la progression, puis
SuperMenu réactive la cible et colle le résultat.

SuperMenu vérifie juste avant de coller que l’application cible est toujours
active et, grâce à Accessibilité, que la même fenêtre ou le même document a
le focus. Si l’application ou la fenêtre a changé, l’insertion est annulée au
lieu de coller au mauvais endroit. Si Accessibilité ne répond pas, seule
l’application est vérifiée.

Une réponse dont l’insertion est annulée n’est pas perdue : elle s’affiche
dans la fenêtre de réponse, avec **Réessayer**, ou elle est copiée dans le
presse-papiers si cette fenêtre attend déjà une autre réponse. Le message
indique où la retrouver. Après une erreur, la fermeture du message rend le
premier plan à l’application cible.

### Presse-papiers

Quand Accessibilité ne fournit pas la sélection, SuperMenu la copie avec
`Cmd+C`. Il sauvegarde d’abord le presse-papiers et ne le restaure que si
personne ne l’a modifié entre-temps.

Les valeurs que SuperMenu écrit pour son propre usage (marqueur de copie et
réponse à coller) sont signalées comme temporaires et propres à ce Mac : les
gestionnaires d’historique du presse-papiers les ignorent, et le
presse-papiers universel ne les envoie pas à vos autres appareils.

Une application figée ne bloque pas SuperMenu : les demandes Accessibilité
ont un délai court, au-delà duquel le presse-papiers prend le relais.

## Gérer les prompts

### Modifier un prompt

L’onglet **Prompts** affiche la liste à gauche et l’éditeur à droite. Le champ
**Rechercher un prompt…** filtre la liste ; l’ordre se change par
glisser-déposer et devient celui du menu. **Ajouter** crée un prompt,
**Supprimer** en retire un après confirmation.

Champs d’un prompt :

- **Nom** : libellé affiché dans le menu ;
- **Instructions** : texte envoyé au modèle, conservé tel quel, balises HTML
  ou XML comprises ;
- **Modèle de texte pour ce prompt** : fonctions avancées, voir plus bas ;
- **Raisonnement (si disponible)** : voir plus bas ;
- **Message pendant le traitement** ;
- **Insérer le résultat sans ouvrir la fenêtre de réponse** ;
- **Raccourci direct** : fonctions avancées.

**Enregistrer** valide le nom, l’instruction et les raccourcis. Un raccourci
refusé est signalé avec le nom du prompt concerné.

### Raisonnement par prompt

**Raisonnement (si disponible)** propose **Réglage du moteur**, **Sans
raisonnement** (adapté à « Corriger ») ou **Avec raisonnement** (adapté à une
analyse). Le choix agit sur OpenAI, Ollama et LM Studio selon les capacités
du modèle ; certains modèles, comme GPT-OSS, imposent un raisonnement
minimal. Apple Intelligence ne propose pas ce réglage. Le choix est enregistré
avec le prompt, conservé à l’export et réutilisé par **Réessayer**.

### Modèle par prompt

Disponible avec les [fonctions avancées](#fonctions-avancées-et-expérimentales).
**Modèle de texte pour ce prompt** propose **Utiliser le réglage général**,
**LM Studio / Ollama — serveur configuré**, **OpenAI** ou **Apple
Intelligence — sur ce Mac**.

Un prompt LM Studio / Ollama suit toujours le serveur des réglages Texte : son
adresse n’est pas enregistrée dans le prompt. **Actualiser** interroge le
serveur actuel, et un poste LM Link ne peut être choisi que si ce serveur est
LM Studio.

### Réinitialiser, restaurer, revenir à une copie

- **Réinitialiser** rétablit le prompt d’origine sélectionné.
- **Tout restaurer…** remplace la liste de l’onglet courant par les prompts
  d’origine, y compris ceux supprimés. La confirmation indique que les prompts
  personnels et leurs raccourcis seront retirés ; les modèles et autres
  réglages ne changent pas.
- **Restaurer une sauvegarde…** remet la sauvegarde précédente de la liste,
  après confirmation ; le message indique sa date, son origine et le nombre de
  prompts. La liste remplacée est elle-même sauvegardée. Chaque nouvel usage
  remonte d’une sauvegarde, jusqu’à la plus ancienne des cinq conservées.

SuperMenu garde les cinq dernières copies de chaque liste, faites avant une
restauration, avant un import ou lorsqu’une configuration partiellement
illisible est lue. Elles sont stockées dans la configuration
(`prompts_backups` et `voice_prompts_backups`). Une entrée illisible n’efface
jamais les autres prompts : elle est réparée ou écartée.

### Importer et exporter

**Exporter** produit `SuperMenu-prompts.json`, qui contient les prompts
textuels et vocaux et s’échange avec Windows. **Importer** remplace les
prompts actuels après validation complète du fichier :

- une erreur nomme le prompt concerné et ne modifie rien ;
- un prompt sans instruction est accepté comme brouillon ;
- un ancien fichier Mac qui ne contient que des prompts textuels conserve
  votre bibliothèque vocale ;
- une copie de vos prompts est gardée avant l’import.

**Aucune adresse de serveur n’est échangée** : l’export n’en contient pas et
l’import ignore celles d’un fichier. Un prompt LM Studio / Ollama importé
utilise votre serveur des réglages Texte. Le moteur, le modèle et le poste
LM Link de chaque prompt sont repris : un fichier importé ne peut viser que
les moteurs déjà configurés dans vos réglages. Avec les fonctions avancées, un
prompt importé peut toutefois utiliser OpenAI si votre clé est enregistrée,
même si votre moteur Texte est local : vérifiez le modèle des prompts
importés.

## Voix et dictée

Disponibles avec les [fonctions expérimentales](#fonctions-avancées-et-expérimentales).
Le moteur de **Dictée** reconnaît la voix, puis le moteur de **Texte**
applique l’instruction. Pour un traitement entièrement local, choisissez
Apple Speech pour la dictée et Apple Intelligence pour le texte.

### Régler la dictée

Dans **Réglages > Dictée** :

1. Choisissez le **Microphone**, puis cliquez sur **Tester le micro** : le
   niveau s’affiche pendant cinq secondes, sans enregistrement ni envoi.
2. Choisissez le **Moteur de transcription** : **OpenAI · en ligne** (GPT Live
   Transcribe, avec votre clé OpenAI) ou **Apple Speech · sur ce Mac**
   (macOS 26 ou plus récent, la voix reste sur le Mac).
3. Choisissez la **Langue**. Apple Speech demande une langue précise.
4. Pour Apple Speech, cliquez sur **Vérifier le moteur**, puis sur
   **Télécharger le modèle** si le modèle de langue manque. La préparation
   distingue la vérification, le téléchargement éventuel et le chargement en
   mémoire.
5. Cliquez sur **Enregistrer**. Tant que la page diffère des réglages
   enregistrés, « Modifications non enregistrées » s’affiche.

L’accès au microphone est demandé au lancement de la première dictée ou du
test du micro.

### Dicter du texte

1. Choisissez **Dicter du texte…** dans la barre des menus ou dans le
   sous-menu **Voix**.
2. Attendez **À l’écoute** avant de parler.
3. Le texte et le niveau du microphone apparaissent en direct.
4. **Terminer** finalise la dictée ; **Annuler** arrête la capture.
5. Le texte final reste dans la même fenêtre : retouchez-le si besoin, puis
   cliquez sur **Copier** ou **Insérer**.

La limite est de cinq minutes de parole, hors préparation du moteur. Aucun
fichier audio n’est enregistré.

Dans **Réglages > Dictée > Après la dictée**, activez si vous le souhaitez
**Coller automatiquement quand la dictée se termine** et **Corriger avec le
moteur de texte avant d’insérer**. La correction utilise le raisonnement du
prompt « Corriger » et, avec les fonctions avancées, le modèle choisi pour ce
prompt. Une correction échouée conserve la dictée sans la coller.

### Prompts vocaux

L’onglet **Voix** crée, modifie, réordonne et supprime des prompts vocaux,
identiques à ceux de Windows. Par exemple, **Résumer** applique une
instruction de résumé au texte dicté. Choisissez l’affichage du résultat ou
son insertion directe.

Pour répondre à un texte existant, activez **Inclure le texte sélectionné dans
la requête vocale** et choisissez l’**Ordre des éléments**. La sélection et
l’application cible sont conservées pendant la dictée.

Lancez un prompt vocal depuis le sous-menu **Voix** du menu des prompts, ou
avec le bouton **Dicter** de l’éditeur, qui enregistre le prompt avant de le
lancer. **Prompt vocal personnalisé…** dicte une instruction ponctuelle.
Changer de prompt avec des modifications en cours demande s’il faut
**Enregistrer**, **Ignorer** ou **Annuler**.

### Dictée instantanée

Dans **Réglages > Raccourcis > Dictée instantanée**, cliquez sur **Définir**
pour choisir un raccourci, aucun n’étant défini au départ. Choisissez
**Appuyer une fois — arrêter avec Terminer** ou **Maintenir pour parler —
relâcher pour terminer**. Attendez **À l’écoute** avant de parler ; relâcher
pendant la préparation annule le démarrage. Le raccourci conserve
l’application où vous écriviez.

### Mémoire du modèle vocal

Apple Speech reste en mémoire entre deux dictées, puis se décharge après cinq
minutes d’inactivité. Avec les
[fonctions avancées](#fonctions-avancées-et-expérimentales), **Options
avancées** propose **Décharger le modèle vocal après** (chaque dictée, 1, 5,
15 ou 30 minutes, ou à la fermeture) et **Décharger maintenant**, qui libère
la mémoire sans supprimer les ressources téléchargées. Le microphone s’arrête
à chaque fin de dictée.

## Barre des menus et apparence

SuperMenu continue de fonctionner quand sa fenêtre est fermée. Un clic sur
l’icône de la barre des menus ouvre son menu :

- **Ouvrir SuperMenu** ;
- **Afficher le menu des prompts** ;
- **Dicter du texte…** (fonctions expérimentales) ;
- **Afficher la dernière réponse** ;
- **Vérifier les mises à jour** ;
- **Autorisations macOS…** ;
- **Quitter**.

Dans **Réglages > Application > Interface et mises à jour**, choisissez le
thème **Sombre**, **Clair** ou **Automatique (Système)**, puis cliquez sur
**Appliquer**.

## Mises à jour

Le **Canal de mise à jour** (Stable ou Bêta) se choisit dans **Réglages >
Application > Interface et mises à jour** et s’enregistre immédiatement.
SuperMenu vérifie discrètement au démarrage, au plus une fois par jour ;
**Vérifier les mises à jour**, sur cette page ou dans la barre des menus,
lance une vérification.

Bêta et Stable sont la même application : installer l’une remplace l’autre.
Une bêta `X.Y.Z-beta.N` précède la Stable `X.Y.Z`, et SuperMenu ne propose
qu’une version plus récente : en repassant sur le canal Stable, vous gardez
votre bêta jusqu’à la Stable suivante, ou réinstallez la Stable depuis la
[dernière release](https://github.com/lfpoulain/SuperMenu/releases/latest).

L’updater lit un manifeste propre à macOS :

| Canal | Manifeste | DMG |
|---|---|---|
| Stable | `update-macos-stable.json` | `SuperMenu-macOS-arm64.dmg` |
| Bêta | `update-macos-beta.json` | `SuperMenu_Beta-macOS-arm64.dmg` |

Le manifeste indique la version, le canal, l’architecture, le tag, le nom
exact du DMG et son empreinte SHA-256. SuperMenu ouvre directement le
téléchargement du DMG compatible ; il ne peut pas choisir un installateur
Windows.

SuperMenu ne se remplace pas pendant son exécution. Après le téléchargement :

1. quittez SuperMenu ;
2. ouvrez le nouveau DMG ;
3. glissez `SuperMenu.app` vers `/Applications` et acceptez le remplacement ;
4. relancez l’application.

## Données et confidentialité

La configuration est stockée ici :

```text
~/Library/Application Support/SuperMenu/SuperMenu.ini
```

Le fichier n’est lisible que par votre compte (`0600`). SuperMenu n’utilise
pas le Trousseau, pour éviter des demandes d’accès répétées : protégez la clé
API comme tout autre secret de votre compte.

Les journaux se trouvent ici :

```text
~/Library/Logs/SuperMenu/supermenu.log
~/Library/Logs/SuperMenu/native-crash.log
```

Ils décrivent les étapes techniques, les durées, les autorisations et les
erreurs, sans enregistrer les clés, la sélection, le contenu des prompts ni
les touches tapées. **Réglages > Application > Dossiers et diagnostic** ouvre
ces deux dossiers.

## Dépannage

### Le raccourci ne répond pas

1. Ouvrez **Autorisations macOS…** depuis la barre des menus.
2. Vérifiez que l’état indique « Raccourcis globaux actifs ».
3. Cliquez sur **Revérifier**.
4. Utilisez **Afficher le menu des prompts** pour tester sans raccourci.
5. Vérifiez qu’aucun prompt n’utilise la même combinaison.

Si le menu manuel fonctionne mais pas le raccourci, le problème vient de
l’autorisation ou de l’écoute clavier. Si aucun des deux ne fonctionne,
consultez les journaux.

### SuperMenu n’apparaît pas dans Accessibilité

Cliquez d’abord sur **Configurer Accessibilité…** dans l’application. macOS
ajoute une application à la liste quand elle demande l’autorisation, pas
simplement quand elle est copiée dans `/Applications`.

Si un ajout manuel est nécessaire, sélectionnez exactement
`/Applications/SuperMenu.app`. N’autorisez pas une copie restée dans le DMG ou
dans le dossier Téléchargements.

### Le menu s’ouvre mais les prompts sont grisés

SuperMenu n’a lu aucun texte. Vérifiez que :

- une sélection est bien active ;
- l’application autorise la copie de cette sélection ;
- le texte n’est pas dans une zone protégée, un champ de mot de passe ou une
  vue qui n’expose pas sa sélection.

### « L’application cible a changé » ou « Insertion annulée »

L’application, la fenêtre ou le document capturé n’est plus considéré comme
une cible sûre. Ne changez pas d’application, de fenêtre ou de document
pendant la requête. En insertion directe, la réponse reste disponible dans la
fenêtre de réponse ou dans le presse-papiers. Pour seulement récupérer le
résultat, utilisez **Copier** plutôt que **Insérer le texte**.

### L’endpoint local ne répond pas

- vérifiez que le serveur Ollama ou LM Studio est démarré ;
- vérifiez l’URL et le port ;
- choisissez le bon type d’endpoint ;
- cliquez sur **Actualiser** pour tester la liste des modèles ;
- vérifiez le jeton si le serveur est protégé.

### Apple Intelligence ou Apple Speech indisponible

Vérifiez la version de macOS (26 ou plus récent), l’activation d’Apple
Intelligence et la fin du téléchargement de son modèle. Si le message indique
qu’un composant Apple manque, réinstallez SuperMenu depuis le DMG.

### La mise à jour n’est pas proposée

- vérifiez le canal sélectionné ;
- comparez la version de l’onglet **À propos** à celle de la release ;
- cliquez sur **Vérifier les mises à jour** ;
- une version ancienne, antérieure au manifeste macOS, doit être remplacée une
  fois à la main depuis les releases GitHub.

### Où trouver les journaux ?

Ouvrez **Réglages > Application > Dossiers et diagnostic > Ouvrir le dossier
des journaux**. `supermenu.log` trace notamment la réception du raccourci, la
capture et l’activation de la cible, la lecture de la sélection, l’affichage
du menu et les erreurs d’insertion ou de moteur.

## Désinstallation

1. Quittez SuperMenu depuis son menu.
2. Si vous souhaitez aussi supprimer réglages et journaux, ouvrez d’abord les
   deux dossiers depuis **Réglages > Application > Dossiers et diagnostic**.
3. Placez `/Applications/SuperMenu.app` dans la Corbeille.
4. Placez les dossiers `SuperMenu` de `~/Library/Application Support` et de
   `~/Library/Logs` dans la Corbeille, si vous le souhaitez.
5. Retirez éventuellement SuperMenu de la liste Accessibilité.

Retour au [README macOS](../README.md) ou au
[README principal](../../README.md).
