from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.store.models import BackfillResult

runner = CliRunner()


def test_migrate_command_reports_backfilled_count() -> None:
    with patch(
        "cos.cli._run_migrate",
        new=AsyncMock(return_value=BackfillResult(backfilled=3, already_canonical=1)),
    ):
        result = runner.invoke(app, ["migrate"])

    assert result.exit_code == 0
    assert "3 document(s) backfilled" in result.output
    assert "1 already canonical" in result.output


def test_migrate_command_exits_zero_on_success() -> None:
    with patch(
        "cos.cli._run_migrate",
        new=AsyncMock(return_value=BackfillResult(backfilled=0, already_canonical=2)),
    ):
        result = runner.invoke(app, ["migrate"])

    assert result.exit_code == 0


def test_migrate_command_exits_one_on_error() -> None:
    with patch(
        "cos.cli._run_migrate",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = runner.invoke(app, ["migrate"])

    assert result.exit_code == 1
    assert "Migration failed: boom" in result.output
