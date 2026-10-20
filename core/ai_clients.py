"""The only place Claude and Tavily clients are created. Every call is metered.

Calls are recorded against the reservation set by `metered()`. Enter it inside the
thread that makes the calls: context variables don't follow work into executor threads.
A call made with no reservation (CLI runs) is reserved as "cli" against the owner and
refused once the monthly ceiling is reached.
"""
import asyncio
import contextvars
import math
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator, Optional

from core import usage

_current_reservation: ContextVar[Optional[str]] = ContextVar("usage_reservation", default=None)


def _real_anthropic():
    import anthropic
    return anthropic.Anthropic()


def _real_tavily():
    from tavily import TavilyClient
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


@contextmanager
def metered(reservation_id: str) -> Iterator[None]:
    token = _current_reservation.set(reservation_id)
    try:
        yield
    finally:
        _current_reservation.reset(token)


async def run_in_thread(fn: Callable):
    """run_in_executor that carries the current reservation into the worker thread."""
    return await asyncio.get_event_loop().run_in_executor(None, contextvars.copy_context().run, fn)


def _run_metered(call: Callable, record: Callable[[str, object], None]):
    reservation_id = _current_reservation.get()
    if reservation_id is not None:
        result = call()
        record(reservation_id, result)
        return result
    cli_id = usage.reserve(None, "cli", is_owner=True)
    try:
        result = call()
    except Exception:
        usage.release(cli_id)
        raise
    record(cli_id, result)
    usage.commit(cli_id)
    return result


class _MeteredMessages:
    def __init__(self, inner):
        self._inner = inner

    @staticmethod
    def _record(model: str):
        def record(reservation_id, response):
            u = getattr(response, "usage", None)
            usage.record_call(
                reservation_id,
                model=model,
                input_tokens=getattr(u, "input_tokens", 0) or 0,
                output_tokens=getattr(u, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            )
        return record

    def create(self, **kwargs):
        return _run_metered(lambda: self._inner.messages.create(**kwargs), self._record(kwargs.get("model", "")))

    @contextmanager
    def stream(self, **kwargs):
        record = self._record(kwargs.get("model", ""))
        reservation_id = _current_reservation.get()
        cli_id = None if reservation_id is not None else usage.reserve(None, "cli", is_owner=True)
        try:
            with self._inner.messages.stream(**kwargs) as stream:
                yield stream
                record(reservation_id or cli_id, stream.get_final_message())
        except Exception:
            if cli_id:
                usage.release(cli_id)
            raise
        if cli_id:
            usage.commit(cli_id)


class MeteredAnthropic:
    def __init__(self, inner):
        self.messages = _MeteredMessages(inner)


class MeteredTavily:
    def __init__(self, inner):
        self._inner = inner

    def search(self, query: str, **kwargs):
        credits = 2 if kwargs.get("search_depth") == "advanced" else 1
        return _run_metered(lambda: self._inner.search(query=query, **kwargs),
                            lambda rid, _: usage.record_call(rid, tavily_credits=credits))

    def extract(self, urls, **kwargs):
        per_five = 2 if kwargs.get("extract_depth") == "advanced" else 1
        credits = per_five * max(1, math.ceil(len(urls) / 5))
        return _run_metered(lambda: self._inner.extract(urls=urls, **kwargs),
                            lambda rid, _: usage.record_call(rid, tavily_credits=credits))


def make_anthropic() -> MeteredAnthropic:
    return MeteredAnthropic(_real_anthropic())


def make_tavily() -> MeteredTavily:
    return MeteredTavily(_real_tavily())
