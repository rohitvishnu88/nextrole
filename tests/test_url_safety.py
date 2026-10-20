import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from core import url_safety
from core.url_safety import UnsafeURL, validate_public_url


def resolves_to(monkeypatch, *ips):
    def fake(host, port, *a, **kw):
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))
                for ip in ips]
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake)


def test_rejects_metadata_ip(monkeypatch):
    resolves_to(monkeypatch, "169.254.169.254")
    with pytest.raises(UnsafeURL):
        validate_public_url("http://169.254.169.254/latest/meta-data/")


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.1", "::1", "0.0.0.0"])
def test_rejects_localhost_and_private_ranges(monkeypatch, ip):
    resolves_to(monkeypatch, ip)
    with pytest.raises(UnsafeURL):
        validate_public_url("http://example.test/job")


def test_rejects_hostname_resolving_to_private(monkeypatch):
    resolves_to(monkeypatch, "93.184.216.34", "10.1.2.3")
    with pytest.raises(UnsafeURL):
        validate_public_url("https://jobs.example.com/1")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)", "example.com/job"])
def test_rejects_non_http_scheme(url):
    with pytest.raises(UnsafeURL):
        validate_public_url(url)


def test_accepts_public_https(monkeypatch):
    resolves_to(monkeypatch, "93.184.216.34")
    assert validate_public_url("https://jobs.lever.co/acme/1") == "https://jobs.lever.co/acme/1"


def test_tailor_start_rejects_unsafe_url_400(tmp_path, monkeypatch):
    import importlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from auth_helpers import OWNER, sign_in
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    (tmp_path / "profiles" / "rohit").mkdir(parents=True)
    resolves_to(monkeypatch, "127.0.0.1")
    import a2a.routes.tailor_api as mod
    importlib.reload(mod)
    app = FastAPI()
    app.include_router(mod.router)
    sign_in(app, OWNER)
    resp = TestClient(app).post("/api/tailor", json={"profile_slug": "rohit", "url": "http://localhost:8000/api/profiles"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "unsafe_url"


def test_playwright_route_handler_aborts_private_redirect(monkeypatch):
    import tailor_agent
    calls = []
    route = SimpleNamespace(request=SimpleNamespace(url="http://192.168.0.1/admin", resource_type="script"),
                            abort=lambda *a: calls.append("abort"), continue_=lambda: calls.append("continue"))
    resolves_to(monkeypatch, "192.168.0.1")
    tailor_agent._guard_route(route)
    assert calls == ["abort"]
    resolves_to(monkeypatch, "93.184.216.34")
    route.request.url = "https://www.linkedin.com/jobs/view/1"
    tailor_agent._guard_route(route)
    assert calls == ["abort", "continue"]


def test_fetch_validates_before_fetching(monkeypatch):
    import tailor_agent
    resolves_to(monkeypatch, "10.0.0.1")
    monkeypatch.setattr(tailor_agent, "make_tavily", lambda: pytest.fail("fetched an unsafe URL"))
    with pytest.raises(UnsafeURL):
        tailor_agent.fetch_job_description_with_source("http://intranet.example/job")


def test_rejects_cgnat_range_used_by_tailscale(monkeypatch):
    resolves_to(monkeypatch, "100.64.0.1")
    with pytest.raises(UnsafeURL):
        validate_public_url("http://my-mac.tailnet.example/")


def test_playwright_only_used_for_real_linkedin_host(monkeypatch):
    import tailor_agent
    resolves_to(monkeypatch, "93.184.216.34")
    used = []
    monkeypatch.setattr(tailor_agent, "_fetch_with_playwright", lambda url: used.append(url) or "x" * 500)

    class NoTavily:
        def extract(self, urls, **kw): return {"results": [{"raw_content": "ad text"}]}
        def search(self, query, **kw): return {"results": []}
    monkeypatch.setattr(tailor_agent, "make_tavily", NoTavily)
    tailor_agent.fetch_job_description_with_source("https://attacker.example/x?linkedin.com/jobs")
    assert used == []
    tailor_agent.fetch_job_description_with_source("https://www.linkedin.com/jobs/view/123")
    assert used == ["https://www.linkedin.com/jobs/view/123"]


def test_playwright_does_not_follow_redirect_to_blocked_address(monkeypatch):
    """Real Chromium against a real local server: /start 302s to /secret."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import tailor_agent

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/secret")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<main>" + b"secret internal content " * 20 + b"</main>")

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_port

    def only_start_is_public(url):
        if url.endswith("/start"):
            return url
        raise UnsafeURL("blocked")
    monkeypatch.setattr(tailor_agent, "validate_public_url", only_start_is_public)
    try:
        content = tailor_agent._fetch_with_playwright(f"http://127.0.0.1:{port}/start")
    finally:
        server.shutdown()
    assert "secret internal content" not in content
