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


def test_an_orphan_closing_tag_ends_the_reasoning():
    """Templates that inject <think> in the prompt only emit the closing tag."""
    visible, reasoning = thinking.split_inline_thinking(
        "L'utilisateur veut une correction…\n</think>\n\nBonjour…"
    )

    assert visible == "Bonjour…"
    assert reasoning == "L'utilisateur veut une correction…"
    assert thinking.mask_thinking("calcul[/think]\n\nréponse") == ("réponse", True)


def test_a_literal_tag_inside_a_sentence_does_not_swallow_the_answer():
    text = "Voici le code HTML : <think> est une balise"

    assert thinking.split_inline_thinking(text) == (text, "")


def test_a_closing_tag_quoted_in_a_line_stays_in_the_answer():
    """Templates emit the orphan tag on its own line; a quoted one is text."""
    for text in (
        "Dans Qwen3, la balise </think> ferme le raisonnement ; le texte qui suit est la réponse.",
        'THINK_CLOSE = re.compile(r"</think>")  # ferme le bloc\nprint("ok")',
        "Le format [/think] ferme le bloc entre crochets.",
    ):
        assert thinking.split_inline_thinking(text) == (text, "")
        # Nothing is hidden, so the window offers no reasoning toggle.
        assert thinking.mask_thinking(text) == (text, False)


def test_an_orphan_closing_tag_that_opens_its_line_still_ends_the_reasoning():
    visible, reasoning = thinking.split_inline_thinking(
        "L'utilisateur veut une correction…\n</think>Bonjour…"
    )

    assert visible == "Bonjour…"
    assert reasoning == "L'utilisateur veut une correction…"


def test_blocks_then_an_orphan_closing_tag_keep_every_trace():
    visible, reasoning = thinking.split_inline_thinking(
        "<think>a</think>b</think>\n\nréponse"
    )

    assert visible == "réponse"
    assert reasoning == "a\n\nb"
