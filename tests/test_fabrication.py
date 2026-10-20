import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.fabrication import find_fabrications

BASE = {
    "name": "Test User",
    "email": "t@example.com",
    "phone": "07700 900123",
    "summary": "Integration architect working with Kafka and AWS.",
    "experience": [
        {
            "title": "Data Architect",
            "company": "Acme",
            "start_date": "Jan 2020",
            "end_date": "Present",
            "description": ["Cut costs across the integration estate", "Built Kafka pipelines on AWS"],
        }
    ],
    "skills": {"Streaming": ["Kafka"], "Cloud": ["AWS Glue"]},
}


def tailored_with(**changes):
    t = copy.deepcopy(BASE)
    for path, value in changes.items():
        if path == "bullet0":
            t["experience"][0]["description"][0] = value
        elif path == "skills":
            t["skills"] = value
        elif path == "title":
            t["experience"][0]["title"] = value
    return t


def test_new_metric_flagged():
    flags = find_fabrications(BASE, tailored_with(bullet0="Cut costs across the integration estate by 40%"))
    assert flags == [{"location": "experience[0].description[0]", "kind": "number", "text": "40%"}]


def test_reworded_bullet_not_flagged():
    flags = find_fabrications(BASE, tailored_with(bullet0="Reduced costs across the integration estate"))
    assert flags == []


def test_new_skill_flagged():
    flags = find_fabrications(BASE, tailored_with(skills={"Streaming": ["Kafka"], "Cloud": ["AWS Glue", "Terraform"]}))
    assert flags == [{"location": "skills", "kind": "skill", "text": "Terraform"}]


def test_new_tech_name_flagged():
    flags = find_fabrications(BASE, tailored_with(bullet0="Migrated the integration estate to PySpark"))
    assert {"location": "experience[0].description[0]", "kind": "name", "text": "PySpark"} in flags


def test_title_change_flagged_as_identity():
    flags = find_fabrications(BASE, tailored_with(title="Principal Data Architect"))
    assert {"location": "experience[0]", "kind": "identity", "text": "title: Principal Data Architect"} in flags


def test_missing_sections_do_not_crash():
    assert find_fabrications({"name": "A"}, {"name": "A", "experience": []}) == []
