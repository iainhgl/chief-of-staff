import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import cast

import psycopg
import typer

from cos.config import CosConfig
from cos.services.health import ComponentStatus, HealthService
from cos.services.ingestion import SUPPORTED_SUFFIXES, IngestService
from cos.services.provenance import DocumentSummary, ProvenanceService, VersionSummary
from cos.store.db import backfill_legacy_documents
from cos.store.models import BackfillResult

app = typer.Typer(name="cos", help="CoS platform CLI")

_RESTART_TIMEOUT = 30
_POLL_INTERVAL = 2
_SERVICES = ("postgres", "tika", "cos")
_DISPLAY_NAMES = {"postgres": "Postgres", "tika": "Tika", "cos": "MCP server"}
_VALID_COMPONENTS = frozenset(_SERVICES)


@app.command()
def status() -> None:
    """Show platform health status."""
    try:
        config = CosConfig.load()
        statuses = asyncio.run(_check_status(config))
        for line in _render_status_report(statuses):
            typer.echo(line)
        if any(not status.healthy for status in statuses):
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error running status check: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command()
def restart() -> None:
    """Restart platform services."""
    try:
        typer.echo("Restarting platform...")
        _run_docker_compose_restart()
        stuck = _wait_for_healthy()
        if stuck is not None:
            display = _DISPLAY_NAMES.get(stuck, stuck.title())
            typer.echo(f"{display} did not become healthy. Run: cos logs {stuck}")
            raise typer.Exit(code=1)
        typer.echo("Platform restarted. All components healthy.")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error restarting platform: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command()
def logs(
    component: str | None = typer.Argument(
        None, help="Component name: postgres, tika, or cos"
    ),
    since: str | None = typer.Option(
        None, "--since", help="Show logs since duration (e.g. 10m, 1h)"
    ),
) -> None:
    """Export platform logs for diagnosis or support."""
    try:
        if component is not None and component not in _VALID_COMPONENTS:
            valid_options = ", ".join(_SERVICES)
            typer.echo(
                f"Unknown component: {component}. Valid options: {valid_options}",
            )
            raise typer.Exit(code=1)

        if not _any_containers_running():
            typer.echo(
                "No containers running. Start the platform first: "
                "docker compose up -d"
            )
            raise typer.Exit(code=1)

        cmd = ["docker", "compose", "logs", "--no-color", "--timestamps"]
        if since:
            cmd.extend(["--since", since])
        else:
            cmd.extend(["--tail", "100"])
        if component:
            cmd.append(component)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "docker compose logs failed")
        typer.echo(result.stdout, nl=False)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error retrieving logs: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command()
def ingest(
    path: str = typer.Argument(..., help="File or folder path to ingest"),
) -> None:
    """Ingest a document or folder into the knowledge base."""
    config = CosConfig.load()
    target = Path(path).resolve()

    if not target.exists():
        typer.echo(f"Error: path not found: {path}", err=True)
        raise typer.Exit(code=1)

    service = IngestService(config)

    try:
        if target.is_file():
            asyncio.run(_ingest_file(target, service))
            return
        if target.is_dir():
            asyncio.run(_ingest_folder(target, service))
            return
    except Exception as exc:
        typer.echo(f"Error ingesting {target.name}: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Error: unsupported path type: {path}", err=True)
    raise typer.Exit(code=1)


async def _ingest_file(target: Path, service: IngestService) -> None:
    result = await service.ingest_file(str(target))
    if result.outcome == "unchanged":
        typer.echo(f"No change detected in {target.name} — already up to date")
    elif result.outcome == "new_source_known_content":
        typer.echo(f"Recorded {target.name} as new source — content already indexed")
    elif result.outcome == "changed_content":
        typer.echo(
            "Updated "
            f"{target.name} -> {result.chunk_count} new chunks indexed "
            "(new version)"
        )
    else:
        typer.echo(f"Ingested {target.name} -> {result.chunk_count} chunks indexed")


async def _ingest_folder(target: Path, service: IngestService) -> None:
    total_files = 0
    total_chunks = 0
    supported_files = 0

    for file_path in sorted(target.rglob("*")):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            typer.echo(f"Skipped {file_path.name} — unsupported format")
            continue
        supported_files += 1

        try:
            result = await service.ingest_file(str(file_path))
        except Exception as exc:
            typer.echo(f"Error ingesting {file_path.name}: {exc}", err=True)
            continue

        if result.outcome == "unchanged":
            typer.echo(f"No change detected in {file_path.name} — already up to date")
        elif result.outcome == "new_source_known_content":
            typer.echo(
                f"Recorded {file_path.name} as new source — content already indexed"
            )
        elif result.outcome == "changed_content":
            typer.echo(
                "Updated "
                f"{file_path.name} -> {result.chunk_count} new chunks indexed "
                "(new version)"
            )
        else:
            typer.echo(
                f"Ingested {file_path.name} -> {result.chunk_count} chunks indexed"
            )
        total_files += 1
        total_chunks += result.chunk_count

    if supported_files == 0:
        typer.echo(f"No supported files found in {target}")
    elif total_files == 0:
        typer.echo(f"No files were ingested successfully from {target}")
    else:
        typer.echo(
            f"Ingested {total_files} files -> {total_chunks} total chunks indexed"
        )


@app.command()
def docs(
    versions: str | None = typer.Option(
        None, "--versions", help="Show version history for document ID"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
) -> None:
    """List ingested documents and provenance metadata."""
    config = CosConfig.load()
    service = ProvenanceService(config)

    if versions is not None:
        if not versions:
            typer.echo("Error: --versions requires a non-empty document ID.", err=True)
            raise typer.Exit(code=1)
        asyncio.run(_docs_versions(service, versions, json_output))
    else:
        asyncio.run(_docs_list(service, json_output))


@app.command()
def migrate() -> None:
    """Backfill legacy documents onto the canonical identity model."""
    try:
        result = asyncio.run(_run_migrate())
        typer.echo(
            f"Migration complete: {result.backfilled} document(s) backfilled, "
            f"{result.already_canonical} already canonical."
        )
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Migration failed: {exc}", err=True)
        raise typer.Exit(code=1)


async def _docs_list(service: ProvenanceService, json_output: bool) -> None:
    documents = await service.list_documents()
    if not documents:
        typer.echo("No documents ingested yet. Run: cos ingest <path>")
        return

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "id": document.id,
                        "source_alias": document.source_alias,
                        "source_locator": document.source_locator,
                        "ingested_at": document.ingested_at.isoformat(),
                        "current_version": document.current_version,
                        "chunk_count": document.chunk_count,
                    }
                    for document in documents
                ],
                indent=2,
            )
        )
        return

    _print_documents_table(documents)


async def _docs_versions(
    service: ProvenanceService,
    document_id: str,
    json_output: bool,
) -> None:
    version_records = await service.list_document_versions(document_id)
    if not version_records:
        typer.echo(f"No versions found for document ID: {document_id}")
        return

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "version_number": version.version_number,
                        "ingested_at": version.ingested_at.isoformat(),
                        "file_hash": version.file_hash,
                    }
                    for version in version_records
                ],
                indent=2,
            )
        )
        return

    _print_versions_table(version_records)


def _print_documents_table(documents: list[DocumentSummary]) -> None:
    header = (
        f"{'ID':<36}  {'SOURCE ALIAS':<40}  {'INGESTED AT':<26}  {'VER':>3}  "
        f"{'CHUNKS':>6}"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for document in documents:
        typer.echo(
            f"{document.id:<36}  "
            f"{document.source_alias[-40:]:<40}  "
            f"{document.ingested_at.isoformat(timespec='seconds'):<26}  "
            f"{document.current_version:>3}  "
            f"{document.chunk_count:>6}"
        )


def _print_versions_table(versions: list[VersionSummary]) -> None:
    header = f"{'VER':>3}  {'INGESTED AT':<26}  FILE HASH"
    typer.echo(header)
    typer.echo("-" * 72)
    for version in versions:
        typer.echo(
            f"{version.version_number:>3}  "
            f"{version.ingested_at.isoformat(timespec='seconds'):<26}  "
            f"{version.file_hash}"
        )


async def _run_migrate() -> BackfillResult:
    config = CosConfig.load()
    async with await psycopg.AsyncConnection.connect(
        config.database.libpq_dsn
    ) as conn:
        return await backfill_legacy_documents(conn)


async def _check_status(config: CosConfig) -> list[ComponentStatus]:
    service = HealthService(
        db_dsn=config.database.libpq_dsn,
        tika_url=config.tika.url,
        role_pack_path=config.role_pack.path,
    )
    return await service.check_all()


def _render_status_report(statuses: list[ComponentStatus]) -> list[str]:
    lines = ["CoS Platform Status", "-------------------"]
    for status in statuses:
        icon = "✓" if status.healthy else "✗"
        message = _display_status_message(status)
        line = f"{status.name:<16}{icon} {message}"
        if not status.healthy and status.recovery_hint:
            line += f" — {status.recovery_hint}"
        lines.append(line)
    return lines


def _display_status_message(status: ComponentStatus) -> str:
    if status.name == "MCP server" and status.healthy:
        return "healthy"
    return status.message


def _run_docker_compose_restart() -> None:
    result = subprocess.run(
        ["docker", "compose", "restart"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker compose restart failed")


def _wait_for_healthy(
    timeout: int = _RESTART_TIMEOUT, poll_interval: int = _POLL_INTERVAL
) -> str | None:
    deadline = time.monotonic() + timeout
    while True:
        stuck = _first_unhealthy_service()
        if stuck is None:
            return None
        if time.monotonic() >= deadline:
            return stuck
        time.sleep(poll_interval)


def _first_unhealthy_service() -> str | None:
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return "cos"

    text = result.stdout.strip()
    if not text:
        return "cos"

    try:
        services = _parse_compose_ps_json(text)
    except Exception:
        return "cos"

    healthy = {
        service.get("Service", "")
        for service in services
        if service.get("Health") == "healthy"
    }
    for name in _SERVICES:
        if name not in healthy:
            return name
    return None


def _parse_compose_ps_json(text: str) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed.append(cast(dict[str, object], json.loads(line)))

    if parsed:
        return parsed
    return cast(list[dict[str, object]], json.loads(text))


def _any_containers_running() -> bool:
    """Return True if at least one Compose service container is running."""
    result = subprocess.run(
        ["docker", "compose", "ps", "-q", "--status=running"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.returncode == 0 and bool(result.stdout.strip())
