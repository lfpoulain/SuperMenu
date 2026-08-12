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

