MODEL = "claude-sonnet-4-6"

HUMANISE_RULES = """
Writing rules — apply to every sentence:
- No em dashes. Use a comma or a full stop instead.
- No filler openers: never start with "Certainly", "Absolutely", "Great", "Sure", "Of course".
- No AI padding: cut "it's worth noting", "it is important to highlight", "as mentioned", "in conclusion".
- Plain words first: "use" not "utilise", "start" not "initiate", "show" not "demonstrate", "help" not "facilitate".
- Short sentences. Split anything over 20 words.
- Active voice. Flip passive constructions unless passive is clearly better.
- Direct and confident. No hedging unless uncertainty is real.
- No promotional fluff: no "seamless", "robust", "cutting-edge", "world-class", "transformative", "innovative".
- No tacked-on -ing phrases for fake depth: cut "enabling...", "showcasing...", "demonstrating...".
- No synonym cycling: pick one word and stick with it.
- No rule-of-three padding.
- No sycophantic openers or closers.
- Vary sentence length. Mix short punchy lines with longer ones.
- Use "I" when it fits. First person is honest, not unprofessional.
- Be specific. Vague claims get cut.
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_object(text: str) -> str:
    """Return the outermost {...} span from text (first { to last }), stripping markdown fences. Returns text unchanged if no braces found."""
    text = _strip_fences(text)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        return text[start:end]
    return text


def extract_json_array(text: str) -> str:
    """Return the outermost [...] span from text (first [ to last ]), stripping markdown fences. Returns text unchanged if no brackets found."""
    text = _strip_fences(text)
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return text[start:end]
    return text
