"""Copy the license files of the third-party distributions shipped in a build.

Run inside the build environment, this script reads the installed
distributions with importlib.metadata only (no network, no pip). It walks the
runtime dependency closure of the requirement roots, adds the distributions
that own a file collected by PyInstaller, and copies every license file they
provide into one folder, together with an INDEX.txt summary.

A distribution without a license file never stops the build: it is listed in
the index with a warning and its project page, and THIRD_PARTY_NOTICES.md at
the repository root documents how it is licensed.

Command line, from the repository root:

    python tools/collect_third_party_licenses.py --output build/third_party_licenses \
        --requirements win32/requirements.txt --distribution pyinstaller

The PyInstaller specs call pyinstaller_datas() instead.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import os
import platform
import re
import shutil
import sys
import sysconfig
from pathlib import Path, PurePosixPath

INDEX_NAME = "INDEX.txt"
PYTHON_RUNTIME = "python"

_LICENSE_NAME = re.compile(
    r"^(licen[cs]e|copying|notice|copyright)([._-].*)?$", re.IGNORECASE
)
_TEXT_SUFFIXES = {
    "",
    ".txt",
    ".md",
    ".rst",
    ".text",
    ".markdown",
    ".lgpl",
    ".gpl",
    ".apache",
    ".apache2",
    ".mit",
    ".bsd",
    ".psf",
}
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _default_warn(message):
    print(f"WARNING: third-party licenses: {message}", file=sys.stderr)


def canonical_name(name):
    """PEP 503 normalized name, also used as the folder name of a distribution."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _marker_matches(marker_text):
    """Evaluate a PEP 508 marker for this interpreter, without any extra."""
    if not marker_text:
        return True
    try:
        from packaging.markers import Marker
    except ImportError:
        # Without packaging, only optional extras are skipped: shipping one
        # license file too many is harmless, one too few is not.
        return "extra" not in marker_text
    try:
        return Marker(marker_text).evaluate({"extra": ""})
    except Exception:
        return "extra" not in marker_text


def _requirement_name(text):
    """Return the distribution name of a requirement if it applies here."""
    requirement, _separator, marker_text = text.partition(";")
    if not _marker_matches(marker_text.strip()):
        return None
    match = _REQUIREMENT_NAME.match(requirement)
    return match.group(1) if match else None


def _local_project(path, warn):
    """Name and dependencies of a local project installed with ``-e PATH``."""
    pyproject = Path(path) / "pyproject.toml"
    try:
        import tomllib
    except ImportError:  # Python 3.10: the installed metadata is used alone.
        tomllib = None
    if tomllib is None or not pyproject.is_file():
        warn(f"{pyproject} could not be read, its installed metadata is used")
        return None, []
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get(
            "project", {}
        )
    except (OSError, ValueError) as error:
        warn(f"{pyproject} could not be read: {error}")
        return None, []
    return project.get("name"), list(project.get("dependencies", []))


def read_requirement_files(paths, warn=_default_warn):
    """Return (roots, first_party) from pip requirement files.

    ``-r`` includes are followed. A ``-e PATH`` line names a local project of
    this repository: its dependencies become roots and the project itself is
    first-party, so its own license is not copied as a third-party one.
    """
    roots, first_party, seen = [], set(), set()
    pending = [Path(path) for path in paths]
    while pending:
        path = pending.pop(0).resolve()
        if path in seen:
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            warn(f"{path} could not be read: {error}")
            continue
        for raw in lines:
            line = raw.split(" #", 1)[0].strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("-r ", "--requirement ")):
                pending.append(path.parent / line.split(None, 1)[1].strip())
                continue
            if line.startswith(("-e ", "--editable ")):
                project_dir = path.parent / line.split(None, 1)[1].strip()
                name, dependencies = _local_project(project_dir, warn)
                if name:
                    first_party.add(canonical_name(name))
                    roots.append(name)
                for dependency in dependencies:
                    dependency_name = _requirement_name(dependency)
                    if dependency_name:
                        roots.append(dependency_name)
                continue
            if line.startswith("-"):
                continue  # Other pip options (index URLs, hashes...).
            name = _requirement_name(line)
            if name:
                roots.append(name)
    return roots, first_party


def _installed_distributions():
    """Map canonical names to installed distributions, first on sys.path wins."""
    installed = {}
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            installed.setdefault(canonical_name(name), distribution)
    return installed


def dependency_closure(roots, installed, warn=_default_warn):
    """Canonical names of the roots and of their runtime dependencies."""
    closure, pending = set(), [canonical_name(root) for root in roots]
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        distribution = installed.get(name)
        if distribution is None:
            # A dependency for another platform, or one that is missing.
            continue
        closure.add(name)
        for requirement in distribution.requires or []:
            dependency_name = _requirement_name(requirement)
            if dependency_name:
                pending.append(canonical_name(dependency_name))
    for root in roots:
        if canonical_name(root) not in installed:
            warn(f"{root} is not installed in this environment")
    return closure


def _normalized(path):
    return os.path.normcase(os.path.abspath(str(path)))


def distributions_owning(paths, installed):
    """Canonical names of the distributions that recorded one of these files.

    PyInstaller reports the source path of each collected module, extension
    and data file; RECORD lists the files of each installed distribution.
    """
    wanted = {_normalized(path) for path in paths if path}
    if not wanted:
        return set()
    owners = set()
    for name, distribution in installed.items():
        for file in distribution.files or []:
            try:
                if _normalized(distribution.locate_file(file)) in wanted:
                    owners.add(name)
                    break
            except (OSError, ValueError):
                continue
    return owners


def _toc_sources(toc):
    """Source paths of PyInstaller TOC entries (dest_name, src_name, typecode)."""
    sources = []
    for entry in toc or []:
        try:
            source = entry[1]
        except (IndexError, TypeError):
            continue
        if isinstance(source, (str, os.PathLike)) and os.path.isabs(source):
            sources.append(source)
    return sources


def _is_license_file(file):
    parts = PurePosixPath(str(file).replace("\\", "/")).parts
    if not parts:
        return False
    in_metadata = parts[0].endswith((".dist-info", ".egg-info"))
    # PEP 639 keeps every license file under <name>.dist-info/licenses/.
    if in_metadata and len(parts) > 2 and parts[1] == "licenses":
        return True
    name = parts[-1]
    return bool(_LICENSE_NAME.match(name)) and Path(name).suffix.lower() in _TEXT_SUFFIXES


def _safe_relative_path(file):
    """Path inside the output folder, without the dist-info directory name.

    Directory components keep only letters, digits, "-" and "_": the folder is
    also collected into a macOS app bundle, where dotted directory names can
    be mistaken for nested bundles.
    """
    parts = list(PurePosixPath(str(file).replace("\\", "/")).parts)
    if parts and parts[0].endswith((".dist-info", ".egg-info")):
        parts = parts[1:]
    parts = [part for part in parts if part not in ("", ".", "..")]
    if not parts:
        return None
    directories = [re.sub(r"[^A-Za-z0-9_-]", "_", part) for part in parts[:-1]]
    file_name = re.sub(r"[^A-Za-z0-9._-]", "_", parts[-1])
    return PurePosixPath(*directories, file_name)


def _license_summary(distribution):
    fields = distribution.metadata
    expression = fields.get("License-Expression")
    if expression:
        return expression.strip()
    license_text = (fields.get("License") or "").strip()
    # Some distributions paste their whole license text in this field.
    if license_text and "\n" not in license_text and len(license_text) <= 80:
        return license_text
    classifiers = [
        classifier.split(" :: ")[-1]
        for classifier in fields.get_all("Classifier") or []
        if classifier.startswith("License :: ")
    ]
    return " / ".join(classifiers) or "non précisée dans les métadonnées"


def _homepage(distribution):
    fields = distribution.metadata
    if fields.get("Home-page"):
        return fields["Home-page"].strip()
    urls = []
    for entry in fields.get_all("Project-URL") or []:
        label, _separator, url = entry.partition(",")
        urls.append((label.strip().lower(), url.strip()))
    for wanted in ("homepage", "home", "source", "source code", "repository", "code"):
        for label, url in urls:
            if label == wanted and url:
                return url
    return urls[0][1] if urls else ""


def _copy_distribution_licenses(distribution, destination):
    """Copy the license files of one distribution, return their relative paths."""
    copied, seen = [], set()
    candidates = [file for file in distribution.files or [] if _is_license_file(file)]
    for file in candidates:
        relative = _safe_relative_path(file)
        if relative is None or str(relative).lower() in seen:
            continue
        source = Path(distribution.locate_file(file))
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # copyfile, not copy2: data files must not keep an executable bit.
        shutil.copyfile(source, target)
        seen.add(str(relative).lower())
        copied.append(relative)
    if not copied:
        # Without RECORD, License-File entries can still be read by name.
        for entry in distribution.metadata.get_all("License-File") or []:
            for candidate in (f"licenses/{entry}", entry):
                text = distribution.read_text(candidate)
                if text is None:
                    continue
                relative = _safe_relative_path(candidate)
                if relative is None:
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                copied.append(relative)
                break
    return copied


def _python_runtime_entry(output_dir, warn):
    """The interpreter and standard library bundled by PyInstaller."""
    destination = output_dir / PYTHON_RUNTIME
    # Windows installs it next to python.exe, POSIX builds in the stdlib.
    candidates = [
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    ]
    files = []
    for candidate in candidates:
        if candidate.is_file():
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, destination / "LICENSE.txt")
            files = [PurePosixPath("LICENSE.txt")]
            break
    if not files:
        warn("the Python LICENSE.txt was not found next to the interpreter")
    return {
        "name": "Python",
        "folder": PYTHON_RUNTIME,
        "version": platform.python_version(),
        "license": "PSF-2.0",
        "homepage": "https://www.python.org/",
        "files": files,
    }


def collect(
    output_dir,
    roots=(),
    requirement_files=(),
    distributions=(),
    toc=(),
    exclude=(),
    include_python=True,
    warn=_default_warn,
):
    """Write the license files and INDEX.txt into output_dir, return the entries.

    roots and requirement_files: requirements whose runtime closure is shipped.
    distributions: names shipped without their dependencies (e.g. the
    PyInstaller bootloader, whose build-time dependencies are not shipped).
    toc: PyInstaller TOC entries; the distributions owning them are added.
    exclude: first-party distributions, never listed.
    """
    output_dir = Path(output_dir)
    if output_dir.exists():
        # Only a folder this script wrote (it starts with the index) is wiped.
        if any(output_dir.iterdir()) and not (output_dir / INDEX_NAME).is_file():
            raise RuntimeError(f"{output_dir} is not empty and has no {INDEX_NAME}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    write_index(output_dir, [])

    file_roots, first_party = read_requirement_files(requirement_files, warn)
    excluded = first_party | {canonical_name(name) for name in exclude}
    installed = _installed_distributions()
    names = dependency_closure(list(roots) + file_roots, installed, warn)
    for name in distributions:
        if canonical_name(name) in installed:
            names.add(canonical_name(name))
        else:
            warn(f"{name} is not installed in this environment")
    names |= distributions_owning(_toc_sources(toc), installed)

    entries = []
    if include_python:
        entries.append(_python_runtime_entry(output_dir, warn))
    for name in sorted(names - excluded):
        distribution = installed[name]
        try:
            files = _copy_distribution_licenses(distribution, output_dir / name)
        except OSError as error:
            warn(f"{name}: license files could not be copied: {error}")
            files = []
        if not files:
            warn(f"{name} {distribution.version} ships no license file")
        entries.append({
            "name": distribution.metadata["Name"],
            "folder": name,
            "version": distribution.version,
            "license": _license_summary(distribution),
            "homepage": _homepage(distribution),
            "files": files,
        })
    write_index(output_dir, entries)
    return entries


def write_index(output_dir, entries):
    lines = [
        "Licences des composants tiers inclus dans SuperMenu",
        "===================================================",
        "",
        "Ce dossier est généré à chaque build. Pour chaque paquet Python tiers",
        "inclus dans l'application, il contient les fichiers de licence fournis",
        "par sa distribution. Les bibliothèques natives livrées dans ces paquets",
        "ou trouvées pendant le build (Qt, FFmpeg, OpenSSL, runtime Microsoft…)",
        "n'y sont pas détaillées : THIRD_PARTY_NOTICES.md les décrit et explique",
        "comment remplacer les bibliothèques LGPL ; le dossier licenses/ contient",
        "les textes complets des licences qu'il cite.",
        "",
    ]
    for entry in entries:
        lines.append(f"Composant : {entry['name']} {entry['version']}")
        lines.append(f"Licence   : {entry['license']}")
        if entry["homepage"]:
            lines.append(f"Site      : {entry['homepage']}")
        if entry["files"]:
            paths = [f"{entry['folder']}/{file}" for file in entry["files"]]
            lines.append(f"Fichiers  : {paths[0]}")
            lines.extend(f"            {path}" for path in paths[1:])
        else:
            lines.append(
                "Fichiers  : aucun fichier de licence dans la distribution ;"
                " voir THIRD_PARTY_NOTICES.md et le site du projet."
            )
        lines.append("")
    (Path(output_dir) / INDEX_NAME).write_text("\n".join(lines), encoding="utf-8")


def pyinstaller_datas(output_dir, requirement_files=(), toc=(), distributions=("pyinstaller",),
                      warn=_default_warn):
    """Collect the licenses and return them as PyInstaller DATA TOC entries.

    The entries are placed under a folder named like output_dir. Any failure
    is reported as a warning and yields no entry: the build goes on with
    LICENSE and THIRD_PARTY_NOTICES.md, which the spec collects directly.
    """
    output_dir = Path(output_dir)
    try:
        collect(
            output_dir,
            requirement_files=requirement_files,
            distributions=distributions,
            toc=toc,
            warn=warn,
        )
        return [
            (
                str(PurePosixPath(output_dir.name, path.relative_to(output_dir).as_posix())),
                str(path),
                "DATA",
            )
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        ]
    except Exception as error:  # noqa: BLE001 - never fail the build here.
        warn(f"collection failed, the bundle ships without them: {error!r}")
        return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", required=True, help="folder to (re)create")
    parser.add_argument(
        "--requirements", action="append", default=[],
        help="pip requirements file whose runtime closure is shipped",
    )
    parser.add_argument(
        "--root", action="append", default=[],
        help="distribution shipped with its runtime dependencies",
    )
    parser.add_argument(
        "--distribution", action="append", default=[],
        help="distribution shipped without its dependencies",
    )
    parser.add_argument(
        "--exclude", action="append", default=[],
        help="first-party distribution to leave out",
    )
    arguments = parser.parse_args(argv)
    warnings = []

    def warn(message):
        warnings.append(message)
        _default_warn(message)

    entries = collect(
        arguments.output,
        roots=arguments.root,
        requirement_files=arguments.requirements,
        distributions=arguments.distribution,
        exclude=arguments.exclude,
        warn=warn,
    )
    print(f"{len(entries)} composants, {len(warnings)} avertissements : {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
