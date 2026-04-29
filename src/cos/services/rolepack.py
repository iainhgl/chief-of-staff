from cos.rolepack.loader import RolePackConfig


class RolePackService:
    def __init__(self, role_pack: RolePackConfig) -> None:
        self._role_pack = role_pack

    def get_active(self) -> RolePackConfig:
        return self._role_pack
