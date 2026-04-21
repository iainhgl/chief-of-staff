import pytest

from cos.rolepack.loader import load


def test_load_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        load("path/to/role.yaml")
