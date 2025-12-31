# ANSI Art Technical Learnings

A comprehensive guide to parsing, rendering, and generating ANSI art based on hard-won implementation experience.

---

## 1. ANSI Escape Sequence Parsing

### Critical Insight: Parse at Byte Level BEFORE Encoding Conversion

```
The ESC character (0x1B) must be handled at the RAW BYTE level
BEFORE any CP437-to-Unicode conversion. If you convert first,
ESC becomes ← (U+2190) and sequence parsing breaks!
```

### CSI (Control Sequence Introducer) Sequences

| Sequence | Command | Description |
|----------|---------|-------------|
| `ESC[...m` | SGR | Select Graphic Rendition (colors, bold) |
| `ESC[...H` / `ESC[...f` | CUP | Cursor Position (row;col) |
| `ESC[...A` | CUU | Cursor Up |
| `ESC[...B` | CUD | Cursor Down |
| `ESC[...C` | CUF | Cursor Forward (right) |
| `ESC[...D` | CUB | Cursor Back (left) |
| `ESC[...J` | ED | Erase in Display (0=to end, 1=to start, 2=all) |
| `ESC[...K` | EL | Erase in Line |
| `ESC[s` | SCP | Save Cursor Position |
| `ESC[u` | RCP | Restore Cursor Position |

### SGR (Select Graphic Rendition) Color Codes

```python
# Attributes
0   = Reset all
1   = Bold ON (makes colors bright)
5   = Blink ON
22  = Bold OFF
25  = Blink OFF

# Standard foreground (30-37)
30=black, 31=red, 32=green, 33=yellow, 34=blue, 35=magenta, 36=cyan, 37=white
39  = Default foreground

# Standard background (40-47)
40=black, 41=red, 42=green, 43=yellow, 44=blue, 45=magenta, 46=cyan, 47=white
49  = Default background

# Bright colors (bold flag OR explicit codes)
90-97   = Bright foreground
100-107 = Bright background

# 256-color mode
38;5;N  = Foreground color N
48;5;N  = Background color N
```

### Sequences to IGNORE (Cause Problems)

```python
ESC[...t  # Window manipulation - causes flicker/resize!
ESC[?...h # Mode set (e.g., ?7h for line wrap)
ESC[?...l # Mode reset
```

---

## 2. CP437 Character Encoding

### The Challenge

ANSI art files use CP437 (IBM PC/DOS) encoding. Bytes 0x00-0xFF map to graphical characters, not just ASCII. Modern systems use Unicode.

### Essential Block Drawing Characters

```
Hex   CP437  Unicode  Description
0xDB  █      U+2588   Full block
0xDC  ▄      U+2584   Lower half block
0xDF  ▀      U+2580   Upper half block
0xDD  ▌      U+258C   Left half block
0xDE  ▐      U+2590   Right half block
0xB0  ░      U+2591   Light shade
0xB1  ▒      U+2592   Medium shade
0xB2  ▓      U+2593   Dark shade
```

### Box Drawing Characters (0xB3-0xDA range)

```
Single: ─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼
Double: ═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬
Mixed:  Various single/double combinations
```

### Control Character Range (0x00-0x1F) - GOTCHA!

In CP437, control codes display as SYMBOLS:
```
0x01 = ☺   0x02 = ☻   0x03 = ♥   0x04 = ♦
0x05 = ♣   0x06 = ♠   0x0E = ♫   0x0F = ☼
0x10 = ►   0x11 = ◄   0x1E = ▲   0x1F = ▼
```

BUT some must be handled as control characters during parsing!

---

## 3. Control Characters Requiring Special Handling

### Must Handle at Parse Time (NOT convert to CP437 symbols)

| Byte | Name | Action |
|------|------|--------|
| 0x1B | ESC | Start of escape sequence |
| 0x0D | CR | Carriage return → cursor_x = 0 |
| 0x0A | LF | Line feed → cursor_y += 1 |
| 0x09 | TAB | Advance to next 8-column tab stop |
| 0x1A | EOF | SAUCE marker - STOP PARSING |

### The SAUCE EOF Marker (0x1A)

```
Many ANSI files have SAUCE metadata at the end:
[art content...] 0x1A SAUCE00 [metadata...]

When you see 0x1A, STOP - don't parse the SAUCE as art!
```

### Tab Stop Calculation

```python
cursor_x = ((cursor_x // 8) + 1) * 8
if cursor_x >= width:
    cursor_x = 0
    cursor_y += 1
```

---

## 4. Terminal Rendering Gotchas

### Color Bleeding into Clear-to-EOL

**Problem:** `ESC[K` (clear to end of line) uses current background color.

**Solution:** Reset colors at end of each rendered line:
```python
if last_bg != 40 or last_bold:
    line_parts.append('\x1b[0m')
```

### Black Background Mismatch

**Problem:** `ESC[40m` (palette black) renders as dark gray on some terminals.

**Solution:** Use `ESC[49m` (default background) instead:
```python
# Black should match terminal's actual background
sgr_parts.append('49' if cell.bg == 40 else str(cell.bg))
```

### Screen Flicker

**Problem:** Clearing screen before redraw causes visible flicker.

**Solution:** Move cursor to home and overwrite in place:
```python
# DON'T: Terminal.clear()  # Causes flicker
# DO: Move to home and overwrite
Terminal.move_to(1, 1)
# End each line with ESC[K to clear leftovers
```

### Redraw Optimization

**Problem:** Constant redraws prevent mouse text selection.

**Solution:** Only redraw when state changes:
```python
if self._needs_redraw:
    self._render()
    self._needs_redraw = False
```

---

## 5. Input Handling Challenges

### Escape Sequence Timing

**Problem:** Arrow keys send `ESC[A`, but bytes may arrive split:
- Read 1: `ESC` (0x1B)
- Read 2: `[A`

A bare `ESC` could be the Escape key OR start of a sequence!

**Solution:** Buffer and wait with timeout:
```python
if self._buffer == '\x1b':
    # Wait up to 100ms for more bytes
    self._wait_for_escape_sequence()
```

### Use os.read() Not sys.stdin.read()

```python
# sys.stdin.read() uses Python buffering - breaks sequences!
# Use os.read() to bypass:
data = os.read(sys.stdin.fileno(), 1024)
```

### Arrow Key Formats (Two Variants!)

```python
# CSI format (most common)
ESC[A = Up, ESC[B = Down, ESC[C = Right, ESC[D = Left

# SS3 format (application mode)
ESC O A = Up, ESC O B = Down, etc.
```

---

## 6. Virtual Terminal State Machine

### State to Track

```python
cursor_x: int = 0
cursor_y: int = 0
fg: int = 37        # Default white
bg: int = 40        # Default black
bold: bool = False
blink: bool = False
saved_x: int = 0    # For ESC[s
saved_y: int = 0    # For ESC[u
```

### Line Wrapping

```python
# Wrap BEFORE placing character
if cursor_x >= width:
    cursor_x = 0
    cursor_y += 1
```

---

## 7. Known Issues in Wild ANSI Files

### Window Manipulation Sequences

Some files contain `ESC[...t` sequences that resize/move terminal windows. **Must filter out!**

### Mode Set/Reset Sequences

`ESC[?7h` (enable line wrap) and similar. Safe to ignore for display.

### Artist Signature Blocks

Some files have intentional single-character marks (like `░` in dark gray) near the end. These are legitimate design elements, not parsing errors.

### Inconsistent Line Endings

Some files use:
- LF only (Unix style)
- CR+LF (DOS style)
- CR only (old Mac style)

Handle all three!

---

## 8. Parser Architecture Summary

```
Raw Bytes (CP437 encoded)
         │
         ▼
┌─────────────────────────────────┐
│ Byte-level Control Check        │
│ 0x1B → Parse escape sequence    │
│ 0x0D → CR (cursor to col 0)     │
│ 0x0A → LF (next row)            │
│ 0x09 → TAB (next tab stop)      │
│ 0x1A → STOP (SAUCE marker)      │
└─────────────────────────────────┘
         │ (if displayable)
         ▼
┌─────────────────────────────────┐
│ CP437 → Unicode Conversion      │
│ ONLY for display characters     │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Place on Canvas at cursor       │
│ with current FG/BG/Bold state   │
└─────────────────────────────────┘
```

---

## 9. For ANSI Art Generation

### Clean Output Requirements

When generating ANSI art for reliable display:

1. **Use only well-supported sequences:**
   - `ESC[0m` - Reset
   - `ESC[1m` - Bold
   - `ESC[30-37m` - Foreground colors
   - `ESC[40-47m` - Background colors

2. **Avoid problematic sequences:**
   - No `ESC[...t` (window manipulation)
   - No `ESC[?...h/l` (mode changes)
   - No 256-color unless needed

3. **Always reset at end:**
   - End file with `ESC[0m`
   - Reset colors at end of each line

4. **Use standard width:**
   - 80 columns is traditional BBS width
   - Some art uses 160 columns

5. **Character set:**
   - Stick to printable CP437 (0x20-0xFF)
   - Avoid control characters except CR/LF
   - Block characters: █ ▄ ▀ ░ ▒ ▓

---

*Last updated: 2024-12-31*
*Based on bbs-ansi-art implementation experience*
