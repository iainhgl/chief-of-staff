"""Smoke tests for scripts/init-instance.sh."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "init-instance.sh"
EXPECTED_FILES = ["compose.yaml", ".env", "config.yaml", "role_packs"]
EXPECTED_DIRS = ["data", "tokens", "local/certs"]


def _run_init(
    dest: Path,
    name: str,
    *extra_args: str,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(dest), name, *extra_args],
        capture_output=True,
        text=True,
    )


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


@pytest.mark.skipif(not SCRIPT.exists(), reason="init-instance.sh not found")
class TestInitInstance:
    def test_creates_expected_structure(self, tmp_path: Path) -> None:
        dest = tmp_path / "my-instance"
        result = _run_init(dest, "my-instance")
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        for name in EXPECTED_FILES:
            assert (dest / name).exists(), f"Missing: {name}"
        for name in EXPECTED_DIRS:
            assert (dest / name).is_dir(), f"Missing directory: {name}"

    def test_env_contains_compose_project_name(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        result = _run_init(dest, "inst")
        assert result.returncode == 0
        env = _read_env(dest / ".env")
        project_name = env.get("COMPOSE_PROJECT_NAME", "")
        assert project_name.startswith("cos-inst-")
        assert project_name.removeprefix("cos-inst-").isdigit()

    def test_env_contains_ports(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        result = _run_init(dest, "inst")
        assert result.returncode == 0
        env = _read_env(dest / ".env")
        assert "POSTGRES_PORT" in env
        assert "TIKA_PORT" in env
        assert env["POSTGRES_PORT"].isdigit()
        assert env["TIKA_PORT"].isdigit()

    def test_two_instances_have_distinct_identifiers(self, tmp_path: Path) -> None:
        dest_a = tmp_path / "alpha"
        dest_b = tmp_path / "beta"

        assert _run_init(dest_a, "alpha").returncode == 0
        assert _run_init(dest_b, "beta").returncode == 0

        env_a = _read_env(dest_a / ".env")
        env_b = _read_env(dest_b / ".env")

        assert env_a["COMPOSE_PROJECT_NAME"] != env_b["COMPOSE_PROJECT_NAME"]
        assert env_a["POSTGRES_PORT"] != env_b["POSTGRES_PORT"]
        assert env_a["TIKA_PORT"] != env_b["TIKA_PORT"]

    def test_sanitized_name_collisions_still_have_distinct_identifiers(
        self, tmp_path: Path
    ) -> None:
        dest_a = tmp_path / "ai-reading-a"
        dest_b = tmp_path / "ai-reading-b"

        assert _run_init(dest_a, "AI Reading").returncode == 0
        assert _run_init(dest_b, "ai-reading").returncode == 0

        env_a = _read_env(dest_a / ".env")
        env_b = _read_env(dest_b / ".env")

        assert env_a["COMPOSE_PROJECT_NAME"] != env_b["COMPOSE_PROJECT_NAME"]
        assert env_a["POSTGRES_PORT"] != env_b["POSTGRES_PORT"]
        assert env_a["TIKA_PORT"] != env_b["TIKA_PORT"]

    def test_explicit_ports_are_honored(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        result = _run_init(
            dest,
            "inst",
            "--postgres-port",
            "25432",
            "--tika-port",
            "29998",
        )
        assert result.returncode == 0
        env = _read_env(dest / ".env")
        assert env["POSTGRES_PORT"] == "25432"
        assert env["TIKA_PORT"] == "29998"

    def test_refuses_non_empty_destination(self, tmp_path: Path) -> None:
        dest = tmp_path / "existing"
        dest.mkdir()
        (dest / "some-file").write_text("not empty")

        result = _run_init(dest, "existing")
        assert result.returncode != 0
        assert "not empty" in result.stderr or "already exists" in result.stderr

    def test_sanitizes_instance_name(self, tmp_path: Path) -> None:
        dest = tmp_path / "sanitized"
        result = _run_init(dest, "My Instance 2026!")
        assert result.returncode == 0
        env = _read_env(dest / ".env")
        project = env.get("COMPOSE_PROJECT_NAME", "")
        # Must be lowercase and Compose-safe
        assert project.startswith("cos-")
        assert project == project.lower()
        assert all(c.isalnum() or c == "-" for c in project.removeprefix("cos-"))

    def test_truncates_very_long_instance_name(self, tmp_path: Path) -> None:
        dest = tmp_path / "long-name"
        result = _run_init(dest, "a" * 80)
        assert result.returncode == 0
        env = _read_env(dest / ".env")
        prefix = env["COMPOSE_PROJECT_NAME"].rsplit("-", 1)[0]
        assert len(prefix.removeprefix("cos-")) == 48

    def test_printed_commands_quote_paths_with_spaces(self, tmp_path: Path) -> None:
        dest = tmp_path / "instance with spaces"
        result = _run_init(dest, "spacey")
        assert result.returncode == 0
        assert f"cd '{dest}'" in result.stdout

    def test_role_packs_copied(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        assert _run_init(dest, "inst").returncode == 0
        role_pack_dir = dest / "role_packs"
        assert role_pack_dir.is_dir()
        # At minimum the CHRO pack should be present
        yaml_files = list(role_pack_dir.glob("*.yaml"))
        assert len(yaml_files) >= 1, "No role pack YAML files copied"

    def test_config_yaml_generated(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        assert _run_init(dest, "inst").returncode == 0
        config = dest / "config.yaml"
        assert config.exists()
        content = config.read_text()
        # Should look like the example config
        assert "llm:" in content
        assert "database:" in content

    def test_compose_template_rendered(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        assert _run_init(dest, "inst").returncode == 0
        compose = (dest / "compose.yaml").read_text()
        # No unreplaced placeholders
        assert "{{" not in compose
        # Image reference present
        assert "cos-platform:" in compose
        assert "migrate:" in compose
        assert "service_completed_successfully" in compose

    @pytest.mark.skipif(
        shutil.which("docker") is None,
        reason="docker not available",
    )
    def test_compose_config_validates(self, tmp_path: Path) -> None:
        dest = tmp_path / "inst"
        assert _run_init(dest, "inst").returncode == 0

        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(dest / "compose.yaml"),
                "--env-file",
                str(dest / ".env"),
                "config",
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"docker compose config failed:\n{result.stderr}"
        )
