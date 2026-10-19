import os

from src.utils import window_target


def test_current_application_activation_uses_macos_activation_options():
    calls = []

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

    assert window_target._activate_current_application(
        None,
        FakeRunningApplication,
        2,
    ) is True
    assert calls == [2]


def test_current_application_prefers_modern_self_activation():
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

    assert window_target._activate_current_application(
        FakeNSApplication,
        None,
        0,
    ) is True
    assert calls == ["activate"]


def test_current_application_activation_fails_safely_without_appkit():
    assert window_target._activate_current_application(
        None,
        None,
        0,
    ) is False


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

    assert target.request_activation() is True
    assert calls == [
        ("yield", target_application),
        ("activate", 0),
    ]


def test_paste_target_force_falls_back_when_cooperative_activation_is_rejected(
    monkeypatch,
):
    calls = []

    class OwnApplication:
        @staticmethod
        def isActive():
            return True

        @staticmethod
        def yieldActivationToApplication_(_application):
            calls.append("yield")

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
            return options == 2

    class FakeRunningApplication:
        @staticmethod
        def runningApplicationWithProcessIdentifier_(_process_id):
            return TargetApplication()

    monkeypatch.setattr(window_target, "NSApplication", FakeNSApplication)
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
    monkeypatch.setattr(window_target.PasteTarget, "is_current", lambda _self: False)
    target = window_target.PasteTarget(
        process_id=42,
        bundle_identifier="com.example.target",
    )

    assert target.request_activation() is True
    assert calls == ["yield", ("activate", 0), ("activate", 2)]


def test_paste_target_rejects_reused_pid_with_a_different_bundle(monkeypatch):
    class FrontmostApplication:
        @staticmethod
        def processIdentifier():
            return 42

        @staticmethod
        def bundleIdentifier():
            return "com.example.other"

    monkeypatch.setattr(
        window_target,
        "_frontmost_application",
        lambda: FrontmostApplication(),
    )
    target = window_target.PasteTarget(
        process_id=42,
        bundle_identifier="com.example.original",
    )

    assert target.is_current() is False


class _FakeFrontmost:
    def __init__(self, process_id, bundle="com.example.editor", name="Editor"):
        self._process_id = process_id
        self._bundle = bundle
        self._name = name

    def processIdentifier(self):
        return self._process_id

    def bundleIdentifier(self):
        return self._bundle

    def localizedName(self):
        return self._name

    def isTerminated(self):
        return False


def test_ui_triggered_menus_reuse_the_application_the_user_came_from(monkeypatch):
    """SuperMenu is frontmost when its own UI opens the prompt menu.

    Without a remembered target the capture returns None, the selection is
    always empty and every prompt in the menu stays greyed out.
    """
    window_target.PasteTarget.forget_last_known()
    editor = _FakeFrontmost(4321)
    frontmost = {"application": editor}
    monkeypatch.setattr(
        window_target,
        "_frontmost_application",
        lambda: frontmost["application"],
    )
    monkeypatch.setattr(
        window_target,
        "NSRunningApplication",
        type(
            "FakeRunningApplication",
            (),
            {
                "runningApplicationWithProcessIdentifier_": staticmethod(
                    lambda _pid: editor
                )
            },
        ),
    )

    remembered = window_target.PasteTarget.remember_frontmost()
    assert remembered.process_id == 4321

    # SuperMenu takes the foreground.
    frontmost["application"] = _FakeFrontmost(
        os.getpid(),
        bundle="com.supermenu.macos",
        name="SuperMenu",
    )

    assert window_target.PasteTarget.capture() is None
    fallback = window_target.PasteTarget.capture(fall_back_to_last_known=True)
    assert fallback is not None
    assert fallback.process_id == 4321
    window_target.PasteTarget.forget_last_known()


def test_a_terminated_remembered_target_is_dropped(monkeypatch):
    window_target.PasteTarget.forget_last_known()
    editor = _FakeFrontmost(4321)
    frontmost = {"application": editor}
    monkeypatch.setattr(
        window_target,
        "_frontmost_application",
        lambda: frontmost["application"],
    )
    monkeypatch.setattr(
        window_target,
        "NSRunningApplication",
        type(
            "FakeRunningApplication",
            (),
            {
                "runningApplicationWithProcessIdentifier_": staticmethod(
                    lambda _pid: None
                )
            },
        ),
    )

    window_target.PasteTarget.remember_frontmost()
    frontmost["application"] = _FakeFrontmost(
        os.getpid(),
        bundle="com.supermenu.macos",
    )

    assert window_target.PasteTarget.capture(fall_back_to_last_known=True) is None
    window_target.PasteTarget.forget_last_known()
