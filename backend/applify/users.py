MVP_USER_ID = 1


def get_current_user_id() -> int:
    """The MVP has exactly one user and no login (N3); replaced by auth later."""
    return MVP_USER_ID
