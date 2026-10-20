import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from core import ai_clients, usage

TOKEN = "test-a2a-token"


class FakeAnthropic:
    def __init__(self):
        self.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[], usage=SimpleNamespace(input_tokens=1000, output_tokens=1000,
                                              cache_read_input_tokens=0, cache_creation_input_tokens=0)))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("A2A_TOKEN", TOKEN)
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(ai_clients, "_real_anthropic", FakeAnthropic)
    from a2a import db, server
    owner = db.upsert_user("owner@example.com", "Owner", "", True)
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    cover = tmp_path / "c.txt"
    cover.write_text("cover")
    resume_json = tmp_path / "r.json"
    resume_json.write_text(json.dumps({"name": "Owner"}))

    def fake_tailor_run(job_url="", jd_text="", profile_slug=""):
        ai_clients.make_anthropic().messages.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])
        return {"status": "completed", "pdf_file": str(pdf), "cover_letter_file": str(cover), "json_file": str(resume_json)}

    monkeypatch.setattr(server.tailor.tailor_agent, "run", fake_tailor_run)
    return TestClient(server.app), owner


RPC = {"jsonrpc": "2.0", "id": 1, "method": "tasks/send",
       "params": {"id": "t1", "message": {"role": "user", "parts": [{"type": "text", "text": "tailor my resume: Senior Architect role"}]},
                  "metadata": {"skill": "tailor_resume"}}}


def test_rpc_without_token_401(client):
    c, _ = client
    assert c.post("/", json=RPC).status_code == 401


def test_rpc_with_wrong_token_401(client):
    c, _ = client
    assert c.post("/", json=RPC, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_rpc_refused_when_token_unset(client, monkeypatch):
    c, _ = client
    monkeypatch.delenv("A2A_TOKEN")
    assert c.post("/", json=RPC, headers={"Authorization": "Bearer "}).status_code == 401
    assert c.post("/", json=RPC, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 401


def test_rpc_with_token_dispatches_and_reserves_owner_action(client):
    c, owner = client
    resp = c.post("/", json=RPC, headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["result"]["status"]["state"] == "completed"
    assert usage.counts_for(owner["id"], usage.month_of()) == {"tailor": 1}
    assert "cli" not in usage.summary(usage.month_of())["by_action"]


def test_rpc_refused_at_ceiling(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(usage.limits, "MONTHLY_BUDGET_USD", 0.01)
    body = c.post("/", json=RPC, headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert body["error"]["data"]["code"] == "budget_reached"


def test_agent_card_public(client):
    c, _ = client
    assert c.get("/.well-known/agent.json").status_code == 200
