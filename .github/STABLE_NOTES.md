## Nouveautés de SuperMenu 1.3.1

Version Stable recommandée pour une utilisation quotidienne, pour Windows (exécutable portable et installateur) et pour Mac Apple Silicon (DMG signé Developer ID et notarisé par Apple).

- **Anthropic — Claude** : nouveau moteur de texte, avec sa propre clé API, sous Windows et macOS. Modèles Claude Opus 5.5 (par défaut), Sonnet 5.5, Haiku 5.5, Fable 5.2, Opus 5, Sonnet 5 et Opus 4.8, raisonnement réglable de `low` à `max`. Avec les fonctions avancées, il se choisit aussi pour un seul prompt.
- **OpenAI** : la liste des modèles s’élargit aux familles GPT-6 et GPT-5 (`gpt-6.2-astra`, `gpt-6.2-sol`, `gpt-6.1-terra`, `gpt-6-luna`, `gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-astra`, `gpt-5.5`, `gpt-5.4-mini`, `gpt-5.2`). Le modèle par défaut reste `gpt-5.6-sol`.
- **macOS plus stable** : une image copiée survit à la lecture de la sélection et à l’insertion, la fenêtre de dictée reste visible quand vous cliquez dans votre document, les raccourcis ne restent plus ignorés après une erreur de menu, ils fonctionnent avec les dispositions qui passent en lettres latines sous Command, Apple Intelligence et Apple Speech ne sont plus masqués à tort, et les messages de mise à jour s’affichent au premier plan.
- **Windows** : l’enregistreur accepte les raccourcis `Ctrl+lettre` et `Ctrl+Shift+lettre`, déclencher le menu sur des fichiers ou une image sélectionnés ne remplace plus le presse-papiers, et le raccourci de capture ne ferme plus un dialogue ouvert.
- **Serveurs locaux** : un serveur Ollama ou LM Studio arrêté est signalé aussitôt au lieu d’attendre 10 à 20 secondes, les serveurs locaux ne passent plus par le proxy configuré pour Internet, et une adresse Ollama en `/v1` fonctionne.
- **Erreurs plus claires** : **Ouvrir les réglages** apparaît dans la fenêtre de réponse après une clé API manquante ou refusée ; un texte qui cite des balises `<think>` n’est plus amputé.

Les prompts, réglages et modèles déjà téléchargés sont conservés. Sur Mac, les touches F21 à F24, que macOS ne peut pas lier, ne sont plus proposées comme raccourcis.
