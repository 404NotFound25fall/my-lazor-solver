#!/usr/bin/env python3
"""
诊断测试运行器 - 定位到底是 Parser / Simulator / Solver 哪一环出错

运行方式：
    python tests/run_diagnostic_tests.py
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

def find_tiny5_path():
    """查找 tiny_5.bff 文件"""
    for p in [Path("examples/official/tiny_5.bff"), Path("examples/tiny_5.bff")]:
        full_path = _project_root / p
        if full_path.exists():
            return full_path
    return None

def test_parser():
    """测试 1: 解析器"""
    print("=" * 60)
    print("测试 1: Parser (解析器)")
    print("=" * 60)
    
    try:
        from lazor_core.parser import parse_bff
        p = find_tiny5_path()
        if not p:
            print("❌ SKIP: tiny_5.bff not found")
            return False
        
        spec = parse_bff(p)
        # 基本结构
        rows = len(spec.grid_tokens)
        cols = len(spec.grid_tokens[0]) if spec.grid_tokens else 0
        assert rows > 0 and cols > 0, "Invalid grid size"
        # 这关只有 1 枚激光、2 个目标点
        assert len(spec.lasers) == 1, f"Expected 1 laser, got {len(spec.lasers)}"
        assert len(spec.points) == 2, f"Expected 2 points, got {len(spec.points)}"
        
        print("✓ PASS: Parser correctly reads tiny_5.bff")
        print(f"  Grid: {rows}x{cols}")
        print(f"  Lasers: {len(spec.lasers)}")
        print(f"  Points: {len(spec.points)}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Parser error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simulator():
    """测试 2: 模拟器"""
    print("\n" + "=" * 60)
    print("测试 2: Simulator (模拟器)")
    print("=" * 60)
    
    try:
        from lazor_core.parser import parse_bff
        from lazor_core.board import Board
        from lazor_core.simulator import simulate_board

        p = find_tiny5_path()
        if not p:
            print("❌ SKIP: tiny_5.bff not found")
            return False

        spec = parse_bff(p)
        board = Board.from_bffspec(spec)

        # 将"已知可行解"放入网格
        # 解：
        # A B A
        # C o A
        # o o o
        # 其中 (0,1) 是固定的 'B'（已在 fixed_blocks 中），不用动
        board.grid[0][0] = 'a'  # REFLECT at (0,0)
        board.grid[0][2] = 'a'  # REFLECT at (0,2)
        board.grid[1][0] = 'c'  # REFRACT at (1,0)
        board.grid[1][2] = 'a'  # REFLECT at (1,2)

        hits = simulate_board(board)
        
        # 验证所有目标点都被击中
        missing = board.points - hits
        if not board.points.issubset(hits):
            print(f"❌ FAIL: Simulator misses targets!")
            print(f"  Expected targets: {sorted(board.points)}")
            print(f"  Actual hits: {sorted(hits)}")
            print(f"  Missing: {sorted(missing)}")
            return False
        
        print("✓ PASS: Simulator correctly identifies dynamically placed blocks")
        print(f"  Targets: {sorted(board.points)}")
        print(f"  Hits: {sorted(hits)}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Simulator error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_solver():
    """测试 3: 求解器"""
    print("\n" + "=" * 60)
    print("测试 3: Solver (求解器)")
    print("=" * 60)
    
    try:
        from lazor_core.parser import parse_bff
        from lazor_core.board import Board
        from lazor_core.solver import solve_optimized
        from lazor_core.simulator import simulate_board

        p = find_tiny5_path()
        if not p:
            print("❌ SKIP: tiny_5.bff not found")
            return False

        spec = parse_bff(p)
        board = Board.from_bffspec(spec)

        # 注意：solve_optimized 不接受 time_limit 参数，使用默认参数
        print("  开始求解 tiny_5...")
        solved = solve_optimized(board, debug=False, use_hot_slots=True, hot_slots_ratio=1.0)
        
        if solved is None:
            print("❌ FAIL: Solver returned NO_SOLUTION for tiny_5")
            print("  这可能意味着:")
            print("  1. Slot truncation cut off valid positions (槽位截断)")
            print("  2. State cache incorrectly pruned valid solutions (状态缓存误剪)")
            print("  3. Search space was incorrectly constrained (搜索空间被错误约束)")
            return False

        # 验证找到的解确实满足目标
        hits = simulate_board(solved)
        missing = solved.points - hits
        if not solved.points.issubset(hits):
            print("❌ FAIL: Solver found a layout that doesn't really hit targets!")
            print(f"  Expected targets: {sorted(solved.points)}")
            print(f"  Actual hits: {sorted(hits)}")
            print(f"  Missing: {sorted(missing)}")
            return False
        
        print("✓ PASS: Solver correctly finds solution for tiny_5")
        print(f"  Targets: {sorted(solved.points)}")
        print(f"  Hits: {sorted(hits)}")
        return True
    except Exception as e:
        print(f"❌ FAIL: Solver error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有诊断测试"""
    print("\n" + "=" * 60)
    print("Lazor 求解器诊断测试")
    print("=" * 60)
    print("\n测试目标：定位到底是 Parser / Simulator / Solver 哪一环出错\n")
    
    results = {
        "Parser": test_parser(),
        "Simulator": test_simulator(),
        "Solver": test_solver()
    }
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"  {name:15s}: {status}")
    
    print("\n" + "=" * 60)
    print("诊断说明")
    print("=" * 60)
    print("""
如果 (Parser ✓ + Simulator ✓ + Solver ❌) → 是 Solver 搜索/剪枝的问题
  - 检查是否有槽位截断
  - 检查状态缓存是否误剪
  - 检查搜索空间是否被错误约束

如果 (Parser ✓ + Simulator ❌) → 是 Simulator 问题
  - 检查 _block_ch_at 是否正确识别 grid 中的小写 a/b/c
  - 检查边界判断是否正确

如果 (Parser ❌) → 是 Parser/路径问题
  - 检查文件路径
  - 检查解析逻辑
    """)
    
    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

