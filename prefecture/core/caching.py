"""Caching utilities for prefecture operations."""

def operator_cache_key(context, parameters):
    """
    Extracts the component instance from parameters and calls its cache_key() method.
    If the component doesn't implement cache_key, returns None (no caching).
    """
    task_instance = parameters.get("self")
    if task_instance and hasattr(task_instance, "cache_key"):
        return task_instance.cache_key()
    return None
