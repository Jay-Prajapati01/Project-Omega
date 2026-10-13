"""SSRF guard tests (audit P0-2; plan SEC-004 / ING-002 URL validation).

DNS is stubbed with a side effect that resolves the literal IP hosts to
themselves (exactly like the real resolver) so no packet ever leaves the
machine; `respx` intercepts the HTTP layer for `safe_get`.
"""
from __future__ import annotations

import asyncio
import socket
from unittest.mock import patch

import pytest
import respx

from app.core import ssrf
from app.core.config import get_settings
from app.core.ssrf import SSRFBlockedError, validate_public_url

PUBLIC_IP = "93.184.216.34"


def _addr(host: str, ip: str) -> tuple:
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return (family, socket.SOCK_STREAM, 6, "", (ip, 0))


def _fake_getaddrinfo(host, port, *args, **kwargs):
    """Resolve literal IPs to themselves; example.com to a public address."""
    try:
        socket.inet_pton(socket.AF_INET6 if ":" in host else socket.AF_INET, host)
        return [_addr(host, host)]
    except OSError:
        pass
    if host == "example.com":
        return [_addr(host, PUBLIC_IP)]
    raise socket.gaierror(-2, "Name or service not known")


@pytest.fixture
def dns():
    with patch("socket.getaddrinfo", side_effect=_fake_getaddrinfo):
        yield


@pytest.fixture
def guard_on():
    settings = get_settings()
    previous = settings.ssrf_block_private
    settings.ssrf_block_private = True
    yield settings
    settings.ssrf_block_private = previous


# --- validate_public_url: schemes, ports, hostnames ---------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com/",
        "javascript:alert(1)",
        "redis://example.com:6379",
    ],
)
def test_non_http_schemes_blocked(guard_on, url):
    with pytest.raises(SSRFBlockedError, match="http"):
        validate_public_url(url)


@pytest.mark.parametrize("url", ["http:///path", "http://", "https:///"])
def test_missing_hostname_blocked(guard_on, url):
    with pytest.raises(SSRFBlockedError, match="hostname"):
        validate_public_url(url)


@pytest.mark.parametrize("port", [22, 8080, 6379, 9200, 0])
def test_non_standard_ports_blocked(guard_on, port):
    with pytest.raises(SSRFBlockedError, match="ports 80 and 443"):
        validate_public_url(f"http://example.com:{port}/x")


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST",
        "api.localhost",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "printer.local",
        "db.internal",
        "db.INTERNAL",
    ],
)
def test_internal_hostnames_blocked_without_dns(guard_on, host):
    with pytest.raises(SSRFBlockedError, match="internal hosts"):
        validate_public_url(f"http://{host}/secret")


def test_guard_disabled_returns_no_pin(guard_on):
    guard_on.ssrf_block_private = False
    # Documented escape hatch for trusted isolated environments.
    assert validate_public_url("http://localhost:8080/x") is None
    assert validate_public_url("file:///etc/passwd") is None


# --- validate_public_url: resolved addresses ----------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "127.255.255.254",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.10",
        "169.254.169.254",  # cloud metadata
        "0.0.0.0",
        "240.0.0.1",  # reserved
        "224.0.0.1",  # multicast
        "::1",
        "fe80::1",
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:192.168.0.1",
    ],
)
def test_internal_resolved_addresses_blocked(guard_on, ip):
    with patch("socket.getaddrinfo", return_value=[_addr("example.com", ip)]):
        with pytest.raises(SSRFBlockedError, match="internal/private"):
            validate_public_url("http://example.com/x")


def test_public_address_is_pinned(dns, guard_on):
    assert validate_public_url("https://example.com/docs") == PUBLIC_IP
    assert validate_public_url("http://example.com:443/docs") == PUBLIC_IP


def test_any_internal_record_in_a_mixed_answer_blocks(dns, guard_on):
    with patch(
        "socket.getaddrinfo",
        return_value=[_addr("example.com", PUBLIC_IP), _addr("example.com", "10.1.2.3")],
    ):
        with pytest.raises(SSRFBlockedError):
            validate_public_url("http://example.com/x")


def test_unresolvable_host_blocked(dns, guard_on):
    with pytest.raises(SSRFBlockedError, match="Could not resolve"):
        validate_public_url("http://no-such-host.example/x")


def test_empty_dns_answer_blocked(dns, guard_on):
    with patch("socket.getaddrinfo", return_value=[]):
        with pytest.raises(SSRFBlockedError, match="Could not resolve"):
            validate_public_url("http://example.com/x")


# --- connection pinning -------------------------------------------------------


def test_pinned_request_preserves_host_sni_and_port():
    target, headers, ext = ssrf._pinned_request("https://example.com/a?x=1", PUBLIC_IP)
    assert target == f"https://{PUBLIC_IP}/a?x=1"
    assert headers == {"Host": "example.com"}
    assert ext == {"sni_hostname": "example.com"}  # TLS still verifies the name

    target, headers, ext = ssrf._pinned_request("http://example.com/a", PUBLIC_IP)
    assert target == f"http://{PUBLIC_IP}/a"
    assert ext == {}  # no SNI without TLS


def test_pinned_request_keeps_ports_and_brackets_ipv6():
    target, headers, _ = ssrf._pinned_request("https://example.com:8443/x", PUBLIC_IP)
    assert target == f"https://{PUBLIC_IP}:8443/x"
    assert headers == {"Host": "example.com:8443"}

    target, _, _ = ssrf._pinned_request("http://example.com/", "2606:4700:4700::1111")
    assert target == "http://[2606:4700:4700::1111]/"


# --- safe_get -----------------------------------------------------------------


@respx.mock
def test_safe_get_returns_body_and_pins_connection(dns, guard_on):
    respx.get(f"http://{PUBLIC_IP}/page").respond(200, content=b"hello world")
    status, body, final_url = asyncio.run(ssrf.safe_get("http://example.com/page", timeout=5))
    assert status == 200
    assert body == b"hello world"
    assert final_url == "http://example.com/page"
    # The socket went to the pinned IP while the Host header kept the name.
    call = respx.calls[0].request
    assert str(call.url).startswith(f"http://{PUBLIC_IP}/")
    assert call.headers["host"] == "example.com"


@respx.mock
def test_safe_get_revalidates_every_redirect_hop(dns, guard_on):
    respx.get(f"http://{PUBLIC_IP}/page").respond(
        302, headers={"Location": "http://127.0.0.1/admin"}
    )
    with pytest.raises(SSRFBlockedError, match="internal/private"):
        asyncio.run(ssrf.safe_get("http://example.com/page", timeout=5))
    # The internal hop was rejected before a single packet was sent to it.
    assert len(respx.calls) == 1
    assert "127.0.0.1" not in str(respx.calls[0].request.url)


@respx.mock
def test_safe_get_stops_redirect_loops(dns, guard_on):
    respx.get(f"http://{PUBLIC_IP}/loop").respond(
        302, headers={"Location": "/loop"}
    )
    with pytest.raises(RuntimeError, match="Too many redirects"):
        asyncio.run(ssrf.safe_get("http://example.com/loop", timeout=5, max_redirects=3))


@respx.mock
def test_safe_get_raises_on_http_error_status(dns, guard_on):
    respx.get(f"http://{PUBLIC_IP}/missing").respond(404)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        asyncio.run(ssrf.safe_get("http://example.com/missing", timeout=5))


@respx.mock
def test_safe_get_enforces_body_size_cap(dns, guard_on):
    respx.get(f"http://{PUBLIC_IP}/huge").respond(200, content=b"x" * 10_000)
    with pytest.raises(RuntimeError, match="fetch limit"):
        asyncio.run(ssrf.safe_get("http://example.com/huge", timeout=5, max_bytes=100))
