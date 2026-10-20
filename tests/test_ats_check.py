import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ats_check import check_ats, extract_pdf_text


def test_check_ats_terms_and_headings():
    text = "Test User\nt.user@example.com  +44 7700 900123\nEXPERIENCE\nBuilt Kafka pipelines\nSkills\nKafka, AWS"
    result = check_ats(text, ["Kafka", "event-driven architecture", "kafka"])
    assert result["contact"] == {"email": True, "phone": True}
    assert result["headings"]["experience"] is True
    assert result["headings"]["skills"] is True
    assert result["headings"]["summary"] is False
    assert result["terms"] == [
        {"term": "Kafka", "present": True},
        {"term": "event-driven architecture", "present": False},
    ]
    assert result["text"] == text


def test_headings_match_template_labels():
    result = check_ats("PROFILE\nWORK EXPERIENCE\nSKILLS\nEDUCATION", [])
    assert result["headings"] == {"summary": True, "experience": True, "skills": True, "education": True}


def test_extract_pdf_text_from_real_render(tmp_path):
    from core.resume_builder import render_resume
    pdf = tmp_path / "r.pdf"
    render_resume({"name": "Test User", "summary": "Kafka specialist", "experience": []}, str(tmp_path / "r.html"), str(pdf))
    assert "Kafka" in extract_pdf_text(str(pdf))
