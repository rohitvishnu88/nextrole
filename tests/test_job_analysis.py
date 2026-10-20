import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent))

import pytest

import job_analysis
from fakes import FakeClient

RESUME = {"name": "Test User", "summary": "Integration architect", "experience": []}
JD = "Senior Integration Architect. " * 40

ANALYSIS = {
    "what_it_really_is": "An integration lead role.",
    "problem_being_solved": "Their middleware estate is sprawling.",
    "search_terms": ["integration architect", "MuleSoft"],
    "suspicious": [],
    "requirements": [
        {"text": "MuleSoft", "filter_likelihood": "high", "why": "named twice", "key_terms": ["MuleSoft"],
         "meets": "yes", "evidence": "Led MuleSoft programme", "interview_answer": ""},
        {"text": "Golang", "filter_likelihood": "low", "why": "boilerplate", "key_terms": ["Go"],
         "meets": "no", "evidence": "", "interview_answer": "Not used it."},
    ],
    "gaps_that_matter": ["a", "b", "c", "d"],
    "gaps_that_dont": ["Golang"],
    "verdict": "strong fit",
    "verdict_reason": "Core stack matches.",
    "left_off": ["Did you lead the Kafka migration?"],
}


def test_analysis_id_stable_and_resume_sensitive():
    a = job_analysis.make_analysis_id("Senior   Architect\n\nLondon", RESUME)
    b = job_analysis.make_analysis_id("senior architect london", RESUME)
    c = job_analysis.make_analysis_id("senior architect london", dict(RESUME, summary="changed"))
    assert a == b
    assert a != c
    assert job_analysis.ANALYSIS_ID_RE.match(a)


def test_analyse_job_uses_verbatim_prompts_and_scores():
    client = FakeClient(json.dumps(ANALYSIS))
    result = job_analysis.analyse_job(client, RESUME, JD)
    prompt = client.prompt()
    assert "Rank the requirements by how likely each is to be a real filter." in prompt
    assert "Be blunt." in prompt
    assert result["match_score"] == 75
    assert result["gaps_that_matter"] == ["a", "b", "c"]
    assert result["analysis_id"] == job_analysis.make_analysis_id(JD, RESUME)


def test_short_text_raises():
    client = FakeClient()
    with pytest.raises(job_analysis.JobTextTooShort):
        job_analysis.analyse_job(client, RESUME, "x" * 50)
    assert client.calls == []


def test_malformed_model_output_normalised():
    client = FakeClient(json.dumps({"requirements": "oops", "verdict": "amazing"}))
    result = job_analysis.analyse_job(client, RESUME, JD)
    assert result["requirements"] == []
    assert result["match_score"] is None
    assert result["verdict"] == "genuine stretch"
    for field in ("what_it_really_is", "problem_being_solved", "search_terms", "suspicious",
                  "gaps_that_matter", "gaps_that_dont", "verdict_reason", "left_off"):
        assert field in result


def test_get_or_create_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(job_analysis, "ROOT", tmp_path)
    client = FakeClient(json.dumps(ANALYSIS))
    first = job_analysis.get_or_create_analysis(client, "rohit", RESUME, JD)
    second = job_analysis.get_or_create_analysis(client, "rohit", RESUME, JD)
    assert len(client.calls) == 1
    assert first == second
    assert job_analysis.load_analysis("rohit", first["analysis_id"]) == first


def test_analysis_path_rejects_bad_id():
    with pytest.raises(ValueError):
        job_analysis.analysis_path("rohit", "../../x")
    with pytest.raises(ValueError):
        job_analysis.analysis_path("../x", "0123456789abcdef")


def test_same_url_reuses_analysis_even_if_fetched_text_differs(tmp_path, monkeypatch):
    monkeypatch.setattr(job_analysis, "ROOT", tmp_path)
    client = FakeClient(json.dumps(ANALYSIS), json.dumps(ANALYSIS))
    url = "https://jobs.lever.co/acme/1"
    first = job_analysis.get_or_create_analysis(client, "rohit", RESUME, JD, source_url=url)
    second = job_analysis.get_or_create_analysis(client, "rohit", RESUME, JD + " Apply now.", source_url=url)
    assert len(client.calls) == 1
    assert first["analysis_id"] == second["analysis_id"]


def test_shell_text_under_new_minimum_raises():
    client = FakeClient()
    shell = "Sign in to apply. Accept cookies. Workday careers home. " * 10  # ~560 chars of boilerplate
    with pytest.raises(job_analysis.JobTextTooShort):
        job_analysis.analyse_job(client, RESUME, shell)
    assert client.calls == []
