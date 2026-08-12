from pathlib import Path


MACOS_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MACOS_ROOT / "src"


def test_macos_keeps_the_windows_business_layer_shape():
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


def test_macos_has_no_audio_or_capture_subsystem():
    assert not (SOURCE_ROOT / "audio").exists()
    assert not (SOURCE_ROOT / "ui" / "screen_capture.py").exists()

    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in SOURCE_ROOT.rglob("*.py")
    )
    forbidden = (
        "screen_capture",
        "screenshot",
        "transcription",
        "pyaudio",
        "ffmpeg",
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

