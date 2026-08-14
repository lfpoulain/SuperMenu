from src.utils.accessibility_text import AccessibilitySelectionReader


class FakeAXAPI:
    focused_attribute = "AXFocusedUIElement"
    selected_text_attribute = "AXSelectedText"

    def __init__(self, *, focused=("element", 0), selection=("sélection", 0)):
        self.available = True
        self.system_wide = "system"
        self.focused = focused
        self.selection = selection
        self.queried = []

    def is_available(self):
        return self.available

    def system_wide_element(self):
        return self.system_wide

    def copy_attribute(self, element, attribute):
        self.queried.append((element, attribute))
        if attribute == self.focused_attribute:
            value, error = self.focused
            return error, value
        value, error = self.selection
        return error, value


def test_focused_element_selection_is_returned():
    api = FakeAXAPI()

    assert AccessibilitySelectionReader(api=api).selected_text() == "sélection"
    assert api.queried == [
        ("system", "AXFocusedUIElement"),
        ("element", "AXSelectedText"),
    ]


def test_missing_pyobjc_bindings_return_none():
    api = FakeAXAPI()
    api.available = False

    assert AccessibilitySelectionReader(api=api).selected_text() is None


def test_an_error_code_is_not_mistaken_for_an_empty_selection():
    api = FakeAXAPI(selection=("ignoré", -25204))

    assert AccessibilitySelectionReader(api=api).selected_text() is None


def test_an_unfocused_system_falls_back():
    api = FakeAXAPI(focused=(None, 0))

    assert AccessibilitySelectionReader(api=api).selected_text() is None


def test_an_empty_answer_is_treated_as_unknown_not_as_no_selection():
    """Several toolkits report an empty selection even when there is one.

    Returning None keeps the clipboard fallback in play instead of telling the
    user nothing was selected.
    """
    api = FakeAXAPI(selection=("", 0))

    assert AccessibilitySelectionReader(api=api).selected_text() is None


def test_a_raising_api_never_propagates():
    class ExplodingAPI(FakeAXAPI):
        def copy_attribute(self, element, attribute):
            raise RuntimeError("AXUIElementCopyAttributeValue a échoué")

    assert AccessibilitySelectionReader(api=ExplodingAPI()).selected_text() is None
