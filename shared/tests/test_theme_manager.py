from PySide6.QtCore import Qt

from supermenu_core.ui.theme_manager import ThemeManager


class FakeStyleHints:
    def __init__(self, scheme):
        self._scheme = scheme

    def colorScheme(self):
        return self._scheme


class FakeApplication:
    def __init__(self, scheme):
        self._hints = FakeStyleHints(scheme)

    def styleHints(self):
        return self._hints


def _use_scheme(monkeypatch, scheme):
    monkeypatch.setattr(
        "supermenu_core.ui.theme_manager.QGuiApplication.instance",
        staticmethod(lambda: FakeApplication(scheme)),
    )


def test_explicit_themes_are_returned_unchanged():
    assert ThemeManager.resolve_theme("dark") == "dark"
    assert ThemeManager.resolve_theme("light") == "light"


def test_unknown_theme_falls_back_to_dark():
    assert ThemeManager.resolve_theme("chartreuse") == "dark"


def test_auto_follows_the_system_colour_scheme(monkeypatch):
    """'Automatique (Système)' used to be offered and silently mean dark."""
    _use_scheme(monkeypatch, Qt.ColorScheme.Light)
    assert ThemeManager.resolve_theme("auto") == "light"

    _use_scheme(monkeypatch, Qt.ColorScheme.Dark)
    assert ThemeManager.resolve_theme("auto") == "dark"


def test_auto_falls_back_to_dark_without_style_hints(monkeypatch):
    monkeypatch.setattr(
        "supermenu_core.ui.theme_manager.QGuiApplication.instance",
        staticmethod(lambda: None),
    )

    assert ThemeManager.resolve_theme("auto") == "dark"


def test_unknown_system_scheme_falls_back_to_dark(monkeypatch):
    _use_scheme(monkeypatch, Qt.ColorScheme.Unknown)

    assert ThemeManager.resolve_theme("auto") == "dark"
