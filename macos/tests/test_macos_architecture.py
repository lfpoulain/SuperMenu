from pathlib import Path


MACOS_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MACOS_ROOT / "src"
SHARED_ROOT = MACOS_ROOT.parent / "shared" / "supermenu_core"


def test_macos_keeps_the_platform_composition_shape():
    assert {path.name for path in SOURCE_ROOT.iterdir() if path.is_dir()} >= {
        "api",
        "config",
        "ui",
        "utils",
    }
    assert (SOURCE_ROOT / "main.py").is_file()
    assert (SOURCE_ROOT / "ui" / "main_window.py").is_file()
    assert (SOURCE_ROOT / "utils" / "context_menu.py").is_file()
    assert (SOURCE_ROOT / "utils" / "hotkey_manager.py").is_file()


def test_cross_platform_modules_have_one_shared_source():
    assert (SHARED_ROOT / "api" / "openai_client.py").is_file()
    assert (SHARED_ROOT / "config" / "openai_models.py").is_file()
    assert (SHARED_ROOT / "ui" / "response_window.py").is_file()
    assert not (SOURCE_ROOT / "api" / "model_capabilities.py").exists()
    assert not (SOURCE_ROOT / "config" / "openai_models.py").exists()
    assert not (SOURCE_ROOT / "ui" / "theme_manager.py").exists()


def test_macos_uses_shared_audio_without_windows_or_screen_capture():
    assert (SOURCE_ROOT / "audio" / "speech_backend.py").is_file()
    assert (SHARED_ROOT / "audio" / "microphone.py").is_file()
    assert not (SOURCE_ROOT / "ui" / "screen_capture.py").exists()

    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in SOURCE_ROOT.rglob("*.py")
    )
    forbidden = (
        "screen_capture",
        "screenshot",
        "pyaudio",
        "win32gui",
        "win32con",
        "pywin32",
        "from win32",
        "import win32",
    )
    for term in forbidden:
        assert term not in source


def test_macos_does_not_import_the_windows_subproject():
    for path in SOURCE_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "win32." not in source
        assert "../win32" not in source
        assert "..\\win32" not in source
