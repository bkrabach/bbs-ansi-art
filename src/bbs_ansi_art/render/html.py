"""Render ANSI art to HTML."""

from bbs_ansi_art.core.canvas import Canvas


# Standard 16-color palette (CSS colors)
PALETTE_16 = [
    "#000000",  # 0 - Black
    "#aa0000",  # 1 - Red
    "#00aa00",  # 2 - Green
    "#aa5500",  # 3 - Yellow/Brown
    "#0000aa",  # 4 - Blue
    "#aa00aa",  # 5 - Magenta
    "#00aaaa",  # 6 - Cyan
    "#aaaaaa",  # 7 - White
    "#555555",  # 8 - Bright Black
    "#ff5555",  # 9 - Bright Red
    "#55ff55",  # 10 - Bright Green
    "#ffff55",  # 11 - Bright Yellow
    "#5555ff",  # 12 - Bright Blue
    "#ff55ff",  # 13 - Bright Magenta
    "#55ffff",  # 14 - Bright Cyan
    "#ffffff",  # 15 - Bright White
]


class HtmlRenderer:
    """Render a Canvas to HTML with inline styles or CSS classes."""
    
    def __init__(
        self,
        css_class: str = "ansi-art",
        use_inline_styles: bool = True,
        font_family: str = "monospace",
    ):
        self.css_class = css_class
        self.use_inline_styles = use_inline_styles
        self.font_family = font_family
    
    def render(self, canvas: Canvas) -> str:
        """Render canvas to HTML string."""
        lines: list[str] = []
        
        for row in canvas.rows():
            line_spans: list[str] = []
            current_span: list[str] = []
            current_fg = 37
            current_bg = 40
            current_bold = False
            
            for cell in row:
                # Check if style changed
                style_changed = (
                    cell.fg != current_fg or
                    cell.bg != current_bg or
                    cell.bold != current_bold
                )
                
                if style_changed and current_span:
                    # Close previous span
                    line_spans.append(self._make_span(
                        ''.join(current_span),
                        current_fg,
                        current_bg,
                        current_bold,
                    ))
                    current_span = []
                
                current_fg = cell.fg
                current_bg = cell.bg
                current_bold = cell.bold
                current_span.append(self._escape_html(cell.char))
            
            # Close final span
            if current_span:
                line_spans.append(self._make_span(
                    ''.join(current_span),
                    current_fg,
                    current_bg,
                    current_bold,
                ))
            
            lines.append(''.join(line_spans))
        
        body = '<br>\n'.join(lines)
        
        return f'''<pre class="{self.css_class}" style="font-family: {self.font_family}; background: #000; padding: 1em;">
{body}
</pre>'''
    
    def _make_span(
        self,
        text: str,
        fg: int,
        bg: int,
        bold: bool,
    ) -> str:
        """Create an HTML span with styling."""
        fg_color = self._sgr_to_css_color(fg, is_fg=True, bold=bold)
        bg_color = self._sgr_to_css_color(bg, is_fg=False, bold=False)
        
        style_parts = [f"color: {fg_color}"]
        if bg != 40:
            style_parts.append(f"background: {bg_color}")
        if bold:
            style_parts.append("font-weight: bold")
        
        style = "; ".join(style_parts)
        return f'<span style="{style}">{text}</span>'
    
    def _sgr_to_css_color(self, code: int, is_fg: bool, bold: bool) -> str:
        """Convert SGR color code to CSS color."""
        if is_fg:
            if 30 <= code <= 37:
                idx = code - 30
                if bold:
                    idx += 8
                return PALETTE_16[idx]
            elif 90 <= code <= 97:
                return PALETTE_16[code - 90 + 8]
        else:
            if 40 <= code <= 47:
                return PALETTE_16[code - 40]
            elif 100 <= code <= 107:
                return PALETTE_16[code - 100 + 8]
        
        return PALETTE_16[7] if is_fg else PALETTE_16[0]
    
    def _escape_html(self, char: str) -> str:
        """Escape special HTML characters."""
        return (char
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace(' ', '&nbsp;')
        )
