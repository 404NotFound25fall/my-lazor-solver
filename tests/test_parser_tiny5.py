# tests/test_parser_tiny5.py
from pathlib import Path
import pytest

def _tiny5_path():
    for p in [Path("examples/official/tiny_5.bff"), Path("examples/tiny_5.bff")]:
        if p.exists():
            return p
    pytest.skip("tiny_5.bff not found in examples/official or examples")

def test_parser_reads_tiny5():
    """确认解析器能正确读取 tiny_5.bff"""
    from lazor_core.parser import parse_bff
    p = _tiny5_path()
    spec = parse_bff(p)
    # 基本结构
    rows = len(spec.grid_tokens)
    cols = len(spec.grid_tokens[0]) if spec.grid_tokens else 0
    assert rows > 0 and cols > 0
    # 这关只有 1 枚激光、2 个目标点
    assert len(spec.lasers) == 1
    assert len(spec.points) == 2

