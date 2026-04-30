import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app

runner = CliRunner()


def _ps_output(*services: tuple[str, str]) -> str:
    return "\n".join(
        json.dumps({"Service": service, "State": "running", "Health": health})
        for service, health in services
    )


ALL_HEALTHY = _ps_output(
    ("postgres", "healthy"),
    ("tika", "healthy"),
    ("cos", "healthy"),
)
TIKA_STUCK = _ps_output(
    ("postgres", "healthy"),
    ("tika", "starting"),
    ("cos", "healthy"),
)


def test_restart_prints_success_when_all_services_healthy() -> None:
    ok_restart = MagicMock(returncode=0, stderr="")
    ok_ps = MagicMock(returncode=0, stdout=ALL_HEALTHY)

    with (
        patch("cos.cli.subprocess.run", side_effect=[ok_restart, ok_ps]),
        patch("cos.cli.time.sleep"),
        patch("cos.cli.time.monotonic", side_effect=[0.0, 5.0]),
    ):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 0
    assert "Restarting platform..." in result.output
    assert "Platform restarted. All components healthy." in result.output


def test_restart_exits_error_when_docker_compose_restart_fails() -> None:
    fail_restart = MagicMock(returncode=1, stderr="docker: command not found")

    with patch("cos.cli.subprocess.run", return_value=fail_restart):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 1
    assert "Error restarting platform: docker: command not found" in result.output
    assert "Traceback" not in result.output


def test_restart_reports_stuck_component_when_timeout_reached() -> None:
    ok_restart = MagicMock(returncode=0, stderr="")
    stuck_ps = MagicMock(returncode=0, stdout=TIKA_STUCK)

    with (
        patch("cos.cli.subprocess.run", side_effect=[ok_restart, stuck_ps]),
        patch("cos.cli.time.sleep"),
        patch("cos.cli.time.monotonic", side_effect=[0.0, 31.0]),
    ):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 1
    assert "Tika did not become healthy. Run: cos logs tika" in result.output


def test_restart_catches_unexpected_polling_errors_without_traceback() -> None:
    ok_restart = MagicMock(returncode=0, stderr="")

    with (
        patch("cos.cli.subprocess.run", side_effect=[ok_restart, RuntimeError("boom")]),
        patch("cos.cli.time.sleep"),
        patch("cos.cli.time.monotonic", side_effect=[0.0]),
    ):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 1
    assert "Error restarting platform: boom" in result.output
    assert "Traceback" not in result.output
