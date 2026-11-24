class TransportError(Exception):
    """A core answered with a fault, or could not be reached."""

    def __init__(self, status, body=None):
        super().__init__(f"transport fault {status}: {body}")
        self.status = status
        self.body = body


class ExportError(Exception):
    """A complete, correct statement could not be produced for this member."""

    def __init__(self, message, account_id=None):
        super().__init__(message)
        self.account_id = account_id
