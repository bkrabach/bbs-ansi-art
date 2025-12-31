"""Base widget protocol and common functionality."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from bbs_ansi_art.cli.core.input import KeyEvent


@dataclass
class Rect:
    """Rectangle bounds for widget positioning."""
    x: int
    y: int
    width: int
    height: int


@runtime_checkable
class Widget(Protocol):
    """Protocol for TUI widgets."""

    def render(self, bounds: Rect) -> list[str]:
        """Render widget content as list of lines."""
        ...

    def handle_input(self, event: KeyEvent) -> bool:
        """Handle input event. Returns True if consumed."""
        ...

    @property
    def focusable(self) -> bool:
        """Whether this widget can receive focus."""
        ...


class BaseWidget(ABC):
    """Base class with common widget functionality."""

    def __init__(self) -> None:
        self._focused = False
        self._visible = True

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    @property
    def focusable(self) -> bool:
        return True

    @abstractmethod
    def render(self, bounds: Rect) -> list[str]:
        """Subclasses must implement rendering."""
        pass

    def handle_input(self, event: KeyEvent) -> bool:
        """Default: don't consume events."""
        return False
