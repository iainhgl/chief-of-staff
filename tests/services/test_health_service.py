from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cos.services.health import HealthService


async def test_check_all_returns_both_components_healthy():
    svc = HealthService(db_dsn="postgresql://user:pass@localhost/db", tika_url="http://tika:9998")
    with (
        patch.object(svc, "_check_postgres", new_callable=AsyncMock, return_value=True),
        patch.object(svc, "_check_tika", new_callable=AsyncMock, return_value=True),
    ):
        result = await svc.check_all()

    assert result == [{"name": "postgres", "healthy": True}, {"name": "tika", "healthy": True}]


async def test_check_all_returns_postgres_unhealthy():
    svc = HealthService(db_dsn="postgresql://user:pass@localhost/db", tika_url="http://tika:9998")
    with (
        patch.object(svc, "_check_postgres", new_callable=AsyncMock, return_value=False),
        patch.object(svc, "_check_tika", new_callable=AsyncMock, return_value=True),
    ):
        result = await svc.check_all()

    assert result[0] == {"name": "postgres", "healthy": False}
    assert result[1] == {"name": "tika", "healthy": True}


async def test_check_all_returns_tika_unhealthy():
    svc = HealthService(db_dsn="postgresql://user:pass@localhost/db", tika_url="http://tika:9998")
    with (
        patch.object(svc, "_check_postgres", new_callable=AsyncMock, return_value=True),
        patch.object(svc, "_check_tika", new_callable=AsyncMock, return_value=False),
    ):
        result = await svc.check_all()

    assert result[0] == {"name": "postgres", "healthy": True}
    assert result[1] == {"name": "tika", "healthy": False}


async def test_check_postgres_returns_false_on_exception():
    svc = HealthService(db_dsn="postgresql://bad:bad@localhost/db", tika_url="http://tika:9998")
    with patch("cos.services.health.psycopg.AsyncConnection.connect", side_effect=Exception("refused")):
        result = await svc._check_postgres()
    assert result is False


async def test_check_tika_returns_false_on_exception():
    svc = HealthService(db_dsn="postgresql://user:pass@localhost/db", tika_url="http://tika:9998")
    with patch("cos.services.health.httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client
        result = await svc._check_tika()
    assert result is False


async def test_check_tika_returns_true_on_200():
    svc = HealthService(db_dsn="postgresql://user:pass@localhost/db", tika_url="http://tika:9998")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("cos.services.health.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_http
        result = await svc._check_tika()
    assert result is True


async def test_check_tika_returns_false_on_500():
    svc = HealthService(db_dsn="postgresql://user:pass@localhost/db", tika_url="http://tika:9998")
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("cos.services.health.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_http
        result = await svc._check_tika()
    assert result is False
