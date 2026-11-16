import os
import uuid
from functools import wraps
from app.config import settings

if settings.langchain_tracing_v2 and settings.langchain_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

try:
    from langsmith import traceable as ls_traceable
except ImportError:
    ls_traceable = None


def trace_step(name: str, run_type: str = "chain"):
    """Decorator wrapping LangSmith @traceable when configured, no-op otherwise."""
    if ls_traceable and settings.langchain_api_key:
        return ls_traceable(name=name, run_type=run_type)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper

    return decorator


def generate_trace_id() -> str:
    return f"tr-{uuid.uuid4().hex[:12]}"
