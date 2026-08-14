from src.utils.key_events import (
    KEY_CODE_C,
    KEY_CODE_COMMAND,
    KEY_CODE_V,
    KeyEventPoster,
)

from tests.fake_key_api import FakeQuartzKeyAPI


def test_the_modifier_is_pressed_and_released_around_the_key():
    """A bare flag on the letter is not a coherent key sequence.

    An application that receives a key-down carrying the Command flag without
    the matching flagsChanged events can be left believing the modifier is
    still held. Chrome showed this as a missing text cursor and dead selection
    for several seconds afterwards.
    """
    api = FakeQuartzKeyAPI()

    assert KeyEventPoster(api=api).copy() is True
    assert api.posted == [
        (KEY_CODE_COMMAND, True, api.command_flag),
        (KEY_CODE_C, True, api.command_flag),
        (KEY_CODE_C, False, api.command_flag),
        (KEY_CODE_COMMAND, False, 0),
    ]


def test_paste_uses_the_positional_v_key():
    api = FakeQuartzKeyAPI()

    assert KeyEventPoster(api=api).paste() is True
    assert [event[0] for event in api.posted] == [
        KEY_CODE_COMMAND,
        KEY_CODE_V,
        KEY_CODE_V,
        KEY_CODE_COMMAND,
    ]


def test_command_is_released_even_when_the_key_press_fails():
    """A latched Command would turn every later keystroke into a shortcut."""

    class FailAfterModifier(FakeQuartzKeyAPI):
        def post_key(self, key_code, key_down, flags):
            if key_code != KEY_CODE_COMMAND and key_down:
                raise RuntimeError("macOS a refusé l'événement clavier")
            super().post_key(key_code, key_down, flags)

    api = FailAfterModifier()

    assert KeyEventPoster(api=api).copy() is False
    assert api.posted == [
        (KEY_CODE_COMMAND, True, api.command_flag),
        (KEY_CODE_COMMAND, False, 0),
    ]


def test_nothing_is_posted_when_the_modifier_press_itself_fails():
    api = FakeQuartzKeyAPI()
    api.fail_post = True

    assert KeyEventPoster(api=api).copy() is False
    assert api.posted == []


def test_held_modifiers_are_reported_from_the_device_independent_mask():
    api = FakeQuartzKeyAPI()
    poster = KeyEventPoster(api=api)

    assert poster.modifiers_are_released() is True

    api.held = api.shift_flag
    assert poster.modifiers_are_released() is False


def test_the_wait_gives_up_rather_than_stranding_the_shortcut():
    """A genuinely held modifier must not swallow the prompt entirely."""
    api = FakeQuartzKeyAPI()
    api.held = api.command_flag
    scheduled = []
    called = []

    poster = KeyEventPoster(api=api)
    poster.when_modifiers_released(
        lambda _delay, callback: scheduled.append(callback),
        lambda: called.append(True),
    )

    while scheduled and not called:
        scheduled.pop(0)()

    assert called == [True]
