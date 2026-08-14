"""Split a model answer into its visible part and its reasoning trace.

Providers expose reasoning inconsistently: OpenAI-compatible servers use a
separate field, while local runtimes routinely inline ``<think>`` or ``[think]``
blocks in the content, sometimes leaving the final block unclosed when the
generation is cut short.

This lived in two places -- the API client stripped the blocks and the response
window masked them again with its own parallel regexes. One format, one parser.
"""

import re


THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>(.*?)</think>", re.IGNORECASE | re.DOTALL)
THINK_TAG_RE = re.compile(r"</?think\b[^>]*>", re.IGNORECASE)
BRACKET_THINK_BLOCK_RE = re.compile(r"\[think\](.*?)\[/think\]", re.IGNORECASE | re.DOTALL)
BRACKET_THINK_TAG_RE = re.compile(r"\[/?think\]", re.IGNORECASE)

_UNCLOSED_RE = re.compile(r"<think\b[^>]*>", re.IGNORECASE)
_UNCLOSED_BRACKET_RE = re.compile(r"\[think\]", re.IGNORECASE)


def split_inline_thinking(text):
    """Return ``(visible, reasoning)``, including an unclosed final block."""
    if not isinstance(text, str) or not text:
        return "", ""

    reasoning_parts = [
        match.group(1).strip()
        for match in THINK_BLOCK_RE.finditer(text)
        if match.group(1).strip()
    ]
    reasoning_parts.extend(
        match.group(1).strip()
        for match in BRACKET_THINK_BLOCK_RE.finditer(text)
        if match.group(1).strip()
    )

    visible = THINK_BLOCK_RE.sub("", text)
    visible = BRACKET_THINK_BLOCK_RE.sub("", visible)

    unclosed = _UNCLOSED_RE.search(visible)
    if unclosed:
        tail = visible[unclosed.end():].strip()
        if tail:
            reasoning_parts.append(tail)
        visible = visible[: unclosed.start()]

    unclosed_bracket = _UNCLOSED_BRACKET_RE.search(visible)
    if unclosed_bracket:
        tail = visible[unclosed_bracket.end():].strip()
        if tail:
            reasoning_parts.append(tail)
        visible = visible[: unclosed_bracket.start()]

    visible = THINK_TAG_RE.sub("", visible)
    visible = BRACKET_THINK_TAG_RE.sub("", visible)
    return visible.strip(), "\n\n".join(reasoning_parts).strip()


def contains_thinking(text):
    """Whether the text carries any reasoning marker, even an empty block."""
    if not isinstance(text, str) or not text:
        return False
    return bool(
        THINK_TAG_RE.search(text)
        or BRACKET_THINK_TAG_RE.search(text)
    )


def mask_thinking(text):
    """Return ``(visible, has_thinking)`` for display.

    ``has_thinking`` stays true for a marker that carries no text, so the
    "show reasoning" toggle keeps matching what the provider actually sent.
    """
    if not isinstance(text, str) or not text:
        return text, False
    if not contains_thinking(text):
        return text, False
    visible, _reasoning = split_inline_thinking(text)
    return re.sub(r"\n{3,}", "\n\n", visible).strip(), True
