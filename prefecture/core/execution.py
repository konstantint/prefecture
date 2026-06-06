"""Execution logic for Prefecture flows."""

import concurrent.futures
import contextlib
import importlib
import pathlib
import sys
from typing import Any, Dict, List, Set

STEP_MAP = {
    "jinja2": "prefecture.operations.templating.Jinja2Templater",
    "gemini": "prefecture.operations.gemini.GeminiGenerator",
    "gemini_image": "prefecture.operations.gemini_image.GeminiImageGenerator",
    "ntfy": "prefecture.operations.ntfy.NtfySender",
    "mailer": "prefecture.operations.mailer.GmailMailer",
    "google_chat_reader": "prefecture.operations.google_chat_reader.GoogleChatReader",
    "copyfile": "prefecture.operations.copyfile.CopyFile",
}


@contextlib.contextmanager
def pythonpath_prepended(paths: List[str]):
    """Context manager to temporarily prepend paths to sys.path."""
    original_path = list(sys.path)
    try:
        for p in reversed(paths):
            abs_path = str(pathlib.Path(p).resolve())
            if abs_path in sys.path:
                sys.path.remove(abs_path)
            sys.path.insert(0, abs_path)
        yield
    finally:
        sys.path[:] = original_path


def sequential(
    cfg: Dict[str, Any], run_dir: pathlib.Path, config_dir: pathlib.Path
):
    """Executes the steps in the configuration sequentially."""
    steps = _instantiate_steps(cfg, run_dir, config_dir)
    for step_instance in steps:
        step_instance()


def _instantiate_steps(
    cfg: Dict[str, Any], run_dir: pathlib.Path, config_dir: pathlib.Path
) -> List[Any]:
    """Instantiates all steps defined in the configuration."""
    instantiated_steps = []
    for step in cfg.get("steps", []):
        for step_type, step_cfg in step.items():
            class_path = STEP_MAP.get(step_type, step_type)
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            step_class = getattr(module, class_name)

            step_cfg = step_cfg or {}
            step_instance = step_class(
                config_dir=config_dir, run_dir=run_dir, **step_cfg
            )
            instantiated_steps.append(step_instance)
    return instantiated_steps


def _build_dependency_graph(instantiated_steps: List[Any]) -> Dict[Any, Set[Any]]:
    """Creates a step-to-step dependency graph mapping each step to the steps it depends on."""
    # 1. Compute a "producer graph" mapping each output (absolute filename) to the step that produces it.
    producer_graph = {}
    for step in instantiated_steps:
        if hasattr(step, "outputs") and step.outputs:
            for out in step.outputs:
                if out in producer_graph:
                    raise ValueError(f"Output file {out} is produced by multiple steps.")
                producer_graph[out] = step

    # 2. For each step, get its raw dependencies (files or steps)
    raw_deps = {}
    for i, step in enumerate(instantiated_steps):
        if hasattr(step, "dependencies"):
            try:
                deps = step.dependencies
            except AttributeError:
                deps = None
        else:
            deps = None

        if deps is not None:
            raw_deps[step] = deps
        else:
            raw_deps[step] = set(instantiated_steps[:i])

    # 3. Resolve file/step dependencies to step-to-step dependencies
    step_deps = {}
    for step, deps in raw_deps.items():
        resolved_deps = set()
        for dep in deps:
            if isinstance(dep, str):
                if dep in producer_graph:
                    resolved_deps.add(producer_graph[dep])
            else:
                resolved_deps.add(dep)
        step_deps[step] = resolved_deps

    return step_deps


def _has_loop(graph: Dict[Any, Set[Any]]) -> bool:
    """Detects loops in a step-to-step dependency graph using Kahn's algorithm."""
    g = {node: set(deps) for node, deps in graph.items()}

    while True:
        zero_dep_nodes = [node for node, deps in g.items() if not deps]
        if not zero_dep_nodes:
            break
        for node in zero_dep_nodes:
            del g[node]
            for remaining_node in g:
                g[remaining_node].discard(node)

    return len(g) > 0


def graph(
    cfg: Dict[str, Any], run_dir: pathlib.Path, config_dir: pathlib.Path
) -> None:
    """Executes the steps in parallel using a dependency graph and a ThreadPoolExecutor."""
    steps = _instantiate_steps(cfg, run_dir, config_dir)
    deps_graph = _build_dependency_graph(steps)

    if _has_loop(deps_graph):
        raise ValueError("The dependency graph contains a loop.")

    # We will mutate a copy of the graph as steps complete
    g = {node: set(deps) for node, deps in deps_graph.items()}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        running_futures = {}

        while g or running_futures:
            # 1. Find all steps with no dependencies that are not already running
            to_submit = [
                step for step, deps in g.items()
                if not deps and step not in running_futures.values()
            ]

            # 2. Submit them to the executor
            for step in to_submit:
                del g[step]
                future = executor.submit(step)
                running_futures[future] = step

            if not running_futures:
                if g:
                    raise ValueError("Deadlock detected in execution graph.")
                break

            # 3. Wait for the next job to complete
            done, _ = concurrent.futures.wait(
                running_futures.keys(),
                return_when=concurrent.futures.FIRST_COMPLETED
            )

            # 4. Process completed steps
            for future in done:
                completed_step = running_futures.pop(future)
                # Propagate any execution exception
                future.result()

                # Remove this step from the dependencies of all remaining steps
                for remaining_step in g:
                    g[remaining_step].discard(completed_step)


