# Guide d’utilisation de SuperMenu pour macOS

Ce guide couvre l’installation, le premier lancement, les fournisseurs IA, les
raccourcis, les prompts, les mises à jour et le dépannage de la composition
macOS.

## Sommaire

- [Compatibilité](#compatibilité)
- [Installation](#installation)
- [Premier lancement et Accessibilité](#premier-lancement-et-accessibilité)
- [Configurer le fournisseur IA](#configurer-le-fournisseur-ia)
- [Prompts vocaux](#prompts-vocaux)
- [Configurer les raccourcis](#configurer-les-raccourcis)
- [Utilisation quotidienne](#utilisation-quotidienne)
- [Gérer les prompts](#gérer-les-prompts)
- [Interface et barre des menus](#interface-et-barre-des-menus)
- [Mises à jour](#mises-à-jour)
- [Données et confidentialité](#données-et-confidentialité)
- [Dépannage](#dépannage)
- [Désinstallation](#désinstallation)

## Compatibilité

La distribution actuelle cible les Mac **Apple Silicon**. Le nom de chaque
asset contient explicitement `arm64` afin d’éviter son installation sur un Mac
Intel incompatible.

La version macOS propose le texte et la transcription en direct avec OpenAI ou
Apple Speech local (macOS 26+). La dictée demande la permission Microphone.
La capture d’écran reste propre à Windows ; SuperMenu ne demande pas la
permission Enregistrement de l’écran sur Mac.

## Installation

### Choisir un canal

- **Stable** : version recommandée pour un usage quotidien ;
- **Beta** : version reconstruite automatiquement après chaque changement de
  `main` dont la CI complète réussit, ainsi que depuis la branche de test dédiée
  `codex/foundry-local-windows`.

Les deux canaux sont disponibles sur
[GitHub Releases](https://github.com/lfpoulain/SuperMenu/releases).

| Canal | Fichier à télécharger |
|---|---|
| Stable | `SuperMenu-macOS-arm64.dmg` |
| Beta | `SuperMenu_Beta-macOS-arm64.dmg` |

### Installer le DMG

1. Téléchargez le fichier correspondant au canal choisi.
2. Ouvrez le DMG.
3. Glissez `SuperMenu.app` sur le raccourci **Applications**.
4. Éjectez le volume SuperMenu.
5. Lancez l’application depuis `/Applications`.

Les releases publiques sont signées avec Developer ID et notariées par Apple.
Gatekeeper doit donc reconnaître l’éditeur sans exiger **Ouvrir quand même**.

Pour les mises à jour suivantes, remplacez toujours l’application au même
emplacement. Le bundle identifier et l’identité de signature restent ainsi
stables, ce qui aide macOS à conserver l’autorisation Accessibilité.

## Premier lancement et Accessibilité

Au premier démarrage, SuperMenu affiche sa fenêtre de configuration sur la
section des autorisations.

1. Cliquez sur **Configurer Accessibilité…**.
2. Acceptez le dialogue natif indiquant que SuperMenu souhaite contrôler
   l’ordinateur.
3. Activez SuperMenu dans **Réglages Système > Confidentialité et sécurité >
   Accessibilité** si macOS ouvre cette liste.
4. Revenez dans SuperMenu et cliquez sur **Revérifier** si l’état ne s’est pas
   encore actualisé.

Le premier clic demande à macOS de présenter son propre dialogue. Si la
permission reste absente, le bouton devient **Ouvrir les réglages…** pour ne pas
empiler le dialogue système et la fenêtre des réglages.

Une permission accordée recharge normalement les moniteurs de raccourcis sans
redémarrage. Le bouton **Quitter pour appliquer** reste disponible pour les cas
où macOS tarde à propager son nouvel état.

### Pourquoi cette permission ?

Accessibilité est utilisée pour :

- recevoir les raccourcis globaux lorsque vous travaillez dans une autre
  application ;
- lire directement la sélection lorsque l’application cible l’expose ;
- émettre `Cmd+C` et `Cmd+V` lorsque le chemin presse-papiers est nécessaire.

SuperMenu ne demande pas **Surveillance de l’entrée**. L’ajouter manuellement
n’améliore pas le fonctionnement normal de cette version.

## Prompts vocaux

L’onglet **Voix** permet de créer, modifier, réordonner et supprimer les mêmes
prompts vocaux que sur Windows. Par exemple, **Résumer** applique une instruction
de résumé au texte obtenu après votre dictée. Choisissez l’affichage du résultat
ou son insertion directe dans l’application cible.

Pour répondre à un texte existant, activez **Inclure le texte sélectionné** et
choisissez l’ordre des instructions, de la dictée et de la sélection. La sélection
et l’application cible sont conservées pendant la transcription.

Lancez le raccourci principal puis ouvrez le sous-menu **Voix** : dictée simple,
prompt vocal enregistré, ou **Prompt vocal personnalisé…** pour une instruction
ponctuelle. Le bouton **Dicter** de l’éditeur vocal enregistre le prompt avant de
le lancer. **Annuler** interrompt la dictée sans lancer le traitement du texte.

Le moteur de **Dictée** reconnaît la voix, puis le moteur de **Texte** applique
l’instruction. Pour un traitement entièrement local, choisissez Apple Speech
pour la dictée et Apple Intelligence pour le texte, sur un Mac compatible.

Les boutons **Importer** et **Exporter** transfèrent les prompts textuels et
vocaux entre Mac et Windows. Un ancien fichier Mac contenant seulement des
prompts textuels conserve votre bibliothèque vocale actuelle.

## Configurer le fournisseur IA

Ouvrez **SuperMenu > Paramètres** depuis l’icône de la barre des menus.

Pour la voix, ouvrez **Dictée** : le moteur vocal se choisit séparément du moteur
de texte. Sélectionnez OpenAI ou Apple Speech, une langue et le microphone.
**Tester le micro** affiche son niveau pendant cinq secondes, sans sauvegarde
ni envoi. Pour Apple Speech, utilisez **Vérifier** puis téléchargez les ressources
si nécessaire. Enregistrez vos choix, cliquez sur **Dicter** et attendez
**À l’écoute** avant de parler. Le texte apparaît en direct ; **Terminer** le
finalise et **Annuler** arrête la capture. La limite est de cinq minutes de parole,
hors préparation du moteur.

La dictée simple reste dans cette fenêtre : le texte final peut être retouché,
copié ou inséré dans l’application d’origine. Dans **Dictée > Après la dictée**,
activez si souhaité **Coller automatiquement** et/ou **Corriger avec le moteur de
texte avant d’insérer**. Une correction échouée conserve la dictée sans la coller.
Les prompts vocaux conservent leur propre traitement et leur fenêtre de réponse.

Dans **Réglages > Raccourcis > Dictée instantanée**, définissez une combinaison
(facultative, désactivée initialement). Choisissez **Appuyer une fois** pour arrêter
avec **Terminer**, ou **Maintenir pour parler** pour arrêter au relâchement.
Attendez **À l’écoute** avant de parler ; relâcher pendant la préparation annule
le démarrage du microphone. Le raccourci conserve l’application où vous écriviez.

Dans **Options avancées**, choisissez quand décharger le modèle local :
immédiatement, après 1/5/15/30 minutes d’inactivité, ou à la fermeture de
SuperMenu. La valeur par défaut est cinq minutes. **Décharger maintenant**
libère la mémoire sans supprimer les ressources téléchargées.

### OpenAI

Choisissez **OpenAI** dans **Fournisseur IA**, puis renseignez :

1. la clé API OpenAI ;
2. le modèle ;
3. le niveau de raisonnement proposé pour ce modèle.

Cliquez sur **Enregistrer**. Les nouvelles requêtes utilisent immédiatement la
configuration enregistrée ; une requête déjà en cours conserve le client avec
lequel elle a démarré.

### Ollama ou LM Studio

Choisissez **Ollama / LM Studio** dans **Fournisseur IA**, puis configurez :

- l’URL de l’endpoint, par exemple `http://localhost:11434` pour Ollama ;
- un jeton distinct si l’endpoint privé en exige un ;
- le type **Ollama** ou **LM Studio** ;
- le modèle ;
- l’option de raisonnement ou `think` compatible avec le modèle.

Le bouton **Actualiser** interroge l’endpoint et remplit la liste des modèles.
Vous pouvez également saisir un identifiant de modèle manuellement.

La clé OpenAI et le jeton d’endpoint sont deux réglages séparés. Activer un
endpoint local ne réutilise jamais implicitement la clé OpenAI.

### Apple Intelligence — local

Sur un Mac Apple Silicon avec macOS 26 ou supérieur :

1. activez Apple Intelligence dans **Réglages Système > Apple Intelligence et Siri**
   et attendez la fin du téléchargement du modèle ;
2. choisissez **Apple Intelligence — local** dans **Fournisseur IA** ;
3. cliquez sur **Vérifier la disponibilité** : l’état doit indiquer **Prêt** ;
4. cliquez sur **Enregistrer**, puis testez une correction, une reformulation
   ou un résumé sur un court passage.

Le traitement s’exécute sur le Mac. Aucune clé API ni installation d’Ollama
n’est nécessaire. Les réglages des autres fournisseurs sont conservés et restent
accessibles en changeant de fournisseur. Une erreur Apple est affichée ; la
demande n’est jamais envoyée automatiquement à un autre fournisseur.

Le modèle a une capacité de contexte limitée et peut refuser certaines demandes.
Si le texte est trop long, sélectionnez un passage plus court. Cette intégration
ne propose pas de niveau de raisonnement. **Réessayer**, **Copier**, **Écrire**,
les prompts personnalisés sans sélection et l’insertion directe restent disponibles.

Cette intégration est disponible dans la version stable. Le canal **Bêta**
reste disponible pour tester les prochaines évolutions.

## Configurer les raccourcis

Les valeurs par défaut sont :

| Action | Raccourci |
|---|---|
| Menu principal | `Cmd+Shift+Space` |
| Mode personnalisé | `Cmd+Shift+M` |

Pour modifier un raccourci :

1. ouvrez l’onglet **Paramètres** ;
2. cliquez sur **Définir** ;
3. appuyez sur la combinaison souhaitée ;
4. validez l’enregistreur ;
5. cliquez sur **Enregistrer**.

SuperMenu normalise les noms des touches. Par exemple,
`Command+Shift+<` et `Cmd+Shift+<` représentent la même combinaison. Un doublon
est refusé au lieu de remplacer silencieusement un raccourci existant.

Le bouton **Afficher le menu des prompts** permet de tester tout le flux sans
utiliser le raccourci global. Il aide à distinguer un problème d’écoute clavier
d’un problème de sélection ou d’affichage.

## Utilisation quotidienne

### Ouvrir le menu principal

1. Sélectionnez du texte dans l’application courante.
2. Appuyez sur `Cmd+Shift+Space`.
3. Choisissez une action dans le menu affiché près du pointeur.
4. Attendez la réponse.

Les prompts textuels sont désactivés si aucune sélection n’a pu être lue. Le
mode personnalisé reste disponible.

SuperMenu mémorise l’application cible avant de prendre le premier plan. Cette
identité est utilisée pour revenir vers la bonne fenêtre lors d’une insertion.

### Utiliser un raccourci de prompt

Un prompt peut posséder sa propre combinaison globale. Ce chemin :

1. capture l’application active ;
2. lit la sélection ;
3. lance directement le prompt associé sans afficher le menu.

Si aucun texte n’est sélectionné, un indicateur **Aucun texte sélectionné**
apparaît près du curseur.

### Mode personnalisé

Appuyez sur `Cmd+Shift+M` ou choisissez **Mode personnalisé** dans le menu. Une
boîte de dialogue affiche la sélection éventuelle et permet de saisir une
instruction libre.

Exemples :

- « Réécris ce message avec un ton plus chaleureux » ;
- « Transforme ces notes en liste d’actions » ;
- « Explique ce code à un débutant ».

### Fenêtre de réponse

Après un traitement normal, quatre actions peuvent être proposées :

- **Réessayer** renvoie la dernière requête ;
- **Copier** place la réponse affichée dans le presse-papiers ;
- **Voir le raisonnement** affiche ou masque les blocs de raisonnement renvoyés
  par un modèle compatible ;
- **Écrire** réactive l’application capturée et y colle la réponse.

L’insertion est annulée si la cible n’existe plus ou si une autre application
est devenue active au moment critique. Cette vérification évite de coller une
réponse dans la mauvaise fenêtre.

### Insertion directe

Lorsqu’un prompt active **Insérer directement la réponse dans l’application
cible**, la fenêtre de réponse n’est pas ouverte. Un indicateur près du curseur
affiche la progression, puis SuperMenu réactive la cible et colle le résultat.

Évitez de changer d’application pendant cette opération : l’identité et l’état
de la cible sont volontairement vérifiés avant le collage.

## Gérer les prompts

L’onglet **Prompts** affiche le catalogue à gauche et l’éditeur à droite.

Pour chaque prompt, vous pouvez modifier :

- le nom affiché dans le menu ;
- l’instruction envoyée au modèle ;
- le message d’attente ;
- l’insertion directe ;
- le raccourci global facultatif.

La liste peut être réordonnée par glisser-déposer. Cet ordre devient celui du
menu contextuel.

### Ajouter ou supprimer

- **Ajouter** crée un prompt vide en fin de liste ;
- **Supprimer** demande une confirmation ;
- **Enregistrer le prompt** valide le nom, l’instruction et les conflits de
  raccourcis.

### Importer et exporter

**Exporter** produit `SuperMenu-prompts.json` avec un numéro de schéma et le
catalogue complet. **Importer** remplace le catalogue actuel après validation.
Si le fichier contient un raccourci invalide ou dupliqué, l’import est annulé
et les prompts précédents sont restaurés.

Conservez une exportation avant une modification importante du catalogue.

## Interface et barre des menus

SuperMenu continue de fonctionner lorsque sa fenêtre est fermée. L’icône de la
barre des menus propose :

- **Ouvrir SuperMenu** ;
- **Afficher le menu des prompts** ;
- **Afficher la dernière réponse** ;
- **Rechercher une mise à jour** ;
- **Autorisations macOS…** ;
- **Quitter**.

Un clic sur l’icône ouvre uniquement ce menu ; il ne doit pas afficher la
fenêtre de configuration en même temps.

Dans **Paramètres > Interface et mises à jour**, vous pouvez choisir le thème
Sombre, Clair ou Auto, ainsi que le canal Stable ou Beta.

## Mises à jour

SuperMenu effectue au maximum une vérification silencieuse par jour et propose
également **Rechercher une mise à jour** dans l’onglet À propos et la barre des
menus.

L’updater macOS lit un manifeste propre à la plateforme :

| Canal | Manifeste | DMG |
|---|---|---|
| Stable | `update-macos-stable.json` | `SuperMenu-macOS-arm64.dmg` |
| Beta | `update-macos-beta.json` | `SuperMenu_Beta-macOS-arm64.dmg` |

Le manifeste indique la version, le canal, l’architecture, le tag et le nom
exact de l’asset. Le bouton ouvre directement le téléchargement du DMG
compatible ; il ne peut pas sélectionner un installateur Windows.

SuperMenu ne remplace pas une application en cours d’exécution. Après le
téléchargement :

1. quittez SuperMenu ;
2. ouvrez le nouveau DMG ;
3. glissez `SuperMenu.app` vers `/Applications` et acceptez le remplacement ;
4. relancez l’application.

Une installation antérieure à l’introduction du manifeste macOS peut nécessiter
un dernier téléchargement manuel depuis GitHub Releases. Les versions
suivantes utilisent le nouveau chemin intégré.

## Données et confidentialité

La configuration est stockée ici :

```text
~/Library/Application Support/SuperMenu/SuperMenu.ini
```

Le fichier est limité au compte utilisateur (`0600`). La composition macOS
n’utilise pas le Trousseau afin d’éviter les demandes répétées provoquées par
les anciens builds de test non signés. La clé API doit donc être protégée comme
tout autre secret du compte utilisateur.

Les journaux se trouvent ici :

```text
~/Library/Logs/SuperMenu/supermenu.log
~/Library/Logs/SuperMenu/native-crash.log
```

Ils décrivent les étapes techniques, les durées, les permissions et les erreurs
sans enregistrer les clés, la sélection ou le contenu des prompts.

## Dépannage

### Le raccourci ne répond pas

1. Ouvrez **Autorisations macOS…** depuis la barre des menus.
2. Vérifiez que l’état Accessibilité est accordé.
3. Cliquez sur **Revérifier**.
4. Utilisez **Afficher le menu des prompts** pour tester sans raccourci.
5. Vérifiez qu’aucun prompt n’utilise la même combinaison.

Si le menu manuel fonctionne mais pas le raccourci, le problème se situe dans
la permission ou l’écoute clavier. Si aucun des deux ne fonctionne, consultez
les journaux.

### SuperMenu n’apparaît pas dans Accessibilité

Cliquez d’abord sur **Configurer Accessibilité…** dans l’application. macOS
ajoute normalement une application à la liste lorsqu’elle demande la
permission, pas simplement lorsqu’elle est copiée dans `/Applications`.

Si un ajout manuel est nécessaire, sélectionnez exactement
`/Applications/SuperMenu.app`. Évitez d’autoriser une copie laissée dans un DMG
ou le dossier Téléchargements.

### Le menu s’ouvre mais les prompts sont grisés

SuperMenu n’a lu aucun texte. Vérifiez que :

- une sélection réelle est active ;
- l’application autorise la copie de cette sélection ;
- le texte n’est pas situé dans une zone protégée, un champ de mot de passe ou
  une vue qui n’expose pas sa sélection.

### « La cible a changé » ou « Insertion annulée »

L’application capturée n’est plus considérée comme la cible sûre. Ne changez
pas d’application pendant la requête, puis relancez le prompt depuis la fenêtre
où le texte doit être inséré.

Si vous souhaitez seulement récupérer le résultat, utilisez **Copier** plutôt
que **Écrire**.

### L’endpoint local ne répond pas

- vérifiez que le serveur Ollama ou LM Studio est démarré ;
- vérifiez l’URL et le port ;
- choisissez le bon type d’endpoint ;
- utilisez **Actualiser** pour tester la liste des modèles ;
- vérifiez le jeton si le serveur est protégé.

### La mise à jour n’est pas proposée

- vérifiez le canal sélectionné ;
- comparez la version de l’onglet **À propos** à celle de la release ;
- essayez **Rechercher une mise à jour** manuellement ;
- pour une ancienne version sans manifeste macOS, ouvrez directement GitHub
  Releases.

### Où trouver les logs ?

Dans l’onglet **À propos**, cliquez sur **Ouvrir le dossier des journaux**. Le
fichier `supermenu.log` trace notamment :

- réception du raccourci AppKit ;
- passage vers le thread Qt ;
- capture et activation de la cible ;
- lecture de la sélection ;
- présentation du menu ;
- erreurs d’insertion ou d’API.

## Désinstallation

1. Quittez SuperMenu depuis son menu.
2. Placez `/Applications/SuperMenu.app` dans la Corbeille.
3. Retirez éventuellement SuperMenu de la liste Accessibilité.
4. Si vous souhaitez également supprimer les réglages et journaux, ouvrez les
   deux dossiers depuis l’onglet À propos avant de supprimer l’application,
   puis placez le dossier `SuperMenu` correspondant dans la Corbeille.

Retour au [README macOS](../README.md) ou au
[README principal](../../README.md).


## Nouveau cycle bêta : raisonnement par prompt

Dans **Prompts** ou **Voix**, choisissez **Raisonnement (si disponible)** :
**Réglage du moteur** conserve le comportement habituel ; **Sans raisonnement**
convient par exemple à « Corriger » ; **Avec raisonnement** convient à une analyse
ou une extraction de chiffres. Ce choix s’enregistre avec le prompt, s’exporte
et reste identique avec **Réessayer**. Il ne modifie pas le réglage des autres prompts.
Les anciens prompts conservent leur comportement jusqu’à modification.

Le choix agit sur OpenAI et les moteurs compatibles Ollama / LM Studio, selon
les capacités du modèle. Foundry Local le prend en charge avec les deux Qwen3.5.
Apple Foundation Models ne propose pas de commutateur de raisonnement ; il reste
automatique. Certains modèles, notamment GPT-OSS, imposent un effort minimal.
Le raisonnement peut allonger le traitement ; l’insertion conserve la réponse finale.

Avec Foundry, le délai d’inactivité et **Décharger maintenant** libèrent les poids
du modèle tout en conservant le moteur initialisé. Fermer SuperMenu libère aussi
le moteur. L’interface distingue la préparation du GPU, le chargement des poids
et le traitement ou raisonnement. Les durées par phase sont consignées dans les
journaux, sans enregistrer le texte traité.
