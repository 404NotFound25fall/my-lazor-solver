
# lazor_core/parser.py
from __future__ import annotations
import re
from typing import List, Tuple, Dict
from .models import BFFSpec, BlockType, Laser

GRID_START = re.compile(r"^\s*GRID\s+START\s*$", re.IGNORECASE)
GRID_STOP  = re.compile(r"^\s*GRID\s+STOP\s*$", re.IGNORECASE)

def _normalize(line: str) -> str:
    """Normalize a raw line for robust parsing.

    - Strip comments (leading '#' or ' #' after spaces).
    - Replace Unicode minus and dashes with ASCII '-'.
    - Collapse multiple spaces/tabs.
    - Trim.
    """
    # Remove comments
    line = re.split(r"\s#", line, maxsplit=1)[0]
    if line.strip().startswith('#'):
        return ""
    # Normalize unicode minuses/dashes
    line = line.replace('−', '-').replace('–', '-').replace('—', '-')
    # Some OCR glitches sometimes produce '=1' instead of '-1'; be lenient
    line = re.sub(r"\s=\s*(-?\d+)", r" -\1", line)
    # Collapse whitespace
    line = re.sub(r"\s+", " ", line).strip()
    return line

def parse_bff(path: str) -> BFFSpec:
    with open(path, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    lines = [_normalize(ln) for ln in raw_lines]
    lines = [ln for ln in lines if ln]  # drop empty

    in_grid = False
    grid_rows: List[List[str]] = []
    free_blocks: Dict[BlockType, int] = {BlockType.REFLECT: 0, BlockType.OPAQUE: 0, BlockType.REFRACT: 0}
    lasers: List[Laser] = []
    points: List[Tuple[int, int]] = []

    i = 0
    while i < len(lines):
        ln = lines[i]
        if GRID_START.match(ln):
            if in_grid:
                raise ValueError("Nested GRID START found.")
            in_grid = True
            i += 1
            while i < len(lines) and not GRID_STOP.match(lines[i]):
                row_tokens = lines[i].split(' ')
                # Accept tokens like o/x/A/B/C (case-insensitive)
                grid_rows.append([tok.strip() for tok in row_tokens if tok.strip()])
                i += 1
            if i == len(lines) or not GRID_STOP.match(lines[i]):
                raise ValueError("GRID STOP not found.")
            in_grid = False
            i += 1
            continue

        # Counts: A 2 / B 1 / C 0
        m_count = re.match(r"^(?P<typ>[ABCabc])\s+(?P<n>\d+)$", ln)
        if m_count:
            t = BlockType.from_letter(m_count.group('typ'))
            n = int(m_count.group('n'))
            free_blocks[t] = n
            i += 1
            continue

        # Laser: L x y vx vy
        m_laser = re.match(r"^[Ll]\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)$", ln)
        if m_laser:
            x, y, vx, vy = map(int, m_laser.groups())
            lasers.append(Laser(x=x, y=y, vx=vx, vy=vy))
            i += 1
            continue

        # Point: P x y
        m_point = re.match(r"^[Pp]\s+(-?\d+)\s+(-?\d+)$", ln)
        if m_point:
            x, y = map(int, m_point.groups())
            points.append((x, y))
            i += 1
            continue

        # Unknown non-empty line -> error to surface issues early
        raise ValueError(f"Unrecognized line: '{ln}'")

    # Validate grid: rectangular
    if not grid_rows:
        raise ValueError("GRID not found or empty.")
    ncols = len(grid_rows[0])
    for r, row in enumerate(grid_rows):
        if len(row) != ncols:
            raise ValueError(f"Non-rectangular GRID: row 0 has {ncols} cols but row {r} has {len(row)}.")

    return BFFSpec(
        grid_tokens=grid_rows,
        free_blocks=free_blocks,
        lasers=lasers,
        points=points,
    )
