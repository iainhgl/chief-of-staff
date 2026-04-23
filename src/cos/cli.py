import asyncio
from pathlib import Path

import typer

from cos.config import CosConfig
from cos.services.ingestion import SUPPORTED_SUFFIXES, IngestService

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
        typer.echo(
            f"Done: {total_files} file(s) ingested, {total_chunks} total chunks indexed"
        )
