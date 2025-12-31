"""Main CLI entry point with command routing."""

import sys
from pathlib import Path
from typing import Optional


def main() -> None:
    """Main CLI entry point."""
    # Check for TUI dependencies
    try:
        from bbs_ansi_art.cli.app import create_app
        app = create_app()
        app()
    except ImportError:
        # Minimal fallback without typer
        _fallback_main()


def _fallback_main() -> None:
    """Minimal CLI when typer is not installed."""
    args = sys.argv[1:]
    
    if not args or args[0] in ("-h", "--help"):
        print("bbs-ansi-art - ANSI art toolkit")
        print()
        print("Install CLI extras for full functionality:")
        print("  uv pip install bbs-ansi-art[cli]")
        print()
        print("Basic usage (library mode):")
        print("  python -c \"import bbs_ansi_art as ansi; print(ansi.load('art.ans').render())\"")
        return
    
    if args[0] == "view" and len(args) > 1:
        # Basic view command without TUI
        import bbs_ansi_art as ansi
        doc = ansi.load(args[1])
        print(doc.render())
        return
    
    print(f"Unknown command: {args[0]}")
    print("Install CLI extras: uv pip install bbs-ansi-art[cli]")
    sys.exit(1)


if __name__ == "__main__":
    main()
