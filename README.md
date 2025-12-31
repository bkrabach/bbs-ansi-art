# bbs-ansi-art

Python library for ANSI art — create, view, convert, and repair BBS-era artwork.

## Features

- **Load & Parse**: Read `.ans`, `.asc`, `.diz` files with CP437 encoding
- **SAUCE Metadata**: Full support for reading and writing SAUCE records
- **Render**: Output to terminal, HTML, plain text, or images (PNG)
- **Create**: Programmatic ANSI art creation with fluent builder API
- **Studio**: Interactive terminal studio with file browser
- **LLM Integration**: Style presets and ArtSpec for AI-generated art

## Installation

```bash
uv pip install bbs-ansi-art
```

With optional dependencies:
```bash
uv pip install bbs-ansi-art[cli]    # Studio and CLI tools
uv pip install bbs-ansi-art[image]  # PNG rendering (requires Pillow)
uv pip install bbs-ansi-art[llm]    # LLM generation support
uv pip install bbs-ansi-art[all]    # Everything
```

## Quick Start

```python
import bbs_ansi_art as ansi

# Load and display ANSI art
doc = ansi.load("artwork.ans")
print(doc.render())

# Check SAUCE metadata
if doc.sauce:
    print(f"Title: {doc.sauce.title}")
    print(f"Author: {doc.sauce.author}")

# Create new ANSI art programmatically
art = (ansi.create(80)
    .fg(36).bold().text("Hello, BBS World!")
    .newline()
    .reset().text("Welcome back to 1994.")
    .build())
```

## Studio

Launch the interactive ANSI art studio:
```bash
bbs-ansi-art studio ~/Downloads/
bbs-ansi-art view artwork.ans -i
```

## LLM Art Generation (Preview)

```python
from bbs_ansi_art.create import ArtSpec
from bbs_ansi_art.llm import list_styles

# Available styles: acid, ice, blocky, ascii, amiga, dark, neon, minimal
print(list_styles())

# Build a specification for LLM generation
spec = (ArtSpec()
    .with_content("A dragon guarding treasure")
    .with_style("acid")
    .with_dimensions(80, 25)
    .with_instruction("Include fire effects"))
```

## Architecture

```
bbs_ansi_art/
├── core/           # Canvas, Cell, Color, Document
├── codec/          # CP437 encoding, ANSI parser
├── sauce/          # SAUCE metadata read/write
├── render/         # Terminal, HTML, Text renderers
├── create/         # Builder API, ArtSpec
├── io/             # File read/write
├── llm/            # Style presets for AI generation
└── cli/            # Studio and CLI tools
    ├── core/       # Terminal, input handling
    ├── widgets/    # Reusable components
    └── studio/     # Interactive applications
```

## License

MIT License - see [LICENSE](LICENSE) for details.
