from a2a import auth
from a2a.auth import User

OWNER = User("u-owner", "owner@example.com", "Owner", "", True)
FRIEND = User("u-friend", "friend@example.com", "Friend", "", False)
OTHER = User("u-other", "other@example.com", "Other", "", False)


def sign_in(app, user: User) -> None:
    app.dependency_overrides[auth.current_user] = lambda: user
