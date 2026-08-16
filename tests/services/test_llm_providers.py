"""Tests for the OpenAI-backed LLM provider."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.llm_providers import OpenAIProvider


def _mock_completion(text: str):
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _mock_stream(chunks: list[str]):
    events = []
    for text in chunks:
        delta = MagicMock()
        delta.content = text
        choice = MagicMock()
        choice.delta = delta
        chunk = MagicMock()
        chunk.choices = [choice]
        events.append(chunk)
    return iter(events)


def test_generate_returns_message_content():
    with patch("src.services.llm_providers.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_completion("hello world")

        provider = OpenAIProvider(api_key="sk-test", model="gpt-5.6-luna")
        result = provider.generate(prompt="Summarize this paper.", max_tokens=100, temperature=0.5)

        assert result == "hello world"
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-5.6-luna"
        assert kwargs["max_completion_tokens"] == 100
        # temperature is NOT forwarded -- gpt-5.6-luna (and other current
        # reasoning-tier models) reject any value other than the default (1).
        assert "temperature" not in kwargs
        assert kwargs["messages"] == [{"role": "user", "content": "Summarize this paper."}]


def test_generate_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OpenAIProvider(api_key=None)


def test_stream_chat_yields_content_deltas():
    with patch("src.services.llm_providers.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_stream(["Hel", "lo"])

        provider = OpenAIProvider(api_key="sk-test")
        chunks = list(
            provider.stream_chat(
                messages=[{"role": "user", "content": "hi"}],
                system="You are helpful.",
            )
        )

        assert chunks == ["Hel", "lo"]
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["messages"][0] == {"role": "system", "content": "You are helpful."}
        assert kwargs["stream"] is True
        assert "temperature" not in kwargs
