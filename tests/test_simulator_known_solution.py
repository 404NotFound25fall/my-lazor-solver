# tests/test_simulator_known_solution.py
from pathlib import Path
import pytest

def _tiny5_path():
    for p in [Path("examples/official/tiny_5.bff"), Path("examples/tiny_5.bff")]:
        if p.exists():
            return p
    pytest.skip("tiny_5.bff not found")

def test_simulator_hits_targets_on_known_solution():
    """
    确认"动态放置的块"+反射规则是否生效。
    使用已知可行解来直接验证模拟器。
    如果这都命不中，说明模拟器（或半格边界判断）有问题，而不是搜索。
    """
    from lazor_core.parser import parse_bff
    from lazor_core.board import Board
    from lazor_core.simulator import simulate_board

    spec = parse_bff(_tiny5_path())
    board = Board.from_bffspec(spec)

    # 将"已知可行解"放入网格
    # 解：
    # A B A
    # C o A
    # o o o
    # 其中 (0,1) 是固定的 'B'（已在 fixed_blocks 中），不用动
    # 需要动态放置（使用小写字母直接修改 grid）：
    # - (0,0) = A (REFLECT) -> 'a'
    # - (0,2) = A (REFLECT) -> 'a'
    # - (1,0) = C (REFRACT) -> 'c'
    # - (1,2) = A (REFLECT) -> 'a'
    
    # 直接在 grid 中设置小写字母（模拟动态放置的块）
    # 这样模拟器的 _block_ch_at 函数会先检查 grid 中的小写字母
    board.grid[0][0] = 'a'  # REFLECT at (0,0)
    board.grid[0][2] = 'a'  # REFLECT at (0,2)
    board.grid[1][0] = 'c'  # REFRACT at (1,0)
    board.grid[1][2] = 'a'  # REFLECT at (1,2)

    hits = simulate_board(board)
    
    # 验证所有目标点都被击中
    missing = board.points - hits
    assert board.points.issubset(hits), (
        f"hits miss targets!\n"
        f"Expected targets: {sorted(board.points)}\n"
        f"Actual hits: {sorted(hits)}\n"
        f"Missing: {sorted(missing) if missing else 'None'}"
    )

