"""Central application state shared across UI panels."""

from __future__ import annotations

import socket
from typing import List, Optional

from ..compat import dataclass
from ..config import DEFAULT_CONFIG, AppConfig
from ..jobs import JobManager
from ..network import (
    AddressRecord,
    consolidate_hosts,
    format_for_url,
    pick_preferred,
    resolve_hosts,
)
from ..services.rest import RestClient, RestConfig
from ..services.ssh import SSHCredentials, SSHService
from ..settings import load_settings, save_settings


@dataclass(slots=True)
class ServiceRegistry:
    ssh: SSHService
    rest: RestClient


class AppState:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.jobs = JobManager()
        self._ssh: Optional[SSHService] = None
        self._rest: Optional[RestClient] = None
        self._address_book: List[AddressRecord] = []
        self._resolution: Optional[AddressRecord] = None

        self._apply_saved_settings()
        self._refresh_resolution()

    def init_services(self) -> ServiceRegistry:
        ssh = self._ensure_ssh()
        rest = self._ensure_rest()
        return ServiceRegistry(ssh=ssh, rest=rest)

    def _ensure_ssh(self) -> SSHService:
        if self._ssh is None:
            remote_cfg = self.config.remote
            credentials = SSHCredentials(
                host=self._resolved_address(for_url=False),
                username=remote_cfg.ssh_user,
                password=remote_cfg.ssh_password,
            )
            self._ssh = SSHService(credentials)
        return self._ssh

    def _ensure_rest(self) -> RestClient:
        if self._rest is None:
            remote_cfg = self.config.remote
            host = self._resolved_address(for_url=True)
            base_url = f"http://{host}:{remote_cfg.api_port}"
            rest_cfg = RestConfig(base_url=base_url, api_key=self.config.default_api_key)
            self._rest = RestClient(rest_cfg)
        return self._rest

    def close(self) -> None:
        if self._ssh:
            self._ssh.close()
            self._ssh = None

    # Host management -----------------------------------------------------------------

    def _apply_saved_settings(self) -> None:
        settings = load_settings()
        saved_host = settings.get("default_host") if isinstance(settings, dict) else None
        if isinstance(saved_host, str) and saved_host:
            self.config.remote.default_host = saved_host

    def _resolved_address(self, *, for_url: bool) -> str:
        resolution = self._resolution
        if resolution is None:
            return self.config.remote.default_host
        if for_url:
            return format_for_url(resolution.address, resolution.family)
        return resolution.address

    def _refresh_resolution(self, *, require_success: bool = False) -> None:
        hosts = consolidate_hosts(
            self.config.remote.default_host,
            self.config.remote.fallback_hosts,
        )
        records = resolve_hosts(hosts)
        self._address_book = records
        preferred = pick_preferred(records)
        if preferred is not None:
            self._resolution = preferred
            return
        self._resolution = None
        if require_success:
            raise ValueError(f"Unable to resolve host '{self.config.remote.default_host}'.")

    def set_host(self, host: str) -> AddressRecord:
        host = host.strip()
        if not host:
            raise ValueError("Host cannot be empty.")
        if host == self.config.remote.default_host and self._resolution is not None:
            return self._resolution

        self.config.remote.default_host = host
        self._refresh_resolution(require_success=True)
        save_settings({"default_host": host})

        # Reset cached clients so they'll reconnect using the new host.
        if self._ssh:
            self._ssh.close()
            self._ssh = None
        self._rest = None

        assert self._resolution is not None  # for type checkers
        return self._resolution

    def refresh_host_resolution(self) -> Optional[AddressRecord]:
        self._refresh_resolution(require_success=False)
        return self._resolution

    def known_hosts(self) -> List[str]:
        hosts = consolidate_hosts(
            self.config.remote.default_host,
            self.config.remote.fallback_hosts,
        )
        for record in self._address_book:
            if record.address not in hosts:
                hosts.append(record.address)
        return hosts

    def resolved_host_display(self) -> str:
        resolution = self._resolution
        if resolution is None:
            return "Unresolved"
        family = "IPv6" if resolution.family == socket.AF_INET6 else "IPv4"
        return f"{resolution.address} ({family}, from {resolution.source})"
