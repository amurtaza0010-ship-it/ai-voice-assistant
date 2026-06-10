import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_ALLOWED_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "chrome.exe",
    ],
    "edge": ["msedge.exe"],
    "vscode": ["code.cmd", "code.exe"],
    "vs code": ["code.cmd", "code.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
}
_ALIASES = {
    "vs code": "vscode",
    "visual studio code": "vscode",
    "files": "file explorer",
}


def _normalize_app_name(text: str) -> Optional[str]:
    lowered = re.sub(r"\s+", " ", text.lower().strip())
    for alias, canonical in _ALIASES.items():
        if alias in lowered:
            return canonical
    for name in _ALLOWED_APPS:
        if name in lowered:
            return name
    return None


def _resolve_launcher(candidates: list[str]) -> Optional[str]:
    for candidate in candidates:
        if os.path.isabs(candidate) and os.path.isfile(candidate):
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def open_app(query: str) -> str:
    if sys.platform != "win32":
        return "System control is only supported on Windows."

    app_key = _normalize_app_name(query)
    if app_key is None:
        allowed = ", ".join(sorted(_ALLOWED_APPS))
        return f"I can only open these apps: {allowed}."

    launcher = _resolve_launcher(_ALLOWED_APPS[app_key])
    if launcher is None:
        return f"Could not find {app_key} on this system."

    try:
        if launcher.lower().endswith("explorer.exe"):
            subprocess.Popen([launcher], shell=False)
        else:
            os.startfile(launcher)  # type: ignore[attr-defined]
        logger.info("Opened application: app=%s launcher=%s", app_key, launcher)
        return f"Opened {app_key}."
    except Exception as e:
        logger.exception("Failed to open %s", app_key)
        return f"Failed to open {app_key}: {e}"
