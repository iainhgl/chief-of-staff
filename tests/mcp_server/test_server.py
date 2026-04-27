from types import SimpleNamespace

import cos.mcp_server.server as server


async def test_startup_sequence_initialises_output_router(monkeypatch) -> None:
    config = SimpleNamespace(
        database=SimpleNamespace(libpq_dsn="postgresql://test:test@localhost/cos_test"),
        tika=SimpleNamespace(url="http://tika:9998"),
        role_pack=SimpleNamespace(path="role_packs/chro.yaml"),
        channels=["local"],
    )

    async def _check_postgres(_: str) -> bool:
        return True

    async def _check_tika(_: str) -> bool:
        return True

    async def _run_migrations(_: str) -> None:
        return None

    emitted: list[tuple[str, str, str, dict[str, object]]] = []

    def _emit(
        component: str,
        level: str,
        message: str,
        **extra: object,
    ) -> None:
        emitted.append((component, level, message, extra))

    monkeypatch.setattr(server, "_output_router", None)
    monkeypatch.setattr(server, "_check_postgres", _check_postgres)
    monkeypatch.setattr(server, "_check_tika", _check_tika)
    monkeypatch.setattr(server, "run_migrations", _run_migrations)
    monkeypatch.setattr(server, "_emit", _emit)

    await server._startup_sequence(config)

    router = server.get_output_router()
    assert router is not None
    assert router._channels == {"local"}
    assert any(message == "output router: initialised" for _, _, message, _ in emitted)
