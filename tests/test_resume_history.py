import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import a2a.resume_history as rh


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    p = tmp_path / "profiles" / "test-user"
    p.mkdir(parents=True)
    return p


def test_load_current_missing_file_returns_none(profiles_dir):
    assert rh.load_current("test-user") is None


def test_save_and_load_current_round_trip(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    assert rh.load_current("test-user") == {"name": "Ada"}


def test_load_history_missing_file_returns_empty_list(profiles_dir):
    assert rh.load_history("test-user") == []


def test_push_version_noop_when_no_current_resume(profiles_dir):
    rh.push_version("test-user", "Some change")
    assert rh.load_history("test-user") == []


def test_push_version_snapshots_current_state(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    rh.push_version("test-user", "Added Experience: Engineer")
    versions = rh.load_history("test-user")
    assert len(versions) == 1
    assert versions[0]["change_summary"] == "Added Experience: Engineer"
    assert versions[0]["data"] == {"name": "Ada"}
    assert "id" in versions[0] and "timestamp" in versions[0]


def test_push_version_caps_at_max(profiles_dir):
    rh.save_current("test-user", {"n": 0})
    for i in range(1, rh.MAX_HISTORY_VERSIONS + 5):
        rh.save_current("test-user", {"n": i})
        rh.push_version("test-user", f"Change {i}")
    versions = rh.load_history("test-user")
    assert len(versions) == rh.MAX_HISTORY_VERSIONS
    assert versions[0]["change_summary"] == "Change 5"
    assert versions[-1]["change_summary"] == f"Change {rh.MAX_HISTORY_VERSIONS + 4}"


def test_get_version_found_and_not_found(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    rh.push_version("test-user", "Snapshot A")
    version_id = rh.load_history("test-user")[0]["id"]
    assert rh.get_version("test-user", version_id)["change_summary"] == "Snapshot A"
    assert rh.get_version("test-user", "nonexistent") is None


def test_restore_version_pushes_current_then_restores(profiles_dir):
    rh.save_current("test-user", {"name": "Version A"})
    rh.push_version("test-user", "Snapshot A")
    version_a_id = rh.load_history("test-user")[0]["id"]

    rh.save_current("test-user", {"name": "Version B"})

    restored = rh.restore_version("test-user", version_a_id)

    assert restored == {"name": "Version A"}
    assert rh.load_current("test-user") == {"name": "Version A"}
    versions = rh.load_history("test-user")
    assert len(versions) == 2
    assert versions[-1]["data"] == {"name": "Version B"}
    assert versions[-1]["change_summary"].startswith("Restored version from")


def test_restore_version_unknown_id_returns_none(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    assert rh.restore_version("test-user", "nonexistent") is None


def test_resume_file_rejects_path_traversal(profiles_dir):
    with pytest.raises(ValueError):
        rh._resume_file("../../../../tmp/evil")


def test_resume_file_rejects_slash(profiles_dir):
    with pytest.raises(ValueError):
        rh._resume_file("test-user/evil")


def test_history_file_rejects_path_traversal(profiles_dir):
    with pytest.raises(ValueError):
        rh._history_file("../../../../tmp/evil")


def test_history_file_rejects_slash(profiles_dir):
    with pytest.raises(ValueError):
        rh._history_file("test-user/evil")


def test_load_current_rejects_path_traversal(profiles_dir):
    with pytest.raises(ValueError):
        rh.load_current("..")


def test_save_current_rejects_path_traversal(profiles_dir):
    with pytest.raises(ValueError):
        rh.save_current("..", {"name": "Evil"})
