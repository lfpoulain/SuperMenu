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


def test_unavailable_native_check_is_not_reported_as_supported(monkeypatch):
    monkeypatch.setattr(permissions, "_ax_is_process_trusted", None)

    status = permissions.current_permission_status()

    assert status.accessibility_check_available is False


@pytest.mark.skipif(sys.platform != "darwin", reason="native macOS APIs")
def test_native_permission_apis_are_available_on_macos():
    status = permissions.current_permission_status()

    assert status.accessibility_check_available is True
