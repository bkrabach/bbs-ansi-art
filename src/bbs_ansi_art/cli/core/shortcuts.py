"""Centralized keyboard shortcut registry.

This module provides a single source of truth for all keyboard shortcuts
in the application. Shortcuts are defined with keys, labels, descriptions,
and handler names, making them easy to modify and use for generating help menus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from bbs_ansi_art.cli.core.input import Key, KeyEvent


class ShortcutContext(Enum):
    """Context in which a shortcut is active."""
    GLOBAL = auto()          # Always available
    EDITOR = auto()          # In the art editor
    PALETTE = auto()         # In the palette widget
    COLOR_EDITOR = auto()    # In the color editor modal
    EYEDROPPER = auto()      # In eyedropper/sampling mode
    TEXT_INPUT = auto()      # In text input fields


@dataclass
class ShortcutDef:
    """Definition of a keyboard shortcut.
    
    Attributes:
        id: Unique identifier for the shortcut
        keys: List of keys/chars that trigger this shortcut
        label: Short label for status bar (e.g., "Save")
        description: Longer description for help menu
        context: Context(s) where this shortcut is active
        handler: Name of the handler method to call
        category: Category for grouping in help menu
        enabled: Whether the shortcut is currently enabled
    """
    id: str
    keys: list[str | Key]
    label: str
    description: str
    context: list[ShortcutContext] = field(default_factory=lambda: [ShortcutContext.GLOBAL])
    handler: str = ""
    category: str = "General"
    enabled: bool = True
    
    def matches(self, event: KeyEvent) -> bool:
        """Check if a key event matches this shortcut."""
        if not self.enabled:
            return False
        for key in self.keys:
            if isinstance(key, Key):
                if event.key == key:
                    return True
            elif isinstance(key, str):
                if event.char == key:
                    return True
        return False
    
    @property
    def key_display(self) -> str:
        """Get display string for the keys."""
        displays = []
        for key in self.keys:
            if isinstance(key, Key):
                displays.append(_key_to_display(key))
            else:
                displays.append(key)
        return "/".join(displays)


def _key_to_display(key: Key) -> str:
    """Convert a Key enum to display string."""
    display_map = {
        Key.UP: "↑",
        Key.DOWN: "↓",
        Key.LEFT: "←",
        Key.RIGHT: "→",
        Key.ENTER: "Enter",
        Key.ESCAPE: "Esc",
        Key.TAB: "Tab",
        Key.BACKSPACE: "Bksp",
        Key.HOME: "Home",
        Key.END: "End",
        Key.PAGE_UP: "PgUp",
        Key.PAGE_DOWN: "PgDn",
        Key.DELETE: "Del",
        Key.INSERT: "Ins",
        Key.F1: "F1",
        Key.F2: "F2",
        Key.F3: "F3",
        Key.F4: "F4",
        Key.F5: "F5",
        Key.F10: "F10",
        Key.F12: "F12",
    }
    return display_map.get(key, key.name)


class ShortcutRegistry:
    """Central registry for all keyboard shortcuts.
    
    This class manages all shortcuts in the application, providing:
    - Registration and lookup of shortcuts
    - Context-aware filtering
    - Help text generation
    - Status bar shortcut hints
    
    Example:
        registry = ShortcutRegistry()
        registry.register(ShortcutDef(
            id="save",
            keys=["s"],
            label="Save",
            description="Save the current document",
            context=[ShortcutContext.EDITOR],
            handler="handle_save",
            category="File",
        ))
        
        # Check if event matches any shortcut
        shortcut = registry.match(event, ShortcutContext.EDITOR)
        if shortcut:
            getattr(handler, shortcut.handler)()
    """
    
    def __init__(self) -> None:
        self._shortcuts: dict[str, ShortcutDef] = {}
        self._by_context: dict[ShortcutContext, list[ShortcutDef]] = {
            ctx: [] for ctx in ShortcutContext
        }
    
    def register(self, shortcut: ShortcutDef) -> None:
        """Register a shortcut definition."""
        self._shortcuts[shortcut.id] = shortcut
        for ctx in shortcut.context:
            self._by_context[ctx].append(shortcut)
    
    def register_many(self, shortcuts: list[ShortcutDef]) -> None:
        """Register multiple shortcuts at once."""
        for shortcut in shortcuts:
            self.register(shortcut)
    
    def get(self, shortcut_id: str) -> Optional[ShortcutDef]:
        """Get a shortcut by ID."""
        return self._shortcuts.get(shortcut_id)
    
    def match(self, event: KeyEvent, *contexts: ShortcutContext) -> Optional[ShortcutDef]:
        """Find a shortcut matching the event in the given contexts.
        
        Args:
            event: The key event to match
            contexts: Contexts to search in (defaults to GLOBAL)
            
        Returns:
            Matching ShortcutDef or None
        """
        if not contexts:
            contexts = (ShortcutContext.GLOBAL,)
        
        # Always include GLOBAL context
        search_contexts = set(contexts) | {ShortcutContext.GLOBAL}
        
        for ctx in search_contexts:
            for shortcut in self._by_context[ctx]:
                if shortcut.matches(event):
                    return shortcut
        return None
    
    def get_for_context(self, context: ShortcutContext, include_global: bool = True) -> list[ShortcutDef]:
        """Get all shortcuts for a context.
        
        Args:
            context: The context to get shortcuts for
            include_global: Whether to include global shortcuts
            
        Returns:
            List of ShortcutDef objects
        """
        result = list(self._by_context[context])
        if include_global and context != ShortcutContext.GLOBAL:
            result.extend(self._by_context[ShortcutContext.GLOBAL])
        return result
    
    def get_by_category(self, context: ShortcutContext) -> dict[str, list[ShortcutDef]]:
        """Get shortcuts grouped by category.
        
        Args:
            context: The context to get shortcuts for
            
        Returns:
            Dict mapping category names to lists of shortcuts
        """
        shortcuts = self.get_for_context(context)
        by_category: dict[str, list[ShortcutDef]] = {}
        for shortcut in shortcuts:
            if shortcut.category not in by_category:
                by_category[shortcut.category] = []
            by_category[shortcut.category].append(shortcut)
        return by_category
    
    def generate_help_text(self, context: ShortcutContext, width: int = 37) -> list[str]:
        """Generate help text for a context.
        
        Args:
            context: The context to generate help for
            width: Width of the help box content
            
        Returns:
            List of strings for the help display
        """
        by_category = self.get_by_category(context)
        lines = []
        
        # Sort categories for consistent ordering
        category_order = ["Navigation", "Drawing", "Colors", "Palette", "File", "General"]
        sorted_categories = sorted(
            by_category.keys(),
            key=lambda c: category_order.index(c) if c in category_order else 999
        )
        
        for category in sorted_categories:
            shortcuts = by_category[category]
            if not shortcuts:
                continue
            
            # Category header
            lines.append(f"  {category.upper()}")
            
            # Shortcuts
            for shortcut in shortcuts:
                if not shortcut.enabled:
                    continue
                key_str = shortcut.key_display
                desc = shortcut.description
                # Format: "    keys          description"
                padding = 18 - len(key_str)
                line = f"    {key_str}{' ' * padding}{desc}"
                if len(line) > width:
                    line = line[:width-1] + "…"
                lines.append(line)
            
            lines.append("")  # Blank line between categories
        
        return lines[:-1] if lines and lines[-1] == "" else lines  # Remove trailing blank
    
    def get_status_bar_hints(self, context: ShortcutContext, max_hints: int = 6) -> list[tuple[str, str]]:
        """Get shortcut hints for status bar.
        
        Args:
            context: The context to get hints for
            max_hints: Maximum number of hints to return
            
        Returns:
            List of (key_display, label) tuples
        """
        shortcuts = self.get_for_context(context)
        hints = []
        for shortcut in shortcuts:
            if shortcut.enabled and shortcut.label:
                hints.append((shortcut.key_display, shortcut.label))
                if len(hints) >= max_hints:
                    break
        return hints
    
    def set_enabled(self, shortcut_id: str, enabled: bool) -> None:
        """Enable or disable a shortcut."""
        if shortcut_id in self._shortcuts:
            self._shortcuts[shortcut_id].enabled = enabled
    
    def all_shortcuts(self) -> list[ShortcutDef]:
        """Get all registered shortcuts."""
        return list(self._shortcuts.values())


# =============================================================================
# Default Shortcuts - The single source of truth for all app shortcuts
# =============================================================================

def create_default_shortcuts() -> ShortcutRegistry:
    """Create the default shortcut registry with all application shortcuts."""
    registry = ShortcutRegistry()
    
    # -------------------------------------------------------------------------
    # Navigation Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="nav_up",
            keys=[Key.UP, "k"],
            label="",
            description="Move cursor up",
            context=[ShortcutContext.EDITOR],
            handler="move_up",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_down",
            keys=[Key.DOWN, "j"],
            label="",
            description="Move cursor down",
            context=[ShortcutContext.EDITOR],
            handler="move_down",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_left",
            keys=[Key.LEFT, "h"],
            label="",
            description="Move cursor left",
            context=[ShortcutContext.EDITOR],
            handler="move_left",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_right",
            keys=[Key.RIGHT, "l"],
            label="",
            description="Move cursor right",
            context=[ShortcutContext.EDITOR],
            handler="move_right",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_home",
            keys=[Key.HOME],
            label="",
            description="Go to line start",
            context=[ShortcutContext.EDITOR],
            handler="move_home",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_end",
            keys=[Key.END],
            label="",
            description="Go to line end",
            context=[ShortcutContext.EDITOR],
            handler="move_end",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_page_up",
            keys=[Key.PAGE_UP],
            label="",
            description="Page up",
            context=[ShortcutContext.EDITOR],
            handler="page_up",
            category="Navigation",
        ),
        ShortcutDef(
            id="nav_page_down",
            keys=[Key.PAGE_DOWN],
            label="",
            description="Page down",
            context=[ShortcutContext.EDITOR],
            handler="page_down",
            category="Navigation",
        ),
    ])
    
    # -------------------------------------------------------------------------
    # Drawing Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="draw",
            keys=[" ", Key.ENTER],
            label="Draw",
            description="Paint pixel",
            context=[ShortcutContext.EDITOR],
            handler="draw_at_cursor",
            category="Drawing",
        ),
        ShortcutDef(
            id="draw_advance",
            keys=["d"],
            label="",
            description="Paint and move right",
            context=[ShortcutContext.EDITOR],
            handler="draw_and_advance",
            category="Drawing",
        ),
        ShortcutDef(
            id="erase",
            keys=["x"],
            label="",
            description="Erase pixel",
            context=[ShortcutContext.EDITOR],
            handler="erase_at_cursor",
            category="Drawing",
        ),
    ])
    
    # -------------------------------------------------------------------------
    # Color Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="color_prev",
            keys=["["],
            label="",
            description="Previous color",
            context=[ShortcutContext.EDITOR],
            handler="cycle_color_prev",
            category="Colors",
        ),
        ShortcutDef(
            id="color_next",
            keys=["]"],
            label="",
            description="Next color",
            context=[ShortcutContext.EDITOR],
            handler="cycle_color_next",
            category="Colors",
        ),
        ShortcutDef(
            id="eyedropper",
            keys=["i"],
            label="Pick",
            description="Sample color from canvas",
            context=[ShortcutContext.EDITOR],
            handler="enter_eyedropper",
            category="Colors",
        ),
    ])
    
    # Color quick-select (1-9, 0)
    for i in range(10):
        num = str(i) if i > 0 else "0"
        color_idx = i - 1 if i > 0 else 9  # 1-9 map to 0-8, 0 maps to 9
        registry.register(ShortcutDef(
            id=f"color_{num}",
            keys=[num],
            label="",
            description=f"Select color {color_idx}",
            context=[ShortcutContext.EDITOR],
            handler=f"select_color_{color_idx}",
            category="Colors",
        ))
    
    # -------------------------------------------------------------------------
    # Palette Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="palette_toggle",
            keys=["p"],
            label="Palette",
            description="Toggle palette panel",
            context=[ShortcutContext.EDITOR],
            handler="toggle_palette",
            category="Palette",
        ),
        ShortcutDef(
            id="palette_edit",
            keys=["e"],
            label="Edit",
            description="Edit current color",
            context=[ShortcutContext.PALETTE],
            handler="open_color_editor",
            category="Palette",
        ),
        ShortcutDef(
            id="palette_add",
            keys=["+", "a"],
            label="Add",
            description="Add to saved swatches",
            context=[ShortcutContext.PALETTE],
            handler="add_to_saved",
            category="Palette",
        ),
        ShortcutDef(
            id="palette_remove",
            keys=[Key.DELETE, "-"],
            label="Remove",
            description="Remove from saved",
            context=[ShortcutContext.PALETTE],
            handler="remove_from_saved",
            category="Palette",
        ),
        ShortcutDef(
            id="palette_section_next",
            keys=[Key.TAB],
            label="",
            description="Next section",
            context=[ShortcutContext.PALETTE],
            handler="next_section",
            category="Palette",
        ),
    ])
    
    # -------------------------------------------------------------------------
    # Color Editor Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="editor_mode_toggle",
            keys=[Key.TAB],
            label="",
            description="Toggle RGB/HSL mode",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="toggle_color_mode",
            category="Color Editor",
        ),
        ShortcutDef(
            id="editor_apply",
            keys=[Key.ENTER],
            label="Apply",
            description="Apply color",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="apply_color",
            category="Color Editor",
        ),
        ShortcutDef(
            id="editor_cancel",
            keys=[Key.ESCAPE],
            label="Cancel",
            description="Cancel editing",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="cancel_editor",
            category="Color Editor",
        ),
        ShortcutDef(
            id="editor_channel_up",
            keys=[Key.UP],
            label="",
            description="Previous channel",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="prev_channel",
            category="Color Editor",
        ),
        ShortcutDef(
            id="editor_channel_down",
            keys=[Key.DOWN],
            label="",
            description="Next channel",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="next_channel",
            category="Color Editor",
        ),
        ShortcutDef(
            id="editor_value_dec",
            keys=[Key.LEFT],
            label="",
            description="Decrease value",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="decrease_value",
            category="Color Editor",
        ),
        ShortcutDef(
            id="editor_value_inc",
            keys=[Key.RIGHT],
            label="",
            description="Increase value",
            context=[ShortcutContext.COLOR_EDITOR],
            handler="increase_value",
            category="Color Editor",
        ),
    ])
    
    # -------------------------------------------------------------------------
    # Eyedropper Mode Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="eyedropper_pick",
            keys=[Key.ENTER, " "],
            label="Pick",
            description="Pick color",
            context=[ShortcutContext.EYEDROPPER],
            handler="pick_color",
            category="Eyedropper",
        ),
        ShortcutDef(
            id="eyedropper_pick_save",
            keys=["+"],
            label="Pick+Save",
            description="Pick and save to swatches",
            context=[ShortcutContext.EYEDROPPER],
            handler="pick_and_save",
            category="Eyedropper",
        ),
        ShortcutDef(
            id="eyedropper_cancel",
            keys=[Key.ESCAPE, "i"],
            label="Cancel",
            description="Exit eyedropper mode",
            context=[ShortcutContext.EYEDROPPER],
            handler="exit_eyedropper",
            category="Eyedropper",
        ),
    ])
    
    # -------------------------------------------------------------------------
    # File Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="save",
            keys=["s"],
            label="Save",
            description="Save document",
            context=[ShortcutContext.EDITOR],
            handler="save_document",
            category="File",
        ),
        ShortcutDef(
            id="quit",
            keys=["Q"],
            label="Quit",
            description="Quit editor",
            context=[ShortcutContext.GLOBAL],
            handler="quit",
            category="File",
        ),
    ])
    
    # -------------------------------------------------------------------------
    # General Shortcuts
    # -------------------------------------------------------------------------
    registry.register_many([
        ShortcutDef(
            id="help",
            keys=["?"],
            label="Help",
            description="Show/hide help",
            context=[ShortcutContext.GLOBAL],
            handler="toggle_help",
            category="General",
        ),
    ])
    
    return registry


# Global default registry instance
_default_registry: Optional[ShortcutRegistry] = None


def get_shortcut_registry() -> ShortcutRegistry:
    """Get the global shortcut registry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_shortcuts()
    return _default_registry
