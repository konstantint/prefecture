"""Prompt generation utilities for Prefecture."""

import datetime
import os
import pathlib

import prefect
from prefect import artifacts
from prefect import cache_policies
from prefecture import templating


class ContextLoader:
    """Base class for context loaders."""

    def __call__(self, run_dir: pathlib.Path) -> str:
        raise NotImplementedError


_registry = {}


def register_loader(name: str, loader_cls: type):
    """Registers a context loader class."""
    _registry[name] = loader_cls


class RunDirFileLoader(ContextLoader):
    """Loads the contents of a file in the run_dir."""

    def __init__(
        self, file_name: str, days_ago: int = 0, fail_on_error: bool = False
    ):
        """Initializes the RunDirFileLoader."""
        self.file_name = file_name
        self.days_ago = days_ago
        self.fail_on_error = fail_on_error

    def __call__(self, run_dir: pathlib.Path) -> str | None:
        """Loads content from file."""
        if self.days_ago == 0:
            target_path = run_dir / self.file_name
        else:
            try:
                current_date = datetime.datetime.strptime(
                    run_dir.name, "%Y-%m-%d"
                )
                prev_date = current_date - datetime.timedelta(
                    days=self.days_ago
                )
                prev_date_str = prev_date.strftime("%Y-%m-%d")
                target_path = run_dir.parent / prev_date_str / self.file_name
            except ValueError:
                if self.fail_on_error:
                    raise ValueError(
                        f"Could not parse date from run_dir name: {run_dir.name}"
                    )
                return None

        try:
            with open(target_path, "r") as f:
                return f.read()
        except Exception as e:
            if self.fail_on_error:
                raise ValueError(f"could not load {target_path}: {e}")
            return None


register_loader("run_dir_file", RunDirFileLoader)


class PromptGenerator:
    """Generates prompts using templates and context loaders."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        template_file: str,
        output_file_name: str | None = None,
        context_loaders: list | None = None,
        params: dict | None = None,
    ):
        """Initializes the PromptGenerator."""
        self.config_dir = config_dir
        self.template_file = template_file
        self.output_file_name = output_file_name
        self.context_loaders = context_loaders or []
        self.params = params or {}

    @prefect.task(name="PromptGenerator")
    def __call__(self, run_dir: pathlib.Path) -> str:
        """Runs the prompt generation task."""
        context = {}

        for loader_cfg in self.context_loaders:
            loader_type = loader_cfg["type"]
            assign_to = loader_cfg.get("assign_to", loader_type)

            if loader_type in _registry:
                loader_cls = _registry[loader_type]
                loader_params = loader_cfg.get("params", {})
                loader_instance = loader_cls(**loader_params)
                data = loader_instance(run_dir)
                context.update({assign_to: data})
            else:
                print(f"Warning: Unknown context loader type: {loader_type}")
        context.update(self.params)
        template_path = pathlib.Path(self.template_file)
        if not template_path.is_absolute():
            template_path = self.config_dir / template_path

        content = templating.render_template(template_path, context)

        if self.output_file_name:
            out_path = run_dir / self.output_file_name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                f.write(content)

        artifacts.create_markdown_artifact(
            key="prompt", markdown=content, description="Generated Prompt"
        )

        return content
