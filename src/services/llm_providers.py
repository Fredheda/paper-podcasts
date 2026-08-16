"""LLM provider implementations for paper summarization."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Iterator, List, Optional, TypedDict
from openai import OpenAI


class ChatTurn(TypedDict):
    role: str
    content: str

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text from the LLM.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text from the LLM
        """
        pass

    @abstractmethod
    def stream_chat(
        self,
        messages: List[ChatTurn],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Stream a multi-turn chat completion, yielding text chunks."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI chat completions provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.6-luna",
    ):
        """
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: Model to use (default: gpt-5.6-luna -- OpenAI's current
                cost-optimized tier, matching the role claude-haiku-4-5 played
                before this: one-shot summarization, not complex reasoning)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY environment variable"
            )

        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"Initialized OpenAI provider with model: {self.model}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text using OpenAI's Chat Completions API.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text
        """
        logger.info(f"Generating response with {self.model}")

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                # `max_completion_tokens` is OpenAI's current recommended param
                # (covers reasoning tokens too) -- `max_tokens` is legacy.
                max_completion_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = completion.choices[0].message.content or ""
            logger.info(f"Generated {len(response_text)} characters")

            return response_text

        except Exception as e:
            logger.error(f"Error generating with OpenAI: {e}")
            raise

    def stream_chat(
        self,
        messages: List[ChatTurn],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        logger.info(f"Streaming chat with {self.model} ({len(messages)} messages)")

        chat_messages: List[dict] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        stream = self.client.chat.completions.create(
            model=self.model,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            messages=chat_messages,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
