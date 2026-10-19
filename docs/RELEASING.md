# Publier une version de SuperMenu

Ce document décrit la procédure de publication telle qu’elle est implémentée
dans `.github/workflows/`. Elle est réservée au mainteneur : elle demande les
droits d’écriture sur le dépôt et les secrets de signature Apple.

## Vue d’ensemble

| Workflow | Déclencheur | Résultat |
|---|---|---|
| `ci.yml` (**CI**) | push sur `main`, pull request, lancement manuel | tests Windows et macOS, DMG de contrôle non signé ; aucune release |
| `beta-release.yml` (**Beta Release**) | CI réussie après un push sur `main` du dépôt, ou lancement manuel sur `main` | prérelease roulante `beta`, remplacée à chaque build |
| `stable-release.yml` (**Stable Release**) | push d’un tag `vX.Y.Z` sur un commit de `main` | release Stable `vX.Y.Z`, marquée « Latest » si c’est la plus récente |
| `native-helpers.yml` | changement des helpers Swift, chaque semaine, lancement manuel | contrôle informatif sur macOS 26 ; ne bloque rien |

## Numéros de version

- `win32/VERSION` contient la **prochaine version Stable attendue** pour
  Windows, sans `v` (par exemple `1.3.0`). Le tag Stable doit lui correspondre
  exactement, et la release s’appelle « SuperMenu X.Y.Z » d’après ce numéro.
- `macos/VERSION` est **indépendant** et n’est pas comparé au tag : les deux
  fichiers valent `1.3.0` pour la Stable 1.3.0, alors que la Stable `v1.2.1`
  contenait la version macOS 1.2.8. Il doit être augmenté à chaque Stable :
  sinon l’updater macOS ne voit aucune version plus récente. Le workflow
  Stable refuse donc un numéro qui n’est pas supérieur à celui de la Stable
  publiée.
- Une bêta porte le numéro `X.Y.Z-beta.N`, où `X.Y.Z` vient du fichier
  `VERSION` de la plateforme et `N` est le numéro de run du workflow Beta.
- Les updaters considèrent `X.Y.Z-beta.N` comme antérieure à `X.Y.Z`. Après
  chaque Stable, il faut donc passer les deux fichiers à la version suivante
  pour que les bêtas suivantes soient vues comme plus récentes. Le workflow
  Beta refuse de publier tant que ce n’est pas fait (voir ci-dessous).
- Les workflows comparent les versions comme les updaters, avec
  `tools/release_guard.py` : `beta` < `rc` < version finale, puis le numéro.

## Intégration continue

`ci.yml` s’exécute sur chaque push sur `main`, chaque pull request et à la
demande :

- Windows, Python 3.11 et 3.12 : compilation, tests partagés et Windows,
  `flake8 --select=F,E9` ;
- macOS, Python 3.12 : mêmes contrôles et `python run.py --smoke-test` ;
- construction d’un DMG **non signé**, artefact du run conservé 14 jours
  (`SuperMenu-macOS-arm64-unsigned-test`). La CI ne reçoit aucun secret Apple
  et ne contacte pas le service de notarisation : un incident chez Apple ne
  peut pas la faire échouer. Signature et notarisation ont lieu dans les
  workflows Beta et Stable.

Un commit dont le message contient `[skip ci]` ne lance pas la CI, donc aucune
bêta.

## Bêta roulante

### Déclenchement

Le workflow **Beta Release** démarre quand la CI se termine avec succès pour un
**push sur `main` de ce dépôt**. Une pull request, même ouverte depuis la
branche `main` d’un fork, ne déclenche aucun job. Le build utilise exactement le
commit testé par la CI. Dans un fork, qui copie le workflow sans les secrets,
aucun job ne démarre.

Il peut aussi être lancé à la main depuis l’onglet **Actions** (« Run
workflow ») sur `main`. Il construit alors le dernier commit de `main`, sans
attendre la CI, mais en relançant les tests.

Un build plus récent annule un build en cours ; une publication déjà commencée
n’est jamais interrompue.

### Contrôles de version

Avant les tests, chaque job de build vérifie que la bêta pourra être proposée
par les applications installées, et échoue sinon en moins d’une minute :

- **Windows** : le tag `vX.Y.Z` correspondant à `win32/VERSION` ne doit pas
  exister (sinon `X.Y.Z` est déjà Stable : augmentez `win32/VERSION`), et
  `X.Y.Z-beta.N` doit être supérieure à la version de `update-beta.json`
  publié ;
- **macOS** : `X.Y.Z-beta.N` doit être supérieure à la version de
  `update-macos-beta.json` et à celle de `update-macos-stable.json` publiés.

Un manifeste absent (première publication) est accepté ; un manifeste
injoignable après trois essais fait échouer le run.

### Étapes

1. **Windows** : tests, PyInstaller, smoke tests de l’EXE et du runtime
   Foundry, installateur Inno Setup (`SuperMenu_Beta.exe`,
   `SuperMenu_Beta_Setup.exe`).
2. **macOS** : tests, smoke test, signature Developer ID et notarisation
   obligatoires (`SuperMenu_Beta-macOS-arm64.dmg`). Sans les secrets Apple, le
   job échoue et rien n’est publié.
3. **Publication**, seulement si les deux plateformes ont réussi :
   - génération des manifestes `update-beta.json` (Windows) et
     `update-macos-beta.json` (macOS), qui indiquent la version, le canal, le
     tag, le nom du fichier attendu et son empreinte `sha256` ;
   - génération de `SHA256SUMS-beta.txt` ;
   - attestation de provenance de tous ces fichiers (voir
     [Vérifier la provenance](#vérifier-la-provenance)) ;
   - texte de la release : contenu de `.github/BETA_NOTES.md`, puis une ligne
     avec les deux versions et un bloc « Informations de build » ;
   - remplacement des fichiers de la release `beta` un par un : installateurs
     et DMG d’abord, manifestes en dernier, pour qu’un manifeste ne désigne
     jamais un fichier absent ou plus ancien ;
   - déplacement du tag `beta` sur le commit publié.

La release `beta` est une prérelease et n’est jamais marquée « Latest ».

### Notes de bêta

`.github/BETA_NOTES.md` est **remplacé** à chaque bêta par ses points saillants,
sans historique :

- gardez le titre `## Nouveautés de cette bêta` et une courte liste à puces ;
- n’écrivez aucune ligne `Windows version:`, `macOS version:`,
  ``Windows : `X.Y.Z` `` ni ``macOS Apple Silicon : `X.Y.Z` `` : ces formes
  sont ajoutées par le workflow et relues par les applications quand les
  manifestes sont inaccessibles ;
- les notes sont lues dans le commit construit : mettez-les à jour dans le même
  push que les changements qu’elles décrivent.

## Release Stable

### Déclenchement et contrôles

Le workflow **Stable Release** démarre au push d’un tag au format exact
`vX.Y.Z`, dans ce dépôt seulement. Un premier job Linux vérifie en moins d’une
minute, avant tout build et toute notarisation :

- le format du tag ;
- l’égalité entre le tag et `win32/VERSION` ;
- que le tag pointe sur un commit de `main` (`git merge-base --is-ancestor`) ;
- qu’un titre de `.github/STABLE_NOTES.md` nomme exactement `X.Y.Z` (`1.2.1`
  ne correspond ni à `1.2.10`, ni à une simple mention dans le texte) ;
- que `macos/VERSION` est supérieur à la version de `update-macos-stable.json`
  de la release « Latest ».

Il calcule aussi le badge « Latest » : la release ne le prend que si `X.Y.Z`
est supérieure à la version de `update-stable.json` de la release « Latest »
actuelle. Un correctif d’une ligne plus ancienne ne le prend donc pas ; les
applications, qui lisent les manifestes de la release « Latest », ne le
proposent alors pas non plus.

Ne taguez qu’un commit de `main` dont la CI est verte : le contrôle de branche
ne vérifie pas la CI.

### Étapes

1. **Windows** : tests, PyInstaller, smoke tests, installateur
   (`SuperMenu.exe`, `SuperMenu_Setup.exe`).
2. **macOS** : version lue dans `macos/VERSION`, tests, signature et
   notarisation obligatoires (`SuperMenu-macOS-arm64.dmg`).
3. **Publication** :
   - manifestes `update-stable.json` et `update-macos-stable.json` avec
     l’empreinte `sha256` de l’installateur et du DMG, et `SHA256SUMS.txt` ;
   - attestation de provenance de tous ces fichiers ;
   - texte de la release : contenu de `.github/STABLE_NOTES.md`, suivi du bloc
     « Informations de build » (canal, version Windows, version macOS,
     commit) ;
   - release « SuperMenu X.Y.Z », marquée « Latest » selon le calcul
     ci-dessus. Les applications lisent les manifestes à l’adresse
     `releases/latest/download/`.

Les manifestes sont toujours générés par le workflow : ne les modifiez jamais
à la main.

### Une release publiée n’est pas réécrite

Le workflow publie une release Stable une seule fois. S’il est relancé pour un
tag dont la release est déjà publiée, il échoue sans rien modifier ; tant que
la release n’est pas publiée, une relance peut la compléter.

Ne modifiez ni ne supprimez une release publiée, sauf pour ajouter un
avertissement dans le texte d’une release défectueuse.

### Notes Stable

`.github/STABLE_NOTES.md` décrit la version à publier. Gardez sa structure :

- titre `## Nouveautés de SuperMenu X.Y.Z`, qui satisfait aussi le contrôle du
  tag ;
- une phrase d’introduction, une liste à puces et une phrase de conclusion ;
- aucune ligne réservée (voir les notes de bêta).

## Avant de créer le tag

- [ ] Le commit à publier est sur `main` et sa CI est verte (Windows 3.11 et
      3.12, macOS, DMG).
- [ ] La bêta construite depuis ce commit a été testée sur Windows et sur Mac :
      installation neuve et mise à jour depuis la Stable précédente, menu,
      insertion, fournisseurs IA utilisés, dictée, capture d’écran sous
      Windows, **Vérifier les mises à jour**.
- [ ] `win32/VERSION` contient `X.Y.Z`, supérieur à la Stable précédente.
- [ ] `macos/VERSION` est supérieur à la version macOS de la Stable précédente
      (indiquée dans son bloc « Informations de build ») ; le workflow le
      vérifie aussi.
- [ ] `.github/STABLE_NOTES.md` est titré `## Nouveautés de SuperMenu X.Y.Z`
      et décrit cette version.
- [ ] Dans `CHANGELOG.md`, la section « Non publié » devient
      `## [X.Y.Z] - AAAA-MM-JJ`, avec la version macOS, et les liens en bas
      du fichier sont mis à jour : `[X.Y.Z]` compare la Stable précédente à
      `vX.Y.Z`, et `[Non publié]` compare `vX.Y.Z` à `main`. Pour 1.3.0,
      `[1.3.0]` pointe vers la release `v1.3.0` elle-même : depuis la
      republication de `main` en un seul commit, `v1.2.1` ne fait plus partie
      de son historique, et GitHub ne peut pas comparer les deux.
- [ ] README et guides d’utilisation sont à jour.
- [ ] Le certificat Developer ID et le mot de passe d’application Apple sont
      valides (voir [macos/SIGNING.md](../macos/SIGNING.md)).
- [ ] Ces changements sont poussés sur `main` et leur CI est verte.

## Publier

Depuis le commit de `main` validé :

```bash
git switch main
git pull --ff-only
git tag -a vX.Y.Z -m "SuperMenu X.Y.Z"
git push origin vX.Y.Z
```

Poussez le tag seulement quand la bêta de ce commit est publiée et testée :
poussé en même temps que `main`, il fait échouer cette bêta, puisque `vX.Y.Z`
existe déjà.

Poussez toujours une branche ou un tag nommé (`main`, `vX.Y.Z`), jamais avec
`--all`, `--mirror` ni `--tags` : ces options publieraient aussi les branches,
tags et références locales (essais, sauvegardes d’outils, ancien tag `beta`).
Ne poussez, ne déplacez ni ne supprimez jamais le tag `beta` à la main : le
workflow Beta le déplace à chaque publication. Ne supprimez pas non plus le
tag d’une release publiée (`v1.2.0`, `v1.2.1`…) : la release repasserait en
brouillon, et ses fichiers et manifestes ne seraient plus téléchargeables.

Suivez ensuite le run **Stable Release** dans l’onglet **Actions**. Tant que
l’étape de publication n’a pas commencé, rien n’est publié :

- pour un incident passager (notarisation trop longue, runner indisponible),
  utilisez **Re-run failed jobs** ;
- pour une erreur à corriger (version, notes, test), corrigez sur `main`,
  supprimez le tag (`git push --delete origin vX.Y.Z` puis
  `git tag -d vX.Y.Z`) et recommencez.

## Après la publication

1. Vérifiez la release : six fichiers (`SuperMenu.exe`, `SuperMenu_Setup.exe`,
   `SuperMenu-macOS-arm64.dmg`, `SHA256SUMS.txt`, `update-stable.json`,
   `update-macos-stable.json`), mention « Latest » et texte correct, puis
   l’attestation d’un fichier téléchargé (voir
   [Vérifier la provenance](#vérifier-la-provenance)).
2. Sur une installation de la Stable précédente, Windows et Mac, lancez
   **Vérifier les mises à jour** et installez la nouvelle version.
3. Préparez aussitôt le cycle suivant, dans un même commit sur `main`. D’ici
   là, chaque push sur `main` produit une bêta en échec (le tag `vX.Y.Z`
   existe déjà), et les utilisateurs du canal Bêta, qui ne lisent que
   `update-beta.json`, restent sur la dernière bêta sans voir la Stable :
   - passez `win32/VERSION` et `macos/VERSION` à la version suivante (par
     exemple `1.3.0` → `1.3.1` dans les deux fichiers ; chaque numéro suit
     ensuite sa plateforme) ;
   - remplacez le contenu de `.github/BETA_NOTES.md` ;
   - ajoutez une section « Non publié » vide en haut de `CHANGELOG.md`.

## Revenir en arrière

Une release Stable n’est jamais remplacée, et les applications ne proposent
qu’une version plus récente que celle installée. Pour corriger une version
défectueuse `X.Y.Z`, publiez donc `X.Y.Z+1` :

1. Corrigez le problème sur `main`, ou annulez le commit fautif avec
   `git revert`, et attendez une CI verte. La bêta suivante reçoit la
   correction automatiquement.
2. Passez `win32/VERSION` à `X.Y.Z+1` et `macos/VERSION` à son numéro suivant.
3. Décrivez la correction dans `.github/STABLE_NOTES.md` et `CHANGELOG.md`.
4. Taguez et poussez `vX.Y.Z+1` comme ci-dessus. La nouvelle release devient
   « Latest » et les applications la proposent.

Ne supprimez pas la release `vX.Y.Z` et ne déplacez pas son tag : les
utilisateurs déjà mis à jour ne reverraient pas un même numéro republié, et la
correspondance entre le tag, les fichiers et leurs empreintes serait perdue.
Si nécessaire, ajoutez un avertissement dans le texte de la release fautive.
Un utilisateur qui veut revenir tout de suite à l’ancienne version la
réinstalle manuellement depuis la page Releases.

## Vérifier la provenance

Avant de publier, les jobs de publication Beta et Stable créent une
attestation de provenance (`actions/attest-build-provenance`) pour chaque
fichier publié : installateurs, EXE, DMG, manifestes et fichiers d’empreintes.
Signée par GitHub, elle lie l’empreinte du fichier au workflow, au commit et au
run qui l’ont produit. Pour vérifier un fichier téléchargé, avec GitHub CLI
connecté :

```bash
gh attestation verify SuperMenu_Setup.exe --repo lfpoulain/SuperMenu
```

Pour exiger en plus qu’il vienne du workflow Stable :

```bash
gh attestation verify SuperMenu-macOS-arm64.dmg --repo lfpoulain/SuperMenu \
  --signer-workflow lfpoulain/SuperMenu/.github/workflows/stable-release.yml
```

Les releases publiées avant l’ajout de cette étape n’ont pas d’attestation.

## Dépendances et outils de build

- `.github/dependabot.yml` propose chaque semaine les mises à jour des actions
  GitHub et des dépendances Python (`shared`, `win32`, `macos`), regroupées et
  limitées aux versions publiées depuis au moins 7 jours. Elles passent par une
  pull request et la CI comme tout changement.
- Les actions des workflows Beta et Stable, qui manipulent le certificat Apple
  ou un jeton d’écriture, sont épinglées par SHA de commit, avec la version en
  commentaire (`@<sha> # vX.Y.Z`). Dependabot met à jour les deux ensemble.
  N’y référencez jamais une action par tag ou par branche.
- Inno Setup est installé dans une version fixe (`INNO_SETUP_VERSION` dans les
  jobs Windows Beta et Stable), que Dependabot ne suit pas. Pour en changer,
  modifiez les deux valeurs ensemble et testez l’installateur d’une bêta.

## Secrets nécessaires

Les jobs macOS de la bêta et de la Stable exigent les cinq secrets du dépôt
`MACOS_CERTIFICATE_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_APPLE_ID`,
`MACOS_APP_PASSWORD` et `MACOS_TEAM_ID`. Leur préparation est décrite dans
[macos/SIGNING.md](../macos/SIGNING.md). Seuls les jobs de publication reçoivent
le droit d’écrire dans le dépôt, via le `GITHUB_TOKEN` fourni par GitHub, et
le jeton OIDC (`id-token: write`) qui signe l’attestation. La CI ne reçoit
aucun secret.
