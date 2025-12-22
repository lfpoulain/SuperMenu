# Guide d'utilisation de SuperMenu

Ce guide détaille le fonctionnement de SuperMenu et explique comment tirer le meilleur parti de ses fonctionnalités.

## Sommaire
1. [Présentation générale](#présentation-générale)
2. [Installation](#installation)
3. [Premier démarrage](#premier-démarrage)
4. [Utilisation quotidienne](#utilisation-quotidienne)
5. [Personnalisation](#personnalisation)
6. [Fonctionnalités avancées](#fonctionnalités-avancées)
7. [Dépannage](#dépannage)

## Présentation générale

SuperMenu est une application Windows qui intègre l'intelligence artificielle dans votre flux de travail quotidien. Elle vous permet d'effectuer diverses opérations sur du texte sélectionné dans n'importe quelle application grâce à un menu contextuel accessible par raccourci clavier.

### Principales fonctionnalités

- **Menu contextuel intelligent** : Correction, reformulation, résumé, traduction, etc.
- **Reconnaissance vocale** : Dictez vos commandes pour une utilisation mains libres
- **Capture d'écran** : Analysez des images ou du texte à partir de captures d'écran
- **Personnalisation** : Adaptez les prompts, raccourcis et comportements à vos besoins

## Installation

### Méthode recommandée (installateur)

1. Exécutez le fichier d'installation `SuperMenu_Setup.exe`
2. Suivez les instructions à l'écran
3. Une fois l'installation terminée, SuperMenu démarrera automatiquement

Notes :

- SuperMenu s'exécute ensuite en arrière-plan (icône dans la zone de notification).
- Les logs sont disponibles dans `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`.
- La configuration utilisateur est stockée dans `%USERPROFILE%\SuperMenu.ini`.

### Installation manuelle (pour développeurs)

1. Assurez-vous d'avoir Python 3.8 ou supérieur installé
2. **Méthode simple avec les scripts batch** :
   - Exécutez `install.bat` pour créer automatiquement l'environnement virtuel et installer toutes les dépendances
   - Utilisez `start_supermenu.bat` pour lancer l'application à tout moment
3. **Méthode manuelle alternative** :
   - Créez un environnement virtuel : `python -m venv venv`
   - Activez l'environnement : `venv\Scripts\activate`
   - Installez les dépendances : `pip install -r requirements.txt`
   - Lancez l'application : `python run.py`

## Mise à jour

La méthode recommandée est de télécharger le nouvel installateur `SuperMenu_Setup.exe` et de l'exécuter. L'installateur peut être lancé par-dessus une installation existante.

Les fichiers de configuration et les logs sont conservés lors d'une mise à jour.

## Premier démarrage

Lors du premier lancement, vous devrez configurer quelques éléments essentiels :

### Configuration Initiale

Lors du premier lancement de SuperMenu, ou en accédant aux paramètres via l'icône de la barre d'état système, une fenêtre de configuration s'ouvrira. Voici les principaux éléments à configurer :

1.  **Clé API OpenAI** :
    *   Indispensable pour que SuperMenu puisse communiquer avec les services OpenAI.
    *   Entrez votre clé API dans le champ dédié. Elle sera stockée de manière sécurisée dans le trousseau de votre système.

2.  **Modèle / Endpoint** :
     *   Dans l'onglet "Modèles", choisissez :
         * OpenAI (modèles disponibles dans l'interface)
         * ou un endpoint personnalisé compatible OpenAI (ex : Ollama)
     *   Modèles OpenAI proposés par défaut : `gpt-5.1`, `gpt-4.1-mini`.

3.  **Raccourcis Clavier** :
    *   **Raccourci Principal** : Pour afficher le menu contextuel après avoir sélectionné du texte (par défaut : `Ctrl+²`).
    *   **Raccourci Capture d'Écran** : Pour lancer l'outil de capture d'écran (par défaut : `Ctrl+Alt+&`).

### Configuration de l'API

1. Ouvrez les paramètres de SuperMenu
2. Allez dans l'onglet "Modèles"
3. Renseignez la clé API (si vous utilisez OpenAI)
4. Sélectionnez un modèle
5. (Optionnel) activez un endpoint personnalisé et configurez l'URL + le modèle

### Vérification des raccourcis clavier

Par défaut, SuperMenu utilise les raccourcis suivants :
- **Ctrl+²** : Menu contextuel pour le texte sélectionné
- **Ctrl+Alt+&** : Capture d'écran
- **Ctrl+Alt+²** : Reconnaissance vocale

Vous pouvez les modifier dans l'onglet "Réglages" des paramètres.

## Utilisation quotidienne

### Menu contextuel

1. Sélectionnez du texte dans n'importe quelle application
2. Appuyez sur **Ctrl+²** (ou votre raccourci personnalisé)
3. Choisissez l'action souhaitée dans le menu qui apparaît
4. Le résultat s'affiche dans une fenêtre dédiée ou est inséré directement

Si vous cliquez en dehors du menu ou si vous changez de fenêtre sans sélectionner d'action, le menu se ferme automatiquement.

### Reconnaissance vocale

1. Appuyez sur **Ctrl+Alt+²** (ou votre raccourci personnalisé)
2. Parlez clairement dans votre microphone
3. Attendez que la transcription soit traitée
4. Le résultat s'affiche selon la configuration du prompt vocal

### Capture d'écran

1. Appuyez sur **Ctrl+Alt+&** (ou votre raccourci personnalisé)
2. Selon le réglage choisi, SuperMenu capture :
   - plein écran
   - ou une zone sélectionnée à la souris
   - ou vous demande à chaque fois (menu de choix au curseur)
3. Saisissez un prompt (GodMode) pour décrire/analyser l'image
4. La réponse s'affiche dans la fenêtre de réponse

Note : si le mode est réglé sur "demander à chaque capture", le menu de choix (plein écran / sélection de zone) se ferme automatiquement si vous cliquez en dehors ou changez de fenêtre.

## Personnalisation

### Thèmes visuels

SuperMenu propose trois thèmes :
- **Sombre**
- **Clair**
- **Automatique (Système)**

Pour changer de thème :
1. Ouvrez les paramètres
2. Dans l'onglet "Réglages", section "Thème de l'application"
3. Sélectionnez le thème souhaité et cliquez sur "Appliquer le thème"
4. Redémarrez l'application si SuperMenu le propose

### Personnalisation des prompts textuels

1. Ouvrez les paramètres
2. Allez dans l'onglet "Prompts"
3. Sélectionnez un prompt existant ou cliquez sur "Ajouter un prompt"
4. Modifiez les champs selon vos besoins :
   - **Nom** : Nom affiché dans le menu
   - **Prompt** : Instructions envoyées à l'API
   - **Message d'attente** : Texte affiché pendant le traitement
   - **Insérer directement** : Cochez pour insérer la réponse sans afficher de fenêtre
   - **Position** : Ordre d'apparition dans le menu (plus petit = plus haut)

### Personnalisation des prompts vocaux

1. Ouvrez les paramètres
2. Allez dans l'onglet "Prompts Vocaux"
3. Configurez de la même manière que les prompts textuels
4. Options supplémentaires :
   - **Inclure le texte sélectionné** : Ajoute le texte sélectionné à la requête
   - **Ordre des éléments** : Définit l'ordre du prompt, de la transcription et du texte sélectionné

### Modifier le modèle OpenAI utilisé

Dans l'onglet "Modèles", sélectionnez le modèle souhaité dans la liste déroulante puis enregistrez.

## Fonctionnalités avancées

### Insertion directe

Pour les tâches fréquentes comme la correction orthographique, l'option "Insérer directement" permet d'obtenir le résultat sans afficher de fenêtre intermédiaire :

1. Dans l'onglet "Prompts", sélectionnez le prompt souhaité
2. Cochez "Insérer directement la réponse"
3. Ajustez le prompt pour qu'il génère uniquement le texte final sans explications

### Prompts avec capture d'écran

Vous pouvez créer des prompts spécifiques pour l'analyse d'images :

1. Capturez l'écran avec **Ctrl+Alt+&**
2. Saisissez votre prompt personnalisé (ex : "Décris cette image")
3. La réponse s'affiche et peut être copiée ou écrite

Le mode de capture d'écran est configurable dans l'onglet **Réglages**. Vous pouvez choisir :
- plein écran
- sélection de zone
- demander à chaque capture (choix dans un menu au curseur)

### Utilisation avec plusieurs applications

SuperMenu fonctionne avec pratiquement toutes les applications Windows :
- Traitements de texte (Word, Google Docs, etc.)
- Navigateurs web
- Éditeurs de code
- Applications de messagerie
- Et bien d'autres...

## Dépannage

### Le menu contextuel n'apparaît pas

1. Vérifiez que SuperMenu est bien en cours d'exécution (icône dans la barre des tâches)
2. Assurez-vous que le raccourci clavier est correctement configuré
3. Vérifiez qu'aucune autre application n'utilise le même raccourci
4. Redémarrez SuperMenu

Si besoin, consultez les logs : `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`.

### Problèmes de reconnaissance vocale

1. Vérifiez que votre microphone fonctionne correctement
2. Dans les paramètres, onglet "Réglages", sélectionnez explicitement votre microphone
3. Parlez clairement et à un volume normal
4. Assurez-vous d'être dans un environnement relativement calme

Note : le micro est enregistré uniquement via le bouton **💾 Enregistrer le microphone** (pas d'enregistrement automatique).

### Erreurs d'API

1. Vérifiez que votre clé API est correctement saisie
2. Assurez-vous d'avoir une connexion Internet active
3. Vérifiez que votre compte OpenAI dispose de crédits suffisants
4. Essayez un autre modèle (par exemple `gpt-4.1-mini`)

## Désinstallation

Lors de la désinstallation :

- SuperMenu est fermé automatiquement si nécessaire.
- Une option permet de supprimer également les données utilisateur (logs et configuration).

---

Si vous rencontrez d'autres problèmes, n'hésitez pas à consulter la documentation complète ou à contacter le support.
