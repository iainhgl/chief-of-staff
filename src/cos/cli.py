import asyncio
import json as _json
from pathlib import Path

import typer

from cos.config import CosConfig
from cos.services.ingestion import SUPPORTED_SUFFIXES, IngestService
from cos.services.provenance import DocumentSummary, ProvenanceService, VersionSummary

app = typer.Typer(name="cos", help="CoS platform CLI")


@app.command()
def status() -> None:
    """Show platform health status."""
    raise NotImplementedError


@app.command()
def restart() -> None:
    """Restart platform services."""
    raise NotImplementedError


@app.command()
def logs() -> None:
    """Tail platform logs."""
    raise NotImplementedError


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
    typer.echo(f"Ingested {target.name} -> {result.chunk_count} chunks indexed")


async def _ingest_folder(target: Path, service: IngestService) -> None:
    total_files = 0
    total_chunks = 0

    for file_path in sorted(target.rglob("*")):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            typer.echo(f"Skipped {file_path.name} — unsupported format")
            continue

        try:
            result = await service.ingest_file(str(file_path))
        except Exception as exc:
            typer.echo(f"Error ingesting {file_path.name}: {exc}", err=True)
            continue

        typer.echo(f"Ingested {file_path.name} -> {result.chunk_count} chunks indexed")
        total_files += 1
        total_chunks += result.chunk_count

    if total_files == 0:
        typer.echo(f"No supported files found in {target}")
    else:
        typer.echo(f"Ingested {total_files} files -> {total_chunks} total chunks indexed")


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


async def _docs_list(service: ProvenanceService, json_output: bool) -> None:
    documents = await service.list_documents()
    if not documents:
        typer.echo("No documents ingested yet. Run: cos ingest <path>")
        return

    if json_output:
        typer.echo(
            _json.dumps(
                [
                    {
                        "id": document.id,
                        "source_path": document.source_path,
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
            _json.dumps(
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
        f"{'ID':<36}  {'SOURCE PATH':<40}  {'INGESTED AT':<26}  {'VER':>3}  "
        f"{'CHUNKS':>6}"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for document in documents:
        typer.echo(
            f"{document.id:<36}  "
            f"{document.source_path[-40:]:<40}  "
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
