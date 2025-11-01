
# lazor_core/board.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from .models import Block, BlockType, Laser, BFFSpec


@dataclass
class Board:
    """Board stores the *state* of a Lazor level (no solving here).

    - `grid` stores 'o' (placement allowed) or 'x' (no placement) for each (r, c).
    - `fixed_blocks` stores fixed blocks embedded in the starting grid (A/B/C).
    - `free_blocks` stores counts of blocks available for placement.
    - `lasers` is a list of starting lasers.
    - `points` are required target coordinates (half-block units).
    """
    grid: List[List[str]]
    fixed_blocks: Dict[Tuple[int, int], Block] = field(default_factory=dict)
    free_blocks: Dict[BlockType, int] = field(default_factory=dict)
    lasers: List[Laser] = field(default_factory=list)
    points: Set[Tuple[int, int]] = field(default_factory=set)

    @property
    def nrows(self) -> int:
        return len(self.grid)

    @property
    def ncols(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.nrows and 0 <= c < self.ncols

    def cell_token(self, r: int, c: int) -> str:
        if not self.in_bounds(r, c):
            raise IndexError("Cell out of bounds")
        return self.grid[r][c]

    def is_placeable(self, r: int, c: int) -> bool:
        if not self.in_bounds(r, c):
            return False
        if (r, c) in self.fixed_blocks:
            return False
        return self.grid[r][c] == 'o'

    def place_block(self, r: int, c: int, kind: BlockType) -> None:
        if not self.is_placeable(r, c):
            raise ValueError(f"Cannot place block at ({r}, {c}).")
        self.fixed_blocks[(r, c)] = Block(kind=kind, r=r, c=c)

    def remove_block(self, r: int, c: int) -> None:
        self.fixed_blocks.pop((r, c), None)

    @classmethod
    def from_bffspec(cls, spec: BFFSpec) -> "Board":
        # Normalize grid to only 'o'/'x', extract fixed blocks from 'A'/'B'/'C'
        grid: List[List[str]] = []
        fixed: Dict[Tuple[int, int], Block] = {}
        for r, row in enumerate(spec.grid_tokens):
            new_row: List[str] = []
            for c, tok in enumerate(row):
                upper = tok.upper()
                if upper in {'O', 'X'}:
                    new_row.append(upper.lower())
                elif upper in {'A', 'B', 'C'}:
                    # Treat fixed block cell as non-placeable 'x' in the base grid
                    new_row.append('x')
                    fixed[(r, c)] = Block(kind=BlockType.from_letter(upper), r=r, c=c)
                else:
                    raise ValueError(f"Unknown grid token '{tok}' at ({r}, {c}). Expected o/x/A/B/C.")
            grid.append(new_row)
        return cls(
            grid=grid,
            fixed_blocks=fixed,
            free_blocks=dict(spec.free_blocks),
            lasers=list(spec.lasers),
            points=set(spec.points),
        )

    # Pretty printers useful during development
    def to_ascii(self) -> str:
        cells = []
        for r in range(self.nrows):
            row = []
            for c in range(self.ncols):
                if (r, c) in self.fixed_blocks:
                    k = self.fixed_blocks[(r, c)].kind
                    row.append({BlockType.REFLECT: 'A', BlockType.OPAQUE: 'B', BlockType.REFRACT: 'C'}[k])
                else:
                    row.append(self.grid[r][c])
            cells.append(" ".join(row))
        return "\n".join(cells)

    def summary(self) -> str:
        fb = ", ".join(f"{k.name}:{v}" for k, v in self.free_blocks.items())
        lasers = "; ".join(f"L({l.x},{l.y},{l.vx},{l.vy})" for l in self.lasers)
        pts = "; ".join(f"P({x},{y})" for (x, y) in sorted(self.points))
        return (
            f"Board {self.nrows}x{self.ncols}\n"
            f"Grid:\n{self.to_ascii()}\n"
            f"Free blocks: {fb}\n"
            f"Lasers: {lasers}\n"
            f"Points: {pts}\n"
        )
