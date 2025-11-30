"""Utilities for resolving Raspberry Pi hostnames to usable addresses."""

from __future__ import annotations

import socket
from typing import Iterable, List, Sequence

from .compat import dataclass


@dataclass(slots=True)
class AddressRecord:
    """Represents a resolved address for a host."""

    source: str
    address: str
    family: int

    @property
    def is_ipv6(self) -> bool:
        return self.family == socket.AF_INET6

    @property
    def is_ipv4(self) -> bool:
        return self.family == socket.AF_INET


def resolve_hosts(hosts: Sequence[str]) -> List[AddressRecord]:
    """Resolve a collection of hostnames, returning IPv4 addresses first."""

    results: List[AddressRecord] = []
    seen = set()
    for host in hosts:
        if not host:
            continue
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            continue
        for family, _, _, _, sockaddr in infos:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            address = sockaddr[0]
            key = (family, address)
            if key in seen:
                continue
            seen.add(key)
            results.append(AddressRecord(source=host, address=address, family=family))
    # Stable sort: all IPv4 before IPv6 while preserving original order
    results.sort(key=lambda record: 0 if record.is_ipv4 else 1)
    return results


def pick_preferred(records: Sequence[AddressRecord]) -> AddressRecord | None:
    """Choose the preferred address from a list of records (IPv4 first)."""

    for record in records:
        if record.is_ipv4:
            return record
    return records[0] if records else None


def consolidate_hosts(preferred: str, fallbacks: Iterable[str]) -> List[str]:
    """Return hostnames in priority order without duplicates."""

    ordered: List[str] = []
    seen = set()
    for host in (preferred, *fallbacks):
        if host and host not in seen:
            ordered.append(host)
            seen.add(host)
    return ordered


def format_for_url(address: str, family: int) -> str:
    """Format an address so it can be embedded into an HTTP URL."""

    if family == socket.AF_INET6 and not address.startswith("["):
        return f"[{address}]"
    return address
