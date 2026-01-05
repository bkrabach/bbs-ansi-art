# ANSI Art Editor Implementation

## Status: ✅ Complete

## Overview
Dual-format editing capabilities for bbs-ansi-art:
- `.ANS` files: Cell-level editing with 16-color palette
- `.art` files: Pixel-level editing with 24-bit RGB

## Architecture

```
src/bbs_ansi_art/
├── core/
│   ├── cell.py          ✅ Extended with fg_rgb/bg_rgb
│   └── pixel.py          ✅ NEW: Pixel dataclass
├── edit/                  ✅ NEW: Editing subsystem
│   ├── __init__.py
│   ├── editable.py       ✅ EditableCanvas ABC, EditContext
│   ├── cell_canvas.py    ✅ CellEditableCanvas for .ANS
│   ├── pixel_canvas.py   ✅ PixelEditableCanvas for .art
│   └── document.py       ✅ EditableDocument wrapper
├── render/
│   └── terminal.py       ✅ Updated for RGB (38;2;R;G;B)
└── cli/
    ├── widgets/
    │   ├── art_editor.py     ✅ NEW: Editor widget
    │   └── color_palette.py  ✅ NEW: Color picker
    ├── studio/
    │   └── editor.py         ✅ NEW: Editor app
    └── app.py                ✅ Added 'edit' command
```

## Implementation Summary

### Phase 1: Core Data Structures ✅
- [x] Extended `Cell` with `fg_rgb`/`bg_rgb` optional tuple fields
- [x] Added `is_true_color`, `effective_fg`, `effective_bg` properties
- [x] Created `Pixel` dataclass in `core/pixel.py`
- [x] Updated `TerminalRenderer` to emit `38;2;R;G;B` / `48;2;R;G;B` sequences

### Phase 2: Edit Module ✅
- [x] Created `edit/` package structure
- [x] Implemented `EditableCanvas` ABC and `EditContext`
- [x] Implemented `CellEditableCanvas` for .ANS (wraps Canvas)
- [x] Implemented `PixelEditableCanvas` for .art (parses/renders true-color ANSI)
- [x] Implemented `EditableDocument` wrapper with format auto-detection

### Phase 3: Editor Widget ✅
- [x] Created `ArtEditorWidget` with cursor tracking
- [x] Implemented keyboard navigation (arrows, hjkl, Home/End/PgUp/PgDn)
- [x] Implemented drawing (space/enter to paint, 'd' draw+advance)
- [x] Added cursor overlay with reverse video

### Phase 4: Color System ✅
- [x] Created `ColorPaletteWidget` with 16-color mode
- [x] Added RGB mode with R/G/B component sliders
- [x] Integrated color sync between editor and palette

### Phase 5: Studio Integration ✅
- [x] Created `editor.py` with full EditorApp
- [x] Added `bbs-ansi-art edit <file>` CLI command
- [x] Save functionality (Ctrl+S)
- [x] Status bar with cursor position, mode, colors

## Usage

```bash
# Edit existing file
bbs-ansi-art edit artwork.ans
bbs-ansi-art edit image.art

# Keyboard shortcuts in editor:
# Navigation: Arrow keys, h/j/k/l, Home/End, PgUp/PgDn
# Drawing: Space/Enter (paint), d (paint+advance), x (erase)
# Colors: 0-9/a-f (16-color), [/] (cycle FG), {/} (cycle BG)
# UI: P (toggle palette), Tab (focus palette), Ctrl+S (save), Q/Esc (quit)
```

## Key Design Decisions

1. **Separate Canvas Implementations**: `CellEditableCanvas` vs `PixelEditableCanvas` for clean separation between 16-color cell editing and 24-bit pixel editing.

2. **Format Fidelity**: `.ANS` files stay 16-color, `.art` files preserve full RGB. No lossy conversions.

3. **Pixel Grid for .art**: Stores pixel data internally, re-renders to ANSI on save. Enables pixel-level editing and proper round-trip.

4. **Half-block Mapping**: Each terminal cell = 2 vertical pixels. `▀` char with FG=top, BG=bottom.

## Files Created/Modified

| File | Status | Description |
|------|--------|-------------|
| `core/cell.py` | Modified | Added RGB fields |
| `core/pixel.py` | New | Pixel dataclass |
| `render/terminal.py` | Modified | RGB sequence output |
| `edit/__init__.py` | New | Package exports |
| `edit/editable.py` | New | ABC and enums |
| `edit/cell_canvas.py` | New | .ANS editing |
| `edit/pixel_canvas.py` | New | .art editing |
| `edit/document.py` | New | Document wrapper |
| `cli/widgets/art_editor.py` | New | Editor widget |
| `cli/widgets/color_palette.py` | New | Color picker |
| `cli/studio/editor.py` | New | Editor app |
| `cli/app.py` | Modified | Added edit command |

## Future Enhancements (Not Implemented)

- [ ] Undo/redo history
- [ ] Mouse support
- [ ] Additional tools (line, rectangle, fill)
- [ ] Copy/paste regions
- [ ] Character picker for .ANS mode
