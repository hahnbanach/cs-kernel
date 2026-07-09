"""Entry point for `python -m cs`. Delegates to the CLI."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
