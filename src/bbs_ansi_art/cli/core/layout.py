"""Responsive layout system for terminal TUI applications.

Breakpoints designed around 80-column ANSI art as the anchor:
- NARROW (< 80):    Art-only, truncated, browser as overlay
- COMPACT (80-99):  Art-only, full width, browser as overlay  
- SPLIT (100-139):  Minimal browser + full art (80 cols)
- WIDE (140+):      Comfortable browser + art with padding
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LayoutMode(Enum):
    """Layout mode based on terminal width."""
    NARROW = "narrow"      # < 80: Art truncated, browser hidden
    COMPACT = "compact"    # 80-99: Art fits, browser hidden
    SPLIT = "split"        # 100-139: Both panels, tight
    WIDE = "wide"          # 140+: Both panels, comfortable


class ActivePanel(Enum):
    """Which panel has focus."""
    BROWSER = "browser"
    ART = "art"


@dataclass
class Layout:
    """Computed layout dimensions for current terminal size."""
    mode: LayoutMode
    term_width: int
    term_height: int
    
    # Panel dimensions (0 = hidden)
    browser_width: int
    browser_height: int
    art_width: int
    art_height: int
    
    # Chrome
    separator_width: int  # 0 or 1
    status_height: int    # Always 1
    
    # State
    browser_visible: bool
    art_needs_hscroll: bool  # Art wider than panel
    
    @property
    def content_height(self) -> int:
        """Height available for content (excluding status)."""
        return self.term_height - self.status_height


# Layout constants
ART_IDEAL_WIDTH = 80
ART_WIDE_WIDTH = 132
BROWSER_MIN_WIDTH = 20
BROWSER_MAX_WIDTH = 50
SEPARATOR_WIDTH = 1
STATUS_HEIGHT = 1


def calculate_layout(
    term_width: int,
    term_height: int,
    browser_visible: bool = True,
    art_content_width: int = ART_IDEAL_WIDTH,
) -> Layout:
    """
    Calculate responsive layout based on terminal dimensions.
    
    The layout prioritizes showing art at its ideal width (80 cols),
    then allocates remaining space to the file browser.
    
    Args:
        term_width: Terminal width in columns
        term_height: Terminal height in rows
        browser_visible: Whether browser panel should be shown (user preference)
        art_content_width: Width of current art content (80 or 132)
    
    Returns:
        Layout with computed dimensions for each panel
    """
    content_height = term_height - STATUS_HEIGHT
    
    # Determine mode based on width
    # Breakpoints: 80 (art fits), 101 (art + min browser + separator), 140 (comfortable)
    if term_width < 80:
        mode = LayoutMode.NARROW
    elif term_width < 101:  # 80 art + 20 browser + 1 sep = 101 minimum for split
        mode = LayoutMode.COMPACT
    elif term_width < 140:
        mode = LayoutMode.SPLIT
    else:
        mode = LayoutMode.WIDE
    
    # Calculate panel widths based on mode
    if mode == LayoutMode.NARROW:
        # Art only, will be truncated
        return Layout(
            mode=mode,
            term_width=term_width,
            term_height=term_height,
            browser_width=0,
            browser_height=0,
            art_width=term_width,
            art_height=content_height,
            separator_width=0,
            status_height=STATUS_HEIGHT,
            browser_visible=False,
            art_needs_hscroll=True,
        )
    
    if mode == LayoutMode.COMPACT:
        # Art only, fits or nearly fits
        return Layout(
            mode=mode,
            term_width=term_width,
            term_height=term_height,
            browser_width=0,
            browser_height=0,
            art_width=term_width,
            art_height=content_height,
            separator_width=0,
            status_height=STATUS_HEIGHT,
            browser_visible=False,
            art_needs_hscroll=(term_width < art_content_width),
        )
    
    if mode == LayoutMode.SPLIT:
        # Both panels, prioritize art getting exactly 80 cols
        if browser_visible:
            # Art gets its ideal width first, browser gets the rest
            art_w = art_content_width
            browser_w = term_width - art_w - SEPARATOR_WIDTH
            # If browser too small, squeeze art
            if browser_w < BROWSER_MIN_WIDTH:
                browser_w = BROWSER_MIN_WIDTH
                art_w = term_width - browser_w - SEPARATOR_WIDTH
        else:
            browser_w = 0
            art_w = term_width
        
        return Layout(
            mode=mode,
            term_width=term_width,
            term_height=term_height,
            browser_width=browser_w,
            browser_height=content_height if browser_w > 0 else 0,
            art_width=art_w,
            art_height=content_height,
            separator_width=SEPARATOR_WIDTH if browser_w > 0 else 0,
            status_height=STATUS_HEIGHT,
            browser_visible=(browser_w > 0),
            art_needs_hscroll=(art_w < art_content_width),
        )
    
    # WIDE mode - comfortable spacing
    if browser_visible:
        # Browser gets up to max, art gets ideal + padding
        browser_w = min(BROWSER_MAX_WIDTH, max(BROWSER_MIN_WIDTH, (term_width - art_content_width) // 3))
        art_w = term_width - browser_w - SEPARATOR_WIDTH
    else:
        browser_w = 0
        art_w = term_width
    
    return Layout(
        mode=mode,
        term_width=term_width,
        term_height=term_height,
        browser_width=browser_w,
        browser_height=content_height if browser_w > 0 else 0,
        art_width=art_w,
        art_height=content_height,
        separator_width=SEPARATOR_WIDTH if browser_w > 0 else 0,
        status_height=STATUS_HEIGHT,
        browser_visible=(browser_w > 0),
        art_needs_hscroll=False,
    )


class LayoutManager:
    """
    Manages responsive layout state for TUI applications.
    
    Handles:
    - Layout recalculation on terminal resize
    - Panel visibility toggling
    - Focus management between panels
    """
    
    def __init__(self, art_content_width: int = ART_IDEAL_WIDTH):
        self.art_content_width = art_content_width
        self.active_panel = ActivePanel.BROWSER
        self._browser_pinned = True  # User preference to show browser
        self._layout: Optional[Layout] = None
    
    def calculate(self, term_width: int, term_height: int) -> Layout:
        """Calculate and cache layout for current terminal size."""
        # In narrow/compact modes, browser is always hidden
        # In split/wide modes, respect user preference
        browser_visible = self._browser_pinned
        
        self._layout = calculate_layout(
            term_width=term_width,
            term_height=term_height,
            browser_visible=browser_visible,
            art_content_width=self.art_content_width,
        )
        
        # Auto-adjust active panel if browser becomes hidden
        if not self._layout.browser_visible and self.active_panel == ActivePanel.BROWSER:
            self.active_panel = ActivePanel.ART
        
        return self._layout
    
    @property
    def layout(self) -> Optional[Layout]:
        """Current cached layout."""
        return self._layout
    
    def toggle_browser(self) -> bool:
        """
        Toggle browser panel visibility.
        
        Returns True if browser is now visible.
        """
        self._browser_pinned = not self._browser_pinned
        
        # If hiding browser, switch focus to art
        if not self._browser_pinned:
            self.active_panel = ActivePanel.ART
        
        return self._browser_pinned
    
    def cycle_focus(self) -> ActivePanel:
        """Cycle focus between visible panels."""
        if self._layout and self._layout.browser_visible:
            self.active_panel = (
                ActivePanel.ART 
                if self.active_panel == ActivePanel.BROWSER 
                else ActivePanel.BROWSER
            )
        return self.active_panel
    
    def set_art_width(self, width: int) -> None:
        """Update art content width (call when loading new art)."""
        self.art_content_width = width
    
    @property
    def browser_focused(self) -> bool:
        return self.active_panel == ActivePanel.BROWSER
    
    @property
    def art_focused(self) -> bool:
        return self.active_panel == ActivePanel.ART
