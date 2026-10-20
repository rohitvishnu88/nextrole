from types import SimpleNamespace


class FakeClient:
    """Stands in for anthropic.Anthropic. Returns queued texts in order and records prompts."""

    def __init__(self, *texts: str):
        self._texts = list(texts)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text = self._texts.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    def prompt(self, i: int = 0) -> str:
        return self.calls[i]["messages"][0]["content"]
