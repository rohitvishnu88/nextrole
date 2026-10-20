import os

import pytest

# These two are manual scripts, not tests: importing them makes live, paid Claude calls.
collect_ignore = ["test_tailor.py", "test_linkedin.py"]

# a2a.server refuses to start without SESSION_SECRET outside tests.
os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True)
def _isolated_data(tmp_path, monkeypatch):
    # Tests must never touch real data: metered calls write to the usage ledger, and the
    # owner's sign-in claims unowned profiles in profiles.json. Tests that need these
    # locations set their own on top of these.
    monkeypatch.setenv("APPLICATIONS_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "isolated-profiles"))
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path / "isolated-output"))
