# Deferred Work

## Deferred from: code review of 1-1-project-scaffold-containerised-services-and-core-interfaces (2026-04-20)

- `uv:latest` Dockerfile tag unpinned — pin to a specific version for reproducible builds; not spec-mandated for Story 1.1
- Service stubs lack constructor injection points — `IngestService`, `RetrievalService`, etc. have no `__init__` parameters for `CosConfig`/`OutputRouter` injection; will be wired when services are implemented
- `anthropic` SDK not declared in `pyproject.toml` — add when `AnthropicAdapter` is implemented in Story 3.3
- `DocumentRecord.id` defaults to empty string `""` and `EmbeddingRecord.vector` defaults to empty list — unsafe DB defaults; add validation or non-default construction when schema is defined in Story 1.3
- `_CHANNEL_HANDLERS` module-level dict creates test isolation risk — mutations affect all `OutputRouter` instances; acceptable for Phase 1 single-channel scope, revisit when Phase 2 channels are added
- `cos` container has no environment variables for Postgres/Tika connection — no `DATABASE_URL` or equivalent configured in `docker-compose.yml`; addressed in Story 1.2 when `CosConfig` fields are defined

## Deferred from: code review of 1-2-configuration-loader (2026-04-20)

- Docker healthcheck tests only `import cos`, not config validity or service readiness — a crashed-after-start container still passes; revisit when a real health endpoint exists
- `RolePackRef.path` unvalidated — no check it is relative, within bounds, or exists at load time; failure surfaces later at runtime
- `channels`/`connectors` accept empty lists and arbitrary strings — no enum or minimum-length validation; enforce when channel/connector wiring is implemented
- `config.yaml.example` has `password: postgres` with no `CHANGE_ME` warning — operators may copy verbatim into production
- Default `CosConfig.load()` path resolves relative to process cwd — fragile outside Docker; add explicit path resolution if CLI usage grows

## Deferred from: code review of 1-4-mcp-server-foundation (2026-04-22)

- `retrieve` stub ignores `query` parameter — expected for stub until Story 3.4 implements it
- `httpx.AsyncClient` created per health-check call — minor inefficiency acceptable for health check frequency; optimize if needed
- Hardcoded credentials in `config.yaml.example` — pre-existing from Story 1.1/1.2, already in prior deferred list
- `run_migrations` behavior with multi-statement SQL — pre-existing from Story 1.3, not introduced by 1.4
- No test for `run_migrations` raising during `_startup_sequence` — pre-existing gap, revisit when Story 1.5 operator validation runs end-to-end

## Deferred from: code review of 1-5-operator-validation-platform-boots-end-to-end (2026-04-22)

- `_config` set before `_startup_sequence` completes — latent race if FastMCP startup model changes to concurrent; harmless with current sequential `asyncio.run()` then `mcp.run()` [server.py:65-72]
- New DB and HTTP connections per `get_status` call — no pooling; acceptable at Phase 1 poll rates [server.py:34-49]
- `get_status` always returns `status:"ok"` even when `ready:false` — by design; `ready` field captures degraded state [tools.py:14-16]
- `_emit` falls back silently to INFO on unknown level strings — `getattr(logging, level.lower(), logging.info)` swallows "WARN"/"WARNING" mismatch [server.py:30]
- `get_config()` None-guard only enforced in `get_status` — future tools that call `get_config()` without checking will raise AttributeError
- Duplicate startup connection — `_check_postgres` and `run_migrations` each open a separate DB connection [server.py:34-62]
- (Story 1.4 bug) `_startup_sequence` continues to `run_migrations` even when Postgres health check fails — unhandled exception rather than clean error [server.py:54-62]; in practice Compose `depends_on: healthy` prevents this at cold start, but container restarts are at risk
- (Story 1.4 bug) `_check_postgres` and `_check_tika` duplicated in `server.py` and `health.py` — can diverge silently; startup uses server.py copies, get_status uses HealthService [server.py:34-49]
- (Story 1.4 bug) Tika health check accepts 4xx responses as healthy — `status_code < 500` passes 404/401/403; correct threshold is `== 200` [server.py:47, health.py:29]

## Deferred from: code review of 1-6-documentation-and-housekeeping (2026-04-22)

- `claude mcp add` has no cwd equivalent — asymmetry with Claude Desktop `"cwd"` field; command validated working in Story 1.5; Claude Code scopes command to project context [docs/setup.md]
- Restart procedure removes `sleep 3` — `docker compose down` waits for containers to stop so immediate port conflict is low probability; spec prescribed this exact three-step procedure [docs/setup.md]
- Role pack path references `role_packs/chro.yaml` which doesn't exist — pre-existing, intentional, documented in comment; Epic 4 implements the role pack [config.yaml.example]
- `cd cos` in clone step assumes repo cloned to default directory name — minor; any competent operator would infer; spec did not call for handling [docs/setup.md]

## Deferred from: code review of 2-1-document-extraction-and-markdown-normalisation (2026-04-23)

- Filename/stem collision for same-named files from different source directories — `originals_dir / source_path.name` and `markdown_dir / stem.md` silently overwrite; re-ingest conflict detection is Story 2.3 scope [src/cos/ingestion/extractor.py]
- `author` field may receive `list[str]` from tika-client multi-value metadata — `response.data.get(DublinCoreKey.Creator)` behaviour with multiple creators unverified; requires tika-client investigation [src/cos/ingestion/extractor.py]
- Integration test missing assertions for AC 1 metadata fields — `test_extract_pdf_via_tika` does not assert `result.content_type`, `result.title`, or `result.author`; depends on Tika response for minimal PDF fixture [tests/ingestion/test_extractor.py]

## Deferred from: code review of 1-3-database-schema-and-migration-runner (2026-04-21)

- No migration tracking table — every `run_migrations()` call re-executes all SQL files; safe now because all DDL is idempotent, but any future DML or non-idempotent migration will corrupt the database; add a `schema_migrations` ledger table when needed
- `_has_executable_sql()` doesn't detect `/* */` block comments — current migrations use only `--` line comments; add block comment support before any migration uses `/* */`
- `db.py` logs with hardcoded `"mcp_server"` component string — should use a `"store"` or `"db"` component value; low priority refactor
- `test_run_migrations_is_idempotent` makes only a "no exception" assertion — a stronger assertion (e.g. schema unchanged, no extra tables) would give more confidence; acceptable for Phase 1
