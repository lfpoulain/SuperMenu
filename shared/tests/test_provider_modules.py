"""The provider modules stay helpers of OpenAIClient, on its pooled session."""

import ast
from pathlib import Path

import supermenu_core.api.providers as providers

PROVIDERS_ROOT = Path(providers.__file__).resolve().parent


def _trees():
    paths = sorted(PROVIDERS_ROOT.glob("*.py"))
    assert {path.stem for path in paths} >= {
        "catalog",
        "common",
        "lmstudio",
        "ollama",
        "openai_compatible",
    }
    for path in paths:
        yield path.name, ast.parse(path.read_text(encoding="utf-8"))


def _imported_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""
            yield from (alias.name for alias in node.names)


def test_providers_never_import_the_client():
    # openai_client imports the providers: the reverse would be a cycle.
    for name, tree in _trees():
        assert [
            imported for imported in _imported_names(tree) if "openai_client" in imported
        ] == [], name


def test_providers_never_open_their_own_session():
    # Every request goes through openai_client._SESSION, which keeps one
    # connection pool and is the object tests patch.
    for name, tree in _trees():
        assert "Session" not in set(_imported_names(tree)), name
        assert not [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "Session"
        ], name
