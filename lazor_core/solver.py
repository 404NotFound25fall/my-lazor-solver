# lazor_core/solver.py
"""Stage 4: Solver Algorithm

This module implements the backtracking solver for Lazor puzzles.
It generates all possible placements and tests them using the simulator.
"""
from __future__ import annotations
import copy
from typing import List, Tuple, Optional, Dict, Set
from .board import Board
from .models import BlockType
from .simulator import simulate_board


def get_placeable_positions(board: Board) -> List[Tuple[int, int]]:
    """
    获取所有可放置方块的位置。
    
    参数:
        board: 棋盘对象
    
    返回:
        可放置位置 (r, c) 的列表
    """
    positions = []
    for r in range(board.nrows):
        for c in range(board.ncols):
            if board.is_placeable(r, c):
                positions.append((r, c))
    return positions


def get_blocks_to_place(board: Board) -> List[BlockType]:
    """
    获取需要放置的方块列表。
    
    参数:
        board: 棋盘对象
    
    返回:
        需要放置的方块类型列表（例如: [A, A, C]）
    """
    blocks = []
    for block_type, count in board.free_blocks.items():
        blocks.extend([block_type] * count)
    return blocks


def _board_bounds(board: Board) -> Tuple[int, int, int, int]:
    """
    返回棋盘的边界坐标（half-block 单位）。
    """
    # half-block 坐标系统：网格 (r,c) 对应 half-block 坐标范围
    # 列：c -> [2*c, 2*c+2]，行：r -> [2*r, 2*r+2]
    xmin = 0
    xmax = board.ncols * 2
    ymin = 0
    ymax = board.nrows * 2
    return (xmin, xmax, ymin, ymax)


def _hot_slots_by_empty_trace(board: Board) -> Set[Tuple[int, int]]:
    """
    用"空板"追踪所有激光直行路径（只出界，不交互），
    收集被穿过的边所邻接的格子 → 这些格子放块才可能改变路径。
    
    返回:
        可能被光线穿过的格子位置集合（热格子）
    """
    hot = set()
    xmin, xmax, ymin, ymax = _board_bounds(board)
    
    for L in board.lasers:
        x, y, vx, vy = L.x, L.y, L.vx, L.vy
        seen = set()
        steps = 0
        max_steps = (xmax + ymax) * 2  # 防止死循环
        
        while xmin - 2 <= x <= xmax + 2 and ymin - 2 <= y <= ymax + 2 and steps < max_steps:
            steps += 1
            nx, ny = x + vx, y + vy
            mx, my = (x + nx) // 2, (y + ny) // 2  # 半步中点（边界位置）
            
            # 水平移动：经过竖直边界 → 边界上下两侧的格子可能有用
            if vx != 0 and vy == 0 and mx % 2 == 1:
                c = (mx - 1) // 2
                if 0 <= c < board.ncols:
                    # 检查边界两侧的行
                    r_up = (y - 1) // 2
                    r_dn = (y + 1) // 2
                    for r in (r_up, r_dn):
                        if 0 <= r < board.nrows and board.grid[r][c] == "o":
                            hot.add((r, c))
            
            # 垂直移动：经过水平边界 → 边界左右两侧的格子可能有用
            if vx == 0 and vy != 0 and my % 2 == 1:
                r = (my - 1) // 2
                if 0 <= r < board.nrows:
                    # 检查边界两侧的列
                    c_lt = (x - 1) // 2
                    c_rt = (x + 1) // 2
                    for c in (c_lt, c_rt):
                        if 0 <= c < board.ncols and board.grid[r][c] == "o":
                            hot.add((r, c))
            
            # 对角线移动：可能穿过一个角点，保守起见把四邻也纳入
            if vx != 0 and vy != 0:
                # 检查是否穿过网格点
                if mx % 2 == 1 and my % 2 == 1:
                    r_base = (my - 1) // 2
                    c_base = (mx - 1) // 2
                    # 检查周围格子
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            rr, cc = r_base + dr, c_base + dc
                            if 0 <= rr < board.nrows and 0 <= cc < board.ncols:
                                if board.grid[rr][cc] == "o":
                                    hot.add((rr, cc))
            
            x, y = nx, ny
            
            # 防死循环保障
            key = (x, y, vx, vy)
            if key in seen:
                break
            seen.add(key)
            
            # 如果已经离开棋盘区域很远，停止
            if abs(x) > xmax + 10 or abs(y) > ymax + 10:
                break
    
    return hot


def _sort_slots_by_laser_proximity(board: Board, slots: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    优先尝试靠近激光直线路径的槽位（命中概率大）。
    
    参数:
        board: 棋盘对象
        slots: 可放置位置的列表
    
    返回:
        按优先级排序的位置列表（热格子在前）
    """
    hot = _hot_slots_by_empty_trace(board)
    
    # 排序：热格子优先，然后是其他位置（保持行列顺序）
    return sorted(slots, key=lambda rc: ((rc not in hot), rc[0], rc[1]))


def _sort_slots_target_first(board: Board, slots: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    目标驱动的排序：优先尝试靠近未命中目标的槽位。
    结合热格子排序和目标距离。
    """
    targets = set(board.points)
    
    def dist_to_targets(rc: Tuple[int, int]) -> float:
        """计算槽位到所有目标的最小曼哈顿距离"""
        r, c = rc
        # 槽位中心点（half-block坐标）
        x = 2 * c + 1
        y = 2 * r + 1
        if not targets:
            return 0
        return min(abs(x - tx) + abs(y - ty) for (tx, ty) in targets)
    
    # 先按热格子排序
    base_sorted = _sort_slots_by_laser_proximity(board, slots)
    
    # 再按到目标的距离排序（距离近的优先）
    return sorted(base_sorted, key=lambda rc: dist_to_targets(rc))


def solve(board: Board) -> Optional[Board]:
    """
    求解 Lazor 谜题。
    
    使用 brute-force 方法生成所有可能的放置组合并测试。
    
    参数:
        board: 初始棋盘对象（包含 free_blocks 信息）
    
    返回:
        如果找到解，返回包含放置方案的 Board 对象；
        如果无解，返回 None
    """
    # 获取所有可放置位置和需要放置的方块
    positions = get_placeable_positions(board)
    blocks_to_place = get_blocks_to_place(board)
    
    # 如果没有方块要放置，检查是否已满足目标
    if not blocks_to_place:
        hit_points = simulate_board(board)
        if board.points.issubset(hit_points):
            return board
        return None
    
    # 导入 itertools 用于生成组合
    from itertools import permutations
    
    # 生成所有可能的放置顺序
    # 注意：这里使用 permutations 会导致重复计算
    # 更高效的方法是使用 combinations（如果方块类型相同）
    
    # 简单优化：使用 combinations 对于相同类型的方块
    from itertools import combinations
    
    num_blocks = len(blocks_to_place)
    num_positions = len(positions)
    
    # 生成选择的位置组合
    for pos_combination in combinations(positions, num_blocks):
        # 对于每个位置组合，生成方块的排列
        for block_permutation in set(permutations(blocks_to_place)):
            # 创建新的棋盘副本
            test_board = copy.deepcopy(board)
            
            # 放置方块
            for i, (r, c) in enumerate(pos_combination):
                test_board.place_block(r, c, block_permutation[i])
            
            # 模拟激光
            hit_points = simulate_board(test_board)
            
            # 检查是否满足所有目标点（使用 issubset）
            if board.points.issubset(hit_points):
                return test_board
    
    return None


def solve_optimized(board: Board, debug=False, use_hot_slots=True, hot_slots_ratio=1.0) -> Optional[Board]:
    """
    优化的求解器（处理相同类型方块的重复问题）。
    
    这个版本对性能进行优化，避免测试等效的配置。
    新增功能：
    - 热格子剪枝：只在光线路径附近的格子放置方块
    - 状态缓存：避免重复搜索相同的布局
    
    参数:
        board: 初始棋盘对象
        debug: 是否打印调试信息
        use_hot_slots: 是否使用热格子优化（只在前N%的热格子中搜索）
        hot_slots_ratio: 热格子的使用比例（0.0-1.0，1.0表示使用所有热格子）
    """
    # 获取所有可放置位置和需要放置的方块
    positions = get_placeable_positions(board)
    blocks_to_place = get_blocks_to_place(board)
    
    if debug:
        print(f"可放置位置: {len(positions)}")
        print(f"需要放置的方块: {blocks_to_place}")
    
    # 如果没有方块要放置，检查是否已满足目标
    if not blocks_to_place:
        hit_points = simulate_board(board)
        if board.points.issubset(hit_points):
            return board
        return None
    
    # 使用热格子和目标驱动排序（只排序，不截断！）
    if use_hot_slots:
        positions = _sort_slots_target_first(board, positions)
        hot = _hot_slots_by_empty_trace(board)
        
        if debug:
            print(f"热格子数量: {len(hot)} / {len(positions)}")
        
        # ⚠️ 重要：只排序不截断！截断会剪掉正确解（例如 tiny_5 需要非热格子）
        # 如果热格子数量合理，可以考虑限制搜索范围（但默认禁用）
        # if hot_slots_ratio < 1.0 and len(positions) > 10:
        #     # 至少保留足够的位置容纳所有方块
        #     min_needed = len(blocks_to_place) + 2
        #     k = max(min_needed, int(len(positions) * hot_slots_ratio))
        #     # 优先保留热格子
        #     hot_list = [p for p in positions if p in hot]
        #     other_list = [p for p in positions if p not in hot]
        #     positions = hot_list[:k] + other_list[:max(0, k - len(hot_list))]
        #     if debug:
        #         print(f"限制搜索范围到 {len(positions)} 个位置")
    
    # 优化：按类型分组方块（用于统计和优化）
    from collections import Counter
    block_counts = Counter(blocks_to_place)
    
    # 优化提示：如果只有一种类型的块（如 yarn_5 只有 A），排列数会大大减少
    unique_types = len(block_counts)
    if debug and unique_types == 1:
        print(f"  优化提示: 只有 {list(block_counts.keys())[0].name} 类型，排列数 = 1")
    
    # 生成所有可能的放置
    from itertools import combinations, permutations, product
    
    num_blocks = len(blocks_to_place)
    num_positions = len(positions)
    
    if debug:
        print(f"方块数量: {num_blocks}, 位置数量: {num_positions}")
    
    # 如果方块数量超出位置数量，无解
    if num_blocks > num_positions:
        return None
    
    # 状态缓存：避免重复测试相同的布局（使用更细的 key，包含位置信息）
    # ⚠️ 注意：由于使用 combinations，不同的位置组合可能产生相同的 grid，
    # 所以 state_key 应该包含位置信息，或者完全禁用缓存以避免误剪
    # 为了安全，暂时禁用状态缓存，避免误剪正确解
    use_state_cache = False  # 改为 True 启用缓存（但需要更细的 key）
    seen_states: Set[Tuple[Tuple[str, ...], ...]] = set() if use_state_cache else set()
    
    # 优化：只生成去重后的排列（对相同类型的块，避免重复排列）
    def generate_unique_permutations(blocks_list):
        """生成去重后的排列，跳过相同类型的重复排列"""
        # 对于只有一种类型的块（如 yarn_5），只生成一个排列
        from collections import Counter
        block_counts = Counter(blocks_list)
        if len(block_counts) == 1:
            # 只有一种类型，所有排列都相同，只返回一个
            yield tuple(blocks_list)
            return
        
        # 多种类型，需要去重（避免相同类型的重复排列）
        seen = set()
        for perm in permutations(blocks_list):
            if perm not in seen:
                seen.add(perm)
                yield perm
    
    # 搜索统计和诊断
    combo_count = 0
    perm_count = 0
    best_hit_count = -1
    best_snapshot_ascii = None
    total_nodes = 0
    
    for pos_combo in combinations(positions, num_blocks):
        combo_count += 1
        
        # 优化：如果位置组合数太大，可以考虑提前跳过某些明显无效的组合
        # 但为了正确性，这里暂时不做额外剪枝
        
        # 生成方块排列（使用去重生成器）
        for block_perm in generate_unique_permutations(blocks_to_place):
            # 收集所有 REFLECT 块的位置
            reflect_positions = [(r, c) for (r, c), bt in zip(pos_combo, block_perm) if bt is BlockType.REFLECT]
            num_reflects = len(reflect_positions)
            
            # 枚举所有 REFLECT 块的朝向组合 (a='/' 或 d='\')
            for orientation_choices in product(('a', 'd'), repeat=num_reflects):
                perm_count += 1
                total_nodes += 1

                test_board = copy.deepcopy(board)

                try:
                    # 创建位置到朝向的映射
                    orient_map = dict(zip(reflect_positions, orientation_choices))
                    
                    for (r, c), bt in zip(pos_combo, block_perm):
                        test_board.place_block(r, c, bt)
                        # 直接在 grid 上设置字符供模拟器使用
                        if bt is BlockType.REFLECT:
                            test_board.grid[r][c] = orient_map[(r, c)]
                        elif bt is BlockType.OPAQUE:
                            test_board.grid[r][c] = 'b'
                        elif bt is BlockType.REFRACT:
                            test_board.grid[r][c] = 'c'
                except ValueError:
                    continue

                if use_state_cache:
                    state_key = (
                        tuple(sorted((pos, test_board.grid[pos[0]][pos[1]]) for pos in pos_combo)),
                        tuple(sorted(test_board.fixed_blocks.keys()))
                    )
                    if state_key in seen_states:
                        continue
                    seen_states.add(state_key)

                hit_points = simulate_board(test_board)
                hit_count = len(board.points.intersection(hit_points))

                if hit_count > best_hit_count:
                    best_hit_count = hit_count
                    best_snapshot_ascii = test_board.to_ascii()

                if debug and perm_count % 100 == 0:
                    print(f"  已测试 {perm_count} 个配置，最佳命中: {best_hit_count}/{len(board.points)}")

                if board.points.issubset(hit_points):
                    if debug:
                        print(f"✓ 找到解！测试了 {combo_count} 个位置组合，{perm_count} 个方块排列")
                    return test_board
    
    # 未找到解时的诊断信息（总是输出，便于定位问题）
    if best_hit_count < len(board.points):
        target_count = len(board.points)
        print(f"[诊断] 未找到解: 节点数={total_nodes}, "
              f"位置组合={combo_count}, 排列数={perm_count}, "
              f"最佳命中={best_hit_count}/{target_count}")
        
        # 诊断解读
        if total_nodes < 1000 and best_hit_count < target_count:
            print(f"  ⚠️  节点数很小但最佳命中不足 → 可能搜索被过早终止或剪枝过激")
        elif total_nodes > 10000 and best_hit_count >= target_count - 1:
            print(f"  ⚠️  节点数很大且接近目标 → 可能需要更多时间或调整搜索策略")
        
        if best_snapshot_ascii and best_hit_count > 0:
            print(f"  最佳布局命中 {best_hit_count} 个目标点（还差 {target_count - best_hit_count} 个）")
            print("  最佳布局示意:\n" + best_snapshot_ascii)
    
    return None

