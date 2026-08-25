"""Gemini text generation tasks for Prefecture."""

import os
import pathlib
import sys

import dotenv
from google import genai
from google.genai import types
import prefect
from prefecture.core.caching import operator_cache_key
from prefect import artifacts
from prefect import cache_policies


from prefect.tasks import exponential_backoff

class GeminiGenerator:
    """Generates text using Gemini API."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        api_key: str,
        model: str = "gemini-3.1-flash-lite",
        prompt_file_name: str,
        output_file_name: str,
        use_google_search: bool = False,
    ):
        """Initializes the GeminiGenerator."""
        if not api_key:
            raise ValueError("api_key is required")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.prompt_file_name = prompt_file_name
        self.output_file_name = output_file_name
        self.use_google_search = use_google_search
        self.config_dir = config_dir
        self.run_dir = run_dir

    def __repr__(self) -> str:
        return f"GeminiGenerator(model={repr(self.model)}, prompt_file_name={repr(self.prompt_file_name)}, output_file_name={repr(self.output_file_name)}, use_google_search={self.use_google_search})"

    def cache_key(self) -> str | None:
        """Returns the cache key for this task."""
        key_parts = [
            "GeminiGenerator",
            self.model,
            self.prompt_file_name,
            self.output_file_name,
            str(self.use_google_search),
            str(self.run_dir),
        ]
        out_path = self.run_dir / self.output_file_name
        if not out_path.exists():
            return None
        return "-".join(key_parts)

    @prefect.task(name="GeminiGenerator", cache_key_fn=operator_cache_key, persist_result=True, retries=5, retry_delay_seconds=exponential_backoff(backoff_factor=2))
    def __call__(self) -> str:
        """Runs the Gemini generation task."""
        prompt_path = self.run_dir / self.prompt_file_name
        with open(prompt_path, "r") as f:
            prompt_text = f.read()
        system_instruction = ""

        tools = []
        if self.use_google_search:
            tools.append(types.Tool(googleSearch=types.GoogleSearch()))

        generate_content_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
        )

        response_stream = self.client.models.generate_content_stream(
            model=self.model,
            contents=[prompt_text],
            config=generate_content_config,
        )

        full_text = ""
        for chunk in response_stream:
            if chunk.text:
                full_text += chunk.text

        out_path = self.run_dir / self.output_file_name
        with open(out_path, "w") as f:
            f.write(full_text)

        artifacts.create_markdown_artifact(
            key="digest", markdown=full_text, description="Generated Gemini Digest"
        )

        return full_text

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



