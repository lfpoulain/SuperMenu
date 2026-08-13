"""macOS composition for the shared response window."""

from supermenu_core.ui.response_window import BaseResponseWindow
from src.utils.text_inserter import TextInserter
from src.utils.window_target import activate_current_application


class ResponseWindow(BaseResponseWindow):
    def _prepare_presentation(self):
        activate_current_application()

    def _create_text_inserter(self):
        return TextInserter()
