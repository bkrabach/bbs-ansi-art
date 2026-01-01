"""Typer CLI application with command groups."""

from pathlib import Path
from typing import Annotated, Optional

try:
    import typer
    from rich.console import Console
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False


def create_app() -> "typer.Typer":
    """Create and configure the CLI application."""
    if not HAS_TYPER:
        raise ImportError("typer and rich are required for CLI. Install with: uv pip install bbs-ansi-art[cli]")
    
    app = typer.Typer(
        name="bbs-ansi-art",
        help="Create, view, convert, and repair BBS-era ANSI artwork.",
        no_args_is_help=True,
        rich_markup_mode="rich",
    )
    console = Console()
    
    @app.command()
    def view(
        path: Annotated[Path, typer.Argument(help="File or directory to view")],
        interactive: Annotated[bool, typer.Option("--interactive", "-i", help="Launch interactive studio")] = False,
        sauce: Annotated[bool, typer.Option("--sauce", "-s", help="Show SAUCE metadata")] = False,
    ) -> None:
        """View ANSI artwork in terminal or studio."""
        import bbs_ansi_art as ansi
        
        if path.is_dir() or interactive:
            # Launch studio viewer
            from bbs_ansi_art.cli.studio.viewer import run_viewer
            run_viewer(path if path.exists() else None)
        else:
            # Simple terminal output
            doc = ansi.load(path)
            
            if sauce and doc.sauce:
                console.print(f"[bold]Title:[/] {doc.sauce.title}")
                console.print(f"[bold]Author:[/] {doc.sauce.author}")
                console.print(f"[bold]Group:[/] {doc.sauce.group}")
                console.print(f"[bold]Size:[/] {doc.sauce.tinfo1}x{doc.sauce.tinfo2}")
                console.print()
            
            print(doc.render())
    
    @app.command()
    def info(
        path: Annotated[Path, typer.Argument(help="ANSI file to inspect")],
        json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
    ) -> None:
        """Show SAUCE metadata for an ANSI file."""
        import json
        import bbs_ansi_art as ansi
        
        doc = ansi.load(path)
        
        if not doc.sauce:
            console.print(f"[yellow]No SAUCE metadata found in {path}[/]")
            raise typer.Exit(1)
        
        if json_output:
            data = {
                "title": doc.sauce.title,
                "author": doc.sauce.author,
                "group": doc.sauce.group,
                "date": doc.sauce.date.isoformat() if doc.sauce.date else None,
                "width": doc.sauce.tinfo1,
                "height": doc.sauce.tinfo2,
                "comments": doc.sauce.comments,
            }
            print(json.dumps(data, indent=2))
        else:
            console.print(f"[bold cyan]SAUCE Metadata for {path.name}[/]")
            console.print(f"  [bold]Title:[/]  {doc.sauce.title or '(none)'}")
            console.print(f"  [bold]Author:[/] {doc.sauce.author or '(none)'}")
            console.print(f"  [bold]Group:[/]  {doc.sauce.group or '(none)'}")
            if doc.sauce.date:
                console.print(f"  [bold]Date:[/]   {doc.sauce.date.strftime('%Y-%m-%d')}")
            console.print(f"  [bold]Size:[/]   {doc.sauce.tinfo1}x{doc.sauce.tinfo2}")
            if doc.sauce.comments:
                console.print(f"  [bold]Comments:[/]")
                for comment in doc.sauce.comments:
                    console.print(f"    {comment}")
    
    @app.command()
    def convert(
        source: Annotated[Path, typer.Argument(help="Source ANSI file")],
        dest: Annotated[Path, typer.Argument(help="Destination file")],
        format: Annotated[Optional[str], typer.Option("--format", "-f", help="Output format (auto-detected from extension)")] = None,
    ) -> None:
        """Convert ANSI art to HTML, PNG, or plain text."""
        import bbs_ansi_art as ansi
        
        doc = ansi.load(source)
        fmt = format or dest.suffix.lstrip('.').lower()
        
        if fmt == "html":
            dest.write_text(doc.render_to_html())
        elif fmt == "txt" or fmt == "text":
            dest.write_text(doc.render_to_text())
        elif fmt in ("png", "jpg", "jpeg", "gif"):
            console.print("[red]Image export requires Pillow. Install with: uv pip install bbs-ansi-art[image][/]")
            raise typer.Exit(1)
        else:
            console.print(f"[red]Unknown format: {fmt}[/]")
            raise typer.Exit(1)
        
        console.print(f"[green]Converted {source} → {dest}[/]")
    
    @app.command()
    def studio(
        path: Annotated[Optional[Path], typer.Argument(help="Optional file or directory")] = None,
    ) -> None:
        """Launch the interactive ANSI art studio."""
        from bbs_ansi_art.cli.studio.viewer import run_viewer
        run_viewer(path)
    
    @app.command()
    def clean(
        paths: Annotated[list[Path], typer.Argument(help="File(s) or directory to clean")],
        output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output directory for cleaned files")] = None,
        in_place: Annotated[bool, typer.Option("--in-place", "-i", help="Overwrite original files")] = False,
        strip_sauce: Annotated[bool, typer.Option("--strip-sauce", "-s", help="Remove SAUCE metadata")] = False,
        strip_text: Annotated[bool, typer.Option("--strip-text", "-t", help="Replace text with spaces (keep only graphical chars)")] = False,
    ) -> None:
        """Clean problematic escape sequences from ANSI files.
        
        Removes sequences that cause display issues:
        - Window manipulation (causes flicker/resize)
        - Mode set/reset (not needed for display)
        """
        from bbs_ansi_art.repair import clean_file
        
        # Collect all files to process
        files: list[Path] = []
        for p in paths:
            if p.is_dir():
                files.extend(p.glob("*.ANS"))
                files.extend(p.glob("*.ans"))
            else:
                files.append(p)
        
        if not files:
            console.print("[yellow]No .ans files found[/]")
            return
        
        # Determine output directory
        output_dir = output
        if output_dir and not in_place:
            output_dir.mkdir(exist_ok=True)
        
        cleaned_count = 0
        for f in sorted(files):
            if in_place:
                out_path = f
            elif output_dir:
                out_path = output_dir / f.name
            else:
                out_path = f.with_stem(f.stem + "_clean")
            
            _, result = clean_file(f, out_path, strip_sauce_data=strip_sauce, strip_text_data=strip_text)
            
            if result.was_modified:
                msg = f"removed {result.sequences_removed} sequences"
                if result.details.get('sauce_stripped'):
                    msg += f", stripped SAUCE ({result.details['sauce_stripped']} bytes)"
                if result.details.get('text_chars_stripped'):
                    msg += f", stripped {result.details['text_chars_stripped']} text chars"
                console.print(f"[green]{f.name}[/]: {msg}")
                cleaned_count += 1
            else:
                console.print(f"[dim]{f.name}[/]: clean")
        
        console.print(f"\n[bold]Cleaned {cleaned_count}/{len(files)} files[/]")
        if output_dir and not in_place:
            console.print(f"Output: {output_dir}")
    
    return app
