# Publier une version de SuperMenu

Ce document décrit la procédure de publication telle qu’elle est implémentée
dans `.github/workflows/`. Elle est réservée au mainteneur : elle demande les
droits d’écriture sur le dépôt et les secrets de signature Apple.

## Vue d’ensemble

| Workflow | Déclencheur | Résultat |
|---|---|---|
| `ci.yml` (**CI**) | push sur `main`, pull request, lancement manuel | tests Windows et macOS, DMG de contrôle ; aucune release |
| `beta-release.yml` (**Beta Release**) | CI réussie après un push sur `main` du dépôt, ou lancement manuel sur `main` | prérelease roulante `beta`, remplacée à chaque build |
| `stable-release.yml` (**Stable Release**) | push d’un tag `vX.Y.Z` | release Stable `vX.Y.Z`, marquée « Latest » |
| `native-helpers.yml` | changement des helpers Swift, chaque semaine, lancement manuel | contrôle informatif sur macOS 26 ; ne bloque rien |

## Numéros de version

- `win32/VERSION` contient la **prochaine version Stable attendue** pour
  Windows, sans `v` (par exemple `1.2.2`). Le tag Stable doit lui correspondre
  exactement, et la release s’appelle « SuperMenu X.Y.Z » d’après ce numéro.
- `macos/VERSION` est **indépendant** (par exemple `1.2.9`). Le workflow Stable
  l’utilise tel quel, sans le comparer au tag. Il doit donc être augmenté à
  chaque Stable : sinon l’updater macOS ne voit aucune version plus récente et
  ne propose pas la mise à jour.
- Une bêta porte le numéro `X.Y.Z-beta.N`, où `X.Y.Z` vient du fichier
  `VERSION` de la plateforme et `N` est le numéro de run du workflow Beta.
- Les updaters considèrent `X.Y.Z-beta.N` comme antérieure à `X.Y.Z`. Après
  chaque Stable, il faut donc passer les deux fichiers à la version suivante
  pour que les bêtas suivantes soient vues comme plus récentes.

## Intégration continue

`ci.yml` s’exécute sur chaque push sur `main`, chaque pull request et à la
demande :

- Windows, Python 3.11 et 3.12 : compilation, tests partagés et Windows,
  `flake8 --select=F,E9` ;
- macOS, Python 3.12 : mêmes contrôles et `python run.py --smoke-test` ;
- construction d’un DMG : signé et notarisé si les secrets Apple sont
  disponibles, non signé sinon (pull request venant d’un fork). Le DMG reste un
  artefact du run, conservé 14 jours.

Un commit dont le message contient `[skip ci]` ne lance pas la CI, donc aucune
bêta.

## Bêta roulante

### Déclenchement

Le workflow **Beta Release** démarre quand la CI se termine avec succès pour un
**push sur `main` de ce dépôt**. Une pull request, même ouverte depuis la
branche `main` d’un fork, ne déclenche aucun job. Le build utilise exactement le
commit testé par la CI.

Il peut aussi être lancé à la main depuis l’onglet **Actions** (« Run
workflow ») sur `main`. Il construit alors le dernier commit de `main`, sans
attendre la CI, mais en relançant les tests.

Un build plus récent annule un build en cours ; une publication déjà commencée
n’est jamais interrompue.

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
`vX.Y.Z`. Un premier job Linux vérifie en moins d’une minute, avant tout build
et toute notarisation :

- le format du tag ;
- l’égalité entre le tag et `win32/VERSION` ;
- la présence du numéro `X.Y.Z` dans `.github/STABLE_NOTES.md`.

Le workflow ne vérifie pas la branche du tag : ne taguez qu’un commit de
`main` dont la CI est verte.

### Étapes

1. **Windows** : tests, PyInstaller, smoke tests, installateur
   (`SuperMenu.exe`, `SuperMenu_Setup.exe`).
2. **macOS** : version lue dans `macos/VERSION`, tests, signature et
   notarisation obligatoires (`SuperMenu-macOS-arm64.dmg`).
3. **Publication** :
   - manifestes `update-stable.json` et `update-macos-stable.json` avec
     l’empreinte `sha256` de l’installateur et du DMG, et `SHA256SUMS.txt` ;
   - texte de la release : contenu de `.github/STABLE_NOTES.md`, suivi du bloc
     « Informations de build » (canal, version Windows, version macOS,
     commit) ;
   - release « SuperMenu X.Y.Z » marquée « Latest ». Les applications lisent
     les manifestes à l’adresse `releases/latest/download/`.

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
      (indiquée dans son bloc « Informations de build »).
- [ ] `.github/STABLE_NOTES.md` est titré `## Nouveautés de SuperMenu X.Y.Z`
      et décrit cette version.
- [ ] Dans `CHANGELOG.md`, la section « Non publié » devient
      `## [X.Y.Z] - AAAA-MM-JJ`, avec la version macOS, et les liens de
      comparaison en bas du fichier sont mis à jour.
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

Poussez toujours une branche ou un tag nommé (`main`, `vX.Y.Z`), jamais avec
`--all` ni `--mirror` : ces options publieraient aussi les branches et
références locales (essais, sauvegardes d’outils).

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
   `update-macos-stable.json`), mention « Latest » et texte correct.
2. Sur une installation de la Stable précédente, Windows et Mac, lancez
   **Vérifier les mises à jour** et installez la nouvelle version.
3. Préparez le cycle suivant dans un même commit sur `main` :
   - passez `win32/VERSION` et `macos/VERSION` à la version suivante (par
     exemple `1.2.2` → `1.2.3` et `1.2.9` → `1.2.10`) ;
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

## Secrets nécessaires

Les jobs macOS de la bêta et de la Stable exigent les cinq secrets du dépôt
`MACOS_CERTIFICATE_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_APPLE_ID`,
`MACOS_APP_PASSWORD` et `MACOS_TEAM_ID`. Leur préparation est décrite dans
[macos/SIGNING.md](../macos/SIGNING.md). Seuls les jobs de publication reçoivent
le droit d’écrire dans le dépôt, via le `GITHUB_TOKEN` fourni par GitHub.
