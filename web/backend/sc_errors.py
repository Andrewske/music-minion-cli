"""Classify SoundCloud request errors for the nightly follow-suggestion jobs.

An error about the one account asked for (404, other 4xx, a malformed or
partial payload) skips that account. Anything else (HTTP 0 = no usable
token, 401, 429, 5xx, timeouts, connection errors) means SoundCloud or the
session is unwell, so the run should stop.
"""

import re

# Errors that are about the one account asked for; any other error stops a run.
_ACCOUNT_ERROR_RE = re.compile(
    r"^(?:HTTP 4\d\d|.* not found|Invalid JSON response|Malformed response.*"
    r"|.* incomplete: .*)$"
)
# Within 4xx these are about the session, not the account.
_SERVICE_4XX = ("HTTP 401", "HTTP 429")


def is_service_error(error: str) -> bool:
    """True unless the error is about the one account (see module doc)."""
    return error.startswith(_SERVICE_4XX) or not _ACCOUNT_ERROR_RE.match(error)
