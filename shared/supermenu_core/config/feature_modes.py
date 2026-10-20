"""Fonctions avancées et expérimentales, réglables sur chaque plateforme.

Deux interrupteurs indépendants de la page Application :

- « Fonctions avancées » : modèle, fournisseur ou poste LM Link choisi pour
  chaque prompt, raccourci direct par prompt et durée de conservation des
  modèles locaux en mémoire ;
- « Fonctions expérimentales » : prompts vocaux, dictée instantanée, réglages
  de la dictée, test du micro et, sous Windows, capture et analyse d’écran.

Désactiver une fonction la masque et l’ignore, sans jamais rien supprimer :
les prompts, raccourcis et délais enregistrés restent intacts et réapparaissent
quand la fonction est réactivée. Les interrupteurs sont lus au moment de
l’usage, jamais mis en cache.

Une nouvelle installation démarre avec les deux interrupteurs désactivés. Une
installation existante (réglages d’une version précédente) les reçoit activés,
pour qu’une mise à jour ne retire jamais une fonction utilisée.

Ce module ne dépend ni de Qt ni d’une plateforme. Il n’importe ni
``model_target`` ni ``prompts`` : ``model_target`` l’importe.
"""

from .model_memory import DEFAULT_IDLE_SECONDS

ADVANCED_FEATURES_SETTING = "advanced_features_enabled"
EXPERIMENTAL_FEATURES_SETTING = "experimental_features_enabled"

# Valeur d’une nouvelle installation. Toujours lue au moment de l’appel
# (feature_modes.NEW_INSTALL_ENABLED) : les tests la remplacent.
NEW_INSTALL_ENABLED = False

# Clés écrites au premier lancement par toutes les versions précédentes, sur
# les deux plateformes : leur présence signale une installation existante.
LEGACY_MARKER_KEYS = ("hotkey", "prompts", "model", "theme", "update_channel")


class FeatureModesSettingsMixin:
    """Interrupteurs persistés ; attend ``self.settings`` (QSettings) et ``sync()``."""

    def has_saved_preferences(self):
        """Vrai si une version précédente a déjà enregistré des réglages.

        À appeler juste après la création du QSettings, avant d’écrire la
        moindre valeur par défaut.
        """
        try:
            return any(self.settings.contains(key) for key in LEGACY_MARKER_KEYS)
        except Exception:
            return False

    def initialize_feature_modes(self, existing_install):
        """Écrit les interrupteurs absents, sans jamais remplacer un choix."""
        # Read by the startup sequence to welcome a brand-new installation.
        self.first_launch = not bool(existing_install)
        enabled = bool(existing_install) or bool(NEW_INSTALL_ENABLED)
        written = False
        for key in (ADVANCED_FEATURES_SETTING, EXPERIMENTAL_FEATURES_SETTING):
            if not self.settings.contains(key):
                self.settings.setValue(key, enabled)
                written = True
        if written:
            self.sync()

    def get_advanced_features_enabled(self):
        return bool(
            self.settings.value(
                ADVANCED_FEATURES_SETTING, bool(NEW_INSTALL_ENABLED), type=bool
            )
        )

    def set_advanced_features_enabled(self, enabled):
        self.settings.setValue(ADVANCED_FEATURES_SETTING, bool(enabled))

    def get_experimental_features_enabled(self):
        return bool(
            self.settings.value(
                EXPERIMENTAL_FEATURES_SETTING, bool(NEW_INSTALL_ENABLED), type=bool
            )
        )

    def set_experimental_features_enabled(self, enabled):
        self.settings.setValue(EXPERIMENTAL_FEATURES_SETTING, bool(enabled))


def _enabled(settings, getter_name):
    # Un objet sans cette API (ancien adaptateur, faux réglages de test)
    # garde le comportement d’avant les interrupteurs : tout est actif.
    getter = getattr(settings, getter_name, None)
    return True if getter is None else bool(getter())


def advanced_enabled(settings):
    """Fonctions avancées actives ? Lu à chaque usage, sans cache."""
    return _enabled(settings, "get_advanced_features_enabled")


def experimental_enabled(settings):
    """Fonctions expérimentales actives ? Lu à chaque usage, sans cache."""
    return _enabled(settings, "get_experimental_features_enabled")


def effective_model_target(settings, target):
    """Le modèle choisi pour un prompt, ou {} (réglage général) sans le mode avancé."""
    return dict(target or {}) if advanced_enabled(settings) else {}


def effective_text_idle_seconds(settings):
    """Délai de conservation du modèle texte local réellement appliqué."""
    if not advanced_enabled(settings):
        return DEFAULT_IDLE_SECONDS
    return settings.get_text_idle_seconds()


def effective_speech_idle_seconds(settings):
    """Délai de conservation du modèle vocal local réellement appliqué."""
    if not advanced_enabled(settings):
        return DEFAULT_IDLE_SECONDS
    return settings.get_speech_idle_seconds()


def prompts_with_model_target(settings):
    """Nombre de prompts (texte et voix) dont le modèle est choisi pour eux.

    Ne modifie rien ; renvoie 0 si les prompts ne peuvent pas être lus.
    """
    count = 0
    for getter_name in ("get_prompts", "get_voice_prompts"):
        getter = getattr(settings, getter_name, None)
        if getter is None:
            continue
        try:
            prompts = getter()
            if not isinstance(prompts, dict):
                continue
            count += sum(
                1
                for prompt in prompts.values()
                if isinstance(prompt, dict) and prompt.get("model_target")
            )
        except Exception:
            continue
    return count
