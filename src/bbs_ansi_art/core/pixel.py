from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Pixel:
    """A single pixel in half-block art (2 pixels per terminal cell)."""
    r: int
    g: int
    b: int
    transparent: bool = False
    
    @property
    def rgb(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)
    
    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> Pixel:
        return cls(r, g, b)
    
    @classmethod 
    def transparent_pixel(cls) -> Pixel:
        return cls(0, 0, 0, transparent=True)
    
    def blend(self, other: Pixel, alpha: float) -> Pixel:
        """Blend with another pixel (for anti-aliasing)."""
        if self.transparent:
            return other
        if other.transparent:
            return self
        return Pixel(
            r=int(self.r * (1 - alpha) + other.r * alpha),
            g=int(self.g * (1 - alpha) + other.g * alpha),
            b=int(self.b * (1 - alpha) + other.b * alpha),
        )
    
    def distance(self, other: Pixel) -> float:
        """Euclidean distance to another pixel color."""
        return ((self.r - other.r)**2 + (self.g - other.g)**2 + (self.b - other.b)**2) ** 0.5
