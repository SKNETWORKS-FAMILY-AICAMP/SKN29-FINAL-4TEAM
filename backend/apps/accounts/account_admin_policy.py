"""Fixed policy for synthetic-account administrators."""

ACCOUNT_ADMIN_GROUP = "T017_ACCOUNT_ADMINISTRATORS"
ACCOUNT_ADMIN_PERMISSION_CODES = frozenset(
    {
        "add_user",
        "change_user",
        "view_user",
    }
)
