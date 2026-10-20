import os

# a2a.server refuses to start without SESSION_SECRET outside tests.
os.environ.setdefault("TESTING", "1")
