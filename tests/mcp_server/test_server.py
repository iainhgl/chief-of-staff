import logging
from types import SimpleNamespace

import pytest

import cos.mcp_server.server as server


def _make_config(channels: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        database=SimpleNamespace(libpq_dsn="postgresql://test:test@localhost/cos_test"),
        tika=SimpleNamespace(url="http://tika:9998"),
        role_pack=SimpleNamespace(path="role_packs/chro.yaml"),
        channels=channels,
    )


def _patch_server(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str, dict[str, object]]]:
    emitted: list[tuple[str, str, str, dict[str, object]]] = []

    async def _check_postgres(_: str) -> bool:
        return True

    async def _check_tika(_: str) -> bool:
        return True

    async def _run_migrations(_: str) -> None:
        return None

    def _emit(component: str, level: str, message: str, **extra: object) -> None:
        emitted.append((component, level, message, extra))

    monkeypatch.setattr(server, "_output_router", None)
    monkeypatch.setattr(server, "_check_postgres", _check_postgres)
    monkeypatch.setattr(server, "_check_tika", _check_tika)
    monkeypatch.setattr(server, "run_migrations", _run_migrations)
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
