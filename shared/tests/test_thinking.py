from supermenu_core.api.openai_client import OpenAIClient
from supermenu_core.ui.response_window import BaseResponseWindow
from supermenu_core.utils import thinking


def test_angle_and_bracket_blocks_are_split_the_same_way():
    visible, reasoning = thinking.split_inline_thinking(
        "<think>calcul</think>\n\nréponse"
    )
    assert (visible, reasoning) == ("réponse", "calcul")

    visible, reasoning = thinking.split_inline_thinking(
        "[think]calcul[/think]\n\nréponse"
    )
    assert (visible, reasoning) == ("réponse", "calcul")


def test_an_unclosed_final_block_is_treated_as_reasoning():
    """Local runtimes cut the trace off when the generation is truncated."""
    visible, reasoning = thinking.split_inline_thinking(
        "réponse\n\n<think>raisonnement interrompu"
    )

    assert visible == "réponse"
    assert reasoning == "raisonnement interrompu"


def test_masking_keeps_the_toggle_for_a_marker_without_text():
    masked, has_thinking = thinking.mask_thinking("<think></think>réponse")

    assert masked == "réponse"
    assert has_thinking is True


def test_text_without_markers_is_returned_untouched():
    assert thinking.mask_thinking("réponse simple") == ("réponse simple", False)
    assert thinking.split_inline_thinking("") == ("", "")


def test_the_client_and_the_window_share_one_parser():
    """Two parallel regex sets used to drift apart for the same format."""
    sample = "[think]interne[/think]\n\n\n\nvisible"

    assert OpenAIClient._split_inline_thinking(sample)[0] == "visible"
    assert BaseResponseWindow._mask_thinking(None, sample) == ("visible", True)
