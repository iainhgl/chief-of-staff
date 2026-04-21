from pydantic import BaseModel


class RolePackConfig(BaseModel):
    """Role pack configuration — schema defined in Story 4.1."""
    pass


def load(path: str) -> RolePackConfig:
    raise NotImplementedError
