# BBS ANSI Art - Project Roadmap

## Vision

A complete Python toolkit for working with BBS-era ANSI art: viewing, creating, repairing, and generating new art with AI assistance.

---

## Architecture Overview

```
bbs_ansi_art/
├── core/           # Canvas, Cell, Color, Document - data structures
├── codec/          # CP437 encoding, ANSI escape sequence parser
├── sauce/          # SAUCE metadata read/write
├── render/         # Output renderers (terminal, HTML, text, image)
├── create/         # Builder API for programmatic art creation
├── repair/         # Clean/fix problematic ANSI files
├── transform/      # Transformations (resize, crop, etc.)
├── io/             # File read/write operations
├── llm/            # AI generation support (styles, prompts, specs)
└── cli/            # Command-line interface
    ├── core/       # Terminal handling, input, layout
    ├── widgets/    # Reusable TUI components
    ├── studio/     # Interactive applications
    └── commands/   # CLI command implementations
```

---

## Feature Status

### ✅ Completed

**Core Library**
- [x] CP437 ↔ Unicode conversion
- [x] ANSI escape sequence parser (byte-level)
- [x] Canvas/Cell data model
- [x] SAUCE metadata reading
- [x] Terminal renderer with color optimization
- [x] HTML renderer
- [x] Plain text renderer

**CLI & Studio**
- [x] `bbs-ansi-art view <file>` - view single file
- [x] `bbs-ansi-art studio [path]` - interactive browser
- [x] `bbs-ansi-art info <file>` - show SAUCE metadata
- [x] `bbs-ansi-art convert <src> <dst>` - format conversion
- [x] File browser with directory navigation
- [x] Real-time art preview
- [x] SAUCE info panel (press 's')
- [x] Vim-style navigation (j/k, g/G, Ctrl+U/D)

### 🚧 In Progress

**Repair Module**
- [ ] `bbs-ansi-art clean <file>` - remove problematic sequences
- [ ] Clean action in studio (press 'c')
- [ ] Batch cleaning of directories

**Generation (LLM)**
- [ ] Style presets for AI art generation
- [ ] ArtSpec builder for prompts
- [ ] Example-based learning from reference art

### 📋 Planned

**Studio Enhancements**
- [ ] Art editing capabilities
- [ ] Color palette viewer
- [ ] Side-by-side comparison
- [ ] Export options (HTML, PNG)

**Transform Module**
- [ ] Resize/scale art
- [ ] Crop regions
- [ ] Merge multiple artworks
- [ ] Color remapping

**Advanced Features**
- [ ] Animation support (ANSI animations)
- [ ] Font rendering for PNG export
- [ ] Thumbnail generation
- [ ] Art gallery/collection management

---

## CLI Commands

### Current

| Command | Description |
|---------|-------------|
| `studio [path]` | Interactive file browser and viewer |
| `view <file>` | Display art in terminal |
| `info <file>` | Show SAUCE metadata |
| `convert <src> <dst>` | Convert to HTML/text |

### Planned

| Command | Description |
|---------|-------------|
| `clean <file> [-o output]` | Remove problematic escape sequences |
| `clean --batch <dir>` | Clean all files in directory |
| `generate <spec>` | Generate art from specification |
| `diff <file1> <file2>` | Compare two artworks |

---

## Studio Keyboard Shortcuts

### Current

| Key | Action |
|-----|--------|
| `↑/↓` or `j/k` | Navigate files (with wrap) |
| `←/h` | Go to parent directory |
| `→/l` or `Enter` | Enter directory / open file |
| `Ctrl+U/D` | Half-page scroll |
| `g/G` | Jump to top/bottom |
| `PgUp/PgDn` | Full page scroll |
| `s` | Toggle SAUCE info |
| `b` | Toggle browser panel |
| `q` or `Esc` | Quit |

### Planned

| Key | Action |
|-----|--------|
| `c` | Clean current file (save cleaned copy) |
| `e` | Export current file |
| `?` | Help overlay |
| `/` | Search files |

---

## Repair Module Design

### Problematic Sequences to Remove

| Sequence | Issue |
|----------|-------|
| `ESC[...t` | Window manipulation (resize/move) |
| `ESC[?...h/l` | Terminal mode changes |
| `ESC[...r` | Scrolling region (breaks display) |

### Clean Operation

```python
# Library usage
from bbs_ansi_art.repair import clean_file, clean_bytes

# Clean a file
cleaned_path = clean_file("art.ans")  # Returns path to cleaned file

# Clean raw bytes
cleaned_data = clean_bytes(raw_data)

# CLI usage
bbs-ansi-art clean messy.ans -o clean.ans
bbs-ansi-art clean --batch ./downloads/ --output ./cleaned/
```

---

## LLM Generation Design

### Workflow

1. **Load reference art** - Parse existing .ANS files as examples
2. **Build ArtSpec** - Define what to generate (content, style, size)
3. **Generate prompt** - Create LLM prompt with examples and spec
4. **Parse output** - Convert LLM response to valid ANSI art
5. **Validate** - Ensure output renders correctly

### Style Presets

| Style | Characteristics |
|-------|-----------------|
| `acid` | High contrast, neon colors, dripping effects |
| `ice` | Blue/cyan palette, crystalline patterns |
| `blocky` | Heavy use of block characters |
| `ascii` | Pure ASCII, no extended characters |
| `minimal` | Clean lines, limited colors |
| `dark` | Low contrast, shadow effects |

---

## Technical Debt / Known Issues

- [ ] No unit tests for ansi_parser.py (critical)
- [ ] No unit tests for terminal renderer
- [ ] TUI components lack automated testing
- [ ] Some 256-color art may not render perfectly

---

*Last updated: 2024-12-31*
