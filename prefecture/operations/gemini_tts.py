"""Gemini TTS generation tasks for Prefecture."""

import os
import pathlib
import re
import struct
import sys

import dotenv
from google import genai
from google.genai import types
import prefect
from prefect import artifacts
from prefect import cache_policies


class WavFileWriterStream:
    """Writes raw PCM audio samples to a WAV file."""

    def __init__(
        self, filepath: pathlib.Path, mime_type: str = "audio/L16;rate=24000"
    ):
        self.filepath = filepath
        self.mime_type = mime_type
        # parse mime type
        self.params = self._parse_audio_mime_type(mime_type)
        self.bits_per_sample = self.params["bits_per_sample"]
        self.sample_rate = self.params["rate"]
        self.num_channels = 1

        self.f = None
        self.data_size = 0

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self):
        self.f = open(self.filepath, "wb")
        # Write temporary header (44 bytes). We will overwrite it when closing.
        self.f.write(b"\x00" * 44)
        self.data_size = 0

    def write_samples(self, data: bytes):
        if not self.f:
            raise RuntimeError("File not opened. Call open() first.")
        self.f.write(data)
        self.data_size += len(data)

    def close(self):
        if not self.f:
            return
        try:
            # Calculate WAV header parameters
            bytes_per_sample = self.bits_per_sample // 8
            block_align = self.num_channels * bytes_per_sample
            byte_rate = self.sample_rate * block_align
            chunk_size = (
                36 + self.data_size
            )  # 36 bytes for header fields before data chunk size

            header = struct.pack(
                "<4sI4s4sIHHIIHH4sI",
                b"RIFF",  # ChunkID
                chunk_size,  # ChunkSize (total file size - 8)
                b"WAVE",  # Format
                b"fmt ",  # Subchunk1ID
                16,  # Subchunk1Size (16 for PCM)
                1,  # AudioFormat (1 for PCM)
                self.num_channels,  # NumChannels
                self.sample_rate,  # SampleRate
                byte_rate,  # ByteRate
                block_align,  # BlockAlign
                self.bits_per_sample,  # BitsPerSample
                b"data",  # Subchunk2ID
                self.data_size,  # Subchunk2Size (size of audio data)
            )

            self.f.seek(0)
            self.f.write(header)
        finally:
            self.f.close()
            self.f = None

    def _parse_audio_mime_type(self, mime_type: str) -> dict[str, int]:
        bits_per_sample = 16
        rate = 24000

        # Extract rate from parameters
        parts = mime_type.split(";")
        for param in parts:
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
                except (ValueError, IndexError):
                    pass
            elif param.startswith("audio/L"):
                try:
                    bits_per_sample = int(param.split("L", 1)[1])
                except (ValueError, IndexError):
                    pass

        return {"bits_per_sample": bits_per_sample, "rate": rate}


class GeminiTtsGenerator:
    """Generates audio using Gemini TTS API."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        api_key: str,
        model: str = "gemini-3.1-flash-tts-preview",
        prompt: str = None,
        prompt_file_name: str = None,
        output_file_name: str,
        voice: str = "Algieba",
        timeout: int = 300,
    ):
        """Initializes the GeminiTtsGenerator.

        Args:
            config_dir: The directory where configuration files are located.
            run_dir: The directory where execution artifacts are written.
            api_key: Gemini API key.
            model: Gemini model to use for TTS generation.
            prompt: Inline prompt text. Alternative to prompt_file_name.
            prompt_file_name: Name of the file containing the prompt (relative
              to run_dir).
            output_file_name: Name of the generated audio file.
            voice: Name of the prebuilt voice to use (e.g. 'Algieba').
            timeout: Timeout in seconds for API calls.
        """
        if not api_key:
            raise ValueError("api_key is required")
        if not prompt and not prompt_file_name:
            raise ValueError("Either 'prompt' or 'prompt_file_name' must be provided.")

        http_options = None
        if timeout:
            http_options = types.HttpOptions(timeout=timeout * 1000)

        self.client = genai.Client(api_key=api_key, http_options=http_options)
        self.model = model
        self.prompt = prompt
        self.prompt_file_name = prompt_file_name
        self.output_file_name = output_file_name
        self.voice = voice
        self.config_dir = config_dir
        self.run_dir = run_dir

    def __repr__(self) -> str:
        return f"GeminiTtsGenerator(model={repr(self.model)}, voice={repr(self.voice)}, prompt_file_name={repr(self.prompt_file_name)}, prompt={repr(self.prompt)}, output_file_name={repr(self.output_file_name)})"

    @prefect.task(name="GeminiTtsGenerator", cache_policy=cache_policies.NO_CACHE)
    def __call__(self) -> pathlib.Path:
        """Runs the Gemini TTS generation task."""
        if self.prompt:
            prompt_text = self.prompt
        elif self.prompt_file_name:
            prompt_path = self.run_dir / self.prompt_file_name
            with open(prompt_path, "r") as f:
                prompt_text = f.read()
        else:
            raise ValueError("Either prompt or prompt_file_name must be provided.")

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt_text),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            response_modalities=[
                "audio",
            ],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice
                    )
                )
            ),
        )

        response_stream = self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=generate_content_config,
        )

        out_path = self.run_dir / self.output_file_name

        final_file_path = out_path

        wav_writer = None
        is_raw_pcm = False

        try:
            for chunk in response_stream:
                if chunk.parts is None:
                    continue
                if (
                    chunk.parts[0].inline_data
                    and chunk.parts[0].inline_data.data
                ):
                    inline_data = chunk.parts[0].inline_data
                    data_buffer = inline_data.data
                    mime_type = inline_data.mime_type

                    if wav_writer is None:
                        is_raw_pcm = (
                            "audio/L" in mime_type or "rate=" in mime_type
                        )
                        if is_raw_pcm:
                            wav_writer = WavFileWriterStream(
                                final_file_path, mime_type=mime_type
                            )
                            wav_writer.open()
                        else:
                            wav_writer = open(final_file_path, "wb")

                    if is_raw_pcm:
                        wav_writer.write_samples(data_buffer)
                    else:
                        wav_writer.write(data_buffer)
                else:
                    if text := chunk.text:
                        print(text)
        finally:
            if wav_writer:
                wav_writer.close()

        print(f"File saved to: {final_file_path}")

        filename = final_file_path.name
        artifact_key = re.sub(r"[^a-zA-Z0-9-]", "-", filename).lower()
        artifact_key = re.sub(r"-+", "-", artifact_key).strip("-")
        if not artifact_key:
            artifact_key = "gemini-tts"

        artifacts.create_link_artifact(
            link=final_file_path.absolute().as_uri(),
            link_text=filename,
            key=artifact_key,
            description="Generated Gemini Audio (TTS)",
        )

        return final_file_path

    @property
    def dependencies(self) -> set[str]:
        if getattr(self, "prompt_file_name", None):
            path = pathlib.Path(self.prompt_file_name)
            if not path.is_absolute():
                path = self.run_dir / path
            return {str(path.resolve())}
        return set()

    @property
    def outputs(self) -> set[str]:
        if getattr(self, "output_file_name", None):
            path = pathlib.Path(self.output_file_name)
            if not path.is_absolute():
                path = self.run_dir / path
            return {str(path.resolve())}
        return set()


if __name__ == "__main__":
    dotenv.load_dotenv(override=True)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    run_dir = pathlib.Path(".")
    generator = GeminiTtsGenerator(
        config_dir=pathlib.Path("."),
        run_dir=run_dir,
        api_key=api_key,
        prompt="Welcome to your weekly briefing. It is a pleasure to be with you again.",
        voice="Algieba",
        output_file_name="test_briefing.wav",
    )

    generator()
