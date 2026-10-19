"""Command line entry point: ``abap-mcp [--root DIR] [--http] [--port N]``."""

from __future__ import annotations

import argparse
from pathlib import Path

from abap_mcp import __version__
from abap_mcp.server import create_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="abap-mcp", description="MCP server for ABAP code in abapGit format.")
    parser.add_argument("--root", type=Path, default=None, help="workspace folder (default: $ABAP_MCP_ROOT or cwd)")
    parser.add_argument("--http", action="store_true", help="serve Streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    server = create_server(args.root)
    if args.http:
        server.run("streamable-http", host=args.host, port=args.port)
    else:
        server.run()


if __name__ == "__main__":
    main()
