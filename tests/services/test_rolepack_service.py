from cos.rolepack.loader import RolePackConfig
from cos.services.rolepack import RolePackService


def _make_role_pack() -> RolePackConfig:
    return RolePackConfig(
        role_name="CHRO",
        goals=["Improve workforce planning"],
        tone="direct",
        knowledge_taxonomy=["people"],
        stakeholder_map={"CEO": "partner"},
        retrieval_priorities=["people"],
        active_workflows=["brief"],
        output_channels=["local"],
    )


def test_get_active_returns_loaded_role_pack() -> None:
    role_pack = _make_role_pack()
    service = RolePackService(role_pack=role_pack)

    assert service.get_active() is role_pack


def test_get_active_returns_same_instance() -> None:
    service = RolePackService(role_pack=_make_role_pack())

    first = service.get_active()
    second = service.get_active()

    assert first is second
