"""LangSmith Tracing and Observability integration for GraphSupport AI.

Provides transparent, fail-safe tracing for:
- Root Agent Turns (reasoning lifecycle, customer context, tokens, latency)
- Controlled Tool Executions (tool name, arguments, results, security boundaries)
- LLM Provider Invocations (provider, model, prompt messages, tool schemas)

When LANGSMITH_TRACING is false or unconfigured, tracing operates in zero-overhead
no-op mode so local execution and unit tests remain fast, deterministic, and offline.
"""

import contextlib
import logging
import os
import time
from collections.abc import Generator
from typing import Any

from graphsupport.config import get_settings
from graphsupport.core.security import redact_sensitive_text

logger = logging.getLogger("graphsupport.core.tracing")

# Try importing langsmith; if missing or disabled, gracefully degrade
try:
    import langsmith
    from langsmith.run_trees import RunTree

    LANGSMITH_AVAILABLE = True
except ImportError:
    langsmith = None  # type: ignore[assignment]
    RunTree = None  # type: ignore[assignment, misc]
    LANGSMITH_AVAILABLE = False


def is_tracing_active() -> bool:
    """Check whether LangSmith tracing is enabled in settings and client is ready."""
    try:
        settings = get_settings()
        return bool(LANGSMITH_AVAILABLE and settings.is_langsmith_configured)
    except Exception:
        return False


def setup_langsmith_environment() -> None:
    """Export standard LangSmith environment variables if configured in Settings."""
    try:
        settings = get_settings()
        if settings.langsmith_tracing and settings.langsmith_api_key:
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.get_secret_value()
            os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
            os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    except Exception as err:
        logger.debug("Failed to set LangSmith environment variables: %s", err)


_client_instance: Any = None


def get_langsmith_client() -> Any:
    """Return a configured LangSmith Client instance if enabled."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    if not is_tracing_active() or langsmith is None:
        return None

    try:
        settings = get_settings()
        api_key = (
            settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else None
        )
        _client_instance = langsmith.Client(
            api_key=api_key,
            api_url=settings.langsmith_endpoint,
        )
        return _client_instance
    except Exception as err:
        logger.debug("Failed to initialize LangSmith client: %s", err)
        return None


@contextlib.contextmanager
def trace_agent_turn(
    customer_id: str,
    message: str,
    conversation_id: str | None = None,
    ticket_id: str | None = None,
    product_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager to trace an entire agent turn in LangSmith.

    Yields a mutable context dict where callers can attach results, tokens, or artifacts.
    """
    ctx: dict[str, Any] = {
        "output": None,
        "tools_executed": [],
        "iterations": 0,
    }
    start_time = time.perf_counter()

    if not is_tracing_active() or RunTree is None:
        yield ctx
        return

    setup_langsmith_environment()
    settings = get_settings()
    client = get_langsmith_client()

    run_tags = ["agent", "graphsupport", "support-turn"]
    if tags:
        run_tags.extend(tags)

    run_metadata = {
        "customer_id": customer_id,
        "conversation_id": conversation_id,
        "ticket_id": ticket_id,
        "product_id": product_id,
        "project": settings.langsmith_project,
        **(metadata or {}),
    }

    run_tree = None
    try:
        run_tree = RunTree(
            name="graphsupport.agent_turn",
            run_type="chain",
            client=client,
            inputs={
                "customer_id": customer_id,
                "message": redact_sensitive_text(message),
                "conversation_id": conversation_id,
                "focused_ticket_id": ticket_id,
                "focused_product_id": product_id,
            },
            tags=run_tags,
            extra={"metadata": run_metadata},
            project_name=settings.langsmith_project,
        )
        run_tree.post()
    except Exception as err:
        logger.debug("LangSmith agent turn trace init failed: %s", err)
        run_tree = None

    try:
        yield ctx
        if run_tree:
            duration = time.perf_counter() - start_time
            outputs = {
                "response": redact_sensitive_text(str(ctx.get("output") or "")),
                "tools_executed": ctx.get("tools_executed", []),
                "iterations": ctx.get("iterations", 0),
                "duration_seconds": round(duration, 4),
            }
            run_tree.end(outputs=outputs)
            run_tree.patch()
    except Exception as exc:
        if run_tree:
            run_tree.end(error=str(exc))
            try:
                run_tree.patch()
            except Exception:
                pass
        raise


@contextlib.contextmanager
def trace_tool_execution(
    tool_name: str,
    arguments: dict[str, Any],
    correlation_id: str | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager to trace a tool execution as a child span."""
    ctx: dict[str, Any] = {"result": None, "success": True}
    start_time = time.perf_counter()

    if not is_tracing_active() or RunTree is None:
        yield ctx
        return

    setup_langsmith_environment()
    settings = get_settings()
    client = get_langsmith_client()
    run_tree = None
    try:
        run_tree = RunTree(
            name=f"tool:{tool_name}",
            run_type="tool",
            client=client,
            inputs={
                "tool_name": tool_name,
                "arguments": arguments,
                "correlation_id": correlation_id,
            },
            tags=["tool", "graphsupport", tool_name],
            project_name=settings.langsmith_project,
        )
        run_tree.post()
    except Exception as err:
        logger.debug("LangSmith tool trace init failed: %s", err)
        run_tree = None

    try:
        yield ctx
        if run_tree:
            duration = time.perf_counter() - start_time
            run_tree.end(
                outputs={
                    "result": ctx.get("result"),
                    "success": ctx.get("success", True),
                    "duration_seconds": round(duration, 4),
                }
            )
            run_tree.patch()
    except Exception as exc:
        if run_tree:
            run_tree.end(error=str(exc))
            try:
                run_tree.patch()
            except Exception:
                pass
        raise


@contextlib.contextmanager
def trace_llm_generation(
    provider_name: str,
    model_name: str,
    messages_count: int,
    tools_count: int,
) -> Generator[dict[str, Any], None, None]:
    """Context manager to trace an LLM provider call."""
    ctx: dict[str, Any] = {"response": None, "usage": {}}
    start_time = time.perf_counter()

    if not is_tracing_active() or RunTree is None:
        yield ctx
        return

    setup_langsmith_environment()
    settings = get_settings()
    client = get_langsmith_client()
    run_tree = None
    try:
        run_tree = RunTree(
            name=f"llm:{provider_name}:{model_name}",
            run_type="llm",
            client=client,
            inputs={
                "provider": provider_name,
                "model": model_name,
                "messages_count": messages_count,
                "tools_count": tools_count,
            },
            tags=["llm", provider_name, model_name],
            project_name=settings.langsmith_project,
        )
        run_tree.post()
    except Exception as err:
        logger.debug("LangSmith LLM trace init failed: %s", err)
        run_tree = None

    try:
        yield ctx
        if run_tree:
            duration = time.perf_counter() - start_time
            run_tree.end(
                outputs={
                    "finish_reason": getattr(ctx.get("response"), "finish_reason", "stop"),
                    "tool_calls_count": len(getattr(ctx.get("response"), "tool_calls", []) or []),
                    "usage": ctx.get("usage", {}),
                    "duration_seconds": round(duration, 4),
                }
            )
            run_tree.patch()
    except Exception as exc:
        if run_tree:
            run_tree.end(error=str(exc))
            try:
                run_tree.patch()
            except Exception:
                pass
        raise
