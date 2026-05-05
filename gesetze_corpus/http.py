from __future__ import annotations

import os
import random
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import TOOLING_ID

USER_AGENT = (
    f"{TOOLING_ID} "
    "(+https://github.com/gesetze-corpus/tools; contact=noreply@gesetze-corpus.local)"
)

_GII_HOSTS = {"www.gesetze-im-internet.de", "gesetze-im-internet.de"}
_rate_lock = threading.Lock()
_last_gii_request = 0.0


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


def _throttle_gii(url: str) -> None:
    """Serialize and lightly jitter requests to GII.

    GII frequently resets connections when a broad crawl opens too many ZIP
    downloads in quick succession. Keep the defaults conservative; operators
    can tune with GESETZE_GII_REQUEST_DELAY and GESETZE_GII_REQUEST_JITTER.
    """
    host = urlparse(url).hostname
    if host not in _GII_HOSTS:
        return
    delay = _float_env("GESETZE_GII_REQUEST_DELAY", 0.75)
    jitter = _float_env("GESETZE_GII_REQUEST_JITTER", 0.5)
    wait_extra = random.uniform(0, jitter) if jitter else 0.0

    global _last_gii_request
    with _rate_lock:
        now = time.monotonic()
        wait = (_last_gii_request + delay + wait_extra) - now
        if wait > 0:
            time.sleep(wait)
        _last_gii_request = time.monotonic()


class ThrottledSession(requests.Session):
    def request(self, method: str, url: str, **kwargs):  # type: ignore[override]
        _throttle_gii(url)
        return super().request(method, url, **kwargs)


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
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session = ThrottledSession()
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
