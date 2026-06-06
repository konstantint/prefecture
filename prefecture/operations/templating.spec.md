# Specification: Templating and Context Loading

This document describes how templates are rendered and how context is loaded in `prefecture`.

## 1. Overview
Template rendering is handled by the `Jinja2Templater` class inside `prefecture/operations/templating.py`. It combines a Jinja2 template with dynamic context loaded by `ContextLoader` implementations and static parameters.

## 2. Jinja2Templater
`Jinja2Templater` is a callable component (decorated with `@task` for Prefect).

### Configuration
It accepts the following parameters in `__init__`:
- `config_dir`: Path to the directory containing the configuration file. Used to resolve relative template paths.
- `template_file`: Path to the Jinja2 template file.
- `output_file_name`: Optional. If provided, the rendered template will be written to this file in the `run_dir`.
- `context_loaders`: List of context loader configurations.
- `params`: Static parameters to pass to the template.

### Execution
When called with `run_dir`:
1.  It iterates over `context_loaders`.
2.  For each loader, it looks up the registered class in the registry.
3.  It instantiates the class with `params` provided in the configuration.
4.  It calls the instance with `run_dir`.
5.  The output is added to the template context under the `assign_to` key.
6.  It merges static `params` into the context.
7.  It renders the template.
8.  It saves the output if `output_file_name` was provided.
9.  It creates a Prefect markdown artifact named after the sanitized stem of `output_file_name` (falling back to "jinja2" if not provided).

## 3. Context Loaders
Context loaders are classes that implement the `ContextLoader` protocol.

### Protocol
```python
class ContextLoader:
    def __call__(self, run_dir: Path) -> str:
        raise NotImplementedError
```

### Registration
Loaders must be registered using `register_loader(name, class)`. This is typically done on module import.

### `RunDirFileLoader`
Loads the contents of a file from the current or a previous run directory.
Registered name: `"run_dir_file"`

Constructor parameters:
- `file_name`: Name of the file to load.
- `days_ago`: Number of days to look back. Default is 0 (current run dir).
- `fail_on_error`: If True, raises `ValueError` if file cannot be loaded. If False, returns `None`. Default is False.
- `load_json`: If True, parses the loaded file content as JSON. Default is False.

### `SqlAlchemyLoader`
Loads data from a database using SQLAlchemy.
Registered name: `"sqlalchemy"`

Constructor parameters:
- `db_url`: The SQLAlchemy database URL (e.g. `sqlite:////path/to/db`).
- `query`: The SQL query to execute.

The loader returns a list of dictionaries, where each dictionary represents a row in the result set (mapping column names to values).

### `DatetimeNowLoader`
Loads the current local datetime.
Registered name: `"datetime_now"`

Accepts no arguments. Returns the current local `datetime.datetime` object.


## 4. YAML Configuration Example
```yaml
steps:
  - jinja2:
      template_file: "../templates/prompt.j2"
      output_file_name: "prompt.md"
      context_loaders:
        - type: "run_dir_file"
          params:
            file_name: "digest.md"
            days_ago: 7
          assign_to: "last_weeks_digest"
      params:
        additional_info: "Some extra context"
```
