import asyncio
import re
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from core import ai_clients, usage


class FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_text(self):
        return "streamed"

    def get_final_message(self):
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=0, output_tokens=100_000,
                                                     cache_read_input_tokens=0, cache_creation_input_tokens=0))


class FakeAnthropic:
    def __init__(self):
        self.messages = SimpleNamespace(create=self._create, stream=lambda **kw: FakeStream())

    def _create(self, **kw):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=1_000_000, output_tokens=0,
                                  cache_read_input_tokens=None, cache_creation_input_tokens=0),
        )


class FakeTavily:
    def search(self, query, **kw):
        return {"results": []}

    def extract(self, urls, **kw):
        return {"results": []}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(ai_clients, "_real_anthropic", FakeAnthropic)
    monkeypatch.setattr(ai_clients, "_real_tavily", FakeTavily)


def call_claude():
    return ai_clients.make_anthropic().messages.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])


def test_call_inside_metered_records_against_reservation():
    rid = usage.reserve("u1", "tailor", is_owner=False)
    with ai_clients.metered(rid):
        call_claude()
    usage.commit(rid)
    assert usage.spent_this_month() == pytest.approx(3.00)
    assert usage.summary(usage.month_of())["by_user"][0]["user_id"] == "u1"


def test_call_in_worker_thread_with_metered_inside_thread_records_correctly():
    rid = usage.reserve("u1", "tailor", is_owner=False)

    def work():
        with ai_clients.metered(rid):
            call_claude()

    async def main():
        await asyncio.get_event_loop().run_in_executor(None, work)

    asyncio.run(main())
    usage.commit(rid)
    users = {u["user_id"] for u in usage.summary(usage.month_of())["by_user"]}
    assert users == {"u1"}


def test_call_without_reservation_is_cli_and_refused_at_ceiling(monkeypatch):
    call_claude()
    summary = usage.summary(usage.month_of())
    assert summary["by_action"] == {"cli": pytest.approx(3.00)}
    monkeypatch.setattr(usage.limits, "MONTHLY_BUDGET_USD", 3.10)
    with pytest.raises(usage.LimitReached) as exc:
        call_claude()
    assert exc.value.code == "budget_reached"


def test_stream_is_metered():
    rid = usage.reserve("u1", "tailor", is_owner=False)
    with ai_clients.metered(rid):
        with ai_clients.make_anthropic().messages.stream(model="claude-sonnet-4-6", max_tokens=10, messages=[]) as st:
            assert st.get_final_text() == "streamed"
    usage.commit(rid)
    assert usage.spent_this_month() == pytest.approx(1.50)


def test_tavily_credits_recorded():
    rid = usage.reserve("u1", "job_search", is_owner=False)
    with ai_clients.metered(rid):
        client = ai_clients.make_tavily()
        client.search(query="x", search_depth="advanced")
        client.search(query="y")
        client.extract(urls=[f"https://e.com/{i}" for i in range(6)])
    usage.commit(rid)
    assert usage.spent_this_month() == pytest.approx((2 + 1 + 2) * usage.limits.TAVILY_CREDIT_USD)


def test_no_direct_client_construction_left():
    offenders = []
    for folder in ("agents", "a2a", "core"):
        for path in (ROOT / folder).rglob("*.py"):
            if path.name == "ai_clients.py":
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(r"anthropic\.Anthropic\(|TavilyClient\(", text):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
