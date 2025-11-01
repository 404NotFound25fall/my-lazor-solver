
# lazor_core/models.py
"""Core dataclasses and enums for the Lazor solver (Stage 2: Parsing & Data Structures).

Coordinate conventions (per handout):
- Board grid indices (r, c) index *block positions* (top-left is (0, 0)).
- Laser coordinates (x, y) and directions (vx, vy) use the half-block grid used by Lazor:
  even numbers lie between blocks, odd numbers lie on block intersections.
  We *store* them as raw integers; validation happens later during simulation.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional, Dict

class BlockType(str, Enum):
    REFLECT = "reflect"   # 'A'
    OPAQUE  = "opaque"    # 'B'
    REFRACT = "refract"   # 'C'

    @staticmethod
    def from_letter(letter: str) -> "BlockType":
        m = letter.upper()
        if m == "A":
            return BlockType.REFLECT
        if m == "B":
            return BlockType.OPAQUE
        if m == "C":
            return BlockType.REFRACT
        raise ValueError(f"Unknown block letter '{letter}' (expected A/B/C)")


@dataclass(frozen=True)
class Block:
    """Describes a block on the board at a block-grid coordinate (r, c).

    Note on optics (forward-looking for Stage 3):
    - The exact interaction rules depend on the assignment's chosen physics.
      Here we provide a *placeholder* interact() that documents expectations.
    """
    kind: BlockType
    r: int
    c: int

    def interact(self, direction: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Given an incoming laser direction (vx, vy), return outgoing direction(s).

        Placeholder logic for Stage 2:
        - OPAQUE: absorbs (no outgoing directions).
        - REFLECT: simple axis reflection (bounce back). This is *not* the final physics;
          update in Stage 3 based on your chosen rule set.
        - REFRACT: transmits and reflects (two paths): straight-through + bounce-back.

        Parameters
        ----------
        direction: (vx, vy) where each component in {-1, 0, 1} and not both zero.

        Returns
        -------
        List of (vx, vy). Empty list means absorbed.
        """
        vx, vy = direction
        if (vx, vy) == (0, 0):
            raise ValueError("Laser direction cannot be (0, 0).")

        if self.kind is BlockType.OPAQUE:
            return []

        if self.kind is BlockType.REFLECT:
            # Bounce back placeholder: reverse vector
            return [(-vx, -vy)]

        if self.kind is BlockType.REFRACT:
            # Two paths: straight-through and bounce-back (placeholder)
            return [(vx, vy), (-vx, -vy)]

        raise RuntimeError("Unhandled BlockType")


@dataclass(frozen=True)
class Laser:
    """Laser starting state in half-block coordinates."""
    x: int
    y: int
    vx: int
    vy: int

    def direction(self) -> Tuple[int, int]:
        return (self.vx, self.vy)


@dataclass
class BFFSpec:
    """Holds raw parsed information from a .bff file.

    Attributes
    ----------
    grid_tokens : List[List[str]]
        2D list of tokens from GRID (each "o", "x", or optional fixed block letters "A", "B", "C").
    free_blocks : Dict[BlockType, int]
        Counts of free-to-place blocks specified by lines like "A 2", "C 1".
    lasers : List[Laser]
        Laser starts from lines like "L 2 7 1 -1".
    points : List[Tuple[int, int]]
        Target points from lines like "P 3 0".
    """
    grid_tokens: List[List[str]]
    free_blocks: Dict[BlockType, int]
    lasers: List[Laser]
    points: List[Tuple[int, int]]
