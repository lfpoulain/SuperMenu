import ast
import importlib
import pkgutil
import sys
from pathlib import Path

import supermenu_core

CORE_ROOT = Path(supermenu_core.__file__).resolve().parent
FORBIDDEN_IMPORT_ROOTS = {
    # macOS (pyobjc frameworks and the macOS application)
    "AVFoundation",
    "AppKit",
    "ApplicationServices",
    "Cocoa",
    "CoreFoundation",
    "Foundation",
    "HIServices",
    "Quartz",
    "macos",
    "objc",
    "PyObjCTools",
    # Windows (pywin32, COM, Foundry Local and the Windows application)
    "foundry_local",
    "msvcrt",
    "pythoncom",
    "pywintypes",
    "src",
    "win32",
    "win32api",
    "win32clipboard",
    "win32com",
    "win32con",
    "win32event",
    "win32gui",
    "win32process",
    "winreg",
    "winsound",
    "_winapi",
}
# Everything the platform-neutral core may import besides the standard
# library: a new third-party root must be a deliberate, reviewed choice.
ALLOWED_THIRD_PARTY_ROOTS = {
    "PySide6",
    "qdarktheme",
    "requests",
    "supermenu_core",
    "websocket",
}
# Standard-library modules that only exist on one platform.
PLATFORM_ONLY_STDLIB = {
    "_winapi",
    "fcntl",
    "grp",
    "msvcrt",
    "nt",
    "posix",
    "pwd",
    "pty",
    "resource",
    "termios",
    "tty",
    "winreg",
    "winsound",
}


def _imported_roots(tree):
    """Yield (root, lineno) for static and literal dynamic absolute imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".", 1)[0], node.lineno
        elif isinstance(node, ast.ImportFrom):
            # Relative imports stay inside supermenu_core.
            if node.level == 0 and node.module:
                yield node.module.split(".", 1)[0], node.lineno
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            first = node.args[0]
            if (
                name in {"import_module", "__import__"}
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and not first.value.startswith(".")
            ):
                yield first.value.split(".", 1)[0], node.lineno


def _core_imports():
    for source_path in sorted(CORE_ROOT.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        relative = source_path.relative_to(CORE_ROOT).as_posix()
        for root, lineno in _imported_roots(tree):
            yield relative, lineno, root


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
    violations = [
        (path, lineno, root)
        for path, lineno, root in _core_imports()
        if root in FORBIDDEN_IMPORT_ROOTS
    ]

    assert violations == []


def test_shared_core_only_imports_portable_modules():
    """pywin32 is installed on Windows CI, so importing alone proves nothing."""
    portable_stdlib = set(sys.stdlib_module_names) - PLATFORM_ONLY_STDLIB
    violations = [
        (path, lineno, root)
        for path, lineno, root in _core_imports()
        if root not in portable_stdlib and root not in ALLOWED_THIRD_PARTY_ROOTS
    ]

    assert violations == []


def test_the_guard_detects_platform_imports_in_every_form():
    sample = ast.parse(
        "import winreg\n"
        "from Foundation import NSObject\n"
        "def lazy():\n"
        "    import pythoncom\n"
        "    importlib.import_module('AppKit')\n"
        "    __import__('win32api')\n"
        "from . import sibling\n"
    )

    roots = {root for root, _lineno in _imported_roots(sample)}

    assert {"winreg", "Foundation", "pythoncom", "AppKit", "win32api"} <= roots
    assert roots <= FORBIDDEN_IMPORT_ROOTS
