# SuperMenu

SuperMenu est une application Windows (Python + PySide6) qui affiche un menu contextuel piloté par raccourci clavier pour exécuter rapidement des actions IA sur :

- du texte sélectionné
- de la dictée (reconnaissance vocale)
- une capture d'écran

## Fonctionnalités

- Menu contextuel sur texte sélectionné (prompts configurables)
- Fermeture automatique des menus contextuels lors d'un clic extérieur ou d'un changement de fenêtre
- Prompts vocaux (dictée + prompt + option d'inclure le texte sélectionné)
- Capture d'écran (mode actuel : capture de l'écran, puis envoi à l'IA avec prompt)
- Insertion directe (coller automatiquement la réponse dans l'application active)
- Choix du modèle
  - OpenAI : `gpt-5.1`, `gpt-4.1-mini`
  - Endpoint personnalisé compatible OpenAI (ex : Ollama) + modèle libre
- Raccourcis configurables (menu, voix, capture)
- Thèmes (via `ThemeManager`) : sombre, clair, automatique
- Stockage sécurisé de la clé API via `keyring` (la clé n'est pas écrite dans les fichiers de configuration et n'est pas loggée)

## Prérequis

- Windows 10/11
- Connexion Internet (pour les appels API)
- Clé API OpenAI (pour les fonctionnalités d'IA)

Pour l'installation manuelle (développeurs) :

- Python 3.8 ou supérieur

## Installation

### Installation automatique (recommandée)

1. Téléchargez le dernier installateur depuis la [page des releases](https://github.com/lfpoulain/supermenu/releases)
2. Exécutez l'installateur et suivez les instructions à l'écran
3. Lancez SuperMenu depuis le menu Démarrer

### Installation manuelle (pour développeurs)

1. Clonez ce dépôt :
   ```
   git clone https://github.com/lfpoulain/supermenu.git
   cd supermenu
   ```

2. **Méthode simple avec les scripts batch** :
   - Exécutez `install.bat` pour créer l'environnement virtuel et installer les dépendances
   - Utilisez `start_supermenu.bat` pour lancer l'application

3. **Méthode manuelle alternative** :
   - Créez un environnement virtuel et activez-le :
     ```
     python -m venv venv
     venv\Scripts\activate
     ```
   - Installez les dépendances :
     ```
     pip install -r requirements.txt
     ```
   - Lancez l'application :
     ```
     python run.py
     ```

## Configuration

Lors du premier lancement, vous devrez configurer :

1. **Clé API / Endpoint** : Onglet "Modèles" (OpenAI ou endpoint personnalisé)
2. **Raccourcis clavier** : Onglet "Réglages"
3. **Prompts** : Onglets "Prompts" et "Prompts vocaux"

Fichiers et emplacements :

- **Configuration** : `SuperMenu.ini` dans le dossier utilisateur (`%USERPROFILE%\SuperMenu.ini`)
- **Logs** : `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`

## Utilisation

### Raccourcis clavier par défaut

- **Ctrl+²** : Afficher le menu contextuel pour le texte sélectionné
- **Ctrl+Shift+²** : Capturer l'écran pour analyse
- **Ctrl+Alt+²** : Activer la reconnaissance vocale

### Utilisation du menu contextuel

1. Sélectionnez du texte dans n'importe quelle application
2. Appuyez sur le raccourci clavier (par défaut : Ctrl+²)
3. Choisissez l'action souhaitée dans le menu contextuel
4. Le résultat s'affiche dans une fenêtre dédiée ou est inséré directement dans l'application

Le menu se ferme automatiquement si vous cliquez en dehors du menu ou si vous changez de fenêtre sans sélectionner d'action.

### Utilisation de la reconnaissance vocale

1. Appuyez sur le raccourci vocal (par défaut : Ctrl+Alt+²)
2. Parlez clairement dans votre microphone
3. La transcription s'affiche et est envoyée à l'API
4. Le résultat est affiché ou inséré selon la configuration

## Thèmes

SuperMenu propose 3 thèmes :

- Sombre
- Clair
- Automatique (système)

Pour changer de thème :

1. Ouvrez les paramètres de SuperMenu
2. Allez dans l'onglet "Réglages"
3. Choisissez le thème
4. Cliquez sur "Appliquer le thème" (l'application propose ensuite un redémarrage)

## Personnalisation des prompts

### Prompts textuels

Les prompts textuels sont utilisés lorsque vous sélectionnez du texte et utilisez le menu contextuel. Vous pouvez :

- Modifier les prompts existants
- Ajouter de nouveaux prompts
- Réorganiser l'ordre des prompts dans le menu
- Configurer l'insertion directe des réponses

### Prompts vocaux

Les prompts vocaux sont utilisés avec la reconnaissance vocale. Vous pouvez :

- Personnaliser les instructions envoyées à l'API
- Définir l'ordre des éléments (prompt, transcription, texte sélectionné)
- Activer ou désactiver l'inclusion du texte sélectionné

## Fonctionnalités avancées

### Capture d'écran

La fonctionnalité de capture d'écran permet de :

- Capturer l'écran (plein écran)
- Analyser le contenu visuel avec l'IA
- Extraire du texte des images
- Obtenir des descriptions ou des analyses

### Insertion directe

Pour les prompts configurés avec l'option "Insérer directement" :

- La réponse est automatiquement insérée à l'emplacement du curseur
- Aucune fenêtre de réponse n'est affichée
- Idéal pour les corrections rapides ou les reformulations

## Architecture technique

SuperMenu est développé en Python avec PySide6 (Qt) et s'organise comme suit :

- **src/main.py** : Point d'entrée principal et gestion des fenêtres
- **src/utils/** : Utilitaires pour le menu contextuel, les raccourcis, etc.
- **src/ui/** : Composants d'interface utilisateur
- **src/api/** : Intégration avec l'API OpenAI
- **src/audio/** : Gestion de la reconnaissance vocale
- **src/config/** : Configuration et paramètres

Documentation développeur :

- `docs/ARCHITECTURE.md`
- `docs/GUIDE_UTILISATION.md`

## Mise à jour

La méthode recommandée est de publier un nouvel installateur `SuperMenu_Setup.exe` avec une version supérieure. L'utilisateur peut lancer le nouvel installateur par-dessus l'installation existante.

## Désinstallation

Lors de la désinstallation, SuperMenu est fermé automatiquement si nécessaire. Une option permet de supprimer également les données utilisateur (logs et configuration).

## Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. Forkez le dépôt
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/amazing-feature`)
3. Committez vos changements (`git commit -m 'Add some amazing feature'`)
4. Poussez vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrez une Pull Request

## Licence

 2025 LFPoulain - Tous droits réservés

---

## Contact

Pour toute question ou suggestion, veuillez contacter LFPoulain via [GitHub](https://github.com/lfpoulain).
