"""Flows for the Prefecture system."""

import datetime
import pathlib

import prefect
from prefect import runtime

from prefecture.core import config
from prefecture.core import execution


def generate_run_name(**kwargs) -> str:
    """Generates a run name based on the config file."""
    config_file = kwargs.get("config_file") or runtime.flow_run.parameters.get(
        "config_file"
    )

    if not config_file:
        return f"run-flow-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    cfg = config.load_config(config_file)
    name = cfg.get("name", "run-flow")
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{name}-{run_id}"


@prefect.flow(name="prefecture", log_prints=True, flow_run_name=generate_run_name)
def run_flow(config_file: str):
    """Runs the flow based on the provided config file."""
    cfg = config.load_config(config_file)

    name = cfg["name"]

    # run_dir is data/<name>/<date>
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    run_dir = pathlib.Path("data") / name / today_str
    run_dir.mkdir(parents=True, exist_ok=True)

    config_dir = pathlib.Path(config_file).resolve().parent

    with execution.pythonpath_prepended(cfg.get("prepend_to_pythonpath", [])):
        execution.sequential(cfg, run_dir, config_dir)



