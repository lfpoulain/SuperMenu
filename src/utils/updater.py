import re
from typing import Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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


def _parse_version(value: str) -> Tuple[int, ...]:
    parts = [p for p in value.strip().split(".") if p != ""]
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except Exception:
            out.append(0)
    return tuple(out)


def is_newer_version(current: Optional[str], candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    return _parse_version(candidate) > _parse_version(current)


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


def get_github_release_by_tag(owner: str, repo: str, tag: str, timeout_s: int = 15) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    resp = _SESSION.get(url, timeout=(5, timeout_s))
    resp.raise_for_status()
    return resp.json()


def extract_version_from_release(release: dict) -> Optional[str]:
    body = release.get("body") or ""
    m = re.search(r"Version:\s*([0-9]+(?:\.[0-9]+)*)", body)
    if m:
        return m.group(1)

    name = release.get("name") or ""
    m = re.search(r"([0-9]+(?:\.[0-9]+)*)", name)
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
