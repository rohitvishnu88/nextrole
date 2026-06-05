# Reliability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralise shared constants, remove the subprocess call in tailor_agent, harden JSON extraction, fix base resume output path, and move test scripts into a proper `tests/` directory.

**Architecture:** Extract `MODEL`, `HUMANISE_RULES`, and JSON extraction helpers into `core/config.py`. Add a `render_resume()` wrapper to `core/resume_builder.py` so `tailor_agent.py` can import and call it directly instead of shelling out. Update all three agent files to import from config. Move test scripts to `tests/`.

**Tech Stack:** Python 3.11+, no new dependencies.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| CREATE | `core/config.py` | `MODEL`, `HUMANISE_RULES`, `extract_json_object()`, `extract_json_array()` |
| MODIFY | `core/resume_builder.py` | Add `render_resume(data, html_path, pdf_path)` wrapper; fix auto-name output dir |
| MODIFY | `agents/tailor_agent.py` | Import from `core.config`; replace `subprocess.run` with `render_resume()` |
| MODIFY | `agents/job_search_agent.py` | Import `MODEL` from `core.config`; use `extract_json_array()` |
| MODIFY | `agents/linkedin_agent.py` | Import `MODEL` from `core.config` |
| CREATE | `tests/__init__.py` | Empty — marks `tests/` as a package |
| MOVE | `test_tailor.py` → `tests/test_tailor.py` | Update sys.path |
| MOVE | `test_job_search.py` → `tests/test_job_search.py` | Update sys.path |
| MOVE | `test_linkedin.py` → `tests/test_linkedin.py` | Update sys.path |
| CREATE | `tests/test_config.py` | Unit tests for `extract_json_object` and `extract_json_array` |

---

### Task 1: Create `core/config.py`

**Files:**
- Create: `core/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import extract_json_object, extract_json_array


def test_extract_json_object_plain():
    text = '{"name": "Alice"}'
    assert extract_json_object(text) == '{"name": "Alice"}'


def test_extract_json_object_strips_markdown():
    text = '```json\n{"name": "Alice"}\n```'
    result = extract_json_object(text)
    assert result == '{"name": "Alice"}'


def test_extract_json_object_with_preamble():
    text = 'Here is the result:\n{"name": "Alice"}\nDone.'
    result = extract_json_object(text)
    assert result == '{"name": "Alice"}'


def test_extract_json_array_plain():
    text = '[{"title": "Engineer"}]'
    assert extract_json_array(text) == '[{"title": "Engineer"}]'


def test_extract_json_array_strips_markdown():
    text = '```\n[{"title": "Engineer"}]\n```'
    result = extract_json_array(text)
    assert result == '[{"title": "Engineer"}]'


def test_extract_json_array_with_preamble():
    text = 'Results:\n[{"title": "Engineer"}]\nEnd.'
    result = extract_json_array(text)
    assert result == '[{"title": "Engineer"}]'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/rohit/resume-builder
python -m pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.config'`

- [ ] **Step 3: Create `core/config.py`**

```python
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
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]).strip()
    if text.endswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[:-1]).strip()
    return text


def extract_json_object(text: str) -> str:
    """Return the first {...} block from text, stripping markdown fences."""
    text = _strip_fences(text)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        return text[start:end]
    return text


def extract_json_array(text: str) -> str:
    """Return the first [...] block from text, stripping markdown fences."""
    text = _strip_fences(text)
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return text[start:end]
    return text
```

- [ ] **Step 4: Create `tests/__init__.py`**

Create an empty file at `tests/__init__.py`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_config.py -v
```

Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add core/config.py with shared MODEL, HUMANISE_RULES, JSON helpers"
```

---

### Task 2: Add `render_resume()` to `core/resume_builder.py`

**Files:**
- Modify: `core/resume_builder.py`

- [ ] **Step 1: Add `render_resume()` wrapper function**

Add the following function to `core/resume_builder.py` after the `write_pdf` function (before `resolve_output_path`):

```python
def render_resume(data: dict, html_path: str, pdf_path: str) -> None:
    """Render resume data dict to HTML and PDF using the bundled template."""
    template_path = str(Path(__file__).parent / "resume_template.html")
    html = render_html(data, template_path)
    write_html(html, html_path)
    write_pdf(html, pdf_path)
```

- [ ] **Step 2: Fix auto-name output directory**

Replace `resolve_output_path` so auto-named files land in `output/` instead of the project root:

```python
def resolve_output_path(args, data: dict) -> str:
    if args.auto_name:
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        name_slug = data.get("name", "resume").lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return str(output_dir / f"{name_slug}_resume_{timestamp}.html")
    return args.output
```

- [ ] **Step 3: Verify manually**

```bash
cd /Users/rohit/resume-builder
python3 core/resume_builder.py --data data/resume_data.json --auto-name --pdf
```

Expected: HTML and PDF appear in `output/`, not in the project root.

- [ ] **Step 4: Commit**

```bash
git add core/resume_builder.py
git commit -m "feat: add render_resume() wrapper; auto-name output goes to output/ dir"
```

---

### Task 3: Fix `tailor_agent.py` — remove subprocess, use config

**Files:**
- Modify: `agents/tailor_agent.py`

- [ ] **Step 1: Replace the imports block at the top of `agents/tailor_agent.py`**

Remove:
```python
import subprocess
```

Add (alongside the existing imports):
```python
import sys
sys.path.insert(0, str(ROOT / "core"))
from config import MODEL as DEFAULT_MODEL, HUMANISE_RULES, extract_json_object
import resume_builder as _resume_builder
```

Then remove the module-level constants:
```python
MODEL = "claude-sonnet-4-6"   # DELETE this line

HUMANISE_RULES = """           # DELETE this entire block (14 lines)
...
"""
```

And rename usages: add at top after imports:
```python
MODEL = DEFAULT_MODEL
```

- [ ] **Step 2: Replace the subprocess block in `tailor_agent.run()`**

Find and replace:
```python
    result = subprocess.run(
        ["python3", str(CORE_DIR / "resume_builder.py"),
         "--data", str(json_out), "--output", str(html_out), "--pdf"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ Resume PDF: {pdf_out.name}")
    else:
        print(f"  ⚠️  Resume PDF failed: {result.stderr[:200]}")
```

With:
```python
    _resume_builder.render_resume(tailored, str(html_out), str(pdf_out))
```

- [ ] **Step 3: Replace JSON extraction in `tailor_resume()` function**

Find and replace the manual strip+find block inside `tailor_resume()`:
```python
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    return json.loads(text.strip())
```

With:
```python
    text = extract_json_object(response.content[0].text)
    return json.loads(text)
```

- [ ] **Step 4: Also remove unused `CORE_DIR` constant**

Delete the line:
```python
CORE_DIR = ROOT / "core"
```

- [ ] **Step 5: Run a smoke test**

```bash
cd /Users/rohit/resume-builder
python3 -c "
import sys; sys.path.insert(0, 'agents')
import tailor_agent
print('Import OK')
print('MODEL:', tailor_agent.MODEL)
print('HUMANISE_RULES length:', len(tailor_agent.HUMANISE_RULES))
"
```

Expected: Prints `Import OK`, correct MODEL value, non-zero HUMANISE_RULES length.

- [ ] **Step 6: Commit**

```bash
git add agents/tailor_agent.py
git commit -m "fix: tailor_agent uses render_resume() directly; imports constants from core/config"
```

---

### Task 4: Fix `job_search_agent.py` — use config

**Files:**
- Modify: `agents/job_search_agent.py`

- [ ] **Step 1: Add config import**

Add after the existing imports at the top of `job_search_agent.py`:

```python
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL, extract_json_array
```

- [ ] **Step 2: Remove the local `MODEL` constant**

Delete:
```python
MODEL = "claude-sonnet-4-6"
```

Add after the imports:
```python
MODEL = DEFAULT_MODEL
```

- [ ] **Step 3: Replace JSON extraction in the `run()` function**

Find the block inside `while True:` that parses the response (around lines 244-258 in the original):

```python
            all_jobs = []
            for block in response.content:
                if not hasattr(block, "text") or not block.text.strip():
                    continue
                text = block.text.strip()
                # Strip markdown code fences
                if text.startswith("```"):
                    text = "\n".join(text.split("\n")[1:])
                if text.endswith("```"):
                    text = "\n".join(text.split("\n")[:-1])
                text = text.strip()
                # Find JSON array within the text
                start = text.find("[")
                end = text.rfind("]") + 1
                if start != -1 and end > start:
                    text = text[start:end]
                if text:
                    all_jobs = json.loads(text)
                    break
```

Replace with:
```python
            all_jobs = []
            for block in response.content:
                if not hasattr(block, "text") or not block.text.strip():
                    continue
                text = extract_json_array(block.text)
                if text:
                    all_jobs = json.loads(text)
                    break
```

- [ ] **Step 4: Smoke test**

```bash
python3 -c "
import sys; sys.path.insert(0, 'agents')
import job_search_agent
print('Import OK')
print('MODEL:', job_search_agent.MODEL)
"
```

Expected: `Import OK`, correct MODEL value.

- [ ] **Step 5: Commit**

```bash
git add agents/job_search_agent.py
git commit -m "fix: job_search_agent imports MODEL and uses extract_json_array from core/config"
```

---

### Task 5: Fix `linkedin_agent.py` — use config MODEL

**Files:**
- Modify: `agents/linkedin_agent.py`

- [ ] **Step 1: Add config import**

Add after the existing imports at the top of `linkedin_agent.py`:

```python
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL
```

- [ ] **Step 2: Remove local MODEL constant**

Delete:
```python
MODEL = "claude-sonnet-4-6"
```

Add after imports:
```python
MODEL = DEFAULT_MODEL
```

- [ ] **Step 3: Smoke test**

```bash
python3 -c "
import sys; sys.path.insert(0, 'agents')
import linkedin_agent
print('Import OK')
print('MODEL:', linkedin_agent.MODEL)
"
```

Expected: `Import OK`, correct MODEL value.

- [ ] **Step 4: Commit**

```bash
git add agents/linkedin_agent.py
git commit -m "fix: linkedin_agent imports MODEL from core/config"
```

---

### Task 6: Move test scripts to `tests/`

**Files:**
- Create: `tests/test_tailor.py` (from `test_tailor.py`)
- Create: `tests/test_job_search.py` (from `test_job_search.py`)
- Create: `tests/test_linkedin.py` (from `test_linkedin.py`)
- Delete: `test_tailor.py`, `test_job_search.py`, `test_linkedin.py` from root

- [ ] **Step 1: Create `tests/test_tailor.py`**

```python
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import tailor_agent

result = tailor_agent.run(job_url="https://www.databricks.com/company/careers/field-engineering---fe-invested-dsa/delivery-solutions-architect-8452394002")

print("Status:", result.get("status"))
if result.get("status") == "completed":
    print("PDF:", result.get("pdf_file"))
    print("Cover letter:", result.get("cover_letter_file"))
else:
    print("Reason:", result.get("reason"))
```

- [ ] **Step 2: Copy the other test scripts**

Check what `test_job_search.py` and `test_linkedin.py` contain:

```bash
cat test_job_search.py
cat test_linkedin.py
```

Create `tests/test_job_search.py` and `tests/test_linkedin.py` with the same content but update the sys.path line to:
```python
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
```

- [ ] **Step 3: Delete the root-level scripts**

```bash
rm test_tailor.py test_job_search.py test_linkedin.py
```

- [ ] **Step 4: Verify unit tests still pass**

```bash
python -m pytest tests/test_config.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/ test_tailor.py test_job_search.py test_linkedin.py
git commit -m "chore: move test scripts from root into tests/"
```

---

## Verification Checklist

After all tasks, confirm:

- [ ] `python -m pytest tests/test_config.py -v` — 6 tests pass
- [ ] `python3 -c "from core.config import MODEL, HUMANISE_RULES, extract_json_object, extract_json_array; print('OK')"` — prints OK
- [ ] `python3 core/resume_builder.py --data data/resume_data.json --auto-name --pdf` — PDF appears in `output/`, not root
- [ ] No `subprocess` import in `agents/tailor_agent.py`
- [ ] No `MODEL = "claude-sonnet-4-6"` in any agent file
- [ ] No test scripts in the project root
