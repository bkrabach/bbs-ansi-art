"""Convert images to terminal art (.art format).

The .art format is UTF-8 text with ANSI SGR color codes for true color display
in modern terminals. It uses half-block characters (▀) to achieve 2x vertical
resolution - each character cell represents two pixels.

This is distinct from classic .ANS files which use CP437 encoding and 16 colors.

Example:
    from bbs_ansi_art.import_image import from_png
    
    # Convert PNG to .art file
    from_png("logo.png", "logo.art", width=78)
    
    # Then display with: cat logo.art
"""

from pathlib import Path
from typing import Union

try:
    from PIL import Image, ImageEnhance, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Block characters for transparency handling
UPPER_HALF = "▀"  # FG = top pixel, BG = bottom pixel
LOWER_HALF = "▄"  # FG = bottom pixel, BG = top pixel


def _check_pil() -> None:
    """Raise ImportError if PIL is not available."""
    if not HAS_PIL:
        raise ImportError(
            "Pillow is required for image import. "
            "Install with: uv pip install bbs-ansi-art[image]"
        )


def _parse_color(color: str) -> tuple[int, int, int]:
    """Parse a color string to RGB tuple.
    
    Accepts:
        - Named colors: "black", "white", "red", "green", "blue", "magenta", "cyan", "yellow"
        - Hex colors: "#FF00FF", "FF00FF", "#F0F", "F0F"
        - RGB tuples: "255,0,255" or "255 0 255"
    """
    color = color.strip().lower()
    
    # Named colors
    named = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "magenta": (255, 0, 255),
        "cyan": (0, 255, 255),
        "yellow": (255, 255, 0),
    }
    if color in named:
        return named[color]
    
    # Hex color
    if color.startswith("#"):
        color = color[1:]
    if len(color) == 3:
        # Short form: F0F -> FF00FF
        color = color[0]*2 + color[1]*2 + color[2]*2
    if len(color) == 6:
        try:
            return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
        except ValueError:
            pass
    
    # RGB tuple: "255,0,255" or "255 0 255"
    import re
    match = re.match(r'(\d+)[,\s]+(\d+)[,\s]+(\d+)', color)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    
    raise ValueError(f"Cannot parse color: {color!r}")


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculate Euclidean distance between two RGB colors."""
    return ((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2) ** 0.5


def from_png(
    input_path: Union[str, Path],
    output_path: Union[str, Path, None] = None,
    width: int = 78,
    *,
    sharpen: bool = True,
    sharpen_amount: int = 200,
    color_boost: float = 1.5,
    contrast_boost: float = 1.2,
    black_threshold: int = 30,
    transparent: bool = False,
    alpha_threshold: int = 128,
    transparent_color: str | None = None,
    color_tolerance: int = 30,
) -> str:
    """
    Convert a PNG image to terminal art (.art format).
    
    Uses half-block rendering (▀/▄) with true color (24-bit RGB) for high-fidelity
    output in modern terminals. The image is intelligently downscaled with
    sharpening and color enhancement to preserve detail at small sizes.
    
    Args:
        input_path: Path to input PNG/JPG/GIF image
        output_path: Path to output .art file (default: input with .art extension)
        width: Target width in characters (default: 78, leaves room for margins)
        sharpen: Apply unsharp mask to restore crispness after downscale
        sharpen_amount: Sharpening intensity as percentage (default: 200)
        color_boost: Saturation multiplier to prevent washed-out colors (default: 1.5)
        contrast_boost: Contrast multiplier (default: 1.2)
        black_threshold: RGB values below this become pure black (default: 30)
        transparent: Preserve alpha channel as terminal default background
        alpha_threshold: Alpha values below this are considered transparent (default: 128)
        transparent_color: Treat this color as transparent (e.g., "black", "#FF00FF", "255,0,255")
        color_tolerance: How close a color must be to transparent_color to be transparent (default: 30)
        
    Returns:
        The generated art as a string (also written to output_path if provided)
        
    Raises:
        ImportError: If Pillow is not installed
        IOError: If input image cannot be opened
    """
    _check_pil()
    
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_suffix(".art")
    else:
        output_path = Path(output_path)
    
    # Load image - preserve alpha if transparent mode
    img = Image.open(input_path)
    if transparent and img.mode in ('RGBA', 'LA', 'PA'):
        img = img.convert("RGBA")
        has_alpha = True
    else:
        img = img.convert("RGB")
        has_alpha = False
    
    # Calculate new height maintaining aspect ratio
    aspect_ratio = img.height / img.width
    new_height = int(width * aspect_ratio)
    
    # Downscale with Lanczos (high quality, preserves text structure)
    img = img.resize((width, new_height), Image.Resampling.LANCZOS)
    
    # Restore crispness lost during downscale
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(
            radius=1.0,
            percent=sharpen_amount,
            threshold=5
        ))
    
    # Boost colors to prevent washed-out appearance
    if color_boost != 1.0:
        img = ImageEnhance.Color(img).enhance(color_boost)
    if contrast_boost != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast_boost)
    
    # Parse transparent color if provided
    chroma_key: tuple[int, int, int] | None = None
    if transparent_color:
        chroma_key = _parse_color(transparent_color)
    
    # Convert to art
    pixels = img.load()
    lines: list[str] = []
    
    # Process two rows at a time
    for y in range(0, img.height, 2):
        line_parts: list[str] = []
        last_fg: tuple[int, int, int] | None = None
        last_bg: tuple[int, int, int] | None = None
        last_bg_transparent = False
        
        for x in range(img.width):
            # Get top pixel
            pixel_t = pixels[x, y]
            if has_alpha:
                r_t, g_t, b_t, a_t = pixel_t
                top_transparent = a_t < alpha_threshold
            else:
                r_t, g_t, b_t = pixel_t
                top_transparent = False
            
            # Check chroma key (color-based transparency)
            if chroma_key and not top_transparent:
                if _color_distance((r_t, g_t, b_t), chroma_key) <= color_tolerance:
                    top_transparent = True
            
            # Get bottom pixel
            if y + 1 < img.height:
                pixel_b = pixels[x, y + 1]
                if has_alpha:
                    r_b, g_b, b_b, a_b = pixel_b
                    bottom_transparent = a_b < alpha_threshold
                else:
                    r_b, g_b, b_b = pixel_b
                    bottom_transparent = False
                
                # Check chroma key for bottom pixel
                if chroma_key and not bottom_transparent:
                    if _color_distance((r_b, g_b, b_b), chroma_key) <= color_tolerance:
                        bottom_transparent = True
            else:
                r_b, g_b, b_b = (0, 0, 0)
                bottom_transparent = transparent or chroma_key is not None  # Treat missing row as transparent
            
            # Black clipping (only for opaque pixels)
            if black_threshold > 0:
                if not top_transparent and r_t < black_threshold and g_t < black_threshold and b_t < black_threshold:
                    r_t, g_t, b_t = 0, 0, 0
                if not bottom_transparent and r_b < black_threshold and g_b < black_threshold and b_b < black_threshold:
                    r_b, g_b, b_b = 0, 0, 0
            
            # Choose character and colors based on transparency
            if top_transparent and bottom_transparent:
                # Both transparent - space with default BG
                char = " "
                fg = None
                bg_transparent = True
            elif top_transparent:
                # Top transparent, bottom opaque - lower half block
                char = LOWER_HALF
                fg = (r_b, g_b, b_b)  # FG shows bottom pixel
                bg_transparent = True
            elif bottom_transparent:
                # Top opaque, bottom transparent - upper half block
                char = UPPER_HALF
                fg = (r_t, g_t, b_t)  # FG shows top pixel
                bg_transparent = True
            else:
                # Both opaque - upper half block with both colors
                char = UPPER_HALF
                fg = (r_t, g_t, b_t)
                bg_transparent = False
            
            # Emit color codes
            if fg is not None and fg != last_fg:
                line_parts.append(f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m")
                last_fg = fg
            
            if bg_transparent:
                if not last_bg_transparent:
                    line_parts.append("\x1b[49m")  # Default/transparent background
                    last_bg_transparent = True
            else:
                bg = (r_b, g_b, b_b)
                if bg != last_bg or last_bg_transparent:
                    line_parts.append(f"\x1b[48;2;{r_b};{g_b};{b_b}m")
                    last_bg = bg
                    last_bg_transparent = False
            
            line_parts.append(char)
        
        # Reset at end of line
        line_parts.append("\x1b[0m")
        lines.append("".join(line_parts))
    
    # Final output - just the art, no screen manipulation
    art = "\n".join(lines) + "\n"
    
    # Write to file
    output_path.write_text(art, encoding="utf-8")
    
    return art


def to_canvas(
    input_path: Union[str, Path],
    width: int = 78,
    **kwargs,
) -> "Canvas":
    """
    Convert an image to a Canvas object for further manipulation.
    
    This allows importing images into the bbs-ansi-art pipeline for
    transformation, rendering to different formats, etc.
    
    Note: True color information is quantized to 16 colors when stored
    in a Canvas (which uses the classic ANSI color model).
    
    Args:
        input_path: Path to input image
        width: Target width in characters
        **kwargs: Additional arguments passed to from_png()
        
    Returns:
        Canvas object with the imported image
    """
    _check_pil()
    
    from bbs_ansi_art.core.canvas import Canvas
    from bbs_ansi_art.core.cell import Cell
    
    input_path = Path(input_path)
    img = Image.open(input_path).convert("RGB")
    
    # Calculate dimensions
    aspect_ratio = img.height / img.width
    new_height = int(width * aspect_ratio)
    
    # Downscale
    img = img.resize((width, new_height), Image.Resampling.LANCZOS)
    
    # Apply enhancements
    sharpen = kwargs.get("sharpen", True)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=200, threshold=5))
    
    color_boost = kwargs.get("color_boost", 1.5)
    contrast_boost = kwargs.get("contrast_boost", 1.2)
    if color_boost != 1.0:
        img = ImageEnhance.Color(img).enhance(color_boost)
    if contrast_boost != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast_boost)
    
    pixels = img.load()
    
    # Create canvas - each row of canvas represents 2 pixel rows
    canvas_height = (img.height + 1) // 2
    canvas = Canvas(width=width)
    
    for canvas_y in range(canvas_height):
        canvas.ensure_row(canvas_y)
        pixel_y = canvas_y * 2
        
        for x in range(width):
            # Get top and bottom pixels
            r_t, g_t, b_t = pixels[x, pixel_y]
            if pixel_y + 1 < img.height:
                r_b, g_b, b_b = pixels[x, pixel_y + 1]
            else:
                r_b, g_b, b_b = (0, 0, 0)
            
            # Quantize to nearest 16-color palette
            # This is a simple approximation - could be improved with dithering
            fg = _rgb_to_ansi16(r_t, g_t, b_t)
            bg = _rgb_to_ansi16(r_b, g_b, b_b)
            
            cell = Cell(char=UPPER_HALF, fg=fg, bg=bg + 10)  # bg codes are fg + 10
            canvas.set(x, canvas_y, cell)
    
    return canvas


def _rgb_to_ansi16(r: int, g: int, b: int) -> int:
    """
    Convert RGB to nearest ANSI 16-color code (30-37, 90-97).
    
    Uses simple threshold-based mapping.
    """
    # Determine if each channel is "on" (bright enough)
    threshold = 128
    bright_threshold = 192
    
    red = r >= threshold
    green = g >= threshold
    blue = b >= threshold
    
    # Check if it's a bright color
    is_bright = r >= bright_threshold or g >= bright_threshold or b >= bright_threshold
    
    # Build color code
    # 30=black, 31=red, 32=green, 33=yellow, 34=blue, 35=magenta, 36=cyan, 37=white
    code = 30
    if red:
        code += 1
    if green:
        code += 2
    if blue:
        code += 4
    
    # Use bright variant (90-97) for bright colors
    if is_bright and code > 30:
        code += 60
    
    return code
