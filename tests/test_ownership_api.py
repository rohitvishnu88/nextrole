import importlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth_helpers import FRIEND, OTHER, OWNER, sign_in


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    d = tmp_path / "profiles"
    monkeypatch.setenv("PROFILES_DIR", str(d))
    monkeypatch.setenv("APPLICATIONS_DB", str(tmp_path / "app.db"))
    meta = [
        {"id": "1", "name": "Friend", "slug": "friend", "created_at": "t", "owner_user_id": FRIEND.id},
        {"id": "2", "name": "Other", "slug": "other", "created_at": "t", "owner_user_id": OTHER.id},
        {"id": "3", "name": "Legacy", "slug": "legacy", "created_at": "t"},
    ]
    d.mkdir(parents=True)
    (d / "profiles.json").write_text(json.dumps(meta))
    for p in meta:
        (d / p["slug"]).mkdir()
        (d / p["slug"] / "resume_data.json").write_text(json.dumps({"name": p["name"], "experience": []}))
    return d


def make_app(user):
    import a2a.routes.profiles as profiles
    import a2a.routes.resume_versions as versions
    import a2a.routes.search_brief as brief
    for m in (profiles, versions, brief):
        importlib.reload(m)
    app = FastAPI()
    for m in (profiles, versions, brief):
        app.include_router(m.router)
    sign_in(app, user)
    return TestClient(app)


def test_friend_sees_only_own_profiles(profiles_dir):
    c = make_app(FRIEND)
    assert [p["slug"] for p in c.get("/api/profiles").json()] == ["friend"]


@pytest.mark.parametrize("method,path", [
    ("get", "/api/profiles/other/resume"),
    ("patch", "/api/profiles/other"),
    ("delete", "/api/profiles/other"),
    ("get", "/api/profiles/other/resume/history"),
    ("post", "/api/profiles/other/resume/sections/summary/draft"),
    ("post", "/api/profiles/other/resume/sections/summary/apply"),
    ("get", "/api/profiles/other/search-brief"),
    ("post", "/api/profiles/other/search-brief/generate"),
])
def test_other_users_profile_is_404(profiles_dir, method, path):
    c = make_app(FRIEND)
    body = {"name": "x", "instruction": "x", "action": "edit", "value": "x"}
    resp = getattr(c, method)(path, json=body) if method in ("post", "patch") else getattr(c, method)(path)
    assert resp.status_code == 404
    assert (profiles_dir / "other").exists()


def test_unowned_profile_visible_to_owner_only(profiles_dir):
    assert make_app(OWNER).get("/api/profiles/legacy/resume").status_code == 200
    assert make_app(FRIEND).get("/api/profiles/legacy/resume").status_code == 404
    assert "legacy" in [p["slug"] for p in make_app(OWNER).get("/api/profiles").json()]


def test_create_with_taken_slug_gets_unique_slug(profiles_dir):
    c = make_app(OTHER)
    before = (profiles_dir / "friend" / "resume_data.json").read_text()
    created = c.post("/api/profiles", json={"name": "Friend"}).json()
    assert created["slug"] == "friend-2"
    assert created["owner_user_id"] == OTHER.id
    assert (profiles_dir / "friend" / "resume_data.json").read_text() == before


def test_profile_limit_for_friend_not_owner(profiles_dir):
    c = make_app(FRIEND)
    for name in ("Two", "Three"):
        assert c.post("/api/profiles", json={"name": name}).status_code == 200
    resp = c.post("/api/profiles", json={"name": "Four"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "profile_limit"
    owner = make_app(OWNER)
    for name in ("A", "B", "C", "D"):
        assert owner.post("/api/profiles", json={"name": name}).status_code == 200


def test_assign_unowned_to_owner(profiles_dir):
    from a2a import ownership
    assert ownership.assign_unowned_to(OWNER.id) == 1
    meta = {p["slug"]: p for p in ownership.load_meta()}
    assert meta["legacy"]["owner_user_id"] == OWNER.id
    assert meta["friend"]["owner_user_id"] == FRIEND.id
