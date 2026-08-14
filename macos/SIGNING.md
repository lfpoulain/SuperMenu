# Signature et notarisation macOS

SuperMenu reste distribué directement dans un DMG, sans Mac App Store. Le
workflow GitHub utilise une identité **Developer ID Application** stable, active
le Hardened Runtime par l'intermédiaire de PyInstaller, signe l'application et
le DMG, puis soumet le DMG à `notarytool` et agrafe le ticket Apple.

Le bundle identifier de distribution est `com.supermenu.macos`. Il ne doit plus
être modifié : il fait partie de l'identité utilisée par macOS pour reconnaître
les mises à jour et conserver les autorisations.

## 1. Créer l'identité Developer ID Application

Deux chemins sont possibles. Le résultat attendu est toujours un fichier P12
qui contient à la fois le certificat **Developer ID Application** et la clé
privée ayant servi à créer sa demande CSR.

### Option A — Depuis un Mac

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

### Option B — Entièrement depuis Windows

Cette méthode utilise l'OpenSSL fourni avec Git pour Windows. Les fichiers sont
créés volontairement hors du dépôt SuperMenu.

Ouvrir PowerShell et préparer un dossier privé :

```powershell
$signingDir = Join-Path $env:USERPROFILE "SuperMenu-signing-private"
New-Item -ItemType Directory -Force -Path $signingDir | Out-Null
Set-Location $signingDir

$openssl = "C:\Program Files\Git\mingw64\bin\openssl.exe"
if (-not (Test-Path -LiteralPath $openssl)) {
    throw "OpenSSL est introuvable. Installer Git for Windows avant de continuer."
}

$env:OPENSSL_CONF = "C:\Program Files\Git\mingw64\etc\ssl\openssl.cnf"
$env:OPENSSL_MODULES = "C:\Program Files\Git\mingw64\lib\ossl-modules"
```

Générer une clé RSA 2048 bits chiffrée, puis la demande CSR :

```powershell
& $openssl genrsa -aes256 -out developer-id-private.key 2048
& $openssl req -new -sha256 `
    -key developer-id-private.key `
    -out SuperMenu.certSigningRequest
```

OpenSSL demande d'abord une phrase secrète pour protéger la clé. Lors de la
création du CSR, utiliser le nom légal comme `Common Name`, l'adresse du compte
Apple Developer comme email et laisser le `challenge password` vide.

Sur le site Apple Developer :

1. ouvrir **Certificates, Identifiers & Profiles > Certificates** ;
2. cliquer sur `+`, choisir **Developer ID**, puis
   **Developer ID Application** ;
3. envoyer `SuperMenu.certSigningRequest` ;
4. télécharger le certificat et le placer dans le dossier privé sous le nom
   `developer-id-application.cer`.

Revenir dans la même fenêtre PowerShell, convertir le certificat Apple et
assembler le P12 :

```powershell
& $openssl x509 -inform DER `
    -in developer-id-application.cer `
    -out developer-id-application.pem

& $openssl pkcs12 -export -legacy `
    -inkey developer-id-private.key `
    -in developer-id-application.pem `
    -out SuperMenu-Developer-ID.p12 `
    -name "SuperMenu Developer ID"
```

Saisir la phrase secrète de la clé, puis choisir un mot de passe d'export P12
fort. C'est ce second mot de passe qui deviendra le secret GitHub
`MACOS_CERTIFICATE_PASSWORD`. L'option `-legacy` assure la compatibilité du P12
avec l'import par le trousseau macOS du runner GitHub ; elle rend indispensable
un mot de passe fort et la conservation du fichier dans un emplacement privé.

Vérifier enfin que le P12 est lisible avant de continuer :

```powershell
& $openssl pkcs12 -legacy `
    -in SuperMenu-Developer-ID.p12 `
    -info -noout
```

Le fichier `.p12` et son mot de passe donnent le droit de signer au nom du
développeur. Ils ne doivent jamais être ajoutés au dépôt ou envoyés dans une
conversation. Après le premier build signé réussi, conserver une sauvegarde du
P12 dans un gestionnaire de mots de passe ou un coffre chiffré, puis supprimer
le dossier de travail contenant la clé et les fichiers intermédiaires.

## 2. Créer les identifiants de notarisation

1. Sur `account.apple.com`, ouvrir **Connexion et sécurité > Mots de passe pour
   application** et créer un mot de passe nommé `SuperMenu notarization`.
2. Relever le **Team ID** dans les détails d'adhésion du compte Apple Developer.
3. Conserver l'adresse du compte Apple utilisé pour l'adhésion.

Le mot de passe spécifique est utilisé uniquement par `notarytool`. Il ne faut
jamais fournir le mot de passe principal du compte Apple.

## 3. Ajouter les secrets GitHub Actions

Depuis un Mac, encoder le P12 et copier le résultat :

```bash
base64 -i /chemin/SuperMenu-Developer-ID.p12 | pbcopy
```

Depuis la fenêtre PowerShell Windows utilisée précédemment :

```powershell
$p12Path = Join-Path $signingDir "SuperMenu-Developer-ID.p12"
$p12Base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($p12Path))
Set-Clipboard -Value $p12Base64
Remove-Variable p12Base64
```

Le contenu Base64 est alors dans le presse-papiers et peut être collé
directement dans le secret GitHub, sans créer de copie texte supplémentaire.

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
