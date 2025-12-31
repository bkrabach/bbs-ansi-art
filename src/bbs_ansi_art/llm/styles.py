"""Predefined art styles for LLM generation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StylePreset:
    """A named style with description and example guidance."""
    name: str
    description: str
    guidance: str
    example_prompt: str


# Registry of built-in styles
STYLES: dict[str, StylePreset] = {
    "acid": StylePreset(
        name="ACiD Style",
        description="Classic ACiD Productions aesthetic from the 1990s",
        guidance="""Use shading blocks (░▒▓█), bold vibrant colors,
high contrast, dramatic shadows. Layer shading from light to dark.
Use the full CP437 character set including box drawing characters.
Prefer cyan, magenta, and white for highlights.""",
        example_prompt="In the style of ACiD Productions circa 1994-1996"
    ),
    
    "ice": StylePreset(
        name="iCE Style",
        description="iCE Advertisements aesthetic - clean and professional",
        guidance="""Clean lines, vibrant colors, detailed shading,
professional appearance. Use smooth gradients with block characters.
Emphasize readability and visual impact. Often blue/cyan themed.""",
        example_prompt="In the style of iCE Advertisements"
    ),
    
    "blocky": StylePreset(
        name="Blocky/Oldschool",
        description="Simple block characters, minimal shading",
        guidance="""Use primarily █ full blocks and solid colors.
Bold, simple shapes without complex shading. High contrast.
Reminiscent of early BBS art before detailed shading techniques.""",
        example_prompt="Oldschool blocky ANSI style with minimal shading"
    ),
    
    "ascii": StylePreset(
        name="Pure ASCII",
        description="Traditional ASCII art using only printable ASCII",
        guidance="""Use only printable ASCII characters (32-126).
No extended CP437 characters. Create form through character density
and careful selection of glyphs like @#$%&*+=- etc.""",
        example_prompt="Traditional ASCII art style, no extended characters"
    ),
    
    "amiga": StylePreset(
        name="Amiga Style",
        description="Amiga demoscene inspired aesthetic",
        guidance="""Colorful, playful, with smooth curves suggested by
careful block placement. Often features gradients and a more
European demoscene sensibility. Use creative Unicode if allowed.""",
        example_prompt="Amiga demoscene inspired ANSI art"
    ),
    
    "dark": StylePreset(
        name="Dark/Gothic",
        description="Dark, moody, gothic aesthetic",
        guidance="""Dark background, limited bright colors. Use deep
reds, purples, and grays. Heavy use of shadow blocks (░▒).
Atmospheric and brooding. Skulls, flames, and dark imagery.""",
        example_prompt="Dark gothic ANSI art with moody atmosphere"
    ),
    
    "neon": StylePreset(
        name="Neon/Cyberpunk",
        description="Bright neon colors on dark background",
        guidance="""High contrast neon colors: bright cyan, magenta,
yellow, green on black. Cyberpunk aesthetic with tech imagery.
Glowing effects suggested by color gradients.""",
        example_prompt="Neon cyberpunk style with glowing effects"
    ),
    
    "minimal": StylePreset(
        name="Minimalist",
        description="Clean, simple, lots of whitespace",
        guidance="""Sparse design with careful use of space.
Few colors, clean lines. Let negative space do the work.
Focus on essential shapes and forms.""",
        example_prompt="Minimalist ANSI art with clean lines"
    ),
}


def get_style(name: str) -> StylePreset | None:
    """Get a style preset by name (case-insensitive)."""
    return STYLES.get(name.lower())


def list_styles() -> list[str]:
    """Get list of available style names."""
    return list(STYLES.keys())


def get_style_guidance(name: str) -> str:
    """Get the guidance text for a style, or empty string if not found."""
    style = get_style(name)
    return style.guidance if style else ""
