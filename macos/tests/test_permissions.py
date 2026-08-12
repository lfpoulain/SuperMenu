import sys

import pytest

from src.utils import permissions
from src.utils.permissions import PermissionStatus


def test_permission_status_names_every_missing_authorization():
    status = PermissionStatus(False, False)

    assert status.all_granted is False
    assert status.missing_labels == (
        "Accessibilité",
        "Surveillance de l’entrée",
    )


def test_permission_status_requires_both_authorizations():
    assert PermissionStatus(True, False).all_granted is False
    assert PermissionStatus(False, True).all_granted is False
    assert PermissionStatus(True, True).all_granted is True


def test_native_permission_checks_are_independent(monkeypatch):
    monkeypatch.setattr(permissions, "_ax_is_process_trusted", lambda: True)
    monkeypatch.setattr(
        permissions,
        "_cg_preflight_listen_event_access",
        lambda: False,
    )

    status = permissions.current_permission_status()

    assert status.accessibility is True
    assert status.input_monitoring is False
    assert status.accessibility_check_available is True
    assert status.input_monitoring_check_available is True


def test_unavailable_native_check_is_not_reported_as_supported(monkeypatch):
    monkeypatch.setattr(permissions, "_ax_is_process_trusted", None)
    monkeypatch.setattr(permissions, "_cg_preflight_listen_event_access", None)

    status = permissions.current_permission_status()

    assert status.accessibility_check_available is False
    assert status.input_monitoring_check_available is False


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS APIs")
def test_native_permission_apis_are_available_on_macos():
    status = permissions.current_permission_status()

    assert status.accessibility_check_available is True
    assert status.input_monitoring_check_available is True
