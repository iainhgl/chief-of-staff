"""Local stdout/MCP response channel."""
import sys


def send(content: str) -> None:
    sys.stdout.write(content + "\n")
    sys.stdout.flush()
