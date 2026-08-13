import ast
import importlib
import pkgutil
from pathlib import Path

import supermenu_core

CORE_ROOT = Path(supermenu_core.__file__).resolve().parent
FORBIDDEN_IMPORT_ROOTS = {
    "AppKit",
    "Quartz",
    "macos",
    "objc",
    "src",
    "win32",
    "win32api",
    "win32clipboard",
    "win32con",
    "win32gui",
    "win32process",
}


def test_every_shared_module_imports_without_a_platform_package():
    modules = [
        module.name
        for module in pkgutil.walk_packages(
            supermenu_core.__path__,
            prefix="supermenu_core.",
        )
    ]

    for module_name in modules:
        importlib.import_module(module_name)


def test_shared_core_has_no_platform_imports():
    violations = []
    for source_path in CORE_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module.split(".", 1)[0]]
            else:
                continue
            forbidden = FORBIDDEN_IMPORT_ROOTS.intersection(imported)
            if forbidden:
                violations.append((source_path.name, sorted(forbidden)))

    assert violations == []
