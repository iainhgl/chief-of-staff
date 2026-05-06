# Story 6.6: OAuth Authentication Setup for Gmail and Calendar

Status: review

## Story

As an operator,
I want to authenticate Gmail and Google Calendar once with local token refresh,
So that connectors can access live data without repeated re-authorisation.

## Acceptance Criteria

1. **Given** `config.yaml` contains valid Google OAuth client credentials,
   **When** `cos auth gmail` or `cos auth calendar` is run for the first time,
   **Then** a browser-based OAuth flow completes and the resulting token is stored under `tokens/` with a plain-language success confirmation.

2. **Given** tokens exist and later expire,
   **When** a connector makes an API call,
   **Then** the auth library refreshes the token locally using the stored refresh token without requiring a new manual consent flow.

3. **Given** the `tokens/` directory exists,
   **When** repository ignore rules are reviewed,
   **Then** the token directory is gitignored and no generated token artifact is committed.

4. **Given** a connector runs without the required token file,
   **When** authentication fails,
   **Then** the system logs a connector-scoped error with a direct recovery instruction and leaves the MCP retrieval path available.

---

## Tasks / Subtasks

- [x] Task 1: Extend the config contract for Google OAuth client credentials without breaking the current local-only baseline (AC: #1)
  - [x] Add an optional `GoogleOAuthConfig` model in [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) and wire it into `CosConfig` as `google_oauth: GoogleOAuthConfig | None = None`
  - [x] Use `SecretStr` for `client_secret` so the new credential stays masked in repr/str output just like the LLM and database secrets
  - [x] Keep the block optional so existing Epic 1-5 configs still load unchanged when connectors/auth are not being used
  - [x] Document the new `google_oauth` block in [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) with a clear note that it is required only for Epic 6 connected-source auth

- [x] Task 2: Add a shared Google auth helper that owns scopes, token paths, browser flow, token persistence, and refresh semantics (AC: #1, #2, #4)
  - [x] Create [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)
  - [x] Define the connector-specific scope and token mapping in one place:
    - Gmail: scope `https://www.googleapis.com/auth/gmail.readonly`, token file `tokens/gmail.json`
    - Calendar: scope `https://www.googleapis.com/auth/calendar.readonly`, token file `tokens/google_calendar.json`
  - [x] Implement a browser-based installed-app OAuth flow using Google’s supported client libraries; request offline access so the stored token contains a refresh token
  - [x] Persist newly issued credentials to the connector-specific token file and rewrite the same file after a successful refresh
  - [x] If a token file is missing, malformed, missing required scopes, or cannot be refreshed, raise a connector-scoped auth error with a direct recovery command (`cos auth gmail` or `cos auth calendar`)

- [x] Task 3: Add explicit `cos auth` CLI commands for first-time authorisation (AC: #1)
  - [x] Introduce a Typer sub-app in [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py) so the CLI shape matches the acceptance criteria exactly: `cos auth gmail` and `cos auth calendar`
  - [x] Print plain-language success output that names the connector and the token file written under `tokens/`
  - [x] Fail with a direct, operator-friendly message when `google_oauth` is missing or the OAuth flow fails
  - [x] Keep the commands host-friendly: they should work with `uv run cos auth ...` from the repo root so the browser opens on the operator’s machine

- [x] Task 4: Make the connector stubs auth-capable without implementing live polling or ingestion yet (AC: #2, #4)
  - [x] Replace the stub-only contents of [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py) with a small helper surface that loads Gmail credentials through the shared auth module
  - [x] Replace the stub-only contents of [src/cos/connectors/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/calendar.py) with the equivalent Calendar credential loader
  - [x] On missing/invalid credentials, emit structured JSON logs using the existing repo pattern (`logging.error(json.dumps({...}))`) with `component: "connector"`, the connector name, the failure message, and a recovery instruction
  - [x] Do not implement Gmail polling, Calendar event fetches, jobs, or ingest logic here; those belong to Stories 6.7, 6.8, and 6.9

- [x] Task 5: Persist token files across host auth and container-side refresh (AC: #2, #3)
  - [x] Update [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml) to mount `./tokens` into the `cos` container as a writable path so connector-side token refresh survives container restarts and rebuilds
  - [x] Keep `.gitignore` as the protection boundary for generated token files; only adjust comments if needed, do not remove the existing `tokens/` ignore rule
  - [x] Ensure the auth helper creates the token directory automatically when it does not exist

- [x] Task 6: Add dependency coverage for the chosen Google auth implementation (AC: #1, #2)
  - [x] Add the required Google OAuth libraries to [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml) and refresh `uv.lock`
  - [x] Prefer the smallest dependency set that cleanly supports installed-app browser auth plus local refresh; do not add Gmail/Calendar API client code yet unless it is strictly required for credential refresh

- [x] Task 7: Add automated tests for config loading, auth flow orchestration, refresh behaviour, and CLI UX (AC: #1, #2, #4)
  - [x] Extend [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py) to cover the optional `google_oauth` block and secret masking of `client_secret`
  - [x] Add [tests/connectors/test_google_auth.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_google_auth.py) for connector/token-path selection, missing-token recovery errors, refresh-and-rewrite behaviour, and malformed token handling
  - [x] Add [tests/cli/test_cli_auth.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_auth.py) for `cos auth gmail` and `cos auth calendar` success/failure output and exit codes
  - [x] Keep all tests offline by patching the Google flow/credentials objects; no real browser launch, token exchange, or Google API call should occur in CI

- [x] Task 8: Update the operator docs for the new auth flow and recovery path (AC: #1, #3, #4)
  - [x] Update [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) with a short Google OAuth setup section covering the new `google_oauth` config block, host-side `uv run cos auth ...` commands, token file locations, and recovery steps
  - [x] Keep [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) as the Epic 5 baseline for now; the full connected-source smoke test belongs to Story 6.11 / 6.12

---

## Dev Notes

### Story Positioning

Story 6.6 is the first **connected-source enablement** story after the canonical identity hardening run:

- Story 6.1 introduced `content_blobs`, `sources`, `source_versions`, and `document_versions`
- Story 6.2 enforced hash-first exact-byte deduplication
- Story 6.3 locked the four canonical ingest outcomes
- Story 6.4 switched citations/listings to `source_alias` + `source_locator`
- Story 6.5 backfilled legacy records and documented operator recovery

That work is now complete. This story does **not** revisit ingest semantics, provenance schema, chunking, retrieval, or MCP tool contracts. Its sole job is to put a stable Google OAuth foundation in place so Stories 6.8 and 6.9 can consume live Gmail and Calendar data safely.

### Product and Architecture Requirements Driving This Story

- FR31: a single human-editable config artifact remains the operator contract for credentials and connector settings
- FR32 / FR33: Google Calendar and Gmail are the first external read connectors
- NFR5: credentials must never be logged or exposed in responses
- NFR11: connector auth failures must degrade the connector path only, not the core retrieval path
- NFR20: Google OAuth tokens must refresh locally without repeated re-authorisation

Architecture decisions already recorded in [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md):

- OAuth tokens live in a separate `tokens/` directory, not in `config.yaml`
- The `connectors/` package is the right ownership boundary for connector-specific auth helpers
- Connected-source work must not undermine the existing `docker compose up` / MCP baseline
- The future container layout explicitly expects `tokens/gmail.json` and `tokens/google_calendar.json`

### Critical Implementation Guardrails

1. **Do not make Google OAuth mandatory at startup.**
Current users can still run the whole Epic 1-5 platform with `connectors: []`. `CosConfig.load()` must continue to accept configs that do not define `google_oauth`.

2. **Do not run auth at MCP server startup.**
This story adds explicit operator commands and reusable credential loaders. It must not block `docker compose up`, `cos status`, `retrieve`, or any other existing core path waiting for Gmail/Calendar consent.

3. **Do not store refreshable tokens inside the image filesystem only.**
Today [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml) mounts `data/`, `config.yaml`, `role_packs/`, and `local/certs/`, but not `tokens/`. Without a writable `tokens/` mount, connector-side refresh would be lost on rebuild/recreate. Fix that in this story.

4. **Use least-privilege scopes.**
This story only needs read access:
   - Gmail: `gmail.readonly`
   - Google Calendar: `calendar.readonly`

5. **Request offline access explicitly.**
The first-time OAuth flow must reliably obtain a refresh token. A one-time access token without offline refresh fails AC #2 and NFR20.

6. **Contain connector auth failures.**
Missing token, revoked token, invalid scope, or refresh failure should become a connector-scoped error with a direct recovery instruction, not a crash that breaks unrelated platform features.

7. **Keep scope tight.**
No jobs queue, no polling scheduler, no Gmail message parsing, no Calendar event shaping, no ingest writes, and no health/status expansion in this story.

### Suggested File Touchpoints

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
- [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py)
- [src/cos/connectors/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/calendar.py)
- [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)
- [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml)
- [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml)
- [uv.lock](/Users/iain.livingstone/Development/CoS/cos/uv.lock)
- [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
- [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py)
- [tests/cli/test_cli_auth.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_auth.py)
- [tests/connectors/test_google_auth.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_google_auth.py)

### Recommended Config Shape

Keep the operator-facing config minimal and human-editable. A suggested block is:

```yaml
google_oauth:
  client_id: YOUR_GOOGLE_OAUTH_CLIENT_ID
  client_secret: YOUR_GOOGLE_OAUTH_CLIENT_SECRET
```

Hardcode Google’s standard auth/token endpoints in the implementation rather than forcing the operator to paste verbose client JSON into `config.yaml`.

### CLI and Runtime Behaviour

- `cos auth gmail` should perform first-time consent for Gmail and save `tokens/gmail.json`
- `cos auth calendar` should perform first-time consent for Calendar and save `tokens/google_calendar.json`
- Future connector code should call a shared credential loader that:
  - loads the token file
  - checks validity/scopes
  - refreshes expired credentials locally when a refresh token is present
  - rewrites the token file after refresh
  - raises a recovery-friendly error if the operator needs to re-run auth

The host/container split matters here:

- Operators should run `uv run cos auth ...` on the host so a browser can open normally
- Gmail/Calendar connector code will run inside the `cos` container later, so the token directory must be mounted into the container and remain writable for refresh updates

### Logging Pattern

Match the repo’s existing structured logging convention, for example:

```python
logging.error(
    json.dumps(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "component": "connector",
            "connector": "gmail",
            "message": "missing Gmail OAuth token",
            "recovery": "Run: uv run cos auth gmail",
        }
    )
)
```

Keep the message plain-language and recovery-oriented. Never log token contents, refresh tokens, or the raw client secret.

### Testing Strategy

- Patch Google OAuth flow objects rather than launching a real browser
- Patch credential refresh rather than calling Google
- Verify that refreshed credentials are written back to disk
- Verify that missing tokens produce connector-specific recovery text
- Verify that adding `google_oauth.client_secret` does not leak in `repr(config)` or `str(config)`
- Verify that existing non-Google configs still load unchanged

### Non-Goals

- No Gmail API message fetch implementation yet
- No Google Calendar event fetch implementation yet
- No queue/worker integration yet
- No MCP tool additions yet
- No schema migration work is expected in this story
- No changes to retrieval, citation, or canonical ingest semantics are expected in this story

### Source References

- [Epic 6 in epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture decisions for OAuth/token storage](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD external connectivity and credential requirements](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Previous story: 6.5 migration/backfill](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-5-migration-backfill-and-operator-recovery.md)

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No blockers or debug sessions required.

### Completion Notes List

- Added `GoogleOAuthConfig` Pydantic model to `src/cos/config.py` with `SecretStr` for `client_secret`; wired as `google_oauth: GoogleOAuthConfig | None = None` on `CosConfig` — existing configs load unchanged.
- Created `src/cos/connectors/google_auth.py`: owns scope/token-path mapping, `InstalledAppFlow` browser OAuth, token file persistence, automatic refresh via `google-auth`, and `AuthError` with connector-scoped recovery instructions.
- Added `auth_app` Typer sub-app to `src/cos/cli.py` with `cos auth gmail` and `cos auth calendar` commands; prints named token file on success, exits 1 with operator-friendly message on missing config or flow failure.
- Replaced stub `gmail.py` and `calendar.py` with `get_gmail_credentials()` / `get_calendar_credentials()` helpers that delegate to the shared auth module and emit structured JSON error logs on failure.
- Added `./tokens:/app/tokens` volume mount to `docker-compose.yml` so container-side token refresh survives rebuilds.
- Added `google-auth-oauthlib>=1.2.0` to `pyproject.toml`; `uv sync` pulled in `google-auth==2.50.0`, `google-auth-oauthlib==1.3.1`, and transitive deps.
- Added 5 new config tests, 12 google_auth unit tests, and 8 CLI auth tests — all offline (no real browser/Google API calls). 230 total non-integration tests pass; lint clean.
- Added Google OAuth setup section to `docs/setup.md` covering credentials, first-time auth, token storage, refresh, and recovery.

### File List

- `src/cos/config.py` — added `GoogleOAuthConfig`, `CosConfig.google_oauth` field
- `src/cos/cli.py` — added `auth_app`, `auth_gmail`, `auth_calendar`, `_run_connector_auth`
- `src/cos/connectors/google_auth.py` — new: shared auth helper
- `src/cos/connectors/gmail.py` — replaced stub with `get_gmail_credentials()`
- `src/cos/connectors/calendar.py` — replaced stub with `get_calendar_credentials()`
- `config.yaml.example` — added commented-out `google_oauth` block with setup instructions
- `docker-compose.yml` — added `./tokens:/app/tokens` volume mount
- `pyproject.toml` — added `google-auth-oauthlib>=1.2.0`
- `uv.lock` — updated with google-auth / google-auth-oauthlib / transitive deps
- `docs/setup.md` — added Google OAuth Setup section
- `tests/test_config.py` — extended with 5 Google OAuth config tests
- `tests/connectors/__init__.py` — new: package init
- `tests/connectors/test_google_auth.py` — new: 12 offline auth helper tests
- `tests/cli/test_cli_auth.py` — new: 8 CLI auth command tests

## Change Log

- 2026-05-06: Story created and marked ready-for-dev.
- 2026-05-06: Implementation complete; status set to review.
