from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app

runner = CliRunner()


def test_logs_no_args_calls_docker_compose_logs() -> None:
    ok_result = MagicMock(returncode=0, stdout="log line 1\nlog line 2\n")

    with (
        patch("cos.cli._any_containers_running", return_value=True),
        patch("cos.cli.subprocess.run", return_value=ok_result) as mock_run,
    ):
        result = runner.invoke(app, ["logs"])

    assert result.exit_code == 0
    assert "log line 1" in result.output
    assert mock_run.call_args[0][0] == [
        "docker",
        "compose",
        "logs",
        "--no-color",
        "--timestamps",
        "--tail",
        "100",
    ]


def test_logs_component_filters_to_single_service() -> None:
    ok_result = MagicMock(returncode=0, stdout="postgres log\n")

    with (
        patch("cos.cli._any_containers_running", return_value=True),
        patch("cos.cli.subprocess.run", return_value=ok_result) as mock_run,
    ):
        result = runner.invoke(app, ["logs", "postgres"])

    assert result.exit_code == 0
    assert "postgres log" in result.output
    assert mock_run.call_args[0][0] == [
        "docker",
        "compose",
        "logs",
        "--no-color",
        "--timestamps",
        "--tail",
        "100",
        "postgres",
    ]


def test_logs_since_omits_tail_flag() -> None:
    ok_result = MagicMock(returncode=0, stdout="recent log\n")

    with (
        patch("cos.cli._any_containers_running", return_value=True),
        patch("cos.cli.subprocess.run", return_value=ok_result) as mock_run,
    ):
        result = runner.invoke(app, ["logs", "--since", "10m"])

    assert result.exit_code == 0
    assert "recent log" in result.output
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd == [
        "docker",
        "compose",
        "logs",
        "--no-color",
        "--timestamps",
        "--since",
        "10m",
    ]
    assert "--tail" not in called_cmd


def test_logs_invalid_component_returns_clean_error() -> None:
    result = runner.invoke(app, ["logs", "redis"])

    assert result.exit_code == 1
    assert "Unknown component: redis." in result.output
    assert "postgres, tika, cos" in result.output
    assert "Traceback" not in result.output


def test_logs_no_containers_running_returns_operator_message() -> None:
    with patch("cos.cli._any_containers_running", return_value=False):
        result = runner.invoke(app, ["logs"])

    assert result.exit_code == 1
    assert (
        "No containers running. Start the platform first: docker compose up -d"
        in result.output
    )


def test_logs_subprocess_failure_returns_clean_error() -> None:
    fail_result = MagicMock(returncode=1, stderr="docker compose logs failed")

    with (
        patch("cos.cli._any_containers_running", return_value=True),
        patch("cos.cli.subprocess.run", return_value=fail_result),
    ):
        result = runner.invoke(app, ["logs"])

    assert result.exit_code == 1
    assert "Error retrieving logs: docker compose logs failed" in result.output
    assert "Traceback" not in result.output
