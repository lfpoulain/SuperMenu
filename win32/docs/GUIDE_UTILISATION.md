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

1. Installez Python 3.11 ou 3.12.
2. Placez-vous dans le dossier `win32/` du dépôt.
3. Créez un environnement : `python -m venv .venv`.
4. Activez-le : `.venv\Scripts\activate`.
5. Installez les dépendances et le cœur partagé :
   `python -m pip install -r requirements-dev.txt`.
6. Lancez l'application : `python run.py`.

## Mise à jour

SuperMenu propose deux canaux dans l'onglet **À propos** :

- **Stable — recommandé** : reçoit uniquement les releases officielles validées. Les préversions GitHub sont ignorées.
- **Beta — versions de test** : reçoit le dernier build automatique après chaque push validé sur `main`. Ce canal permet de tester les nouveautés immédiatement mais peut contenir des régressions.

Changer de canal réinitialise la date de vérification afin que vous puissiez lancer immédiatement **Vérifier les mises à jour**. Les installateurs sont distincts : `SuperMenu_Setup.exe` pour Stable et `SuperMenu_Beta_Setup.exe` pour Beta.

La méthode recommandée est d'utiliser le canal Stable. Un installateur peut être exécuté par-dessus une installation existante.

La vérification utilise normalement un manifeste léger téléchargé avec la release et ne dépend donc pas du quota de l'API GitHub.

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
     *   Modèles OpenAI proposés : `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` et `gpt-5.4`.
     *   `gpt-5.6-sol` est le choix par défaut pour la qualité maximale, `terra` équilibre qualité et coût, et `luna` vise les usages rapides ou volumineux.
     *   L'effort de raisonnement est enregistré séparément des réglages Ollama / LM Studio. Les modèles GPT-5.6 proposent `none`, `low`, `medium`, `high`, `xhigh` et `max`; GPT-5.4 propose les mêmes niveaux sauf `max`.

3.  **Raccourcis Clavier** :
    *   **Raccourci Principal** : Pour afficher le menu contextuel après avoir sélectionné du texte (par défaut : `Ctrl+²`).
    *   **Raccourci Capture d'Écran** : Pour lancer l'outil de capture d'écran (par défaut : `Ctrl+Alt+&`).
    *   **Raccourci Vocal** : Pour ouvrir le menu vocal (par défaut : `Ctrl+Alt+²`).
    *   Règles : les raccourcis doivent contenir au moins un modificateur (`Ctrl`, `Alt` ou `Shift`). Les touches de fonction `F1` à `F24` sont prises en charge. La touche `Win` n'est pas autorisée et les raccourcis à une seule touche ne sont pas supportés.

4. **Dictée et transcription** :
   * Dans **Réglages > Dictée**, choisissez OpenAI ou Foundry Local avec Nemotron. Ce choix est indépendant du moteur de texte.
   * Sélectionnez le microphone puis utilisez **Tester le micro** : le niveau s'affiche pendant cinq secondes, sans sauvegarde ni envoi d'audio.
   * Choisissez la langue. OpenAI accepte plusieurs langues attendues ; Nemotron accepte une langue ou la détection automatique.
   * Avec Foundry Local, **Vérifier** indique si les composants et le modèle sont disponibles. Téléchargez-les si nécessaire ; le chargement en mémoire intervient ensuite pour dicter.
   * Dans **Options avancées**, ajustez le vocabulaire, le contexte et le délai de déchargement du modèle local. Par défaut, il reste en mémoire cinq minutes après la dernière dictée. **Décharger maintenant** libère la mémoire sans supprimer les fichiers téléchargés.
   * Enregistrez les réglages avant de lancer une dictée.
   * La dictée simple affiche son texte final dans la même fenêtre, avec **Copier** et **Insérer**. Vous pouvez retoucher le texte avant l’insertion.
   * Dans **Après la dictée**, **Coller automatiquement** et **Corriger avec le moteur de texte avant d’insérer** sont deux options indépendantes. Une correction utilise le moteur choisi dans **Texte**. Un échec conserve votre dictée sans rien coller. Les prompts vocaux conservent leur fonctionnement propre.
   * Dans **Réglages > Raccourcis > Dictée instantanée**, définissez un raccourci facultatif, sans passer par le menu. Choisissez **Appuyer une fois** (arrêt avec **Terminer**) ou **Maintenir pour parler** (arrêt au relâchement). Attendez **À l’écoute** avant de parler ; un relâchement pendant le chargement annule le démarrage.

5. **Mémoire du modèle texte Foundry** : dans **Texte > Foundry Local > Matériel et mémoire du modèle**, choisissez un déchargement après chaque requête, après 1/5/15/30 minutes d’inactivité, ou à la fermeture. Le délai par défaut est de cinq minutes. **Décharger maintenant** libère la RAM/VRAM quand aucune requête n’est en cours ; les modèles restent téléchargés.

### Configuration de l'API

1. Ouvrez les paramètres de SuperMenu
2. Allez dans **Réglages > Texte**
3. Renseignez la clé API (si vous utilisez OpenAI)
4. Sélectionnez un modèle
5. (Optionnel) activez un endpoint personnalisé et configurez l'URL + le modèle

### Vérification des raccourcis clavier

Par défaut, SuperMenu utilise les raccourcis suivants :
- **Ctrl+²** : Menu contextuel pour le texte sélectionné
- **Ctrl+Alt+&** : Capture d'écran
- **Ctrl+Alt+²** : Reconnaissance vocale

Vous pouvez les modifier dans l'onglet "Réglages" des paramètres.

Notes importantes :
- Les raccourcis sont enregistrés au niveau Windows (raccourcis globaux).
- Si un raccourci est déjà utilisé par une autre application, SuperMenu ne pourra pas l'enregistrer.
- Certaines touches dépendent de la disposition clavier (ex : `²`, `&` en AZERTY). Si vous changez de layout, ajustez le raccourci.

## Utilisation quotidienne

### Menu contextuel

1. Sélectionnez du texte dans n'importe quelle application
2. Appuyez sur **Ctrl+²** (ou votre raccourci personnalisé)
3. Choisissez l'action souhaitée dans le menu qui apparaît
4. Le résultat s'affiche dans une fenêtre dédiée ou est inséré directement

Si vous cliquez en dehors du menu ou si vous changez de fenêtre sans sélectionner d'action, le menu se ferme automatiquement.

### Raccourcis directs par prompt

1. Dans l'onglet **Prompts**, sélectionnez un prompt puis cliquez sur **Définir** à côté de **Raccourci direct**.
2. Saisissez la combinaison voulue et enregistrez le prompt.
3. Sélectionnez du texte dans n'importe quelle application.
4. Appuyez sur le raccourci de ce prompt.
5. Le raccourci lance le prompt sans afficher le menu :
   - si **Insérer directement** est coché, une petite notification confirme l'envoi puis le résultat remplace la sélection ;
   - si l'option est décochée, la fenêtre de réponse s'ouvre et affiche le résultat.

Chaque prompt peut avoir son propre raccourci, ou aucun. Deux prompts ne peuvent pas partager la même combinaison. En cas de conflit avec Windows, une autre application ou un raccourci principal de SuperMenu, l'ancien réglage est conservé.

### Reconnaissance vocale

1. Appuyez sur **Ctrl+Alt+²** (ou votre raccourci personnalisé), puis choisissez l'action vocale
2. Attendez **À l'écoute** avant de parler. Le modèle local déjà en mémoire est réutilisé
3. La fenêtre affiche le texte en direct, le niveau du microphone et la durée, limitée à cinq minutes de capture
4. Cliquez sur **Terminer** pour finaliser, ou sur **Annuler** pour abandonner la dictée et arrêter le microphone
5. La finalisation intègre les derniers mots ; vous pouvez copier le texte affiché
6. Avec la dictée simple, la transcription s'ouvre dans la fenêtre de réponse : vous pouvez la relire, la copier ou cliquer sur **Écrire**
7. Avec un prompt vocal, la transcription est traitée selon les options de ce prompt

La préparation du moteur ne compte pas dans les cinq minutes de capture. Aucun
fichier audio n'est sauvegardé. Avec OpenAI, le son est transmis au service ; avec
Nemotron, il est traité sur le PC. Les mots-clés doivent rester courts et
correspondre à des termes susceptibles d'être prononcés.

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
   - **Raccourci direct** : Combinaison optionnelle propre à ce prompt, sans menu intermédiaire ; elle respecte le réglage **Insérer directement**
   - **Position** : Ordre d'apparition dans le menu (plus petit = plus haut)

### Personnalisation des prompts vocaux

1. Ouvrez les paramètres
2. Allez dans l'onglet "Prompts Vocaux"
3. Configurez de la même manière que les prompts textuels
4. Options supplémentaires :
   - **Inclure le texte sélectionné** : Ajoute le texte sélectionné à la requête
   - **Ordre des éléments** : Définit l'ordre du prompt, de la transcription et du texte sélectionné

### Modifier le modèle OpenAI utilisé

Dans l'onglet "Modèles", sélectionnez le modèle et son effort de raisonnement, puis enregistrez. Les anciennes sélections sont migrées automatiquement selon leur rôle : anciens modèles phares vers Sol, variantes mini vers Terra et variantes nano vers Luna.

Avec LM Studio 0.4 ou plus récent, SuperMenu utilise l'API REST native et adapte le réglage de raisonnement aux capacités annoncées par le modèle. Par exemple, un modèle limité à `off/on` reçoit ces valeurs même si l'interface utilise `none/low/medium/high`. Les anciennes versions de LM Studio restent prises en charge via un repli compatible OpenAI. Aucune limite fixe de 2 048 tokens n'est appliquée aux réponses LM Studio.

Avec Ollama, SuperMenu consulte les capacités de `/api/show`. Qwen 3, DeepSeek R1 et DeepSeek v3.1 reçoivent un booléen `think`. GPT‑OSS reçoit obligatoirement `low`, `medium` ou `high` : comme son raisonnement ne peut pas être désactivé, le choix `none` utilise `low` mais masque la trace. Les modèles sans capacité `thinking` ne reçoivent aucun paramètre inutile. SuperMenu ne fixe plus `num_predict` à 2 048 et respecte donc la configuration du modèle.

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

Astuce : si vous venez de modifier un raccourci, choisissez une combinaison différente (certaines applications réservent des raccourcis globaux). En cas de conflit, un message d'erreur apparaît et le raccourci précédent est restauré.

Si besoin, consultez les logs : `%LOCALAPPDATA%\SuperMenu\logs\supermenu.log`.

Le menu utilise toujours le composant Qt natif. L'ancien choix « Standard Qt / Forcer via Windows » concernait uniquement la fenêtre de résultat et a été retiré. Cette fenêtre applique maintenant automatiquement Qt puis un renforcement Win32.

### Problèmes de reconnaissance vocale

1. Dans **Réglages > Dictée**, sélectionnez votre microphone et cliquez sur **Tester le micro**
2. Si aucun niveau n'apparaît, vérifiez les autorisations Microphone de Windows et essayez une autre entrée
3. Pour OpenAI, vérifiez la clé API et la connexion Internet. Pour Foundry Local, utilisez **Vérifier** puis téléchargez les composants manquants
4. Distinguez le téléchargement sur disque du chargement en mémoire : un modèle déchargé peut être rechargé sans être téléchargé à nouveau
5. Enregistrez les réglages puis relancez une dictée ; attendez **À l'écoute** avant de parler

### Erreurs d'API

1. Vérifiez que votre clé API est correctement saisie
2. Assurez-vous d'avoir une connexion Internet active
3. Vérifiez que votre compte OpenAI dispose de crédits suffisants
4. Essayez un autre modèle (par exemple `gpt-5.6-terra`)

## Désinstallation

Lors de la désinstallation :

- SuperMenu est fermé automatiquement si nécessaire.
- Une option permet de supprimer également les données utilisateur (logs et configuration).

---

Si vous rencontrez d'autres problèmes, n'hésitez pas à consulter la documentation complète ou à contacter le support.
