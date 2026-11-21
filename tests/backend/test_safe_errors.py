"""Tests for the error redaction used by the chat route's log line."""

import pytest

from backend.app.safe_errors import GENERIC_CHAT_ERROR, describe, redact


def test_generic_chat_error_is_the_documented_text():
    assert GENERIC_CHAT_ERROR == "The assistant hit an error. Please try again."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("key sk-proj-PLANTEDKEY1234 here", "key [redacted-key] here"),
        (
            "Incorrect API key provided: sk-proj-****abcd.",
            "Incorrect API key provided: [redacted-key].",
        ),
        ("organization org-PLANTEDORG", "organization [redacted-org]"),
        ("request req_PLANTEDREQ", "request [redacted-request]"),
        (
            "at https://planted.invalid/v1/chat?code=sk-PLANTEDQUERYKEY now",
            "at [redacted-url] now",
        ),
        ("x-functions-key: PLANTEDFUNCKEY", "x-functions-key [redacted-credential]"),
        ("Authorization: Bearer PLANTEDTOKEN", "Authorization [redacted-credential]"),
    ],
)
def test_redact_replaces_each_secret_shape(text, expected):
    assert redact(text) == expected


@pytest.mark.parametrize(
    "text", ["", "The model is overloaded.", "Error code: 429 - rate limited"]
)
def test_redact_leaves_plain_text_alone(text):
    assert redact(text) == text


def test_describe_names_the_type_when_the_message_is_empty():
    assert describe(RuntimeError("")) == "RuntimeError: "


def test_describe_flattens_exception_groups():
    group = ExceptionGroup(
        "transport", [RuntimeError("at https://planted.invalid/x"), ValueError("x")]
    )
    text = redact(describe(group))
    assert text.startswith("ExceptionGroup(2): RuntimeError: ")
    assert "[redacted-url]" in text
    assert "ValueError: x" in text
    assert "planted.invalid" not in text
