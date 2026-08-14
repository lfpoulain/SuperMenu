# Signature et notarisation macOS

SuperMenu reste distribué directement dans un DMG, sans Mac App Store. Le
workflow GitHub utilise une identité **Developer ID Application** stable, active
le Hardened Runtime par l'intermédiaire de PyInstaller, signe l'application et
le DMG, puis soumet le DMG à `notarytool` et agrafe le ticket Apple.

Le bundle identifier de distribution est `com.supermenu.macos`. Il ne doit plus
être modifié : il fait partie de l'identité utilisée par macOS pour reconnaître
les mises à jour et conserver les autorisations.

## 1. Créer le certificat Developer ID Application

Ces opérations sont à faire sur le Mac du titulaire du compte Apple Developer.

1. Ouvrir **Trousseaux d'accès**.
2. Choisir **Assistant de certification > Demander un certificat à une
   autorité de certification**, puis enregistrer la demande sur le disque.
3. Dans **Certificates, Identifiers & Profiles** sur le site Apple Developer,
   ajouter un certificat de type **Developer ID Application**. Ne pas choisir
   `Developer ID Installer`, qui sert aux paquets PKG.
4. Fournir la demande `.certSigningRequest`, télécharger le fichier `.cer`, puis
   double-cliquer dessus pour l'installer.
5. Dans **Mes certificats**, développer le certificat et vérifier que sa clé
   privée apparaît dessous.
6. Exporter le certificat et sa clé privée au format `.p12`, avec un mot de
   passe fort et temporaire.

Le fichier `.p12` et son mot de passe donnent le droit de signer au nom du
développeur. Ils ne doivent jamais être ajoutés au dépôt ou envoyés dans une
conversation.

## 2. Créer les identifiants de notarisation

1. Sur `account.apple.com`, ouvrir **Connexion et sécurité > Mots de passe pour
   application** et créer un mot de passe nommé `SuperMenu notarization`.
2. Relever le **Team ID** dans les détails d'adhésion du compte Apple Developer.
3. Conserver l'adresse du compte Apple utilisé pour l'adhésion.

Le mot de passe spécifique est utilisé uniquement par `notarytool`. Il ne faut
jamais fournir le mot de passe principal du compte Apple.

## 3. Ajouter les secrets GitHub Actions

Encoder le P12 sur le Mac et copier le résultat :

```bash
base64 -i /chemin/SuperMenu-Developer-ID.p12 | pbcopy
```

Dans le dépôt GitHub, ouvrir **Settings > Secrets and variables > Actions > New
repository secret**, puis créer exactement ces cinq secrets :

| Secret | Valeur |
|---|---|
| `MACOS_CERTIFICATE_BASE64` | contenu Base64 du fichier P12 |
| `MACOS_CERTIFICATE_PASSWORD` | mot de passe d'export du P12 |
| `MACOS_APPLE_ID` | adresse du compte Apple Developer |
| `MACOS_APP_PASSWORD` | mot de passe spécifique `SuperMenu notarization` |
| `MACOS_TEAM_ID` | Team ID Apple Developer |

Le workflow crée un trousseau temporaire sur le runner, y importe le P12 et le
supprime toujours en fin de job. Si aucun secret n'est présent, il conserve un
artifact suffixé `unsigned-test`. Une version prête à installer est suffixée
`signed-notarized`. Si seulement une partie des secrets est configurée, le job
échoue explicitement au lieu de publier un paquet incomplet.

## 4. Première migration signée

La première version Developer ID constitue une nouvelle identité par rapport
aux anciens builds ad hoc. Sur le Mac de test :

1. quitter l'ancienne application ;
2. remplacer `/Applications/SuperMenu.app` par celle du DMG notarié ;
3. lancer SuperMenu et accorder une dernière fois Accessibilité et Surveillance
   de l'entrée si macOS le demande ;
4. toujours installer les versions suivantes au même emplacement.

Les mises à jour suivantes, signées avec la même équipe et le même bundle
identifier, doivent alors être reconnues comme la même application.
