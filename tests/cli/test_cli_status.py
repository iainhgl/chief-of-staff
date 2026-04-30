from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.services.health import ComponentStatus

runner = CliRunner()


def test_status_command_prints_plain_language_table_for_healthy_components() -> None:
    statuses = [
        ComponentStatus("Postgres", True, "healthy"),
        ComponentStatus("Tika", True, "healthy"),
        ComponentStatus("MCP server", True, "listening on stdio"),
        ComponentStatus("Role pack", True, "CHRO loaded"),
        ComponentStatus("Database", True, "connected (42 documents indexed)"),
    ]

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        patch("cos.cli._check_status", new=AsyncMock(return_value=statuses)),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert result.output == (
        "CoS Platform Status\n"
        "-------------------\n"
        "Postgres        ✓ healthy\n"
        "Tika            ✓ healthy\n"
        "MCP server      ✓ healthy\n"
        "Role pack       ✓ CHRO loaded\n"
        "Database        ✓ connected (42 documents indexed)\n"
    )


def test_status_command_exits_non_zero_and_prints_recovery_hint_for_unhealthy_component(
) -> None:
    statuses = [
        ComponentStatus("Postgres", False, "container not running", "Run: cos restart"),
        ComponentStatus("Tika", True, "healthy"),
        ComponentStatus("MCP server", True, "listening on stdio"),
        ComponentStatus("Role pack", True, "CHRO loaded"),
        ComponentStatus("Database", True, "connected (2 documents indexed)"),
    ]

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        patch("cos.cli._check_status", new=AsyncMock(return_value=statuses)),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "Postgres        ✗ container not running — Run: cos restart" in result.output


def test_status_command_catches_runtime_errors() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        patch("cos.cli._check_status", new=AsyncMock(side_effect=RuntimeError("boom"))),
    ):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "Error running status check: boom" in result.output
