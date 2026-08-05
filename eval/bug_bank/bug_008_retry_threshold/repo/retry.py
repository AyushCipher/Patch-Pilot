from config import MAX_RETRY_ATTEMPTS


def should_retry(attempt_number: int) -> bool:
    """Return True if another retry attempt should be made.

    attempt_number is 1-indexed (the attempt that just failed). Retries are
    allowed as long as attempt_number is below MAX_RETRY_ATTEMPTS.
    """
    return attempt_number < MAX_RETRY_ATTEMPTS - 1
