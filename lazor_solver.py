#!/usr/bin/env python3
"""
Lazor Puzzle Solver - Main Entry Point

This is the complete implementation of the Lazor puzzle solver,
combining all stages:
- Stage 2: Parsing & Data Structures
- Stage 3: Laser Physics Simulation
- Stage 4: Solver Algorithm
- Stage 5: Output & Testing
"""
import sys
import time
from pathlib import Path
from lazor_core import parse_bff, Board, solve_optimized
from lazor_core.models import BlockType


def format_board_with_solution(board: Board) -> str:
    """格式化输出棋盘和解"""
    result = []
    result.append("# Solved Board Configuration")
    result.append("GRID START")
    
    # 创建网格字符串
    for r in range(board.nrows):
        row = []
        for c in range(board.ncols):
            if (r, c) in board.fixed_blocks:
                block = board.fixed_blocks[(r, c)]
                row.append({
                    BlockType.REFLECT: 'A',
                    BlockType.OPAQUE: 'B',
                    BlockType.REFRACT: 'C'
                }[block.kind])
            else:
                ch = board.grid[r][c]
                if isinstance(ch, str):
                    if ch.lower() in ("a", "d"):
                        row.append("A")  # 两种朝向都显示为 A
                    elif ch.lower() in ("b", "c"):
                        row.append(ch.upper())
                    else:
                        row.append(ch)
                else:
                    row.append(ch)
        result.append(" ".join(row))
    
    result.append("GRID STOP")
    return "\n".join(result)


def main():
    if len(sys.argv) < 2:
        print("用法: python lazor_solver.py <path/to/puzzle.bff> [output.txt]")
        print("  或: python lazor_solver.py <path/to/puzzle.bff>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        # 默认输出文件名
        input_path = Path(input_file)
        output_file = input_path.with_suffix('.sol').name
    
    # 解析输入文件
    print(f"正在解析文件: {input_file}")
    try:
        spec = parse_bff(input_file)
        board = Board.from_bffspec(spec)
        print("解析成功！")
        print(board.summary())
    except Exception as e:
        print(f"解析错误: {e}")
        sys.exit(1)
    
    # 开始求解
    print("\n开始求解...")
    start_time = time.time()
    
    try:
        # 先测试模拟器
        from lazor_core import simulate_board, get_placeable_positions, get_blocks_to_place
        hit_points = simulate_board(board)
        print(f"\n当前配置的激光击中点: {sorted(hit_points)}")
        print(f"期望的目标点: {sorted(board.points)}")
        
        # 显示需要放置的方块信息
        positions = get_placeable_positions(board)
        blocks = get_blocks_to_place(board)
        print(f"\n可放置位置数: {len(positions)}")
        print(f"需要放置的方块: {blocks}")
        
        solved_board = solve_optimized(board, debug=True)
        elapsed_time = time.time() - start_time
        
        if solved_board:
            print(f"\n✓ 找到解！ (耗时: {elapsed_time:.2f}秒)")
            
            # 生成输出
            output_content = format_board_with_solution(solved_board)
            
            # 写入文件
            with open(output_file, 'w') as f:
                f.write(output_content)
            
            print(f"\n解已保存到: {output_file}")
            print("\n解的内容:")
            print(output_content)
            
            # 验证解
            from lazor_core import simulate_board
            hit_points = simulate_board(solved_board)
            print(f"\n验证:")
            print(f"  期望的目标点: {sorted(board.points)}")
            print(f"  实际击中的点: {sorted(hit_points)}")
            ok = board.points.issubset(hit_points)
            print(f"  是否覆盖全部目标: {ok}")
            
        else:
            print(f"\n✗ 未找到解 (耗时: {elapsed_time:.2f}秒)")
            sys.exit(1)
            
    except Exception as e:
        print(f"求解错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

