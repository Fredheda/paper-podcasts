"""Keep provider error text away from chat clients.

A model or transport error can carry an API key (full or masked), an
organisation id, a request id, a host or a header value. The client gets one
fixed message; the log gets the real error with secret-shaped parts replaced.
The client text is a constant, never a filtered string.
"""

import re

GENERIC_CHAT_ERROR = "The assistant hit an error. Please try again."

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsk-[\w*-]{4,}"), "[redacted-key]"),
    (re.compile(r"\borg-[\w-]{8,}"), "[redacted-org]"),
    (re.compile(r"\breq_[\w-]{8,}"), "[redacted-request]"),
    (re.compile(r"https?://[^\s'\"<>]+"), "[redacted-url]"),
    (
        re.compile(
            r"(?i)\b(bearer|api-key|x-functions-key|authorization)\b[\s:=]*"
            r"(?:bearer\s+)?[^\s'\",;]+"
        ),
        r"\1 [redacted-credential]",
    ),
)


def redact(text: str) -> str:
    """Replace secret-shaped substrings; generous on purpose (log lines only)."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def describe(exc: BaseException) -> str:
    """Type and message, with exception groups flattened (httpx and anyio raise them)."""
    if isinstance(exc, BaseExceptionGroup):
        inner = "; ".join(describe(e) for e in exc.exceptions)
        return f"{type(exc).__name__}({len(exc.exceptions)}): {inner}"
    return f"{type(exc).__name__}: {exc}"
