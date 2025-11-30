"""REST client used for communication with the Flask API running on the Pi."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from ..compat import dataclass

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RestConfig:
    base_url: str
    api_key: str = ""
    timeout: int = 5


class RestClient:
    def __init__(self, config: RestConfig) -> None:
        self._cfg = config

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self._cfg.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"User-Agent": "MasterControl/1.0"}
        if self._cfg.api_key:
            headers["X-API-Key"] = self._cfg.api_key
        return headers

    def get(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = self._build_url(path)
        _LOGGER.debug("GET %s", url)
        return requests.get(url, headers=self._headers(), params=params, timeout=self._cfg.timeout)

    def post(
        self, path: str, *, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        url = self._build_url(path)
        _LOGGER.debug("POST %s", url)
        return requests.post(
            url,
            headers=self._headers(),
            json=json,
            data=data,
            timeout=self._cfg.timeout,
        )

    def ping(self) -> bool:
        try:
            response = self.get("/api/health")
            return response.ok
        except requests.RequestException as exc:
            _LOGGER.error("Failed to reach REST API: %s", exc)
            return False
