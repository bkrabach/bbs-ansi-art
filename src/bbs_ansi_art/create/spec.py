"""Art specification for LLM generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ArtSpec:
    """
    Specification for LLM-generated ANSI art.
    
    This is the contract passed to generators. It's intentionally
    serializable (no callables, no canvas objects) so it can be:
    - Logged for reproducibility
    - Cached
    - Sent over network to remote LLM services
    
    Example:
        >>> spec = (ArtSpec()
        ...     .with_content("A dragon guarding treasure")
        ...     .with_style("acid")
        ...     .with_dimensions(80, 25)
        ...     .with_reference("~/art/dragon-example.ans"))
        >>> result = await generator.generate(spec)
    """
    
    # Content description
    content: str = ""
    
    # Dimensions
    width: int = 80
    height: Optional[int] = None  # None = auto
    
    # Style specification
    style_name: Optional[str] = None  # Named preset: "acid", "ice", "blocky"
    style_description: Optional[str] = None  # Freeform style guidance
    
    # Reference materials
    reference_files: list[Path] = field(default_factory=list)
    reference_urls: list[str] = field(default_factory=list)
    
    # Additional LLM instructions
    instructions: list[str] = field(default_factory=list)
    
    # Technical constraints
    color_mode: str = "16"  # "16", "256", "truecolor"
    charset: str = "cp437"  # "cp437", "ascii", "unicode"
    
    # Generation parameters
    temperature: float = 0.7
    seed: Optional[int] = None  # For reproducibility attempts
    
    # Fluent builder methods
    def with_content(self, content: str) -> ArtSpec:
        """Set the content/subject description."""
        self.content = content
        return self
    
    def with_style(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> ArtSpec:
        """Set style by name and/or description."""
        if name:
            self.style_name = name
        if description:
            self.style_description = description
        return self
    
    def with_dimensions(
        self,
        width: int,
        height: Optional[int] = None
    ) -> ArtSpec:
        """Set output dimensions."""
        self.width = width
        self.height = height
        return self
    
    def with_reference(self, path: Path | str) -> ArtSpec:
        """Add a reference art file for style guidance."""
        self.reference_files.append(Path(path).expanduser())
        return self
    
    def with_reference_url(self, url: str) -> ArtSpec:
        """Add a reference URL for style guidance."""
        self.reference_urls.append(url)
        return self
    
    def with_instruction(self, instruction: str) -> ArtSpec:
        """Add an additional instruction for the LLM."""
        self.instructions.append(instruction)
        return self
    
    def with_color_mode(self, mode: str) -> ArtSpec:
        """Set color mode: '16', '256', or 'truecolor'."""
        if mode not in ("16", "256", "truecolor"):
            raise ValueError(f"Invalid color mode: {mode}")
        self.color_mode = mode
        return self
    
    def with_charset(self, charset: str) -> ArtSpec:
        """Set character set: 'cp437', 'ascii', or 'unicode'."""
        if charset not in ("cp437", "ascii", "unicode"):
            raise ValueError(f"Invalid charset: {charset}")
        self.charset = charset
        return self
    
    def with_temperature(self, temp: float) -> ArtSpec:
        """Set LLM temperature (0.0-1.0)."""
        self.temperature = max(0.0, min(1.0, temp))
        return self
    
    def with_seed(self, seed: int) -> ArtSpec:
        """Set random seed for reproducibility attempts."""
        self.seed = seed
        return self
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/caching."""
        return {
            "content": self.content,
            "width": self.width,
            "height": self.height,
            "style_name": self.style_name,
            "style_description": self.style_description,
            "reference_files": [str(p) for p in self.reference_files],
            "reference_urls": self.reference_urls,
            "instructions": self.instructions,
            "color_mode": self.color_mode,
            "charset": self.charset,
            "temperature": self.temperature,
            "seed": self.seed,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtSpec:
        """Deserialize from dictionary."""
        spec = cls()
        spec.content = data.get("content", "")
        spec.width = data.get("width", 80)
        spec.height = data.get("height")
        spec.style_name = data.get("style_name")
        spec.style_description = data.get("style_description")
        spec.reference_files = [Path(p) for p in data.get("reference_files", [])]
        spec.reference_urls = data.get("reference_urls", [])
        spec.instructions = data.get("instructions", [])
        spec.color_mode = data.get("color_mode", "16")
        spec.charset = data.get("charset", "cp437")
        spec.temperature = data.get("temperature", 0.7)
        spec.seed = data.get("seed")
        return spec
    
    def __str__(self) -> str:
        """Human-readable summary."""
        parts = [f"ArtSpec: {self.content[:50]}..." if len(self.content) > 50 else f"ArtSpec: {self.content}"]
        if self.style_name:
            parts.append(f"  Style: {self.style_name}")
        parts.append(f"  Size: {self.width}x{self.height or 'auto'}")
        if self.reference_files:
            parts.append(f"  References: {len(self.reference_files)} files")
        if self.instructions:
            parts.append(f"  Instructions: {len(self.instructions)}")
        return "\n".join(parts)
