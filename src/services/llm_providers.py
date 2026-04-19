"""LLM provider implementations for paper summarization."""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, List, Optional, TypedDict
from anthropic import Anthropic


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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-haiku-4-5",
    ):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)
            model: Model to use (default: claude-haiku-4-5)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key must be provided or set in ANTHROPIC_API_KEY environment variable"
            )

        self.model = model
        self.client = Anthropic(api_key=self.api_key)
        logger.info(f"Initialized Anthropic provider with model: {self.model}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text using Claude.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Generated text from Claude
        """
        logger.info(f"Generating response with {self.model}")

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            logger.info(f"Generated {len(response_text)} characters")

            return response_text

        except Exception as e:
            logger.error(f"Error generating with Anthropic: {e}")
            raise

    def stream_chat(
        self,
        messages: List[ChatTurn],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        logger.info(f"Streaming chat with {self.model} ({len(messages)} messages)")
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
