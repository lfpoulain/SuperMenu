import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = REPOSITORY_ROOT / "tools" / "collect_third_party_licenses.py"


def _load_collector():
    # The PyInstaller specs load the tool the same way: tools/ is no package.
    spec = importlib.util.spec_from_file_location("collector_under_test", COLLECTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = _load_collector()


def _fake_distribution(site, name, version, files=None, requires=(), license_expression=None):
    """Write an installed distribution that importlib.metadata can discover."""
    dist_info = site / f"{name}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    headers = ["Metadata-Version: 2.4", f"Name: {name}", f"Version: {version}"]
    if license_expression:
        headers.append(f"License-Expression: {license_expression}")
    headers.append(f"Project-URL: Homepage, https://example.invalid/{name}")
    headers.extend(f"Requires-Dist: {requirement}" for requirement in requires)
    (dist_info / "METADATA").write_text("\n".join(headers) + "\n", encoding="utf-8")
    record = [f"{dist_info.name}/METADATA,,", f"{dist_info.name}/RECORD,,"]
    for relative, content in (files or {}).items():
        path = site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        record.append(f"{relative},,")
    (dist_info / "RECORD").write_text("\n".join(record) + "\n", encoding="utf-8")


@pytest.fixture
def site(tmp_path, monkeypatch):
    site = tmp_path / "site-packages"
    site.mkdir()
    monkeypatch.syspath_prepend(str(site))
    return site


def test_license_starts_with_the_polyform_required_notice():
    text = (REPOSITORY_ROOT / "LICENSE").read_text(encoding="utf-8")
    first_line = text.splitlines()[0]

    # PolyForm requires every recipient to get the "Required Notice:" lines.
    assert first_line.startswith("Required Notice: Copyright (c) ")
    assert first_line.endswith(" LFPoulain (https://github.com/lfpoulain/SuperMenu)")
    assert "# PolyForm Noncommercial License 1.0.0" in text
    assert "https://polyformproject.org/licenses/noncommercial/1.0.0" in text


def test_full_license_texts_and_notices_are_in_the_repository():
    licenses = REPOSITORY_ROOT / "licenses"
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in (licenses / "LGPL-3.0.txt").read_text(
        encoding="utf-8"
    )
    assert "GNU GENERAL PUBLIC LICENSE" in (licenses / "GPL-3.0.txt").read_text(
        encoding="utf-8"
    )
    assert "Apache License" in (licenses / "Apache-2.0.txt").read_text(encoding="utf-8")

    notices = (REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for component in ("PySide6", "pynput", "PyInstaller", "Inno Setup", "Foundry Local"):
        assert component in notices


def test_collect_follows_runtime_dependencies_and_copies_license_files(site, tmp_path):
    _fake_distribution(
        site, "fake_root", "1.0",
        files={
            "fake_root-1.0.dist-info/licenses/LICENSE": "root license",
            "fake_root-1.0.dist-info/licenses/NOTICE": "root notice",
        },
        requires=(
            "fake-dep>=1",
            "fake-extra; extra == 'docs'",
            "fake-other-os; sys_platform == 'no-such-platform'",
        ),
        license_expression="MIT",
    )
    _fake_distribution(
        site, "fake_dep", "2.0",
        files={
            "fake_dep-2.0.dist-info/LICENSE.txt": "dep license",
            "fake_dep/__init__.py": "",
            "fake_dep/vendored/COPYING": "vendored license",
            "fake_dep/license.py": "not a license file",
        },
    )
    for skipped in ("fake_extra", "fake_other_os"):
        _fake_distribution(site, skipped, "1.0", files={f"{skipped}-1.0.dist-info/LICENSE": "x"})
    output = tmp_path / "out"
    warnings = []

    entries = collector.collect(
        output, roots=["fake-root"], include_python=False, warn=warnings.append
    )

    assert [entry["folder"] for entry in entries] == ["fake-dep", "fake-root"]
    root_license = output / "fake-root" / "licenses" / "LICENSE"
    assert root_license.read_text(encoding="utf-8") == "root license"
    assert (output / "fake-root" / "licenses" / "NOTICE").is_file()
    assert (output / "fake-dep" / "LICENSE.txt").read_text(encoding="utf-8") == "dep license"
    assert (output / "fake-dep" / "fake_dep" / "vendored" / "COPYING").is_file()
    assert not (output / "fake-dep" / "fake_dep" / "license.py").exists()
    index = (output / collector.INDEX_NAME).read_text(encoding="utf-8")
    assert "Composant : fake_root 1.0" in index
    assert "Licence   : MIT" in index
    assert "https://example.invalid/fake_root" in index
    assert warnings == []


def test_a_distribution_without_license_file_only_warns(site, tmp_path):
    _fake_distribution(site, "fake_bare", "3.0", files={"fake_bare/__init__.py": ""})
    output = tmp_path / "out"
    warnings = []

    entries = collector.collect(
        output, roots=["fake-bare", "fake-missing"], include_python=False, warn=warnings.append
    )

    assert [entry["files"] for entry in entries] == [[]]
    assert any("fake-bare 3.0 ships no license file" in message for message in warnings)
    assert any("fake-missing is not installed" in message for message in warnings)
    index = (output / collector.INDEX_NAME).read_text(encoding="utf-8")
    assert "aucun fichier de licence dans la distribution" in index


def test_collect_adds_the_owners_of_bundled_files(site, tmp_path):
    _fake_distribution(
        site, "fake_bundled", "1.0",
        files={
            "fake_bundled/__init__.py": "",
            "fake_bundled-1.0.dist-info/LICENSE": "bundled license",
        },
    )
    _fake_distribution(site, "fake_unused", "1.0", files={"fake_unused-1.0.dist-info/LICENSE": "x"})
    toc = [
        ("fake_bundled", str(site / "fake_bundled" / "__init__.py"), "PYMODULE"),
        ("os", os.__file__, "PYMODULE"),
        ("python3.dll", "relative/ignored.dll", "BINARY"),
    ]

    entries = collector.collect(tmp_path / "out", toc=toc, include_python=False, warn=print)

    assert [entry["folder"] for entry in entries] == ["fake-bundled"]


def test_requirement_files_follow_editable_projects_and_skip_first_party(site, tmp_path):
    project = tmp_path / "shared"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "fake-first-party"\n'
        'dependencies = ["fake-lib>=1", "fake-new; python_version >= \'9.0\'"]\n',
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# comment\n-e shared\n\nfake-pinned==1.0  # inline comment\n"
        "fake-other-os==1.0; sys_platform == 'no-such-platform'\n",
        encoding="utf-8",
    )
    _fake_distribution(site, "fake_lib", "1.0", files={"fake_lib-1.0.dist-info/LICENSE": "lib"})
    _fake_distribution(site, "fake_pinned", "1.0", files={"fake_pinned-1.0.dist-info/LICENSE": "p"})
    _fake_distribution(site, "fake_first_party", "0.1", requires=("fake-lib",))

    roots, first_party = collector.read_requirement_files([requirements])
    entries = collector.collect(
        tmp_path / "out", requirement_files=[requirements], include_python=False, warn=print
    )

    assert roots == ["fake-first-party", "fake-lib", "fake-pinned"]
    assert first_party == {"fake-first-party"}
    assert [entry["folder"] for entry in entries] == ["fake-lib", "fake-pinned"]


def test_pyinstaller_datas_never_fails_the_build(site, tmp_path):
    _fake_distribution(site, "fake_root", "1.0", files={"fake_root-1.0.dist-info/LICENSE": "x"})
    _fake_distribution(site, "fake_bare", "1.0")
    output = tmp_path / "work" / "third_party_licenses"
    warnings = []

    datas = collector.pyinstaller_datas(
        output, distributions=("fake-root", "fake-bare"), warn=warnings.append
    )

    destinations = {Path(dest).as_posix() for dest, _source, _typecode in datas}
    assert "third_party_licenses/fake-root/LICENSE" in destinations
    assert f"third_party_licenses/{collector.INDEX_NAME}" in destinations
    assert all(typecode == "DATA" and Path(source).is_file() for _dest, source, typecode in datas)
    assert any("fake-bare" in message for message in warnings)

    # An unexpected folder is never wiped: the bundle simply goes without it.
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("keep", encoding="utf-8")
    warnings.clear()
    assert collector.pyinstaller_datas(foreign, warn=warnings.append) == []
    assert (foreign / "keep.txt").is_file()
    assert warnings


def test_collect_includes_the_python_runtime_license(site, tmp_path):
    warnings = []

    entries = collector.collect(tmp_path / "out", warn=warnings.append)

    python = entries[0]
    assert python["name"] == "Python"
    assert python["license"] == "PSF-2.0"
    # Every supported interpreter installs it; a warning would still be fine.
    if python["files"]:
        assert (tmp_path / "out" / "python" / "LICENSE.txt").is_file()
    else:
        assert any("Python LICENSE.txt" in message for message in warnings)


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_about_page_shows_the_license_and_links(monkeypatch):
    from PySide6.QtWidgets import QLabel

    from supermenu_core.ui import about_page

    _app()
    monkeypatch.delattr(sys, "frozen", raising=False)
    page = about_page.AboutPage("1.2.3", lambda: None)
    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "Licence : PolyForm Noncommercial 1.0.0" in texts
    links = page.license_links.text()
    assert 'href="https://github.com/lfpoulain/SuperMenu/blob/main/LICENSE"' in links
    assert (
        'href="https://github.com/lfpoulain/SuperMenu/blob/main/THIRD_PARTY_NOTICES.md"'
        in links
    )
    assert "copie locale" not in links
    assert page.license_links.openExternalLinks()


def test_about_page_links_the_bundled_notices_when_packaged(monkeypatch, tmp_path):
    from supermenu_core.ui import about_page

    _app()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert about_page.bundled_notices_path() is None

    notices = tmp_path / "THIRD_PARTY_NOTICES.md"
    notices.write_text("# Notices", encoding="utf-8")
    assert about_page.bundled_notices_path() == str(notices)
    page = about_page.AboutPage("1.2.3", lambda: None)
    links = page.license_links.text()

    assert "copie locale" in links
    assert 'href="file:///' in links
    assert "THIRD_PARTY_NOTICES.md" in links
