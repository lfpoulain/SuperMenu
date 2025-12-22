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
- **Prompts Personnalisables** : Crée tes propres actions adaptées à tes besoins.

### 🎙️ Voix & Dictée
- **Commandes Vocales** : Parle à l'IA (`Ctrl+Alt+²`).
- **Transcription Intelligente** : Dictée simple ou instructions complexes.
- **Contexte Mixte** : Combine ta voix avec le texte sélectionné à l'écran.

### 📸 Vision & Capture
- **Analyse d'Écran** : Capture une zone ou l'écran entier (`Ctrl+Alt+&`).
- **Vision IA** : Demande à l'IA d'analyser, décrire ou extraire des infos de l'image.
- **Modes de Capture** : Plein écran, Zone sélective ou "Demander à chaque fois".

### ⚙️ Flexibilité & Sécurité
- **Multi-Modèles** : Compatible OpenAI (`gpt-5.2`,`gpt-5.1`, `gpt-4.1`, etc.) et **Endpoints Locaux** (Ollama, LM Studio).
- **Interface Moderne** : Thèmes Sombre/Clair/Auto (basé sur le système).
- **Sécurisé** : Ta clé API est stockée dans le trousseau sécurisé de Windows (Windows Credential Locker), pas en clair.
- **Mises à jour Faciles** : Système de mise à jour intégré via GitHub Releases.

---

## 🚀 Installation

### Recommandée (Utilisateurs)
1. Télécharge la dernière version de l'installateur (`SuperMenu_Setup.exe`) depuis les [Releases](https://github.com/lfpoulain/SuperMenu/releases).
2. Lance l'exécutable et suis les instructions.
3. SuperMenu se lance automatiquement et se loge dans la barre des tâches (systray).

### Mise à jour
- **Automatique** : Via l'onglet "À propos" > "Vérifier les mises à jour".
- **Manuelle** : Télécharge et réinstalle la dernière version par-dessus l'existante.

---

## 🛠️ Configuration Rapide

Au premier lancement (ou via l'icône dans la barre des tâches) :

1. **API Key** : Rentre ta clé OpenAI (ou configure un endpoint local).
2. **Raccourcis** : Vérifie ou modifie les raccourcis par défaut.
   - **Menu** : `Ctrl+²` (le carré, en haut à gauche du clavier AZERTY).
   - **Voix** : `Ctrl+Alt+²`.
   - **Capture** : `Ctrl+Alt+&`.

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

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python run.py
```

### Build (Création de l'exe)

```bash
# Générer l'exécutable avec PyInstaller
pip install pyinstaller
pyinstaller --noconfirm --clean SuperMenu.spec
```

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
