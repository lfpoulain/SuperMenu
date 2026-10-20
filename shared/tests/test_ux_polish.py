"""User-facing polish: response window states, first launch and default prompts."""

import re

import pytest
from PySide6.QtWidgets import QApplication

from supermenu_core.config.feature_modes import FeatureModesSettingsMixin
from supermenu_core.config.prompts import default_text_prompts, default_voice_prompts
from supermenu_core.ui.response_window import (
    ERROR_TITLE,
    LOADING_TITLE,
    RESPONSE_TITLE,
    BaseResponseWindow,
    error_needs_settings,
)


@pytest.fixture
def window():
    QApplication.instance() or QApplication([])
    widget = BaseResponseWindow()
    yield widget
    widget.close()
    widget.deleteLater()


def test_each_state_has_its_own_title(window):
    window.set_loading(True)
    assert window.title_label.text() == LOADING_TITLE
    window.set_response("Bonjour")
    assert window.title_label.text() == RESPONSE_TITLE
    window.set_error("Erreur: délai dépassé")
    assert window.title_label.text() == ERROR_TITLE


@pytest.mark.parametrize(
    "message",
    [
        "Clé API non configurée. Veuillez configurer votre clé API dans les paramètres.",
        "Configuration personnalisée incomplète. Renseignez obligatoirement l'endpoint et le modèle.",
        'Erreur 401: {"error": {"code": "invalid_api_key"}}',
    ],
)
def test_configuration_errors_offer_to_open_the_settings(window, message):
    opened = []
    window.settings_requested.connect(lambda: opened.append(True))
    window.show()
    window.set_error(message)

    assert error_needs_settings(message)
    assert not window.settings_button.isHidden()
    window.settings_button.click()
    assert opened == [True]
    assert not window.isVisible()


def test_other_errors_and_answers_do_not_offer_the_settings(window):
    window.set_error("Erreur: la connexion a été interrompue")
    assert window.settings_button.isHidden()
    window.set_error("Clé API non configurée.")
    window.set_response("Réponse")
    assert window.settings_button.isHidden()


def test_a_refused_key_is_explained_before_the_raw_detail(window):
    window.set_error('Erreur 401: {"error": "invalid_api_key"}')
    text = window.response_text.toPlainText()
    assert text.startswith("Le fournisseur a refusé la clé API.")
    assert text.endswith('Détail : Erreur 401: {"error": "invalid_api_key"}')
    # Copy keeps what the window shows, so a bug report has the raw detail.
    assert window.copy_button.isEnabled()


class _Settings(FeatureModesSettingsMixin):
    def __init__(self, stored):
        self.settings = _Store(stored)

    def sync(self):
        pass


class _Store:
    def __init__(self, values):
        self.values = dict(values)

    def contains(self, key):
        return key in self.values

    def setValue(self, key, value):
        self.values[key] = value


@pytest.mark.parametrize("stored,first", [({}, True), ({"hotkey": "Ctrl+²"}, False)])
def test_first_launch_is_only_a_brand_new_installation(stored, first):
    settings = _Settings(stored)
    settings.initialize_feature_modes(settings.has_saved_preferences())
    assert settings.first_launch is first


def test_default_prompts_are_generic_and_typographically_consistent():
    prompts = {**default_text_prompts(), **default_voice_prompts()}

    # Personal prompts of the author are not offered to new installations.
    assert "corrections_montage" not in prompts
    for prompt in prompts.values():
        text = prompt["prompt"].lower()
        assert "youtube" not in text and "montage" not in text
        assert "envoi directement" not in text
        assert "..." not in prompt["status"]
        # Sentence case: only the first word is capitalised.
        words = prompt["name"].split()
        assert all(not word[0].isupper() for word in words[1:]), prompt["name"]
    assert prompts["extraire_passages_importants"]["name"] == "Extraire les passages importants"
    assert not re.search(r"\bExtrait de ce texte\b", prompts["extraire_passages_importants"]["prompt"])
