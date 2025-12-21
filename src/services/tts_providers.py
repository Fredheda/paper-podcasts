"""Text-to-Speech provider implementations."""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abstractmethod
    def generate_audio(
        self,
        text: str,
        voice: str,
        output_path: str | Path,
    ) -> str:
        """
        Generate audio from text.

        Args:
            text: Text to convert to speech
            voice: Voice to use
            output_path: Where to save audio file

        Returns:
            Path to generated audio file
        """
        pass


class OpenAITTSProvider(TTSProvider):
    """OpenAI Text-to-Speech provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
    ):
        """
        Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key (reads from OPENAI_API_KEY env var if None)
            model: TTS model (gpt-4o-mini-tts)
            voice: Default voice (alloy, echo, fable, onyx, nova, shimmer)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable."
            )

        self.model = model
        self.voice = voice

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install: pip install openai"
            )

        logger.info(f"Initialized OpenAI TTS: model={model}, voice={voice}")

    def generate_audio(
        self,
        text: str,
        voice: Optional[str] = None,
        output_path: Optional[str | Path] = None,
    ) -> str:
        """
        Generate audio using OpenAI TTS.

        Args:
            text: Text to convert to speech
            voice: Voice to use (uses default if None)
            output_path: Where to save audio

        Returns:
            Path to generated audio file
        """
        voice = voice or self.voice

        logger.info(f"Generating audio: model={self.model}, voice={voice}")

        try:
            # Generate output path if not provided
            if output_path is None:
                output_path = f"output_{voice}.mp3"

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Stream audio to file
            with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=voice,
                input=text,
            ) as response:
                response.stream_to_file(str(output_file))

            logger.info(f"Audio saved to: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            raise
