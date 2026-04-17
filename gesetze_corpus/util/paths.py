from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_REPO_ENV = "GESETZE_DATA_REPO"


def resolve_data_repo(explicit: str | None = None) -> Path:
    """Return the path to the data repo.

    Resolution order:
    1. Explicit argument.
    2. Environment variable GESETZE_DATA_REPO.
    3. Sibling directory ../gesetze-corpus-data next to the tools repo root.
    """
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get(DEFAULT_DATA_REPO_ENV)
    if env:
        return Path(env).resolve()
    tools_root = Path(__file__).resolve().parents[2]
    return (tools_root.parent / "gesetze-corpus-data").resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
