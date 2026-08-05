import json
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


UPDATE_CHANNEL_STABLE = "stable"
UPDATE_CHANNEL_BETA = "beta"
UPDATE_CHANNELS = (UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_BETA)

_VERSION_PATTERN = re.compile(
    r"v?(\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?)",
    re.IGNORECASE,
)

_MANIFEST_SCHEMA_VERSION = 1


class UpdateCheckError(RuntimeError):
    """User-facing update lookup failure."""


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


def normalize_update_channel(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == UPDATE_CHANNEL_BETA:
        return UPDATE_CHANNEL_BETA
    return UPDATE_CHANNEL_STABLE


def installer_asset_name(channel: Optional[str]) -> str:
    if normalize_update_channel(channel) == UPDATE_CHANNEL_BETA:
        return "SuperMenu_Beta_Setup.exe"
    return "SuperMenu_Setup.exe"


def release_manifest_name(channel: Optional[str]) -> str:
    if normalize_update_channel(channel) == UPDATE_CHANNEL_BETA:
        return "update-beta.json"
    return "update-stable.json"


def _parse_version(value: str) -> Tuple[int, ...]:
    normalized = str(value or "").strip().lower()
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?",
        normalized,
    )
    if not match:
        return ()

    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    prerelease_kind = match.group(4)
    prerelease_number = int(match.group(5) or 0)
    stage_rank = {
        "beta": 0,
        "rc": 1,
        None: 2,
    }[prerelease_kind]
    return major, minor, patch, stage_rank, prerelease_number


def is_newer_version(current: Optional[str], candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    parsed_candidate = _parse_version(candidate)
    if not parsed_candidate:
        return False
    parsed_current = _parse_version(current or "")
    if not parsed_current:
        return True
    return parsed_candidate > parsed_current


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
    release_base = f"https://github.com/{owner}/{repo}/releases"
    return {
        "name": f"SuperMenu {version}",
        "body": f"Channel: {expected_channel}\nVersion: {version}",
        "tag_name": tag,
        "prerelease": prerelease,
        "html_url": f"{release_base}/tag/{tag}",
        "assets": [
            {
                "name": asset_name,
                "browser_download_url": (
                    f"{release_base}/download/{tag}/{asset_name}"
                ),
            }
        ],
    }


def get_release_from_manifest(
    owner: str,
    repo: str,
    channel: Optional[str],
    timeout_s: int = 15,
) -> Optional[dict]:
    normalized_channel = normalize_update_channel(channel)
    manifest_name = release_manifest_name(normalized_channel)
    if normalized_channel == UPDATE_CHANNEL_BETA:
        url = (
            f"https://github.com/{owner}/{repo}/releases/download/"
            f"beta/{manifest_name}"
        )
    else:
        url = (
            f"https://github.com/{owner}/{repo}/releases/latest/download/"
            f"{manifest_name}"
        )

    response = _SESSION.get(
        url,
        timeout=(5, timeout_s),
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    try:
        payload = json.loads(response.content.decode("utf-8-sig"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Le manifeste de mise à jour est illisible.") from exc
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


def download_to_file(url: str, dest_path: str, timeout_s: int = 60) -> None:
    with _SESSION.get(url, stream=True, timeout=(10, timeout_s)) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
