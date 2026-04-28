import yaml
from pydantic import BaseModel


class RolePackConfig(BaseModel):
    """Role pack configuration — schema defined in Story 4.1."""

    role_name: str
    goals: list[str]
    tone: str
    knowledge_taxonomy: list[str]
    stakeholder_map: dict[str, str]
    retrieval_priorities: list[str]
    active_workflows: list[str]
    output_channels: list[str]


def load(path: str) -> RolePackConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RolePackConfig.model_validate(data)
