"""Integration tests for GraphSupport AI application startup and module readiness."""

import importlib

from graphsupport.config import reload_settings
from graphsupport.core import check_health, configure_logging


def test_package_modules_importable() -> None:
    """Verify that all core packages and submodules can be imported cleanly."""
    modules = [
        "graphsupport",
        "graphsupport.config",
        "graphsupport.config.settings",
        "graphsupport.core",
        "graphsupport.core.exceptions",
        "graphsupport.core.logging_config",
        "graphsupport.core.health",
        "graphsupport.graph",
        "graphsupport.graph.driver",
        "graphsupport.graph.models",
        "graphsupport.graph.schema",
        "graphsupport.graph.repository",
        "graphsupport.graph.repositories.customer_repo",
        "graphsupport.graph.repositories.product_repo",
        "graphsupport.graph.repositories.ticket_repo",
        "graphsupport.graph.repositories.conversation_repo",
        "graphsupport.graph.repositories.troubleshooting_repo",
        "graphsupport.application",
        "graphsupport.application.support_service",
        "graphsupport.memory",
        "graphsupport.memory.models",
        "graphsupport.memory.history_retriever",
        "graphsupport.memory.relevance_ranker",
        "graphsupport.memory.context_builder",
        "graphsupport.memory.memory_writer",
        "graphsupport.agents",
        "graphsupport.agents.provider",
        "graphsupport.agents.tool_registry",
        "graphsupport.agents.prompt_templates",
        "graphsupport.agents.output_parser",
        "graphsupport.agents.support_agent",
        "graphsupport.ui",
        "graphsupport.ui.styles",
        "graphsupport.ui.components",
        "graphsupport.ui.data_management",
        "graphsupport.ui.memory_inspector",
        "graphsupport.ui.chat",
        "graphsupport.ui.navigation",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None


def test_clean_startup_without_external_services() -> None:
    """Verify application boots cleanly when Neo4j and LLM are unconfigured."""
    # Ensure fresh test settings with no env file
    settings = reload_settings(_env_file=None)
    logger = configure_logging(settings, force=True)
    health = check_health(settings)

    assert settings.app_name == "GraphSupport AI"
    assert logger.name == "graphsupport"
    assert health.status == "healthy"
    assert health.neo4j.configured is False
    assert health.llm.configured is False


def test_app_entrypoint_importable() -> None:
    """Verify the Streamlit entrypoint app.py can be parsed and imported without errors."""
    import app

    assert hasattr(app, "main")
    assert callable(app.main)
