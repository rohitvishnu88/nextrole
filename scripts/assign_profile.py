"""Give a profile to another user: python3 -m scripts.assign_profile <slug> <email>

The user must have signed in at least once, so their account exists.
"""
import sys
from typing import List

from a2a import db, ownership


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    slug, email = argv
    user = db.get_user_by_email(email)
    if user is None:
        print(f"No user with email {email} — they need to sign in once first.")
        return 1
    profiles = ownership.load_meta()
    profile = next((p for p in profiles if p["slug"] == slug), None)
    if profile is None:
        print(f"No profile with slug {slug}.")
        return 1
    profile["owner_user_id"] = user["id"]
    ownership.save_meta(profiles)
    print(f"Profile {slug} now belongs to {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
