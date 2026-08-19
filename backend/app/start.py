"""Run database migrations before starting Uvicorn."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    backend_dir = Path(__file__).resolve().parent.parent
    command.upgrade(Config(str(backend_dir / "alembic.ini")), "head")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
