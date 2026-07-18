"""PrimeNet publication visual style."""

from dataclasses import dataclass

@dataclass(frozen=True)
class PrimeNetStyle:
    font_family: str = "DejaVu Sans"
    title_size: int = 16
    label_size: int = 10
    small_size: int = 8
    dpi: int = 220
    line_width: float = 1.4
    box_rounding: float = 0.08

STYLE = PrimeNetStyle()
