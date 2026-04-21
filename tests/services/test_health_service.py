import pytest

from cos.services.health import HealthService


@pytest.mark.asyncio
async def test_check_all_not_implemented() -> None:
    svc = HealthService()
    with pytest.raises(NotImplementedError):
        await svc.check_all()
