import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from psycopg_pool import AsyncConnectionPool

import cos.mcp_server.server as server
from cos.rolepack.loader import RolePackConfig


def _make_config(channels: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        database=SimpleNamespace(libpq_dsn="postgresql://test:test@localhost/cos_test"),
        tika=SimpleNamespace(url="http://tika:9998"),
        role_pack=SimpleNamespace(path="role_packs/chro.yaml"),
        channels=channels,
        llm=SimpleNamespace(
            model="claude-3-haiku-20240307",
            api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
            ca_bundle_path=None,
            proxy_url=None,
            trust_env=None,
        ),
        embedding=SimpleNamespace(
            ca_bundle_path=None,
            proxy_url=None,
            trust_env=False,
        ),
    )


def _patch_server(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str, str, dict[str, object]]]:
    emitted: list[tuple[str, str, str, dict[str, object]]] = []
    mock_role_pack = RolePackConfig(
        role_name="Test",
        goals=["goal"],
        tone="direct",
        knowledge_taxonomy=["cat"],
        stakeholder_map={"CEO": "partner"},
        retrieval_priorities=["cat"],
        active_workflows=["wf"],
        output_channels=["local"],
    )

    async def _check_postgres(_: str) -> bool:
        return True

    async def _check_tika(_: str) -> bool:
        return True

    async def _run_migrations(_: str) -> None:
        return None

    async def _create_pool(_: str) -> AsyncConnectionPool:
        return MagicMock(spec=AsyncConnectionPool)

    def _emit(component: str, level: str, message: str, **extra: object) -> None:
        emitted.append((component, level, message, extra))

    monkeypatch.setattr(server, "_output_router", None)
    monkeypatch.setattr(server, "_config", None, raising=False)
    monkeypatch.setattr(server, "_pool", None, raising=False)
    monkeypatch.setattr(server, "_retrieval_service", None, raising=False)
    monkeypatch.setattr(server, "_output_service", None, raising=False)
    monkeypatch.setattr(server, "_role_pack_service", None, raising=False)
    monkeypatch.setattr(server, "_check_postgres", _check_postgres)
    monkeypatch.setattr(server, "_check_tika", _check_tika)
    monkeypatch.setattr(server, "run_migrations", _run_migrations)
    monkeypatch.setattr(server, "create_pool", _create_pool, raising=False)
    monkeypatch.setattr(server, "load_role_pack", lambda _path: mock_role_pack)
    monkeypatch.setattr(
        server, "AnthropicAdapter", MagicMock(return_value=MagicMock()), raising=False
    )
    monkeypatch.setattr(
        server, "RetrievalService", MagicMock(return_value=MagicMock()), raising=False
    )
    monkeypatch.setattr(server, "_emit", _emit)

    return emitted


@pytest.mark.asyncio
async def test_startup_sequence_initialises_output_router(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    emitted = _patch_server(monkeypatch)

    await server._startup_sequence(_make_config(["local"]))

    router = server.get_output_router()
    assert router is not None
    router.send("local", "probe")
    assert "probe" in capsys.readouterr().out
    assert any(message == "output router: initialised" for _, _, message, _ in emitted)
    assert server.get_output_service() is not None
    assert server.get_retrieval_service() is not None


@pytest.mark.asyncio
async def test_startup_sequence_with_empty_channels_router_created(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_server(monkeypatch)

    await server._startup_sequence(_make_config([]))

    router = server.get_output_router()
    assert router is not None
    with caplog.at_level(logging.ERROR):
        router.send("local", "should be suppressed")
    assert any("unknown output channel" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_startup_sequence_initialises_retrieval_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)

    await server._startup_sequence(_make_config(["local"]))

    assert server.get_retrieval_service() is not None


@pytest.mark.asyncio
async def test_startup_sequence_sets_global_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)
    config = _make_config(["local"])

    await server._startup_sequence(config)

    assert server.get_config() is config


@pytest.mark.asyncio
async def test_startup_sequence_initialises_output_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)

    await server._startup_sequence(_make_config(["local"]))

    assert server.get_output_service() is not None


@pytest.mark.asyncio
async def test_startup_sequence_initialises_role_pack_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)

    await server._startup_sequence(_make_config(["local"]))

    assert server.get_role_pack_service() is not None


@pytest.mark.asyncio
async def test_startup_sequence_role_pack_loaded_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted = _patch_server(monkeypatch)

    await server._startup_sequence(_make_config(["local"]))

    assert any(
        component == "rolepack"
        and message == "Role pack loaded"
        and extra.get("role_name") == "Test"
        for component, _, message, extra in emitted
    )


@pytest.mark.asyncio
async def test_startup_sequence_role_pack_file_not_found_raises_system_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)
    config = _make_config(["local"])

    def _raise_file_not_found(_path: str) -> RolePackConfig:
        raise FileNotFoundError(config.role_pack.path)

    monkeypatch.setattr(server, "load_role_pack", _raise_file_not_found)

    with pytest.raises(SystemExit, match="Role pack file not found") as exc_info:
        await server._startup_sequence(config)

    assert config.role_pack.path in str(exc_info.value)


@pytest.mark.asyncio
async def test_startup_sequence_role_pack_yaml_error_raises_system_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)

    def _raise_yaml_error(_path: str) -> RolePackConfig:
        raise yaml.YAMLError("bad syntax")

    monkeypatch.setattr(server, "load_role_pack", _raise_yaml_error)

    with pytest.raises(SystemExit, match="YAML syntax error"):
        await server._startup_sequence(_make_config(["local"]))


@pytest.mark.asyncio
async def test_startup_sequence_role_pack_validation_error_raises_system_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_server(monkeypatch)

    def _raise_validation_error(_path: str) -> RolePackConfig:
        RolePackConfig.model_validate({})
        raise AssertionError("unreachable")

    monkeypatch.setattr(server, "load_role_pack", _raise_validation_error)

    with pytest.raises(SystemExit, match="validation error") as exc_info:
        await server._startup_sequence(_make_config(["local"]))

    assert "Role pack validation error" in str(exc_info.value)
