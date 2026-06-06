"""Templating utilities for Prefecture."""

import datetime
import json
import os
import pathlib
import re

import jinja2
import prefect
import sqlalchemy
from prefect import artifacts
from prefect import cache_policies


def render_template(template_path: pathlib.Path, context: dict) -> str:
    """Renders a Jinja2 template from an absolute path."""
    template_dir = template_path.parent
    template_name = template_path.name

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


class ContextLoader:
    """Base class for context loaders."""

    def __call__(self, run_dir: pathlib.Path) -> object:
        raise NotImplementedError


_registry = {}


def register_loader(name: str, loader_cls: type):
    """Registers a context loader class."""
    _registry[name] = loader_cls


class RunDirFileLoader(ContextLoader):
    """Loads the contents of a file in the run_dir."""

    def __init__(
        self,
        file_name: str,
        days_ago: int = 0,
        fail_on_error: bool = False,
        load_json: bool = False,
    ):
        """Initializes the RunDirFileLoader."""
        self.file_name = file_name
        self.days_ago = days_ago
        self.fail_on_error = fail_on_error
        self.load_json = load_json

    def __call__(self, run_dir: pathlib.Path) -> object:
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

        content = None
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            if self.fail_on_error:
                raise ValueError(f"could not load {target_path}: {e}")
            return None

        if self.load_json:
            return json.loads(content)
        return content


class SqlAlchemyLoader(ContextLoader):
    """Loads data from a database using SQLAlchemy."""

    def __init__(self, db_url: str, query: str):
        """Initializes the SqlAlchemyLoader."""
        self.db_url = db_url
        self.query = query

    def __call__(self, run_dir: pathlib.Path) -> object:
        """Executes the query and returns results as a list of dicts."""
        engine = sqlalchemy.create_engine(self.db_url)
        try:
            with engine.connect() as connection:
                result = connection.execute(sqlalchemy.text(self.query))
                return [dict(row) for row in result.mappings()]
        except Exception as e:
            raise ValueError(f"Database query failed: {e}")


class DatetimeNowLoader(ContextLoader):
    """Loads the current datetime."""

    def __init__(self):
        """Initializes the DatetimeNowLoader."""
        pass

    def __call__(self, run_dir: pathlib.Path) -> object:
        """Returns the current local datetime."""
        return datetime.datetime.now()


register_loader("run_dir_file", RunDirFileLoader)
register_loader("sqlalchemy", SqlAlchemyLoader)
register_loader("datetime_now", DatetimeNowLoader)


class Jinja2Templater:
    """Renders Jinja2 templates with context loaders and parameters."""

    def __init__(
        self,
        *,
        config_dir: pathlib.Path,
        run_dir: pathlib.Path,
        template_file: str,
        output_file_name: str | None = None,
        context_loaders: list | None = None,
        params: dict | None = None,
    ):
        """Initializes the Jinja2Templater."""
        self.config_dir = config_dir
        self.run_dir = run_dir
        self.template_file = template_file
        self.output_file_name = output_file_name
        self.context_loaders = context_loaders or []
        self.params = params or {}

    @prefect.task(name="Jinja2Templater")
    def __call__(self) -> str:
        """Runs the Jinja2 templating task."""
        context = {}

        for loader_cfg in self.context_loaders:
            loader_type = loader_cfg["type"]
            assign_to = loader_cfg.get("assign_to", loader_type)

            if loader_type in _registry:
                loader_cls = _registry[loader_type]
                loader_params = loader_cfg.get("params", {})
                loader_instance = loader_cls(**loader_params)
                data = loader_instance(self.run_dir)
                context.update({assign_to: data})
            else:
                print(f"Warning: Unknown context loader type: {loader_type}")
        context.update(self.params)
        template_path = pathlib.Path(self.template_file)
        if not template_path.is_absolute():
            template_path = self.config_dir / template_path

        content = render_template(template_path, context)

        if self.output_file_name:
            out_path = self.run_dir / self.output_file_name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                f.write(content)

        artifact_key = "jinja2"
        if self.output_file_name:
            stem = pathlib.Path(self.output_file_name).stem
            artifact_key = re.sub(r'[^a-zA-Z0-9-]', '-', stem).lower()
            artifact_key = re.sub(r'-+', '-', artifact_key).strip('-')
            if not artifact_key:
                artifact_key = "jinja2"

        artifacts.create_markdown_artifact(
            key=artifact_key, markdown=content, description="Rendered Template"
        )

        return content
