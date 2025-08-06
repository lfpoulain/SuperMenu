# SuperMenu

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Python](https://img.shields.io/badge/python-3.8%2B-green)

SuperMenu est une application Windows qui offre un menu contextuel intelligent alimenté par l'IA pour effectuer diverses opérations sur du texte sélectionné. Créée par LFPoulain, cette application vise à simplifier l'utilisation de l'IA au quotidien.

![SuperMenu Screenshot](docs/images/supermenu_screenshot.png)

## Fonctionnalités clés

*   **Menu Contextuel Intelligent** : Sélectionnez du texte dans n'importe quelle application, utilisez un raccourci clavier et choisissez une action IA à effectuer (résumer, traduire, expliquer, etc.).
*   **Interaction Vocale** : Dictez vos prompts et recevez des réponses de l'IA, ou faites transcrire votre parole en texte.
*   **Analyse d'Image** : Capturez une partie de votre écran et demandez à l'IA de l'analyser ou de répondre à des questions à son sujet.
*   **Sélection ou saisie du Modèle compatible OpenAI** : Choisissez parmi les derniers modèles OpenAI (comme GPT-4o, GPT-4o-mini, etc.) ou saisissez le nom de n'importe quel modèle compatible pour vos requêtes textuelles et d'analyse d'image, directement depuis les paramètres de l'application.
*   **Compatibilité avec les API de type OpenAI** : Définissez votre propre URL d'API pour les requêtes texte et image (ex. serveur Ollama local). Le suffixe `/v1` est ajouté automatiquement s'il manque. La transcription vocale utilise toujours l'API OpenAI standard.
*   **Gestion des Prompts** : Créez, modifiez, supprimez et organisez vos propres prompts textuels et vocaux. Exportez et importez vos configurations de prompts au format JSON.
*   **Personnalisation des Raccourcis** : Configurez vos propres raccourcis clavier pour accéder rapidement au menu contextuel, à la capture d'écran et à l'interaction vocale.
*   **Thèmes** : Personnalisez l'apparence de l'application avec des thèmes (par exemple, Clair, Sombre, Abeille).
*   **Sécurité** : Votre clé API OpenAI est stockée de manière sécurisée dans le trousseau de votre système d'exploitation.
*   **Insertion Automatique** : Les réponses de l'IA peuvent être copiées dans le presse-papiers ou "écrites" directement dans l'application active.

## Prérequis

- Windows 10/11
- Python 3.8 ou supérieur
- Connexion Internet (pour les appels API)
- Clé API OpenAI (ou accès à un serveur compatible) (pour les fonctionnalités d'IA)

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
   - Utilisez `startsupermenu.bat` pour lancer l'application

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

1. **Clé API OpenAI** : Entrez votre clé API dans l'onglet "Général" des paramètres (ou laissez vide pour un serveur compatible ne nécessitant pas de clé)
2. **Modèle compatible OpenAI** : Sélectionnez ou saisissez le modèle à utiliser pour les requêtes textuelles et l'analyse d'images
3. **URL de l'API** : Indiquez l'URL d'un service compatible OpenAI pour les requêtes texte et image si nécessaire (par exemple un serveur Ollama local). Le suffixe `/v1` sera ajouté automatiquement s'il n'est pas présent. La reconnaissance vocale ignore ce paramètre et utilise l'API OpenAI standard.
4. **Raccourcis clavier** : Personnalisez les raccourcis selon vos préférences
5. **Prompts** : Modifiez les prompts prédéfinis ou ajoutez-en de nouveaux

## Utilisation

### Raccourcis clavier par défaut

- **Ctrl+²** : Afficher le menu contextuel pour le texte sélectionné
- **Ctrl+Shift+²** : Capturer une partie de l'écran pour analyse
- **Ctrl+Alt+²** : Activer la reconnaissance vocale

### Utilisation du menu contextuel

1. Sélectionnez du texte dans n'importe quelle application
2. Appuyez sur le raccourci clavier (par défaut : Ctrl+²)
3. Choisissez l'action souhaitée dans le menu contextuel
4. Le résultat s'affiche dans une fenêtre dédiée ou est inséré directement dans l'application

### Utilisation de la reconnaissance vocale

1. Appuyez sur le raccourci vocal (par défaut : Ctrl+Alt+²)
2. Parlez clairement dans votre microphone
3. La transcription s'affiche et est envoyée à l'API
4. Le résultat est affiché ou inséré selon la configuration

## Thèmes

SuperMenu propose deux thèmes visuels :

- **Dark** (par défaut) : Thème sombre avec accents bleus
- **Abeille** : Thème noir et jaune inspiré des abeilles

Pour changer de thème :
1. Ouvrez les paramètres de SuperMenu
2. Allez dans l'onglet "Général"
3. Sélectionnez le thème souhaité dans la section "Thème de l'application"
4. Cliquez sur "Appliquer le thème" et redémarrez l'application

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
- Sélectionner une zone de l'écran
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
