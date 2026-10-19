# Politique de sécurité

## Versions prises en charge

| Version | Correctifs de sécurité |
|---|---|
| Dernière version Stable (marquée « Latest » sur la page [Releases](https://github.com/lfpoulain/SuperMenu/releases)) | Oui |
| Bêta roulante (release `beta`) | Oui |
| Versions Stable précédentes | Non : installez la dernière version |
| Forks et builds modifiés | Non |

Un correctif arrive d’abord dans la bêta, puis dans une nouvelle version
Stable.

## Signaler une vulnérabilité

**N’ouvrez pas d’issue publique** et ne décrivez pas la faille dans une pull
request ou un commentaire.

Utilisez le signalement privé de GitHub : onglet **Security** du dépôt, puis
**Report a vulnerability**
([lien direct](https://github.com/lfpoulain/SuperMenu/security/advisories/new)).
Seul le mainteneur voit votre rapport.

Cette fonction doit être activée par le propriétaire du dépôt. Si le bouton
n’apparaît pas encore dans l’onglet **Security**, ne publiez aucun détail :
contactez le mainteneur via son profil GitHub,
[@lfpoulain](https://github.com/lfpoulain), pour convenir d’un échange privé.

Un rapport utile indique :

- la plateforme (Windows ou macOS), la version de SuperMenu et son canal ;
- le composant concerné et l’impact possible ;
- les étapes ou la preuve de concept permettant de reproduire le problème ;
- si possible, une piste de correction.

N’y joignez jamais de vraie clé API, de mot de passe ni de données
personnelles.

## Délais indicatifs

SuperMenu est maintenu par une seule personne, sur son temps libre :

- accusé de réception : sous 7 jours ;
- première évaluation : sous 14 jours ;
- correctif : selon la gravité, publié dans la bêta puis dans une version
  Stable.

Merci d’attendre la publication du correctif, ou 90 jours sans réponse, avant
toute divulgation publique. Si vous le souhaitez, vous serez crédité dans
l’avis de sécurité.

## Périmètre

Sont concernés en priorité :

- **mise à jour et installation** : recherche et téléchargement des mises à
  jour, vérification des manifestes et des empreintes SHA-256, installateur
  Windows, DMG macOS, workflows de publication ;
- **stockage des secrets** : clés API (stockage sécurisé de Windows, fichier
  de configuration réservé au compte sous macOS), fuite de clés, de texte
  sélectionné ou de prompts dans les journaux ;
- **presse-papiers et insertion** : contenu laissé dans le presse-papiers ou
  son historique, texte inséré dans une autre fenêtre que celle visée,
  lecture involontaire de contenu ;
- **routage des requêtes IA** : texte ou clé envoyé à un autre serveur que
  celui configuré (par exemple via un fichier de prompts importé), contenu
  renvoyé par un serveur interprété comme du code ou du HTML.

Sont hors périmètre :

- le comportement des fournisseurs d’IA (OpenAI, Ollama, LM Studio, Foundry
  Local, Apple) : contenu des réponses, erreurs du modèle, injection de prompt
  dans le texte traité, conservation des données par le fournisseur. Signalez
  ces points au fournisseur concerné ;
- les failles d’une dépendance sans impact démontré sur SuperMenu, à signaler
  au projet d’origine ;
- les attaques qui supposent une session utilisateur ou une machine déjà
  compromise, ou un accès administrateur ;
- les versions non prises en charge, les forks et les builds modifiés.
