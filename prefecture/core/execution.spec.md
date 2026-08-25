# Technical Specification: Prefecture Flow Execution Strategies

This specification defines the execution models, step-dependency graph construction, and parallel scheduling behavior of the `prefecture` flow execution module.

## 1. Execution Modes

Prefecture supports two modes of flow execution:

### A. Sequential Execution (`sequential`)
- Instantiates all steps defined in the configuration in their configured order.
- Runs each step synchronously and sequentially.
- If any step fails (raises an exception), the execution halts immediately.

### B. Graph-Based Parallel Execution (`graph`)
- Instantiates all steps defined in the configuration.
- Constructs a step-to-step dependency graph mapping step objects to their required ancestor step objects.
- Detects cycles/loops and fails early if any cycle is detected.
- Executes independent steps in parallel using Prefect's native task runners.
- Uses `Task.submit(wait_for=[...])` to ensure tasks are scheduled according to their dependencies while correctly preserving Prefect context and UI logs.

---

## 2. Dependency Tracking Protocol

Operators expose their data requirements and side-effects via properties:

### A. The `dependencies` Property
- Returns a `set[str]` of absolute, normalized file paths that the operator reads or requires to run.
- If an operator returns an empty set (`set()`), it specifies that it has no external file dependencies and can run immediately.
- If an operator does not implement the `dependencies` property (or returns `None`), it falls back to depending on all steps that precede it in the flow configuration.

### B. The `outputs` Property
- Returns a `set[str]` of absolute, normalized file paths produced by the operator upon successful execution.
- If the operator produces no files (e.g. Gmail Mailer, Ntfy Sender), it returns an empty set.

---

## 3. Dependency Graph Construction

The dedicated helper `_build_dependency_graph(instantiated_steps)` translates file-level and sequential-fallback dependencies into a clean step-to-step DAG:

1.  **Producer Resolution**:
    It builds a mapping of each output file to the step object that produces it. If multiple steps declare the same output file, a `ValueError` is raised to prevent conflicts.
2.  **Raw Dependency Gathering**:
    It gathers dependencies for each step. If a step does not declare `dependencies` or returns `None`, it falls back to depending on all preceding step objects.
3.  **Step-to-Step Resolution**:
    For each step, it resolves its file dependencies (strings) to the producer step objects that produce them (using the mapping from step 1). Any dependency that is not produced by another step (e.g., a pre-existing source file or static database URL) is ignored for scheduling purposes. Any direct step-object dependencies are retained.
4.  **Result**:
    Returns a dictionary mapping `Step -> set[Step]`.

---

## 4. Loop Detection and Scheduling

### A. Cycle Detection (`_has_loop`)
Before executing any steps, the system performs cycle detection using a topological reduction (Kahn's algorithm). If a cycle is detected (i.e. steps depend on each other cyclically), a `ValueError` is raised, preventing any task execution.

### B. Native Prefect Scheduling
The parallel scheduler works by mapping tasks to Prefect futures:
1.  Iterates through the step-to-step dependency graph.
2.  Identifies steps whose dependencies have all been submitted.
3.  Submits those steps to Prefect's task runner using `step.__call__.submit(wait_for=[...])`, passing the `PrefectFuture` objects of their required dependencies. This delegates concurrent execution and synchronization entirely to Prefect.
4.  If a step's dependencies are satisfied, it is submitted; otherwise, it is skipped in the current iteration until its dependencies are submitted.
5.  If an iteration finishes without submitting any new tasks, a `ValueError` for deadlock is raised (though cycle detection should preempt this).
6.  Once all tasks are submitted, the system waits for all futures to complete (`future.result()`), which propagates any task execution exceptions and halts the flow appropriately.
