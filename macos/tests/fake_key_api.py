"""Shared fake for the CoreGraphics keyboard boundary used by the tests."""


class FakeQuartzKeyAPI:
    command_flag = 1 << 20
    shift_flag = 1 << 17

    def __init__(self):
        self.posted = []
        self.held = 0
        self.fail_post = False

    def post_key(self, key_code, key_down, flags):
        if self.fail_post:
            raise RuntimeError("macOS n'a pas créé l'événement clavier")
        self.posted.append((key_code, key_down, flags))

    def held_modifiers(self):
        return self.held
