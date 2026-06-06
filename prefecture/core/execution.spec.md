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
- Executes independent steps in parallel using a `ThreadPoolExecutor`.
- Tracks completed steps dynamically, scheduling dependent steps as soon as their dependencies have successfully completed.

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

### B. Dynamic Thread Pool Scheduling
The parallel scheduler works in a loop using a `ThreadPoolExecutor`:
1.  Identifies all steps in the dependency graph that have zero remaining dependencies and are not currently running.
2.  Removes those steps from the graph and submits them to the thread pool.
3.  Waits for the next running step to finish.
4.  Once a step completes, its result is checked (exceptions are propagated, halting the flow).
5.  The completed step is removed from the dependency sets of all remaining steps.
6.  The loop repeats until the graph is empty and all jobs are complete.
