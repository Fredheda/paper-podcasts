"""Service for generating audio from text."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .tts_providers import TTSProvider
from ..models.audio_result import AudioResult

logger = logging.getLogger(__name__)


def clean_text_for_tts(text: str) -> str:
    """
    Remove markdown and HTML formatting from text for TTS.
    Args:
        text: Text with potential markdown/HTML formatting
    Returns:
        Clean text suitable for text-to-speech
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove markdown headers (# ## ### etc.)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return text


class AudioService:
    """Service for generating podcast audio from text."""

    def __init__(self, provider: TTSProvider):
        """
        Initialize audio service.

        Args:
            provider: TTS provider to use for audio generation
        """
        self.provider = provider
        logger.info(f"Initialized AudioService with {provider.__class__.__name__}")

    def generate_audio(
        self,
        text: str,
        output_dir: str | Path,
        base_filename: str,
        voice: Optional[str] = None,
    ) -> AudioResult:
        """
        Generate audio from text and save to disk.

        Args:
            text: Text to convert to speech
            output_dir: Directory where audio should be saved
            base_filename: Base name for audio file (without extension)
            voice: Voice to use (uses provider default if None)

        Returns:
            AudioResult with audio path and metadata

        Example:
            service = AudioService(provider=OpenAITTSProvider())
            result = service.generate_audio(
                text="This is a summary of the paper.",
                output_dir="output/audio",
                base_filename="paper_summary",
                voice="alloy"
            )
            print(f"Audio saved to: {result.audio_path}")
        """
        logger.info(f"Generating audio for {base_filename}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output path
        audio_filename = f"{base_filename}.mp3"
        audio_path = output_dir / audio_filename

        # Generate audio
        self.provider.generate_audio(
            text=clean_text_for_tts(text),
            voice=voice,
            output_path=audio_path,
        )

        logger.info(f"Generated audio: {audio_path}")

        return AudioResult(
            audio_path=audio_path,
            generated_at=datetime.now(),
        )
