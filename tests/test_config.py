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


def test_extract_json_object_no_braces():
    text = "no braces here"
    assert extract_json_object(text) == "no braces here"


def test_extract_json_object_nested():
    text = '{"a": {"b": 1}}'
    assert extract_json_object(text) == '{"a": {"b": 1}}'


def test_extract_json_array_no_brackets():
    text = "no brackets here"
    assert extract_json_array(text) == "no brackets here"


def test_extract_json_array_with_fence_trailing_space():
    text = '```  \n[{"title": "Engineer"}]\n```'
    result = extract_json_array(text)
    assert result == '[{"title": "Engineer"}]'
