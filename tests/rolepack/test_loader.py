from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cos.rolepack.loader import RolePackConfig, load


def _write_role_pack(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_valid_role_pack(tmp_path: Path) -> None:
    yaml_file = tmp_path / "test_role.yaml"
    _write_role_pack(
        yaml_file,
        """role_name: Test
goals:
  - Goal one
tone: Concise and direct
knowledge_taxonomy:
  - Category A
stakeholder_map:
  CEO: primary partner
retrieval_priorities:
  - Category A
active_workflows:
  - workflow_one
output_channels:
  - local
""",
    )

    result = load(str(yaml_file))

    assert isinstance(result, RolePackConfig)
    assert result.role_name == "Test"
    assert result.goals == ["Goal one"]
    assert result.tone == "Concise and direct"
    assert result.knowledge_taxonomy == ["Category A"]
    assert result.stakeholder_map == {"CEO": "primary partner"}
    assert result.retrieval_priorities == ["Category A"]
    assert result.active_workflows == ["workflow_one"]
    assert result.output_channels == ["local"]


def test_load_missing_required_field(tmp_path: Path) -> None:
    yaml_file = tmp_path / "missing_tone.yaml"
    _write_role_pack(
        yaml_file,
        """role_name: Test
goals:
  - Goal one
knowledge_taxonomy:
  - Category A
stakeholder_map:
  CEO: primary partner
retrieval_priorities:
  - Category A
active_workflows:
  - workflow_one
output_channels:
  - local
""",
    )

    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))

    with pytest.raises(ValidationError, match="tone"):
        RolePackConfig.model_validate(data)


def test_load_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load("nonexistent/path.yaml")


def test_load_invalid_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "invalid.yaml"
    _write_role_pack(yaml_file, "role_name: Test:\n  goals: [broken")

    with pytest.raises(yaml.YAMLError):
        load(str(yaml_file))
