"""LLM provider implementations for paper summarization."""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)
            model: Model to use (default: claude-sonnet-4-20250514)
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


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abstractmethod
    def generate_audio(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate audio from text.

        Args:
            text: The text to convert to speech
            voice: Voice to use for synthesis
            model: TTS model to use
            output_path: Path where audio file should be saved

        Returns:
            Path to the generated audio file
        """
        pass


class OpenAITTSProvider(TTSProvider):
    """OpenAI Text-to-Speech provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "tts-1",
        voice: str = "alloy",
    ):
        """
        Initialize the OpenAI TTS provider.

        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: TTS model to use (tts-1 or tts-1-hd)
            voice: Default voice (alloy, echo, fable, onyx, nova, shimmer)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY environment variable"
            )

        self.model = model
        self.voice = voice

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )

        logger.info(f"Initialized OpenAI TTS provider with model: {self.model}, voice: {self.voice}")

    def generate_audio(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate audio using OpenAI TTS.

        Args:
            text: The text to convert to speech
            voice: Voice to use (if None, uses default from __init__)
            model: TTS model to use (if None, uses default from __init__)
            output_path: Path where audio file should be saved

        Returns:
            Path to the generated audio file
        """
        voice = voice or self.voice
        model = model or self.model

        logger.info(f"Generating audio with model: {model}, voice: {voice}")

        try:
            # Generate output path if not provided
            if output_path is None:
                output_path = f"output_{voice}.mp3"

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Use streaming response to properly stream audio to file
            with self.client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
            ) as response:
                response.stream_to_file(str(output_file))

            logger.info(f"Audio saved to: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Error generating audio with OpenAI: {e}")
            raise
