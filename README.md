# bbs-ansi-art

Python library for ANSI art — create, view, convert, and repair BBS-era artwork.

## Features

- **Load & Parse**: Read `.ans`, `.asc`, `.diz` files with CP437 encoding
- **SAUCE Metadata**: Full support for reading and writing SAUCE records
- **Render**: Output to terminal, HTML, plain text, or images (PNG)
- **Create**: Programmatic ANSI art creation with fluent builder API
- **Transform**: Resize, crop, decolor, merge canvases
- **Repair**: Fix common encoding and sequence issues
- **LLM Integration**: Tools and prompts for AI-generated art

## Installation

```bash
pip install bbs-ansi-art
```

With optional dependencies:
```bash
pip install bbs-ansi-art[image]  # PNG rendering (requires Pillow)
pip install bbs-ansi-art[cli]    # Command-line tools
pip install bbs-ansi-art[all]    # Everything
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

# Create new ANSI art
art = (ansi.create(80)
    .fg(36)  # Cyan
    .bold()
    .text("Hello, BBS World!")
    .newline()
    .reset()
    .text("Welcome back to 1994.")
    .build())

# Save with SAUCE metadata
doc = ansi.AnsiDocument(canvas=art)
doc.sauce = ansi.SauceRecord(title="Hello", author="Me")
doc.save("hello.ans")
```

## Rendering to Different Formats

```python
from bbs_ansi_art.render import TerminalRenderer, HtmlRenderer, TextRenderer

doc = ansi.load("artwork.ans")

# Terminal (ANSI escape sequences)
print(TerminalRenderer().render(doc.canvas))

# HTML
html = HtmlRenderer().render(doc.canvas)

# Plain text (no colors)
text = TextRenderer().render(doc.canvas)
```

## Architecture

```
bbs_ansi_art/
├── core/           # Canvas, Cell, Color, Document
├── codec/          # CP437 encoding, ANSI parser
├── sauce/          # SAUCE metadata read/write
├── render/         # Terminal, HTML, Text, Image renderers
├── create/         # Builder API, fonts, effects
├── transform/      # Resize, crop, decolor, merge
├── repair/         # Fix encoding/sequence issues
├── io/             # File read/write
└── llm/            # AI integration tools
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Inspired by the BBS/ANSI art scene of the 1990s
- SAUCE specification: https://www.acid.org/info/sauce/sauce.htm
- CP437 reference: https://en.wikipedia.org/wiki/Code_page_437
