"""CLI tests for the cos benchmark command."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.retrieval.benchmark import (
    BenchmarkReport,
    QueryResult,
)

runner = CliRunner()

_CORPUS_PATH = str(Path(__file__).parents[1] / "fixtures" / "retrieval_eval")


def _make_report(pass_rate: float = 1.0) -> BenchmarkReport:
    passed = int(pass_rate * 7)
    results = [
        QueryResult(
            f"q{i}",
            "direct_fact",
            i < passed,
            50.0,
            ["loc://a"],
            ["loc://a"] if i < passed else [],
            "correct_answer" if i < passed else "missed_answer",
        )
        for i in range(7)
    ]
    from cos.retrieval.benchmark import aggregate_by_class

    per_class = aggregate_by_class(results)
    from cos.services.retrieval_eval import _build_report

    return _build_report(
        "2026-01-01T00:00:00+00:00",
        "abc123def456",
        results,
        per_class,
    )


# ── Success path ─────────────────────────────────────────────────────────────


def test_benchmark_command_exits_zero_when_all_pass() -> None:
    report = _make_report(pass_rate=1.0)

    with patch("cos.cli._run_benchmark", new=AsyncMock(return_value=report)):
        result = runner.invoke(app, ["benchmark", "--corpus", _CORPUS_PATH])

    assert result.exit_code == 0, result.output


def test_benchmark_command_outputs_human_summary() -> None:
    report = _make_report(pass_rate=1.0)

    with patch("cos.cli._run_benchmark", new=AsyncMock(return_value=report)):
        result = runner.invoke(app, ["benchmark", "--corpus", _CORPUS_PATH])

    assert "Retrieval Benchmark Summary" in result.output
    assert "7/7" in result.output


def test_benchmark_command_outputs_json_report_to_stdout() -> None:
    report = _make_report(pass_rate=1.0)

    with patch("cos.cli._run_benchmark", new=AsyncMock(return_value=report)):
        result = runner.invoke(app, ["benchmark", "--corpus", _CORPUS_PATH])

    output = result.output
    json_start = output.find("{")
    assert json_start != -1, "Expected JSON in stdout"
    parsed = json.loads(output[json_start:])
    assert "run_timestamp" in parsed
    assert "per_query" in parsed
    assert "per_class" in parsed
    assert "summary" in parsed


def test_benchmark_command_writes_json_to_file_when_output_option_given(
    tmp_path: Path,
) -> None:
    report = _make_report(pass_rate=1.0)
    output_file = tmp_path / "report.json"

    with patch("cos.cli._run_benchmark", new=AsyncMock(return_value=report)):
        result = runner.invoke(
            app,
            ["benchmark", "--corpus", _CORPUS_PATH, "--output", str(output_file)],
        )

    assert result.exit_code == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert "run_timestamp" in data


def test_benchmark_command_exits_one_when_not_all_pass() -> None:
    report = _make_report(pass_rate=0.5)

    with patch("cos.cli._run_benchmark", new=AsyncMock(return_value=report)):
        result = runner.invoke(app, ["benchmark", "--corpus", _CORPUS_PATH])

    assert result.exit_code == 1


# ── Error handling ────────────────────────────────────────────────────────────


def test_benchmark_command_exits_one_on_invalid_corpus_path() -> None:
    with patch("cos.cli._run_benchmark", new=AsyncMock(side_effect=SystemExit(1))):
        result = runner.invoke(app, ["benchmark", "--corpus", "/nonexistent/path"])

    assert result.exit_code == 1


def test_benchmark_command_exits_one_on_unexpected_exception() -> None:
    with patch(
        "cos.cli._run_benchmark",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        result = runner.invoke(app, ["benchmark", "--corpus", _CORPUS_PATH])

    assert result.exit_code == 1
    assert "Benchmark failed" in result.output
