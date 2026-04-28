from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import TOOLING_ID

USER_AGENT = (
    f"{TOOLING_ID} "
    "(+https://github.com/gesetze-corpus/tools; contact=noreply@gesetze-corpus.local)"
)


def build_session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


_default_session: requests.Session | None = None


def _shared_session() -> requests.Session:
    global _default_session
    if _default_session is None:
        _default_session = build_session()
    return _default_session


def get(url: str, *, timeout: float = 30.0, **kwargs) -> requests.Response:
    """Convenience GET that uses the shared session and raises on >=400.

    Used by fetcher submodules that don't need a long-lived session
    object (e.g. listing probes, single-shot crawls). The shared
    session keeps the retry/backoff config consistent across modules.
    """
    response = _shared_session().get(url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response
