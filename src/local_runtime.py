from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ServiceStatus:
    available: bool
    detail: str


def run_command_streaming(
    command: list[str],
    cwd: Path,
    on_line: Callable[[str], None],
    *,
    popen_factory: Callable[..., Any] = subprocess.Popen,
) -> int:
    """Run a command and forward merged stdout/stderr one line at a time."""
    process = popen_factory(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is not None:
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            if line:
                on_line(line)
    return process.wait()


def check_ollama(
    base_url: str,
    required_model: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> ServiceStatus:
    request = Request(f"{base_url.rstrip('/')}/api/tags", headers={"Accept": "application/json"})
    open_request = opener or urlopen
    try:
        with open_request(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError) as error:
        return ServiceStatus(False, f"Ollama is unreachable at {base_url}: {error}")

    names = {
        str(model.get("name") or model.get("model"))
        for model in payload.get("models", [])
        if model.get("name") or model.get("model")
    }
    if required_model not in names:
        return ServiceStatus(False, f"Ollama is running, but {required_model} is not installed.")
    return ServiceStatus(True, f"Ollama is running with {required_model}.")


def check_search_index(collection: Any, index_name: str, label: str) -> ServiceStatus:
    """Report one MongoDB search index without hiding other runtime states."""
    try:
        indexes = list(collection.list_search_indexes(name=index_name))
    except Exception as error:
        return ServiceStatus(False, f"{label}: unavailable ({error})")
    state = str(indexes[0].get("status", "UNKNOWN")) if indexes else "MISSING"
    return ServiceStatus(state == "READY", f"{label}: {state}")
