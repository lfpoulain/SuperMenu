import sys

import pytest

from src.utils import permissions
from src.utils.permissions import PermissionStatus


def test_permission_status_names_missing_accessibility_authorization():
    status = PermissionStatus(False)

    assert status.all_granted is False
    assert status.missing_labels == ("Accessibilité",)


def test_permission_status_requires_accessibility():
    assert PermissionStatus(False).all_granted is False
    assert PermissionStatus(True).all_granted is True


def test_native_accessibility_permission_check(monkeypatch):
    monkeypatch.setattr(permissions, "_ax_is_process_trusted", lambda: True)

    status = permissions.current_permission_status()

    assert status.accessibility is True
    assert status.accessibility_check_available is True


def test_native_accessibility_prompt_is_dispatched_without_using_trust_result(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        permissions,
        "_ax_is_process_trusted_with_options",
        lambda options: calls.append(options) or False,
    )
    monkeypatch.setattr(permissions, "_ax_prompt_key", "prompt")

    assert permissions.request_accessibility_permission() is True
    assert calls == [{"prompt": True}]


def test_native_accessibility_prompt_reports_unavailable(monkeypatch):
    monkeypatch.setattr(
        permissions,
        "_ax_is_process_trusted_with_options",
        None,
    )

    assert permissions.request_accessibility_permission() is False


def test_unavailable_native_check_is_not_reported_as_supported(monkeypatch):
    monkeypatch.setattr(permissions, "_ax_is_process_trusted", None)

    status = permissions.current_permission_status()

    assert status.accessibility_check_available is False


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS APIs")
def test_native_permission_apis_are_available_on_macos():
    status = permissions.current_permission_status()

    assert status.accessibility_check_available is True


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS APIs")
def test_native_consent_prompt_api_is_packaged():
    """Guard the dependency that owns AXIsProcessTrustedWithOptions.

    ``HIServices`` ships in pyobjc-framework-ApplicationServices, which is not
    pulled in by Cocoa or Quartz. When it is missing the import error is
    swallowed and the app silently degrades to "open System Settings" on a
    pane where macOS never listed SuperMenu, because it never asked.
    """
    assert permissions._ax_is_process_trusted_with_options is not None
    assert permissions._ax_prompt_key is not None
