"""Templating utilities for Prefecture."""

import pathlib

import jinja2


def render_template(template_path: pathlib.Path, context: dict) -> str:
    """Renders a Jinja2 template from an absolute path."""
    template_dir = template_path.parent
    template_name = template_path.name

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


