import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent))

import tailor_agent
from fakes import FakeClient

BASE = {
    "name": "Test User",
    "summary": "Integration architect.",
    "experience": [{
        "title": "Architect", "company": "Acme", "start_date": "2020", "end_date": "Present",
        "description": ["Built Kafka pipelines", "Cut integration costs"],
    }],
    "skills": {"Streaming": ["Kafka"]},
}


def test_realign_changes_uses_final_wording():
    final = json.loads(json.dumps(BASE))
    final["experience"][0]["description"][1] = "Cut integration costs (humanised)"
    changes = [{"location": "experience[0].description[1]", "kind": "reworded", "before": "x",
                "after": "pre-humanise text", "needs_confirmation": False, "reason": ""}]
    result = tailor_agent.realign_changes(changes, final)
    assert result[0]["after"] == "Cut integration costs (humanised)"
    assert "stale" not in result[0]


def test_realign_marks_unresolvable_location_stale():
    changes = [{"location": "experience[3].description[0]", "kind": "reworded", "before": "",
                "after": "kept", "needs_confirmation": True, "reason": ""}]
    result = tailor_agent.realign_changes(changes, BASE)
    assert result[0]["after"] == "kept"
    assert result[0]["stale"] is True


def test_tailor_prompt_contains_rules_verbatim():
    client = FakeClient(json.dumps({"resume": BASE, "changes": []}))
    out = tailor_agent.tailor_resume(client, BASE, "Job ad text", analysis=None)
    prompt = client.prompt()
    assert "You may not:" in prompt
    assert "stuff in keywords, or list a skill I could not be tested on" in prompt
    assert "At the end, list every change you made and mark the ones I need to confirm are accurate." in prompt
    assert out == {"resume": BASE, "changes": []}


def test_tailor_prompt_targets_real_filters_from_analysis():
    analysis = {"search_terms": ["event-driven"], "requirements": [
        {"text": "Kafka at scale", "filter_likelihood": "high", "key_terms": ["Kafka"]},
        {"text": "Golang", "filter_likelihood": "filler", "key_terms": ["Go"]},
    ]}
    client = FakeClient(json.dumps({"resume": BASE, "changes": []}))
    tailor_agent.tailor_resume(client, BASE, "Job ad text", analysis=analysis)
    prompt = client.prompt()
    assert "Kafka at scale" in prompt
    assert "Golang" not in prompt


def test_ats_terms_from_analysis():
    analysis = {"search_terms": ["integration architect", "Kafka"], "requirements": [
        {"filter_likelihood": "high", "key_terms": ["Kafka", "MuleSoft"]},
        {"filter_likelihood": "low", "key_terms": ["Go"]},
    ]}
    assert tailor_agent.ats_terms(analysis) == ["integration architect", "Kafka", "Kafka", "MuleSoft"]
    assert tailor_agent.ats_terms(None) == []


def _write_run(tmp_path, tailored):
    paths = {name: tmp_path / f"{name}.json" for name in ("json", "base", "fit")}
    paths["json"].write_text(json.dumps(tailored))
    paths["base"].write_text(json.dumps(BASE))
    paths["fit"].write_text(json.dumps({"analysis_id": None, "changes": [{"location": "summary"}],
                                        "fabrication_flags": [], "ats": {}, "ats_terms": ["Kafka"]}))
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    return paths, pdf


def test_recheck_fit_flags_hand_added_metric(tmp_path, monkeypatch):
    tailored = json.loads(json.dumps(BASE))
    tailored["experience"][0]["description"][1] = "Cut integration costs by 30%"
    paths, pdf = _write_run(tmp_path, tailored)
    monkeypatch.setattr(tailor_agent, "extract_pdf_text", lambda p: "Cut integration costs by 30% Kafka")

    fit = tailor_agent.recheck_fit(str(paths["json"]), str(pdf), str(paths["base"]), str(paths["fit"]))

    assert {"location": "experience[0].description[1]", "kind": "number", "text": "30%"} in fit["fabrication_flags"]
    assert fit["ats"]["terms"] == [{"term": "Kafka", "present": True}]
    assert fit["changes"] == [{"location": "summary"}]
    assert json.loads(paths["fit"].read_text()) == fit


def test_recheck_fit_survives_missing_sections(tmp_path, monkeypatch):
    paths, pdf = _write_run(tmp_path, {"name": "Test User"})
    monkeypatch.setattr(tailor_agent, "extract_pdf_text", lambda p: "")
    fit = tailor_agent.recheck_fit(str(paths["json"]), str(pdf), str(paths["base"]), str(paths["fit"]))
    assert fit["fabrication_flags"] == []


def test_run_writes_fit_and_base_sidecars(tmp_path, monkeypatch):
    jd = "Senior Integration Architect, Kafka at scale. " * 20
    analysis = {"search_terms": ["Kafka"], "verdict": "strong fit", "requirements": [
        {"text": "Kafka", "filter_likelihood": "high", "key_terms": ["Kafka"], "meets": "yes"}]}
    tailored = json.loads(json.dumps(BASE))
    tailored["experience"][0]["description"][1] = "Cut integration costs by 40%"
    client = FakeClient(
        json.dumps(analysis),
        json.dumps({"resume": tailored, "changes": [
            {"location": "experience[0].description[1]", "kind": "expanded", "before": "Cut integration costs",
             "after": "pre-humanise", "needs_confirmation": True, "reason": "added metric"}]}),
        "Integration architect.",
        "1. Built Kafka pipelines\n2. Cut integration costs by 40%",
        "Cover letter draft",
        "Cover letter final",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(tailor_agent.anthropic, "Anthropic", lambda api_key: client)
    monkeypatch.setattr(tailor_agent, "load_resume", lambda slug: BASE)
    monkeypatch.setattr(tailor_agent, "ROOT", tmp_path)
    monkeypatch.setattr(tailor_agent.job_analysis, "ROOT", tmp_path)

    result = tailor_agent.run(jd_text=jd, profile_slug="test-user")

    assert result["status"] == "completed"
    assert json.loads(Path(result["base_file"]).read_text()) == BASE
    fit = json.loads(Path(result["fit_file"]).read_text())
    assert fit["analysis_id"] == result["analysis_id"]
    assert fit["changes"][0]["after"] == "Cut integration costs by 40%"
    assert {"location": "experience[0].description[1]", "kind": "number", "text": "40%"} in fit["fabrication_flags"]
    assert fit["ats"]["terms"] == [{"term": "Kafka", "present": True}]
