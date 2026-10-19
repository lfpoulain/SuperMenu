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

# An unclosed block only counts when its tag opens a line: a literal "<think>"
# quoted in the middle of an answer must not swallow the rest of the text.
_UNCLOSED_RE = re.compile(r"^[ \t]*<think\b[^>]*>", re.IGNORECASE | re.MULTILINE)
_UNCLOSED_BRACKET_RE = re.compile(r"^[ \t]*\[think\]", re.IGNORECASE | re.MULTILINE)
# Likewise an orphan closing tag only ends the reasoning when it opens or ends
# its line, as templates emit it ("...\n</think>\n\n"): a "</think>" quoted in
# a sentence or in code stays text instead of hiding everything before it.
_CLOSE_RE = re.compile(
    r"^[ \t]*</think\b[^>]*>|</think\b[^>]*>(?=[ \t]*(?:\r?\n|$))",
    re.IGNORECASE | re.MULTILINE,
)
_CLOSE_BRACKET_RE = re.compile(
    r"^[ \t]*\[/think\]|\[/think\](?=[ \t]*(?:\r?\n|$))",
    re.IGNORECASE | re.MULTILINE,
)


def _split_at_last(pattern, visible, reasoning_parts):
    """Treat everything before the last orphan closing tag as reasoning."""
    closings = list(pattern.finditer(visible))
    if not closings:
        return visible
    last = closings[-1]
    head = visible[: last.start()]
    head = BRACKET_THINK_TAG_RE.sub("", THINK_TAG_RE.sub("", head)).strip()
    if head:
        reasoning_parts.append(head)
    return visible[last.end():]


def _split_unclosed(pattern, visible, reasoning_parts):
    unclosed = pattern.search(visible)
    if not unclosed:
        return visible
    tail = visible[unclosed.end():].strip()
    if tail:
        reasoning_parts.append(tail)
    return visible[: unclosed.start()]


def split_inline_thinking(text):
    """Return ``(visible, reasoning)``, including an unclosed final block.

    A closing tag without its opening one is also handled: templates that put
    ``<think>`` in the prompt (Qwen3-Thinking, DeepSeek-R1 distills) only emit
    the closing tag, so everything before it is the reasoning trace.
    """
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

    visible = _split_at_last(_CLOSE_RE, visible, reasoning_parts)
    visible = _split_at_last(_CLOSE_BRACKET_RE, visible, reasoning_parts)
    visible = _split_unclosed(_UNCLOSED_RE, visible, reasoning_parts)
    visible = _split_unclosed(_UNCLOSED_BRACKET_RE, visible, reasoning_parts)

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
    visible, reasoning = split_inline_thinking(text)
    if not reasoning and visible == text.strip():
        # Only quoted tags: nothing is hidden, so no reasoning toggle either.
        return text, False
    return re.sub(r"\n{3,}", "\n\n", visible).strip(), True
