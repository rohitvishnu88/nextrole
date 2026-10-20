"""Refuse user-supplied URLs that would make the server fetch private or local addresses."""
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


def validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURL("Only http(s) job URLs are allowed")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise UnsafeURL(f"Couldn't resolve {parsed.hostname}")
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        # is_global also excludes shared/CGNAT space (100.64.0.0/10, used by Tailscale),
        # which is_private misses on Python 3.9.
        if not address.is_global or address.is_multicast:
            raise UnsafeURL(f"{parsed.hostname} points to a private or local address")
    return url.strip()
