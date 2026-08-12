from src.utils import window_target


def test_current_application_activation_uses_macos_activation_options(monkeypatch):
    calls = []
    # Force the legacy fallback even when this test runs on a real Mac where
    # NSApplication is available and would otherwise take the modern path.
    monkeypatch.setattr(window_target, "NSApplication", None)

    class FakeApplication:
        @staticmethod
        def isTerminated():
            return False

        @staticmethod
        def activateWithOptions_(options):
            calls.append(options)
            return True

    class FakeRunningApplication:
        @staticmethod
        def currentApplication():
            return FakeApplication()

    monkeypatch.setattr(
        window_target,
        "NSRunningApplication",
        FakeRunningApplication,
    )
    monkeypatch.setattr(
        window_target,
        "NSApplicationActivateIgnoringOtherApps",
        2,
    )

    assert window_target.activate_current_application() is True
    assert calls == [2]


def test_current_application_prefers_modern_self_activation(monkeypatch):
    calls = []

    class FakeApplication:
        @staticmethod
        def isActive():
            return False

        @staticmethod
        def activate():
            calls.append("activate")

    class FakeNSApplication:
        @staticmethod
        def sharedApplication():
            return FakeApplication()

    monkeypatch.setattr(window_target, "NSApplication", FakeNSApplication)

    assert window_target.activate_current_application() is True
    assert calls == ["activate"]


def test_current_application_activation_fails_safely_without_appkit(monkeypatch):
    monkeypatch.setattr(window_target, "NSApplication", None)
    monkeypatch.setattr(window_target, "NSRunningApplication", None)

    assert window_target.activate_current_application() is False


def test_paste_target_yields_before_cooperative_activation(monkeypatch):
    calls = []
    active = {"target": False}

    class OwnApplication:
        @staticmethod
        def isActive():
            return True

        @staticmethod
        def yieldActivationToApplication_(application):
            calls.append(("yield", application))

    class FakeNSApplication:
        @staticmethod
        def sharedApplication():
            return OwnApplication()

    class TargetApplication:
        @staticmethod
        def isTerminated():
            return False

        @staticmethod
        def bundleIdentifier():
            return "com.example.target"

        @staticmethod
        def activateWithOptions_(options):
            calls.append(("activate", options))
            active["target"] = True
            return True

    target_application = TargetApplication()

    class FakeRunningApplication:
        @staticmethod
        def runningApplicationWithProcessIdentifier_(_process_id):
            return target_application

    monkeypatch.setattr(window_target, "NSApplication", FakeNSApplication)
    monkeypatch.setattr(
        window_target,
        "NSRunningApplication",
        FakeRunningApplication,
    )
    monkeypatch.setattr(
        window_target.PasteTarget,
        "is_current",
        lambda _self: active["target"],
    )

    target = window_target.PasteTarget(
        process_id=42,
        bundle_identifier="com.example.target",
    )

    assert target.activate_and_verify() is True
    assert calls == [
        ("yield", target_application),
        ("activate", 0),
    ]
