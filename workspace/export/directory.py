"""The account directory: which accounts a member holds and which core is home to each."""


class StaticDirectory:
    """In-memory directory, used by tests and by the nightly job's snapshot loader."""

    def __init__(self, members, home_cores):
        self._members = dict(members)        # member_id -> [account_id, ...] in statement order
        self._home_cores = dict(home_cores)  # account_id -> "KESTREL" | "TERN" | "MIGRATING"

    def accounts_for(self, member_id):
        return list(self._members[member_id])

    def home_core(self, account_id):
        """Raises KeyError when the directory has no record of the account."""
        return self._home_cores[account_id]
