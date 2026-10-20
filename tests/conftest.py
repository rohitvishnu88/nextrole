import os

import pytest

# These two are manual scripts, not tests: importing them makes live, paid Claude calls.
collect_ignore = ["test_tailor.py", "test_linkedin.py"]

# a2a.server refuses to start without SESSION_SECRET outside tests.
os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    # Metered AI calls write to the usage ledger; never let a test touch data/applications.db.
    monkeypatch.setenv("APPLICATIONS_DB", str(tmp_path / "test.db"))
