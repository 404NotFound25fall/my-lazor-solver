#!/usr/bin/env python3
# scripts/batch_solve.py
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径，以便能够导入 lazor_core
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root))

from time import perf_counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from lazor_core.parser import parse_bff
from lazor_core.board import Board
from lazor_core.models import BlockType
from lazor_core.solver import solve_optimized
from lazor_core.simulator import simulate_board

# 用于多进程的函数（需要是可序列化的）
def _solve_wrapper(board_data):
    """在子进程中运行的求解包装函数"""
    from lazor_core.board import Board
    board = Board.from_bffspec(board_data)
    return solve_optimized(board, debug=False)

def solve_one(bff_path: Path, out_dir: Path, time_limit_s: float = 120.0):
    t0 = perf_counter()
    spec = parse_bff(bff_path)
    board = Board.from_bffspec(spec)
    
    # 显示库存和可放位数量（快速诊断难度）
    slots = [(r, c) for r in range(board.nrows) for c in range(board.ncols) 
             if board.is_placeable(r, c)]
    inv_a = board.free_blocks.get(BlockType.REFLECT, 0)
    inv_b = board.free_blocks.get(BlockType.OPAQUE, 0)
    inv_c = board.free_blocks.get(BlockType.REFRACT, 0)
    print(f"  Inventory: A={inv_a}, B={inv_b}, C={inv_c} | slots={len(slots)}")

    # 使用进程池实现超时控制（CPU 密集型任务用进程更合适）
    solved = None
    try:
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_solve_wrapper, spec)
            try:
                solved = future.result(timeout=time_limit_s)
            except FutureTimeoutError:
                print(f"  警告: {bff_path.name} 超时 ({time_limit_s}s)，停止求解")
                future.cancel()
                return {"file": bff_path.name, "status": "TIMEOUT", "time_s": round(time_limit_s, 3)}
    except Exception as e:
        # 如果进程池失败（比如序列化问题），回退到直接调用
        print(f"  注意: 使用进程池失败，改为直接调用求解器: {e}")
        solved = solve_optimized(board, debug=False)
    
    elapsed = perf_counter() - t0

    if not solved:
        return {"file": bff_path.name, "status": "NO_SOLUTION", "time_s": round(elapsed, 3)}

    # 校验并保存 .sol
    hits = simulate_board(solved)
    ok = solved.points.issubset(hits)

    # 生成和 lazor_solver.py 类似的网格文本（固定块优先，其次动态网格）
    rows = []
    for r in range(solved.nrows):
        row = []
        for c in range(solved.ncols):
            if (r, c) in solved.fixed_blocks:
                kind = solved.fixed_blocks[(r, c)].kind
                row.append({"REFLECT":"A","OPAQUE":"B","REFRACT":"C"}[kind.name])
            else:
                ch = solved.grid[r][c]
                if ch.lower() in ("a", "d"):
                    row.append("A")  # 两种朝向都显示为 A
                elif ch.lower() in ("b", "c"):
                    row.append(ch.upper())
                else:
                    row.append(ch)
        rows.append(" ".join(row))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (bff_path.stem + ".sol")
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Solved Board Configuration\nGRID START\n")
        f.write("\n".join(rows))
        f.write("\nGRID STOP\n")
        f.write("\n# Verify\n")
        f.write(f"# Targets: {sorted(solved.points)}\n")
        f.write(f"# Hit OK: {ok}\n")
        f.write(f"# Time(s): {round(elapsed,3)}\n")
    return {"file": bff_path.name, "status": "OK" if ok else "HIT_MISS", "time_s": round(elapsed, 3), "sol": str(out_path)}

def main():
    root = Path(__file__).resolve().parents[1]
    in_dir = root / "examples" / "official"
    out_dir = root / "examples" / "solutions"
    results = []
    
    bff_files = sorted(in_dir.glob("*.bff"))
    print(f"找到 {len(bff_files)} 个 BFF 文件，开始批量求解...\n")
    
    for idx, bff in enumerate(bff_files, 1):
        print(f"[{idx}/{len(bff_files)}] 处理 {bff.name}...")
        results.append(solve_one(bff, out_dir, time_limit_s=120.0))
    
    # 简单打印汇总
    print("\n=== Batch Result ===")
    for r in results:
        line = f"{r['file']:20s}  {r['status']:10s}  {r['time_s']:>7}s"
        if "sol" in r: line += f"  -> {r['sol']}"
        print(line)

if __name__ == "__main__":
    main()
