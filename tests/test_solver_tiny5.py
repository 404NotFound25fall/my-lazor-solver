# tests/test_solver_tiny5.py
from pathlib import Path
import pytest

def _tiny5_path():
    for p in [Path("examples/official/tiny_5.bff"), Path("examples/tiny_5.bff")]:
        if p.exists():
            return p
    pytest.skip("tiny_5.bff not found")

def test_solver_can_find_tiny5():
    """
    确认搜索/剪枝是否把正确解剪没了。
    如果 parser 和 simulator 测试都过了，但这个挂了，
    说明是 solver 搜索/剪枝的问题（例如：截断了槽位，不允许跳过槽位，状态 key 过粗导致误剪）。
    """
    from lazor_core.parser import parse_bff
    from lazor_core.board import Board
    from lazor_core.solver import solve_optimized
    from lazor_core.simulator import simulate_board

    spec = parse_bff(_tiny5_path())
    board = Board.from_bffspec(spec)

    # 注意：solve_optimized 不接受 time_limit 参数，使用默认参数
    # 对于 tiny_5 这种简单关卡，应该在几秒内完成
    solved = solve_optimized(board, debug=False, use_hot_slots=True, hot_slots_ratio=1.0)
    
    assert solved is not None, (
        "solver returned NO_SOLUTION for tiny_5.\n"
        "This likely means:\n"
        "1. Slot truncation cut off valid positions\n"
        "2. State cache incorrectly pruned valid solutions\n"
        "3. Search space was incorrectly constrained"
    )

    # 验证找到的解确实满足目标
    hits = simulate_board(solved)
    missing = solved.points - hits
    assert solved.points.issubset(hits), (
        "solver found a layout that doesn't really hit targets!\n"
        f"Expected targets: {sorted(solved.points)}\n"
        f"Actual hits: {sorted(hits)}\n"
        f"Missing: {sorted(missing) if missing else 'None'}"
    )

