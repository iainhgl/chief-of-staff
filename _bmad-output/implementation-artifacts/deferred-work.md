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

## Deferred from: code review of 2-2-text-chunking-and-embedding-pipeline (2026-04-23)

- Result list construction outside try-except in `_embed_via_voyage` — if `result.embeddings` has unexpected structure, raw exceptions escape instead of `EmbeddingError`; Voyage API structure is trusted for now [src/cos/ingestion/embedder.py:46-53]
- No assertion that `len(result.embeddings) == len(chunks)` — Voyage API guarantees ordering/count correspondence, but a length mismatch would silently return wrong results [src/cos/ingestion/embedder.py:46]
- `ChunkingConfig` has no Pydantic validator for `chunk_overlap >= chunk_size` — invalid combinations are caught at runtime in `chunk()` but a startup-time validator would give earlier, clearer feedback [src/cos/config.py]

## Deferred from: code review of 2-3-provenance-storage-and-transactional-writes (2026-04-23)

- Missing UNIQUE constraint on `documents.source_path` — concurrent ingests with the same path can silently create duplicate rows instead of incrementing the version; adding the constraint requires a new migration; pre-existing schema gap, not introduced by Story 2.3 [src/cos/store/migrations/001_initial.sql]
- Chunks have no version-linking column — after multiple ingests, `chunks` rows from all versions are stored together with no link to `document_versions`; a retrieval query cannot scope chunks to a specific version; intentional for Phase 1, address in the retrieval layer (Story 3.x) [src/cos/store/db.py]

## Deferred from: code review of 2-4-cli-ingest-command-and-ingestservice (2026-04-23)

- Connection-per-file for CLI ingestion — `IngestService.ingest_file` opens a fresh psycopg3 connection per file; `create_pool` is unused by the CLI path; pool is correctly reserved for the MCP server retrieval path (Epic 3); sequential CLI use does not risk AC4 performance target [src/cos/services/ingestion.py]
- Old chunks not deleted on re-ingest — retrieval will return chunks from all document versions simultaneously; version-linking column deferred to Phase 1 retrieval layer; already captured in deferred-work.md from Story 2.3 [src/cos/store/db.py]
- File read twice (hash + extraction) — `hashlib.sha256(source_path.read_bytes())` and `shutil.copy2()` inside `extract()` read the file independently; fixing requires returning raw bytes from the extractor; pre-existing design [src/cos/ingestion/pipeline.py]
- Logging double-encodes JSON — `logging.info(json.dumps(...))` is pre-existing pattern from Story 2.3 migration logging; structured logger migration is a separate cross-cutting concern [src/cos/ingestion/pipeline.py, src/cos/store/db.py]

## Deferred from: code review of 2-5-document-provenance-listing (2026-04-23)

- `_docs_versions` exits code 0 on unknown document ID — spec explicitly says no error handling; misleading for scripts; revisit if a scripting AC is added [src/cos/cli.py]
- `ingested_at` None from DB would crash in `.isoformat()` — NOT NULL constraint in schema makes this theoretical; no handling required at this stage; address if schema relaxed [src/cos/store/models.py]

## Deferred from: code review of 2-6-operator-validation-documents-ingested-and-provenance-verified (2026-04-23)

- `_ingest_folder` exits with code 0 when all files fail to ingest — when every file in a folder fails, the folder ingest prints individual `Error:` lines then prints "No supported files found" and exits 0; a total-failure should arguably exit non-zero; pre-existing design, not introduced by Story 2.6 [`src/cos/cli.py`]

## Deferred from: code review of 2-7-documentation-and-housekeeping (2026-04-24)

- `--versions` + `--json` combination works but is undocumented — `cos docs --versions <id> --json` returns machine-readable version records; not mentioned in setup.md [`src/cos/cli.py`]
- Invalid UUID to `--versions` silently returns empty result — `ProvenanceService` catches `ValueError` from UUID parsing and returns `[]`; same message as valid UUID with no records; operator gets no indication of malformed input [`src/cos/services/provenance.py`]
- "What to do if a file is skipped" guidance not actionable in setup.md — existing content says unsupported types are "skipped with a notice" but gives no operator next-step guidance; pre-existing from Story 2.4 [`docs/setup.md`]
- Voyage AI naming collision: `provider: "anthropic"` routes to `voyageai.AsyncClient` — acknowledged in architecture.md Epic 2 deviation #2 but the name collision risk for a future true Anthropic embedding provider is not flagged [`_bmad-output/planning-artifacts/architecture.md`]

## Deferred from: code review of 3-1-hybrid-search-engine-and-citation-formatting (2026-04-27)

- Semantic search full table scan — no WHERE predicate on the `embeddings` query; full sequential scan per call. ANN index (IVFFlat/HNSW) needed at scale; acceptable for Phase 1 up-to-10k-doc scope [`src/cos/retrieval/search.py`]
- `register_vector_async` called on every `hybrid_search` invocation — redundant re-registration on already-registered connections; matches `db.py:56` pattern; optimize to register once per connection acquisition in a future story [`src/cos/retrieval/search.py:52`]
- `_coerce_priority_weight` prefix match has no path boundary guard — `/reports` would match `/reports-archive/`; Phase 4 concern; `RolePackConfig` empty in Phase 1 [`src/cos/retrieval/search.py:_coerce_priority_weight`]
- `embed()` failure propagates as IndexError — empty API response raises `IndexError` with no context; retry/circuit-breaker logic belongs in a future infrastructure story [`src/cos/retrieval/search.py:68`]
- Orphaned chunks silently dropped from results — missing `source_paths` lookup silently discards results; data integrity edge case for a future story [`src/cos/retrieval/search.py:162`]
- RRF merge ordering and `top_k` truncation not tested — spec task list did not require these tests; cover when role pack weighting is added in Story 4.3 [`tests/retrieval/test_search.py`]
- Semantic score `> 0.0` filter is silent — zero/negative similarity results dropped without logging; logging deferred to a future observability story [`src/cos/retrieval/search.py:121`]
- Role pack weighting path untested — `RolePackConfig` is empty in Phase 1; test coverage deferred to Story 4.3 [`src/cos/retrieval/search.py`]
- Priority weight silent fallback on misconfigured or negative weights — `_coerce_priority_weight` returns `1.0` on no match and accepts negative floats without validation; Phase 4 concern [`src/cos/retrieval/search.py:_coerce_priority_weight`]

## Deferred from: code review of 1-3-database-schema-and-migration-runner (2026-04-21)

- No migration tracking table — every `run_migrations()` call re-executes all SQL files; safe now because all DDL is idempotent, but any future DML or non-idempotent migration will corrupt the database; add a `schema_migrations` ledger table when needed
- `_has_executable_sql()` doesn't detect `/* */` block comments — current migrations use only `--` line comments; add block comment support before any migration uses `/* */`
- `db.py` logs with hardcoded `"mcp_server"` component string — should use a `"store"` or `"db"` component value; low priority refactor
- `test_run_migrations_is_idempotent` makes only a "no exception" assertion — a stronger assertion (e.g. schema unchanged, no extra tables) would give more confidence; acceptable for Phase 1

## Deferred from: code review of 3-2-outputrouter-and-egress-enforcement (2026-04-27)

- Server starts despite unhealthy Postgres/Tika — unhealthy health checks only emit a log; server proceeds regardless; pre-existing design, not introduced by this story [`src/cos/mcp_server/server.py`]
- `OutputRouter` swallows handler exceptions — errors inside `local.py` or future handlers are caught and logged as JSON but not re-raised; pre-existing router behaviour [`src/cos/output/router.py`]

## Deferred from: code review of 3-3-llm-synthesis-and-retrievalservice (2026-04-27)

- No test for `RuntimeError` path when `message.content` contains no text block — `AnthropicAdapter.complete()` raises `RuntimeError` if all content blocks lack a `text` attribute (e.g. tool_use-only response); not in spec scope, low-probability scenario [`tests/llm/test_anthropic_adapter.py`]

## Deferred from: code review of 3-5-operator-validation-end-to-end-qa-with-citations (2026-04-28)

- Quick-script steps assert `len(docs) >= 3` with no prerequisite guard — design concern; prerequisites section references T2.6.1 ingest step; not a doc error [`docs/manual-testing.md`]
- `_startup_sequence` called directly as a private API in all test snippets — fragile if renamed; established documented pattern; not introduced by this story [`docs/manual-testing.md`]
- T3.5.3 no-results query uses domain-specific physics phrase — may match future KB content if science docs are ingested; acceptable for current test-docs corpus [`docs/manual-testing.md`]
- `list_documents` does not filter by document status — "all ingested documents" claim technically includes inactive docs; pre-existing implementation gap [`src/cos/mcp_server/tools.py`]

## Deferred from: code review of 3-6-documentation-and-housekeeping (2026-04-28)

- `cli.py` "stub commands" comment in README project structure tree is stale — `ingest` and `docs` are fully implemented; only `status`/`logs`/`restart` remain stubs; pre-existing, not introduced by this diff [README.md]
- `manual-testing.md` grep `--tail=5` for OutputRouter log verification is fragile — the log line may scroll past in 5 lines of recent output, silently masking a test failure; pre-existing, explicitly out of scope for Story 3.6 [docs/manual-testing.md]
- `retrieve` error cases undocumented in `setup.md` — the new "Query the Knowledge Base" section documents only the happy path; server-not-initialized, retrieval-failed, and synthesis-failed error envelopes are not described; valid coverage gap, beyond Story 3.6 AC scope [docs/setup.md]

## Deferred from: code review of 4-1-role-pack-schema-and-chro-configuration-file (2026-04-28)

- Empty file → `yaml.safe_load` returns `None` → confusing Pydantic `ValidationError`; Story 4.2 startup sequence will translate errors to human-readable messages [`src/cos/rolepack/loader.py:20-21`]
- Non-dict YAML (list/bare string) passes YAML parse then raises confusing `ValidationError`; Story 4.2 handles error translation [`src/cos/rolepack/loader.py:21`]
- Empty lists accepted for all required `list[str]` fields (`goals: []`, `active_workflows: []`) — add `min_length=1` constraint in a future story
- Empty strings accepted for `role_name` and `tone` — add Pydantic `min_length=1` constraint when validation is hardened
- `active_workflows` and `output_channels` accept arbitrary strings with no enum or slug validation — enforce when workflow registry is defined
- No `model_config = ConfigDict(extra="forbid")` — typo'd YAML keys silently ignored; add when role pack schema is considered stable
- Relative `role_pack.path` resolved against process cwd — Story 4.2 startup sequence should resolve relative to the config file's base directory
- No schema version field in role pack YAML — add when a breaking schema change requires a migration path
- `stakeholder_map: dict[str, str]` silently coerces non-string YAML values (int/bool/null) to strings — acceptable for operator config; tighten with `strict=True` if needed
- `retrieval_priorities` ordering contract (high-to-low weight) not documented in any user-facing comment — add a comment to `config.yaml.example` or `chro.yaml` explaining the ordering semantics

## Deferred from: code review of 4-2-role-pack-loader-and-startup-integration (2026-04-29)

- `PermissionError`/`IsADirectoryError` not caught in startup — file exists but unreadable/is-a-directory causes unhandled crash instead of clean `SystemExit`; spec only required FileNotFoundError, YAMLError, ValidationError handling [`src/cos/mcp_server/server.py:98-112`]
- `UnicodeDecodeError` not caught — invalid UTF-8 role pack file causes unhandled crash instead of clean `SystemExit`; outside spec scope [`src/cos/mcp_server/server.py:98-112`]
- Partial startup leaves `_role_pack_service` set while later globals (pool, output_service) remain None if `create_pool` fails — pre-existing globals pattern shared by all services; no transaction semantics on startup [`src/cos/mcp_server/server.py:86-119`]

## Deferred from: code review of 4-3-role-pack-applied-to-retrieval-and-synthesis (2026-04-29)

- Two-letter domain abbreviations (HR, IT, AI) silently filtered by `len(word) > 2` in `_coerce_priority_weight` — spec-prescribed; CHRO role pack unaffected (priorities contain longer words); relevant only if a future role pack uses short-acronym-only priority strings [`src/cos/retrieval/search.py`]
- `get_role_context` no guard for `svc.get_active()` returning None — current `RolePackService.__init__` always sets `_role_pack`; only becomes a real risk if the service contract changes to allow lazy or partial initialisation [`src/cos/mcp_server/tools.py`]
- `test_startup_sequence_uses_role_pack_output_channels` caplog assertion is a weak proxy — confirms the router logs "unknown output channel" but does not assert no output side-effect was produced; acceptable for the current `OutputRouter.send` silent-suppression contract [`tests/mcp_server/test_server.py`]
- Dict/string branch case-sensitivity inconsistency in `_coerce_priority_weight` — dict branch uses case-sensitive `source_path.startswith(candidate)`; string branch uses `path_lower`; pre-existing, spec explicitly says preserve dict handling unchanged [`src/cos/retrieval/search.py`]
- Module-level `_role_pack_service` singleton has no asyncio lock — `_startup_sequence` writes globals without locking; safe under single-threaded sequential startup; pre-existing pattern shared by all services [`src/cos/mcp_server/server.py`]
- `_patch_server` `_emit` mock does not call `logging`; server tests that use `caplog` rely on `OutputRouter.send` calling `logger.error` directly — subtle but correct for current implementation; pre-existing test infrastructure [`tests/mcp_server/test_server.py`]

## Deferred from: code review of 3-4-mcp-retrieve-and-list-documents-tools (2026-04-27)

- Startup partial init leaves pool open if RetrievalService construction raises — if `RetrievalService(...)` raises after `_pool` is assigned, the pool is never closed; no try/finally or cleanup path; Epic 5 hardening scope [`src/cos/mcp_server/server.py`]
- No pool teardown on server shutdown — `_pool` is opened at startup but no shutdown hook closes it; FastMCP lifecycle hooks are not wired; Epic 5 scope [`src/cos/mcp_server/server.py`]
- `output_service.send("local", ...)` hardcodes channel name — if configured channels change, the send silently fails; Phase 1 assumption that "local" is always present; revisit when multi-channel routing is added [`src/cos/mcp_server/tools.py:73`]
- `ProvenanceService` opens a raw psycopg connection per call rather than using the shared `_pool` — ProvenanceService was designed in Story 2.5 before the pool was introduced; spec prohibits modifying it in this story; connection is short-lived but bypasses pooling [`src/cos/mcp_server/tools.py:109`]
- Empty query string not validated in `retrieve()` — empty/whitespace queries flow through to the service and return a "no content" response; not specified as a requirement; add validation if client bugs surface [`src/cos/mcp_server/tools.py:38`]
- `list_documents` returns all rows with no pagination — unbounded query; acceptable for Phase 1 document volumes; add limit/offset when doc counts grow [`src/cos/mcp_server/tools.py:112`]
- No initialization guard preventing tool calls before `_startup_sequence` completes — tools guard on `get_retrieval_service() is None` returning error envelopes, but there is no mechanism to queue or block concurrent startup calls; pre-existing design [`src/cos/mcp_server/server.py`]

## Deferred from: code review of 4-4-role-pack-and-provider-portability (2026-04-29)

- Silent LLM→embedding transport fallback has no log or comment — when LLM transport fields are None, factory silently falls back to embedding transport values; pre-existing logic moved verbatim from server.py; document or make explicit in config schema [`src/cos/llm/factory.py:13-25`]
- `enterprise_architect.yaml` `active_workflows` references unregistered identifiers — `architecture_review`, `roadmap_alignment`, etc. have no registry; same gap in chro.yaml; enforce when a workflow registry is defined [`role_packs/enterprise_architect.yaml:39-43`]
- Provider string not stripped/validated at factory and embedder entry points — leading/trailing whitespace or empty string reaches the comparison check uncaught; Pydantic validation at config load is the correct guard layer; pre-existing for embedder [`src/cos/llm/factory.py:6`, `src/cos/ingestion/embedder.py:47`]
- Embedder registry doesn't enforce error-handling contract for future provider functions — a registered function that raises a non-`EmbeddingError` will propagate uncaught; document the contract when a second provider is added [`src/cos/ingestion/embedder.py:47-50`]
- `isinstance(result, LLMAdapter)` checks presence only, not method signature — runtime_checkable Protocol limitation; signature drift in `AnthropicAdapter.complete()` won't be caught by this test [`tests/llm/test_factory.py:31`]

## Deferred from: code review of 4-5-operator-validation-chro-role-active-and-switchable (2026-04-29)

- T4.5.1 `'Strategic' in result['data']['tone']` is a case-sensitive substring check against CHRO YAML content; fragile if `chro.yaml` tone text changes [docs/manual-testing.md:T4.5.1]
- Section 11 Step 8 OutputRouter check greps `docker compose logs cos` — T3.5.5 explicitly notes this is not the reliable stream for exec-emitted logs; pre-existing from Epic 3 quick-script [docs/manual-testing.md:Section 11]
- `_startup_sequence` called directly inside short-lived `docker compose exec` sessions; opens a transient DB pool per invocation; established pattern from Epic 3 validation [docs/manual-testing.md:all tests]
- "Wait ~30 seconds" before log inspection is vague; no explicit health-check verification step; consistent with existing pattern throughout the doc [docs/manual-testing.md:T4.5.3, T4.5.4]
- T4.5.3 has no pre-check that `config.yaml` was saved and is visible inside the container before restart — operator could edit the wrong file silently [docs/manual-testing.md:T4.5.3]

## Deferred from: code review of 4-6-documentation-and-housekeeping (2026-04-29)

- `active_workflows` no authoritative list of valid values — inherent to the field being reserved for future workflow engine use; no registry exists yet [`docs/role-packs.md`]
- `output_channels` only valid value is `["local"]` — no other channels currently exist; document alternatives when a second channel is implemented [`docs/role-packs.md`]
- `config.yaml.example` stale `channels` top-level key contradicts architecture Deviation 3 (`OutputRouter` now reads `output_channels` from the role pack, not `config.channels`) — explicitly out of scope per Dev Notes; remove `channels` from `config.yaml.example` in a future housekeeping pass
- `get_role_context` missing error envelope on unexpected exception — `svc.get_active()` cannot raise today but unguarded path survives; pre-existing code issue not introduced by this story [`src/cos/mcp_server/tools.py`]
- Startup log at `server.py:121` still logs `config.channels` after switch to role-pack-driven `output_channels` — misleading if the two differ; pre-existing code bug not introduced by this story [`src/cos/mcp_server/server.py:121`]
- Architecture note 5 (`_EMBED_PROVIDERS`) is only half-accurate for future providers — adding a new provider also requires matching the `VoyageTransportConfig | None` transport interface; document transport contract when a second provider is added [`src/cos/ingestion/embedder.py`]

## Deferred from: code review of 5-2-platform-restart-and-recovery (2026-04-30)

- `subprocess.run` called without `cwd` in restart helpers — docker compose project resolved via directory search from process cwd; expected operator behaviour (running from project root); pre-existing pattern applies to all CLI commands that shell out [`src/cos/cli.py`]
- `_first_unhealthy_service` returns `"cos"` on all failure modes (docker not found, empty output, parse error) — reasonable safe fallback; conflates distinct failure causes but Story 5.3 `cos logs` provides full diagnostics [`src/cos/cli.py:300,309`]
- No distinction between container "unhealthy" vs "starting" states — both treated as "not yet healthy"; message "did not become healthy" is accurate for both; directed to `cos logs` for differentiation [`src/cos/cli.py:_first_unhealthy_service`]
- AC2 30-second timeout budget excludes restart command duration — `_wait_for_healthy` starts its 30s countdown after `docker compose restart` completes; total operator wall time can exceed 30s on slow restarts; integration concern validated in Story 5.5 [`src/cos/cli.py:_wait_for_healthy`]
- `_run_docker_compose_restart` only checks `stderr` for error detail; some docker versions emit errors to stdout — minor; fallback message "docker compose restart failed" is still meaningful [`src/cos/cli.py:277`]

## Deferred from: code review of 5-3-diagnostic-log-export (2026-04-30)

- `_any_containers_running` treats docker-unavailable non-zero returncode as "no containers" — shows misleading "Start the platform first" operator message when Docker socket is down or Docker itself is broken; Story 5.5 operator validation will exercise recovery scenarios [`src/cos/cli.py:_any_containers_running`]
- `subprocess.TimeoutExpired` from `_any_containers_running` propagates to `logs()` outer handler as "Error retrieving logs: ..." — message is confusing since the timeout occurred in the status check, not log retrieval; acceptable for Phase 1; revisit in a future hardening pass [`src/cos/cli.py:_any_containers_running`]

## Deferred from: code review of 5-4-secrets-and-security-audit (2026-05-01)

- Non-APIStatusError Anthropic exceptions (`APIConnectionError`, `APITimeoutError`, `APIResponseValidationError`) bypass the new llm-component structured log in `anthropic.py` — no `status_code` or error type logged for network-level failures; outside this story's security scope [`src/cos/llm/anthropic.py`]
- `get_status` and `get_role_context` MCP tools have no `except Exception` wrapper — raw Python exceptions surface through the MCP transport instead of the safe error envelope returned by `retrieve` and `list_documents`; pre-existing [`src/cos/mcp_server/tools.py`]
- `transport` with `has_overrides=False` constructor boundary has no test — `AnthropicAdapter(transport=HttpTransportConfig())` (non-None transport, all fields at defaults) is a real code path with no coverage [`tests/llm/test_anthropic_adapter.py`]
- HTTPS not verified for transport-override path — `test_adapter_client_uses_https_base_url` only tests the no-transport constructor; the `return`-early branch that injects a custom `httpx.AsyncClient` is not covered [`tests/llm/test_anthropic_adapter.py`]
- `output/router.py` uses `str(exc)` in a structured log field (same pattern fixed elsewhere in this story) — story spec explicitly excluded `router.py`; same anti-pattern as was fixed in `retrieval.py` and `tools.py` [`src/cos/output/router.py:52`]
- `RuntimeError` in `AnthropicAdapter.complete()` has no test after the try/except refactor — already tracked from Story 3.3 review; still unaddressed [`tests/llm/test_anthropic_adapter.py`]
- `caplog` logger-name mismatch risk — `anthropic.py` uses the root logger; refactoring to a named `logging.getLogger(__name__)` logger would silently break the negative assertion in `test_complete_logs_status_code_not_key_on_api_error` without a test failure [`tests/llm/test_anthropic_adapter.py`]

## Deferred from: code review of 5-5-operator-validation-recovery-scenario (2026-05-01)

- `docker compose ps -q postgres` may silently return empty string if Docker Compose container naming differs from service name; project defines service as `postgres` so this works currently but is fragile if project name changes [`docs/manual-testing.md`]
- T5.5.4 fresh subprocess via `docker compose exec` does not test the live running MCP server's state — it's a proxy test that re-initialises a new Python process; acceptable by design but the limitation is invisible to operators [`docs/manual-testing.md`]
- T5.5.4 `_startup_sequence` calls `run_migrations` as an undocumented side-effect during the manual test — idempotent, so safe; only a risk if a future migration is non-idempotent [`docs/manual-testing.md`]
- T5.5.4 `result['data']['answer'] is not None` assertion does not guard against an empty string answer — a synthesis that returns `""` would pass the assertion while indicating a real failure [`docs/manual-testing.md`]
- "three services" (Docker health) vs "five components" (`cos status` health) inconsistency in pre-existing sections of manual-testing.md — outside this story's scope [`docs/manual-testing.md`]
- sprint-status.yaml has duplicate `last_updated` field in both comment header block and YAML data block — pre-existing design; both are updated in sync so no functional impact [`_bmad-output/implementation-artifacts/sprint-status.yaml`]
- CosConfig.load('/app/config.yaml') in T5.5.4 uses a hardcoded path that would silently break if the docker-compose.yml volume mount path changes [`docs/manual-testing.md`]

## Deferred from: code review of 5-6-documentation-and-housekeeping (2026-05-01)

- 30-second `subprocess.run` timeout on `docker compose restart` is undisclosed — if `docker compose restart` itself takes >30s the command fails at the restart step, not the polling step; the "35–45 seconds total wall time" estimate does not apply in that case [`src/cos/cli.py:311`]
- `_check_mcp_server` always returns `healthy=True` — MCP server component can never show ✗ or trigger exit code 1; the documented claim that `cos status` "identifies exactly which component failed" is not true for the MCP server [`src/cos/services/health.py:73`]
- `_check_postgres` and `_check_database` can hang for OS-level TCP timeout (~30s each) — if Postgres container is paused/stuck rather than stopped cleanly, `cos status` may block ~60s before returning [`src/cos/services/health.py:38`]
- "MCP server" display name vs "cos" Docker service name mismatch in stuck-component message — if `cos` container is stuck, user sees "MCP server did not become healthy. Run: cos logs cos" (display name and service name differ in one message) [`src/cos/cli.py:49`]

## Deferred from: code review of 6-1-canonical-blob-source-and-version-schema-hardening (2026-05-05)

- Redundant explicit indexes on UNIQUE-constrained columns — PostgreSQL auto-creates a B-tree index per UNIQUE constraint; `idx_content_blobs_sha256` and `idx_sources_type_locator` are therefore duplicate indexes (wasted storage, marginally slower writes); spec mandated both explicit indexes AND the constraints; remove the redundant `CREATE INDEX` statements in a future housekeeping pass [`src/cos/store/migrations/004_canonical_identity.sql`]
- FK constraint names on source_versions use implicit PostgreSQL naming — three FK constraints have no explicit `CONSTRAINT` clause; PostgreSQL generates `source_versions_source_id_fkey` etc. by convention; tests assert these generated names; add explicit names to match the UNIQUE constraint naming pattern in a future story [`src/cos/store/migrations/004_canonical_identity.sql`]
- source_alias NOT NULL column has no existence test — `sources.source_alias TEXT NOT NULL` is mandatory (no default) but has no column-existence migration test equivalent to those for `content_blob_id` and `document_version_id`; add `test_sources_has_source_alias_column()` in a future story [`tests/store/test_migrations.py`]
- No test for ON DELETE behavior of nullable FK columns — `document_versions.content_blob_id` and `chunks.document_version_id` tests verify column existence only; ON DELETE semantics are untested; add FK behavior assertions once the ON DELETE decision (RESTRICT vs SET NULL) is resolved [`tests/store/test_migrations.py`]

## Deferred from: code review of 6-3-re-ingest-semantics-and-no-op-handling (2026-05-06)

- `store_document_canonical` deletes ALL chunks across all historical document versions on `CHANGED_CONTENT` — version-level chunk history is lost; pre-existing from Story 2.4/6.2; Phase 2 concern [`src/cos/store/db.py`]
- Partially-failed prior ingest leaves orphan source row with no `source_version` link, causing `NEW_SOURCE_KNOWN_CONTENT` on retry — `link_new_source_to_existing_blob` heals implicitly but the mismatch is uncovered by tests [`src/cos/ingestion/identity.py`]
- `link_new_source_to_existing_blob` uses oldest-first `ORDER BY created_at ASC` with no tiebreaker — same-microsecond inserts produce non-deterministic document_id; deferred from 6.2 review [`src/cos/store/db.py`]
- Content revert scenario (v1→v2→v1) produces undefined/untested behavior — outcome depends on whether source_version link was retained; add test when version-revert semantics are defined [`src/cos/ingestion/identity.py`]
- `CHANGED_CONTENT` with empty extraction body shows misleading "0 new chunks indexed (new version)" — confusing operator message for empty-file edge case [`src/cos/cli.py`]

## Deferred from: code review of 6-2-hash-first-ingest-and-exact-byte-deduplication (2026-05-06)

- `_repair_existing_schema` DDL deadlock risk — `ALTER TABLE … ADD CONSTRAINT` on `source_versions` acquires a `ShareLock`; concurrent in-flight ingests at startup are blocked until the lock is acquired; under autocommit the DDL cannot be rolled back on failure; intentional design choice (spec: "no new migrations"); single-user startup context makes deadlock theoretical [`src/cos/store/db.py`]
- `_repair_existing_schema` bypasses the project migration convention — schema changes must live as numbered `.sql` files per CLAUDE.md; this code-level repair runs on every startup creating a parallel schema-management path; spec constraint "no new migrations" required this approach; documented in completion notes [`src/cos/store/db.py`]
- Concurrent ingest race condition — two simultaneous calls for the same file both pass `find_content_blob_by_sha256` as `None` and both proceed to `store_document_canonical`, potentially creating duplicate `documents` rows (no UNIQUE constraint on `source_path`); pre-existing gap (noted from Story 2.3 review); single-user CLI context makes simultaneous ingests theoretical [`src/cos/store/db.py`, `src/cos/ingestion/identity.py`]
## Deferred from: code review of 6-4-citation-and-listing-updates-using-source-alias (2026-05-06)

- `document_version_id=""` empty-string sentinel in `CitedChunk` — typed `str` instead of `Optional[str]`; empty string is used for legacy chunks with no `document_version_id`; consistent with codebase `str=""` defaults throughout models, but ambiguous for downstream consumers checking `is not None` vs truthiness [`src/cos/retrieval/citations.py`]
- Fallback `documents.source_path` query in `hybrid_search` runs for all merged document_ids including those already resolved via canonical `source_versions` — unnecessary DB round-trip for canonical records; filter to only doc_ids not found in `source_info_by_version` before executing [`src/cos/retrieval/search.py`]
- Role pack dict-format priority candidates (e.g. `{"source_path": "/docs/hr/", "weight": 2.0}`) silently never match after 6.4 because `_coerce_priority_weight` now receives `source_alias` (short filename) instead of full path; dict-format is unused by current CHRO role pack (uses string-list format which works correctly); document the change when dict-format priorities are needed [`src/cos/retrieval/search.py`]
- Two identical correlated subqueries for `source_alias` and `source_locator` in `list_documents` — same three-table join executed twice per document row; consolidate into a single `LATERAL` join returning both columns [`src/cos/store/db.py`]

- `find_canonical_document_version_for_blob` non-deterministic on same-microsecond inserts — `ORDER BY created_at ASC LIMIT 1` has no tiebreaker; two `document_versions` rows sharing the same `content_blob_id` inserted within the same microsecond produce arbitrary `document_id` for `NEW_SOURCE_KNOWN_CONTENT` path; a surrogate sequence column or UNIQUE constraint on `(content_blob_id)` in `document_versions` would address permanently [`src/cos/store/db.py`]
- Raw SQL in `check_canonical_identity` violates layering — single inline `conn.execute("SELECT document_id::text FROM document_versions …")` in `identity.py` instead of a `db.py` helper; extract to a `find_document_id_for_version()` helper in a future housekeeping pass [`src/cos/ingestion/identity.py`]
- `UNCHANGED` outcome with `document_id=None` produces an opaque `RuntimeError` — if a `source_versions` row exists but its `document_version_id` has no matching `document_versions` row (broken FK), the pipeline raises with no diagnostic context; improve error message in a future pass [`src/cos/ingestion/pipeline.py`]
- Dual identity keys: `documents.source_path` and `sources.source_locator` are parallel lookup paths — pre-6.2 documents lack `sources`/`source_versions` rows; `store_document_canonical` uses `source_path` for the legacy `documents` lookup independently of the new provenance model; Story 6.5 migration backfill addresses [`src/cos/store/db.py`]
- No test for `link_new_source_to_existing_blob` raising when `content_blob` exists but no `document_version` is linked — the `RuntimeError("No document_version found …")` path is untested; reachable on a partially-migrated DB before Story 6.5 backfill [`src/cos/store/db.py`, `tests/ingestion/test_pipeline.py`]
