"""Unit tests for LangSmith tracing and observability integration.

Verifies:
1. Zero-overhead no-op behavior when LangSmith tracing is disabled.
2. Context manager yields and context dict updates.
3. Exception safety: application exceptions are faithfully propagated.
4. Active tracing lifecycle: mock RunTree instantiation, span tagging, and end patches.
"""

from unittest.mock import MagicMock, patch

import pytest

from graphsupport.config.settings import Settings
from graphsupport.core.tracing import (
    is_tracing_active,
    setup_langsmith_environment,
    trace_agent_turn,
    trace_llm_generation,
    trace_tool_execution,
)


def test_tracing_inactive_by_default() -> None:
    """Verify tracing is inactive when not explicitly configured."""
    settings = Settings(_env_file=None, langsmith_tracing=False)
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        assert is_tracing_active() is False


def test_tracing_active_when_configured() -> None:
    """Verify tracing reports active when enabled with valid API key."""
    settings = Settings(
        _env_file=None,
        langsmith_tracing=True,
        langsmith_api_key="lsv2_pt_test_secret_key",
    )
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        assert is_tracing_active() is True


def test_noop_agent_turn_tracing() -> None:
    """Verify trace_agent_turn runs cleanly in no-op mode without network requests."""
    settings = Settings(_env_file=None, langsmith_tracing=False)
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        with trace_agent_turn(
            customer_id="cust-101",
            message="Need help resetting password",
            conversation_id="conv-1",
        ) as ctx:
            assert isinstance(ctx, dict)
            ctx["output"] = "Password reset instructions sent."
            ctx["iterations"] = 1

        assert ctx["output"] == "Password reset instructions sent."


def test_noop_tool_execution_tracing() -> None:
    """Verify trace_tool_execution runs cleanly in no-op mode."""
    settings = Settings(_env_file=None, langsmith_tracing=False)
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        with trace_tool_execution(
            tool_name="get_ticket_status",
            arguments={"ticket_id": "tkt-1"},
            correlation_id="req-123",
        ) as ctx:
            assert isinstance(ctx, dict)
            ctx["result"] = {"status": "open"}
            ctx["success"] = True

        assert ctx["success"] is True


def test_noop_llm_generation_tracing() -> None:
    """Verify trace_llm_generation runs cleanly in no-op mode."""
    settings = Settings(_env_file=None, langsmith_tracing=False)
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        with trace_llm_generation(
            provider_name="sarvam",
            model_name="sarvam-105b",
            messages_count=3,
            tools_count=2,
        ) as ctx:
            assert isinstance(ctx, dict)
            ctx["usage"] = {"total_tokens": 120}

        assert ctx["usage"]["total_tokens"] == 120


def test_tracing_exception_propagation() -> None:
    """Verify exceptions inside traced blocks are propagated without being swallowed."""
    settings = Settings(_env_file=None, langsmith_tracing=False)
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        with pytest.raises(ValueError, match="Simulated application failure"):
            with trace_agent_turn(customer_id="cust-1", message="test"):
                raise ValueError("Simulated application failure")


@patch("graphsupport.core.tracing.RunTree")
def test_active_agent_turn_posts_run_tree(mock_run_tree_cls: MagicMock) -> None:
    """Verify active tracing posts run tree and patches output upon exit."""
    mock_tree = MagicMock()
    mock_run_tree_cls.return_value = mock_tree

    settings = Settings(
        _env_file=None,
        langsmith_tracing=True,
        langsmith_api_key="lsv2_pt_valid_key",
        langsmith_project="graphsupport-test",
    )
    with (
        patch("graphsupport.core.tracing.get_settings", return_value=settings),
        patch("graphsupport.core.tracing.is_tracing_active", return_value=True),
    ):
        with trace_agent_turn(
            customer_id="cust-1",
            message="Hello",
            conversation_id="conv-1",
        ) as ctx:
            ctx["output"] = "Assistant reply"
            ctx["iterations"] = 2

        mock_run_tree_cls.assert_called_once()
        mock_tree.post.assert_called_once()
        mock_tree.end.assert_called_once()
        mock_tree.patch.assert_called_once()


def test_setup_langsmith_environment_exports_vars() -> None:
    """Verify setup_langsmith_environment populates os.environ correctly."""
    settings = Settings(
        _env_file=None,
        langsmith_tracing=True,
        langsmith_api_key="lsv2_pt_env_export_test",
        langsmith_project="custom-project",
    )
    with patch("graphsupport.core.tracing.get_settings", return_value=settings):
        with patch.dict("os.environ", {}, clear=True):
            setup_langsmith_environment()
            import os

            assert os.environ.get("LANGSMITH_TRACING") == "true"
            assert os.environ.get("LANGSMITH_API_KEY") == "lsv2_pt_env_export_test"
            assert os.environ.get("LANGSMITH_PROJECT") == "custom-project"
