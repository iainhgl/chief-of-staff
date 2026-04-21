import typer

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
def ingest(path: str = typer.Argument(..., help="Path to file to ingest")) -> None:
    """Ingest a document into the knowledge base."""
    raise NotImplementedError
