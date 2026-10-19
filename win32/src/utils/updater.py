import hashlib
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Version, channel, manifest and release-notes rules are shared with macOS.
from supermenu_core.utils.updates import (
    MANIFEST_SCHEMA_VERSION as _MANIFEST_SCHEMA_VERSION,
    SHA256_PATTERN as _SHA256_PATTERN,
    UPDATE_CHANNEL_BETA,
    VERSION_PATTERN as _VERSION_PATTERN,
    WINDOWS_VERSION_LINE as _WINDOWS_VERSION_LINE,
    declared_sha256,
    decode_release_manifest,
    normalize_update_channel,
    parse_version as _parse_version,
    release_manifest_url,
    request_release_manifest,
)
# Re-exported for the existing Windows callers.
from supermenu_core.utils.updates import (  # noqa: F401
    UPDATE_CHANNEL_STABLE,
    UPDATE_CHANNELS,
    is_newer_version,
)


# The rolling beta reuses its tag: each push to main replaces the installer
# at this same URL, possibly while the "Télécharger" question was open.
_ROLLING_BETA_ASSET_URL = re.compile(
    r"https://github\.com/([\w.-]+)/([\w.-]+)/releases/download/beta/([\w.-]+)",
    re.IGNORECASE,
)
_DOWNLOAD_FOLDER_PREFIX = "SuperMenu_update_"

# Same logger as src.utils.logger, without importing its file handlers here.
_LOGGER = logging.getLogger("SuperMenu")


class UpdateCheckError(RuntimeError):
    """User-facing update lookup failure."""


class UpdateIntegrityError(UpdateCheckError):
    """The downloaded installer does not match its published SHA-256."""


class UpdateSupersededError(UpdateIntegrityError):
    """A newer rolling beta replaced the installer during the update."""


def _build_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": "SuperMenu-Updater",
            "Accept": "application/vnd.github+json",
        }
    )

    return session


_SESSION = _build_session()


def installer_asset_name(channel: Optional[str]) -> str:
    if normalize_update_channel(channel) == UPDATE_CHANNEL_BETA:
        return "SuperMenu_Beta_Setup.exe"
    return "SuperMenu_Setup.exe"


def release_manifest_name(channel: Optional[str]) -> str:
    if normalize_update_channel(channel) == UPDATE_CHANNEL_BETA:
        return "update-beta.json"
    return "update-stable.json"


def get_installed_app_version(app_id_guid: str) -> Optional[str]:
    try:
        import winreg
    except Exception:
        return None

    uninstall_subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{{{app_id_guid}}}_is1"

    def _try_read(root, view_flag):
        try:
            with winreg.OpenKey(root, uninstall_subkey, 0, winreg.KEY_READ | view_flag) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, "DisplayVersion")
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                except FileNotFoundError:
                    return None
        except FileNotFoundError:
            return None
        except OSError:
            return None
        return None

    version = _try_read(winreg.HKEY_LOCAL_MACHINE, getattr(winreg, "KEY_WOW64_64KEY", 0))
    if version:
        return version

    version = _try_read(winreg.HKEY_LOCAL_MACHINE, getattr(winreg, "KEY_WOW64_32KEY", 0))
    if version:
        return version

    version = _try_read(winreg.HKEY_CURRENT_USER, getattr(winreg, "KEY_WOW64_64KEY", 0))
    if version:
        return version

    version = _try_read(winreg.HKEY_CURRENT_USER, getattr(winreg, "KEY_WOW64_32KEY", 0))
    if version:
        return version

    return None


def _raise_for_github_api_error(response, owner: str, repo: str) -> None:
    if (
        response.status_code == 403
        and response.headers.get("X-RateLimit-Remaining") == "0"
    ):
        reset_text = "dans quelques minutes"
        reset_value = response.headers.get("X-RateLimit-Reset")
        try:
            reset_time = datetime.fromtimestamp(
                int(reset_value),
                tz=timezone.utc,
            ).astimezone()
            reset_text = f"à {reset_time:%H:%M}"
        except (TypeError, ValueError, OSError):
            pass

        raise UpdateCheckError(
            "La limite temporaire de GitHub est atteinte. "
            f"Réessayez {reset_text} ou téléchargez la mise à jour depuis "
            f"https://github.com/{owner}/{repo}/releases"
        )
    response.raise_for_status()


def get_github_release_by_tag(owner: str, repo: str, tag: str, timeout_s: int = 15) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    resp = _SESSION.get(url, timeout=(5, timeout_s))
    _raise_for_github_api_error(resp, owner, repo)
    return resp.json()


def get_latest_stable_release(owner: str, repo: str, timeout_s: int = 15) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    resp = _SESSION.get(url, timeout=(5, timeout_s))
    _raise_for_github_api_error(resp, owner, repo)
    return resp.json()


def _release_from_manifest(
    payload: dict,
    owner: str,
    repo: str,
    expected_channel: str,
) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Le manifeste de mise à jour n'est pas un objet JSON.")
    if payload.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ValueError("Version de manifeste de mise à jour incompatible.")

    channel = str(payload.get("channel") or "").strip().lower()
    if channel != expected_channel:
        raise ValueError("Le canal du manifeste de mise à jour est incorrect.")

    version = str(payload.get("version") or "").strip()
    if not _parse_version(version):
        raise ValueError("La version du manifeste de mise à jour est invalide.")

    prerelease = payload.get("prerelease")
    expected_prerelease = expected_channel == UPDATE_CHANNEL_BETA
    if not isinstance(prerelease, bool) or prerelease != expected_prerelease:
        raise ValueError("Le type de release du manifeste est incorrect.")

    tag = str(payload.get("tag") or "").strip()
    expected_tag = (
        UPDATE_CHANNEL_BETA
        if expected_prerelease
        else f"v{version}"
    )
    if tag != expected_tag:
        raise ValueError("Le tag du manifeste de mise à jour est incorrect.")

    asset_name = installer_asset_name(expected_channel)
    declared_asset = payload.get("asset")
    if declared_asset is not None and declared_asset != asset_name:
        raise ValueError("L'installateur déclaré dans le manifeste est incorrect.")

    # Manifests published before the fingerprint was added have no sha256;
    # a declared one must be valid, otherwise the manifest is rejected.
    sha256 = declared_sha256(
        payload,
        "L'empreinte SHA-256 du manifeste est invalide.",
    )

    release_base = f"https://github.com/{owner}/{repo}/releases"
    asset = {
        "name": asset_name,
        "browser_download_url": (
            f"{release_base}/download/{tag}/{asset_name}"
        ),
    }
    if sha256:
        # Same field and format as the GitHub API release assets.
        asset["digest"] = f"sha256:{sha256}"
    return {
        "name": f"SuperMenu {version}",
        "body": f"Channel: {expected_channel}\nVersion: {version}",
        "tag_name": tag,
        "prerelease": prerelease,
        "html_url": f"{release_base}/tag/{tag}",
        "assets": [asset],
    }


def get_release_from_manifest(
    owner: str,
    repo: str,
    channel: Optional[str],
    timeout_s: int = 15,
) -> Optional[dict]:
    normalized_channel = normalize_update_channel(channel)
    manifest_name = release_manifest_name(normalized_channel)
    url = release_manifest_url(
        f"https://github.com/{owner}/{repo}/releases",
        normalized_channel,
        manifest_name,
    )

    response = request_release_manifest(_SESSION.get, url, timeout_s)
    if response is None:
        return None
    payload = decode_release_manifest(
        response,
        "Le manifeste de mise à jour est illisible.",
    )
    return _release_from_manifest(
        payload,
        owner,
        repo,
        normalized_channel,
    )


def get_release_for_update_channel(
    owner: str,
    repo: str,
    channel: Optional[str],
    timeout_s: int = 15,
) -> dict:
    normalized_channel = normalize_update_channel(channel)
    try:
        manifest_release = get_release_from_manifest(
            owner,
            repo,
            normalized_channel,
            timeout_s=timeout_s,
        )
    except (requests.RequestException, ValueError):
        manifest_release = None
    if manifest_release is not None:
        return manifest_release

    if normalized_channel == UPDATE_CHANNEL_BETA:
        release = get_github_release_by_tag(
            owner,
            repo,
            UPDATE_CHANNEL_BETA,
            timeout_s=timeout_s,
        )
        if not release.get("prerelease"):
            raise ValueError("La release beta n'est pas marquée comme préversion.")
        return release

    release = get_latest_stable_release(owner, repo, timeout_s=timeout_s)
    if release.get("prerelease"):
        raise ValueError("La dernière release stable est une préversion.")
    return release


def extract_version_from_release(release: dict) -> Optional[str]:
    body = release.get("body") or ""
    # Shared releases list both platforms; the metadata lines are appended
    # after the human notes, so the last Windows line wins.
    windows_versions = _WINDOWS_VERSION_LINE.findall(body)
    if windows_versions:
        return windows_versions[-1]

    m = re.search(
        rf"Version:\s*{_VERSION_PATTERN.pattern}",
        body,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    name = release.get("name") or ""
    m = _VERSION_PATTERN.search(name)
    if m:
        return m.group(1)

    tag_name = release.get("tag_name") or ""
    m = _VERSION_PATTERN.fullmatch(tag_name)
    if m:
        return m.group(1)

    return None


def find_asset_download_url(release: dict, asset_name: str) -> Optional[str]:
    assets = release.get("assets") or []
    for a in assets:
        if (a.get("name") or "").lower() == asset_name.lower():
            return a.get("browser_download_url")
    return None


def _normalize_sha256(value) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized[len("sha256:"):]
    if _SHA256_PATTERN.fullmatch(normalized):
        return normalized
    return None


def find_asset_sha256(release: dict, asset_name: str) -> Optional[str]:
    """Return the published SHA-256 of an asset, or None if unknown.

    Manifests and the GitHub API both expose it as "digest": "sha256:<hex>".
    """
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == asset_name.lower():
            return _normalize_sha256(asset.get("digest"))
    return None


def _download_and_hash(url: str, dest_path: str, timeout_s: int) -> str:
    digest = hashlib.sha256()
    with _SESSION.get(url, stream=True, timeout=(10, timeout_s)) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
                    digest.update(chunk)
    return digest.hexdigest()


def download_to_file(url: str, dest_path: str, timeout_s: int = 60) -> None:
    _download_and_hash(url, dest_path, timeout_s)


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discard_downloaded_installer(path: str) -> None:
    """Delete a refused installer, only inside one of our private folders."""
    folder = os.path.dirname(os.path.abspath(path))
    temp_dir = os.path.abspath(tempfile.gettempdir())
    if os.path.basename(folder).startswith(_DOWNLOAD_FOLDER_PREFIX) and (
        os.path.normcase(os.path.dirname(folder)) == os.path.normcase(temp_dir)
    ):
        shutil.rmtree(folder, ignore_errors=True)


def _remove_previous_downloads() -> None:
    """Delete the folders left by earlier downloads, best effort.

    Each download gets a new mkdtemp folder: an installer declined at
    "Lancer l'installation maintenant ?", refused at launch or already run
    would otherwise stay in %TEMP% (about 100 MB each). A file still in use,
    such as a running installer, cannot be deleted and is simply left.
    """
    try:
        with os.scandir(tempfile.gettempdir()) as entries:
            folders = [
                entry.path
                for entry in entries
                if entry.name.startswith(_DOWNLOAD_FOLDER_PREFIX)
                and not entry.is_symlink()
                and entry.is_dir(follow_symlinks=False)
            ]
    except OSError:
        return
    for folder in folders:
        # rmtree refuses a junction and never follows links inside the folder.
        shutil.rmtree(folder, ignore_errors=True)


def _rolling_beta_republished(url: str, expected_sha256: str) -> bool:
    """Whether the beta manifest now publishes another installer fingerprint.

    Read once and best effort: any failure keeps the strict integrity refusal.
    """
    match = _ROLLING_BETA_ASSET_URL.fullmatch(str(url or ""))
    if not match:
        return False
    owner, repo, asset_name = match.groups()
    try:
        release = get_release_from_manifest(owner, repo, UPDATE_CHANNEL_BETA)
        published = find_asset_sha256(release or {}, asset_name)
    except Exception:
        return False
    return bool(published) and published != expected_sha256


def verify_installer_sha256(path: str, expected_sha256: Optional[str]) -> None:
    """Check an installer again right before it is launched.

    Without a published fingerprint (older manifests) there is nothing to
    compare, and the download already logged a warning. A refused installer
    is deleted when it sits in a folder created by download_verified_installer.
    """
    if not expected_sha256:
        return
    expected = _normalize_sha256(expected_sha256)
    if expected is None or _file_sha256(path) != expected:
        _discard_downloaded_installer(path)
        raise UpdateIntegrityError(
            "L'installateur ne correspond plus à l'empreinte publiée. "
            "Il ne sera pas lancé."
        )


def download_verified_installer(
    url: str,
    file_name: str,
    expected_sha256: Optional[str],
    timeout_s: int = 60,
) -> str:
    """Download an installer into a private temporary folder and verify it.

    The folder comes from tempfile.mkdtemp, so the path is not predictable;
    the folders of earlier downloads are deleted first. The installer is
    returned only once its SHA-256 matches the published one; on mismatch,
    the folder is deleted and UpdateIntegrityError raised, or its subclass
    UpdateSupersededError when a newer rolling beta was published meanwhile.
    Older manifests have no fingerprint: the download is then accepted with
    a warning in the logs, so updates keep working during the transition.
    """
    expected = None
    if expected_sha256:
        expected = _normalize_sha256(expected_sha256)
        if expected is None:
            raise UpdateIntegrityError(
                "L'empreinte publiée pour l'installateur est invalide."
            )

    safe_name = os.path.basename(str(file_name or "").replace("\\", "/"))
    if not safe_name or safe_name in (".", ".."):
        safe_name = "SuperMenu_Setup.exe"

    _remove_previous_downloads()
    folder = tempfile.mkdtemp(prefix=_DOWNLOAD_FOLDER_PREFIX)
    dest_path = os.path.join(folder, safe_name)
    try:
        actual = _download_and_hash(url, dest_path, timeout_s)
        if expected is None:
            _LOGGER.warning(
                "Mise à jour : aucune empreinte SHA-256 publiée pour %s ; "
                "intégrité du téléchargement non vérifiée.",
                safe_name,
            )
        elif actual != expected:
            if _rolling_beta_republished(url, expected):
                raise UpdateSupersededError(
                    "Une nouvelle bêta a été publiée pendant la mise à jour. "
                    "Le fichier téléchargé a été supprimé ; relancez « Vérifier "
                    "les mises à jour » pour installer la dernière bêta."
                )
            raise UpdateIntegrityError(
                "L'installateur téléchargé ne correspond pas à l'empreinte "
                "publiée. Il a été supprimé ; réessayez plus tard."
            )
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return dest_path
