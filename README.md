# SuperMenu 🚀

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)
![Status](https://img.shields.io/badge/status-Active-success)

**SuperMenu** est ton assistant IA personnel pour Windows. Accessible instantanément via un raccourci clavier, il s'intègre à n'importe quelle application pour traiter du texte, de la voix ou des images.

> 💡 **Idée clé** : Ne perds plus de temps à copier-coller vers ChatGPT. SuperMenu amène l'IA directement là où tu travailles.

---

## ✨ Fonctionnalités Principales

### 📝 Texte & Productivité
- **Menu Contextuel Universel** : Sélectionne du texte n'importe où et lance SuperMenu (`Ctrl+²`).
- **Actions Rapides** : Corriger, Reformuler, Résumer, Traduire, Expliquer...
- **Insertion Directe** : Remplace automatiquement le texte sélectionné par la réponse de l'IA (idéal pour les corrections).
- **Raccourcis par Prompt** : Attribue une combinaison différente à chaque prompt pour le lancer sans ouvrir le menu. Selon l'option du prompt, le résultat remplace directement la sélection ou s'affiche dans la fenêtre de réponse.
- **Prompts Personnalisables** : Crée tes propres actions adaptées à tes besoins.
- **Mode Personnalisé Direct** : Lance le prompt libre sans passer par le menu contextuel (`Ctrl+Alt+M`).

### 🎙️ Voix & Dictée
- **Commandes Vocales** : Parle à l'IA (`Ctrl+Alt+²`).
- **GPT Transcribe** : Modèle OpenAI recommandé pour les enregistrements terminés, avec détection ou indices multilingues.
- **Retour Visuel Complet** : Durée d'enregistrement, limite visible, préparation, transcription, succès et erreurs dans une seule carte.
- **Vocabulaire Personnalisé** : Langues attendues, termes techniques et contexte facultatif configurables.
- **Contexte Mixte** : Combine ta voix avec le texte sélectionné à l'écran.

### 📸 Vision & Capture
- **Analyse d'Écran** : Capture une zone ou l'écran entier (`Ctrl+Alt+&`).
- **Vision IA** : Demande à l'IA d'analyser, décrire ou extraire des infos de l'image.
- **Modes de Capture** : Plein écran, Zone sélective ou "Demander à chaque fois".

### ⚙️ Flexibilité & Sécurité
- **Multi-Modèles** : Sélecteur OpenAI limité à `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` et `gpt-5.4`, plus les **Endpoints Locaux** (Ollama, LM Studio).
- **Thinking / Raisonnement** : GPT‑OSS utilise ses niveaux `low/medium/high`, Qwen et DeepSeek utilisent l’interrupteur `think`, et LM Studio suit les capacités natives du modèle (`off/on` ou niveaux).
- **Sélecteur d'Endpoint** : Choisis explicitement Ollama ou LM Studio dans les paramètres au lieu de dépendre d'une détection automatique.
- **Interface Moderne** : Thèmes Sombre/Clair/Auto (basé sur le système).
- **Fenêtres Fiables** : Menu Qt natif et présentation hybride Qt/Win32 pour la fenêtre de résultat, sans mode expérimental à choisir.
- **Sécurisé** : Ta clé API est stockée dans le trousseau sécurisé de Windows (Windows Credential Locker), pas en clair.
- **Mises à jour Faciles** : Système de mise à jour intégré via GitHub Releases.

---

## 🚀 Installation

### Recommandée (Utilisateurs)
1. Télécharge la dernière version de l'installateur (`SuperMenu_Setup.exe`) depuis les [Releases](https://github.com/lfpoulain/SuperMenu/releases).
2. Lance l'exécutable et suis les instructions.
3. SuperMenu se lance automatiquement et se loge dans la barre des tâches (systray).

### Mise à jour
- **Stable (recommandé)** : uniquement les releases officielles non expérimentales.
- **Beta** : build automatique produit après chaque push sur `main` dont la CI réussit, publié comme prérelease.
- Le canal se choisit dans **À propos > Canal de mise à jour**.
- **Automatique** : utilise **Vérifier les mises à jour** ou la vérification quotidienne discrète.
- **Manuelle** : télécharge `SuperMenu_Setup.exe` pour une stable ou `SuperMenu_Beta_Setup.exe` pour une beta.
- La vérification automatique lit d'abord un petit manifeste attaché à la release, sans consommer le quota de l'API GitHub. L'API reste disponible comme solution de secours.

---

## 🛠️ Configuration Rapide

Au premier lancement (ou via l'icône dans la barre des tâches) :

1. **API Key** : Rentre ta clé OpenAI (ou configure un endpoint local).
2. **Raccourcis** : Vérifie ou modifie les raccourcis par défaut.
   - **Menu** : `Ctrl+²` (le carré, en haut à gauche du clavier AZERTY).
   - **Voix** : `Ctrl+Alt+²`.
   - **Capture** : `Ctrl+Alt+&`.
   - **Mode personnalisé** : `Ctrl+Alt+M`.

---

## 🧑‍💻 Développement

Envie de contribuer ou de modifier le code ?

### Prérequis
- Windows 10/11
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (inclus dans les builds, mais requis pour le dev audio)

### Installation Dev

```bash
# Cloner le dépôt
git clone https://github.com/lfpoulain/SuperMenu.git
cd SuperMenu

# Créer l'environnement virtuel
python -m venv venv
venv\Scripts\activate

# Installer les dépendances runtime et développement
pip install -r requirements-dev.txt

# Lancer l'application
python run.py
```

### Build (Création de l'exe)

```bash
# Générer l'exécutable avec la version PyInstaller validée
pyinstaller --noconfirm --clean SuperMenu.spec

# Vérifier les ressources du bundle sans lancer l'interface
dist\SuperMenu.exe --smoke-test
```

### CI et publication

- `.github/workflows/ci.yml` valide chaque pull request et chaque push sur `main` avec Python 3.10 et 3.12, sans publier de release.
- `.github/workflows/beta-release.yml` construit la prérelease roulante `beta` après la réussite de la CI d'un push sur `main`, avec des artefacts clairement suffixés `Beta` et leurs checksums SHA-256.
- `.github/workflows/stable-release.yml` publie une release stable immuable uniquement lors du push d'un tag `vMAJOR.MINOR.PATCH`.
- `VERSION` contient la prochaine version stable attendue. Le tag stable doit correspondre exactement à ce fichier.

Pour publier une stable, il faut volontairement effectuer ces trois opérations :

1. inscrire le nouveau numéro sans `v` dans `VERSION`, par exemple `1.2.1` ;
2. commiter et pousser ce changement sur `main`, puis attendre que la CI réussisse ;
3. créer et pousser le tag correspondant avec un `v`, par exemple `v1.2.1`.

Exemple lorsque `VERSION` contient déjà `1.2.1` et que ce changement est sur `main` :

```bash
# VERSION contient 1.2.1 et le commit a déjà été poussé sur main
git tag v1.2.1
git push origin v1.2.1
```

À partir du push du tag, les tests, la compilation des exécutables et de l'installateur, les checksums et la publication de la release GitHub Stable sont automatiques. Si le tag et `VERSION` ne correspondent pas, le workflow s'arrête sans publier.

---

## 📚 Documentation

Pour aller plus loin, consulte les guides dans le dossier `docs/` :
- [📖 Guide d'Utilisation Complet](docs/GUIDE_UTILISATION.md)
- [🏗️ Architecture Technique](docs/ARCHITECTURE.md)

---

## 📄 Licence

© 2025 LFPoulain. Tous droits réservés.
Distribué sous licence **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

> Vous êtes autorisé à partager et adapter le matériel, à condition de créditer l'auteur.
> **L'utilisation commerciale est strictement interdite.**
> Voir le fichier [LICENSE](LICENSE) pour plus de détails.
