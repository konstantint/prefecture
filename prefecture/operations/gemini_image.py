"""Gemini image generation tasks for Prefecture."""

import os
import pathlib
import sys
import mimetypes

import dotenv
from google import genai
from google.genai import types
import prefect
from prefect.tasks import exponential_backoff
from prefecture.core.caching import operator_cache_key
from prefect import artifacts
from prefect import cache_policies

VALID_ASPECT_RATIOS = {
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4",
    "4:1", "4:3", "4:5", "5:4", "8:1", "9:16",
    "16:9", "21:9"
}

class GeminiImageGenerator:
    """Generates images using Gemini API."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        api_key: str,
        model: str = "gemini-3.1-flash-image",
        prompt: str = None,
        prompt_file_name: str = None,
        output_file_name: str,
        aspect_ratio: str = None,
    ):
        """Initializes the GeminiImageGenerator.

        Args:
            config_dir: The directory where configuration files are located.
            run_dir: The directory where execution artifacts are written.
            api_key: Gemini API key.
            model: Gemini model to use for image generation.
            prompt: Inline prompt text. Alternative to prompt_file_name.
            prompt_file_name: Name of the file containing the prompt (relative to run_dir).
            output_file_name: Name of the generated image file.
            aspect_ratio: Optional aspect ratio for the generated image.
              Must be one of: '1:1', '1:4', '1:8', '2:3', '3:2', '3:4', '4:1', '4:3',
              '4:5', '5:4', '8:1', '9:16', '16:9', or '21:9'. If None, the default
              model aspect ratio will be used.
        """
        if not api_key:
            raise ValueError("api_key is required")
        if aspect_ratio is not None and aspect_ratio not in VALID_ASPECT_RATIOS:
            raise ValueError(
                f"Invalid aspect_ratio '{aspect_ratio}'. Must be one of: {sorted(list(VALID_ASPECT_RATIOS))}"
            )
        if not prompt and not prompt_file_name:
            raise ValueError("Either 'prompt' or 'prompt_file_name' must be provided.")
            
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.prompt = prompt
        self.prompt_file_name = prompt_file_name
        self.output_file_name = output_file_name
        self.aspect_ratio = aspect_ratio
        self.config_dir = config_dir
        self.run_dir = run_dir

    def __repr__(self) -> str:
        return f"GeminiImageGenerator(model={repr(self.model)}, prompt_file_name={repr(self.prompt_file_name)}, prompt={repr(self.prompt)}, output_file_name={repr(self.output_file_name)}, aspect_ratio={repr(self.aspect_ratio)})"

    @prefect.task(name="GeminiImageGenerator", cache_policy=cache_policies.NO_CACHE, retries=5, retry_delay_seconds=exponential_backoff(backoff_factor=2))
    def __call__(self) -> pathlib.Path:
        """Runs the Gemini image generation task."""
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
        
        image_config_args = {
            "image_size": "1K",
        }
        if self.aspect_ratio:
            image_config_args["aspect_ratio"] = self.aspect_ratio

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="MINIMAL",
            ),
            image_config=types.ImageConfig(**image_config_args),
            response_modalities=[
                "IMAGE",
                "TEXT",
            ],
        )

        # Using a dummy run_dir
        run_dir = self.run_dir

        response_stream = self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=generate_content_config,
        )

        out_path = run_dir / self.output_file_name
        final_file_path = out_path

        for chunk in response_stream:
            if chunk.parts is None:
                continue
            if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
                inline_data = chunk.parts[0].inline_data
                data_buffer = inline_data.data
                
                final_file_path = out_path

                with open(final_file_path, "wb") as f:
                    f.write(data_buffer)
                print(f"File saved to: {final_file_path}")
            else:
                if text := chunk.text:
                    print(text)

        import re
        filename = final_file_path.name
        artifact_key = re.sub(r'[^a-zA-Z0-9-]', '-', filename).lower()
        artifact_key = re.sub(r'-+', '-', artifact_key).strip('-')
        if not artifact_key:
            artifact_key = "gemini-image"

        artifacts.create_image_artifact(
            image_url=final_file_path.absolute().as_uri(),
            key=artifact_key,
            description="Generated Gemini Image"
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
        
    # Using a dummy run_dir
    run_dir = pathlib.Path(".")
    generator = GeminiImageGenerator(
        config_dir=pathlib.Path("."),
        run_dir=run_dir,
        api_key=api_key,
        prompt="Generate an image depicting true, absolute, impeccable beauty",
        aspect_ratio="16:9",
        output_file_name="impeccable_beauty.png"
    )
    
    generator()
