#!/usr/bin/env python3
"""Environment and prerequisite validation script for GraphSupport AI.

Run this script to verify that your local environment meets all requirements
for running and developing GraphSupport AI on macOS / Linux.
"""

import importlib
import os
import platform
import subprocess
import sys
from typing import NamedTuple


class CheckResult(NamedTuple):
    name: str
    passed: bool
    details: str


def check_python_version() -> CheckResult:
    """Verify Python interpreter is 3.10 or newer."""
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    passed = (major, minor) >= (3, 10)
    details = f"Detected Python {version_str} (>= 3.10 required, 3.12 recommended)"
    return CheckResult("Python Version", passed, details)


def check_virtual_environment() -> CheckResult:
    """Verify script is running inside a virtual environment."""
    in_venv = sys.prefix != sys.base_prefix or bool(os.environ.get("VIRTUAL_ENV"))
    if in_venv:
        details = f"Active Prefix: {sys.prefix}"
    else:
        details = "Running outside a virtual environment (.venv recommended)"
    return CheckResult("Virtual Environment", in_venv, details)


def check_git_status() -> CheckResult:
    """Verify Git repository exists and check current branch."""
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        return CheckResult("Git Repository", True, f"Active Branch: '{branch or 'detached'}'")
    except Exception:
        return CheckResult("Git Repository", False, "Not a valid Git repository")


def check_package(package_name: str, import_name: str) -> CheckResult:
    """Verify availability of a required Python dependency."""
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "installed")
        return CheckResult(f"Package: {package_name}", True, f"Version: {version}")
    except ImportError:
        return CheckResult(f"Package: {package_name}", False, "Not installed in active environment")


def check_graphsupport_package() -> CheckResult:
    """Verify GraphSupport AI package imports and health check runs."""
    try:
        from graphsupport.config import get_settings
        from graphsupport.core import check_health

        settings = get_settings()
        health = check_health(settings)
        return CheckResult(
            "GraphSupport Core",
            health.status == "healthy",
            f"Health: {health.status}, Phase: {health.current_phase}",
        )
    except Exception as err:
        return CheckResult("GraphSupport Core", False, f"Import/Health failure: {err}")


def check_neo4j_connectivity() -> CheckResult:
    """Check optional live Neo4j database connectivity if configured."""
    try:
        from graphsupport.config import get_settings
        from graphsupport.graph.driver import get_driver_manager

        settings = get_settings()
        if not settings.is_neo4j_configured:
            return CheckResult(
                "Neo4j Live Connection", True, "Optional: unconfigured in .env (skipped)"
            )

        dm = get_driver_manager(settings=settings)
        dm.verify_connectivity()
        srv = dm.get_server_info()
        return CheckResult(
            "Neo4j Live Connection", True, f"Connected ({srv.get('agent', 'Neo4j')})"
        )
    except Exception as err:
        return CheckResult(
            "Neo4j Live Connection", False, f"Connection failed: {type(err).__name__}"
        )


def main() -> int:
    """Execute all diagnostic checks and display formatted results."""
    print("=" * 72)
    print(" GraphSupport AI — Environment Diagnostics")
    print(f" Platform: {platform.system()} {platform.machine()} ({platform.platform()})")
    print("=" * 72)

    checks = [
        check_python_version(),
        check_virtual_environment(),
        check_git_status(),
        check_package("pydantic", "pydantic"),
        check_package("pydantic-settings", "pydantic_settings"),
        check_package("streamlit", "streamlit"),
        check_package("neo4j", "neo4j"),
        check_package("pytest", "pytest"),
        check_package("ruff", "ruff"),
        check_graphsupport_package(),
        check_neo4j_connectivity(),
    ]

    all_passed = True
    for c in checks:
        icon = "✓" if c.passed else "✗"
        status = "PASS" if c.passed else "FAIL"
        print(f"[{icon}] {c.name:<26} : {status:<5} - {c.details}")
        if not c.passed:
            all_passed = False

    print("=" * 72)
    if all_passed:
        print("RESULT: All environment checks PASSED successfully.")
        return 0
    else:
        print("RESULT: One or more checks FAILED. Please review instructions in README.md.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
