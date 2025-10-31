# lazor_core/simulator.py
"""Stage 3: Laser Physics Engine

This module implements the laser simulation engine for Lazor.
It handles laser path tracing with proper collision detection and interaction.
"""
from __future__ import annotations
from typing import Set, Tuple, List, Optional
from .models import Laser, Block, BlockType
from .board import Board


def get_block_at_position(board: Board, row: int, col: int) -> Block | None:
    """
    获取棋盘上指定位置的方块。
    
    参数:
        board: 棋盘对象
        row, col: 方块的网格坐标 (不是 half-block 坐标)
    
    返回:
        如果位置有方块返回 Block 对象，否则返回 None
    """
    if board.in_bounds(row, col):
        return board.fixed_blocks.get((row, col))
    return None


def _block_ch_at(board: Board, r: int, c: int) -> Optional[str]:
    if not board.in_bounds(r, c):
        return None
    # 1) 网格中的标记（支持 'a', 'b', 'c', 'd'）
    try:
        gch = board.grid[r][c]
        if isinstance(gch, str):
            if gch.lower() in {'a', 'b', 'c', 'd'}:
                return gch.lower()
    except Exception:
        pass

    # 2) fixed_blocks 作为兜底
    blk = board.fixed_blocks.get((r, c))
    if blk:
        if blk.kind is BlockType.REFLECT:
            return 'a'  # 固定块默认 '/' 朝向
        if blk.kind is BlockType.OPAQUE:
            return 'b'
        if blk.kind is BlockType.REFRACT:
            return 'c'
    return None


def _reflect_slash(vx: int, vy: int) -> Tuple[int, int]:
    """'/' 朝向的镜面反射：围绕 y=-x 反射"""
    return (-vy, -vx)


def _reflect_backslash(vx: int, vy: int) -> Tuple[int, int]:
    """'\' 朝向的镜面反射：围绕 y=+x 反射"""
    return (vy, vx)


def _interact(block_ch: str, vx: int, vy: int, boundary: str) -> List[Tuple[int, int]]:
    """
    方块与激光的交互：
    - 'a' = A（反射块 '/'）：镜面反射 (-vy, -vx)
    - 'd' = A（反射块 '\'）：镜面反射 (vy, vx)
    - 'b' = opaque（不透明块）：吸收激光
    - 'c' = refract（折射块）：直行 + 轴对齐反射
    """
    if block_ch == 'b':
        return []  # 吸收，无出射光束

    if block_ch == 'a':
        # A："/" 朝向 - 镜面反射
        return [_reflect_slash(vx, vy)]

    if block_ch == 'd':
        # A："\" 朝向 - 镜面反射
        return [_reflect_backslash(vx, vy)]

    if block_ch == 'c':
        # 折射：直行 + 反射（反射部分仍按边界翻分量，轴对齐规则）
        passing = (vx, vy)
        if boundary == "vertical":
            reflected = (-vx, vy)
        elif boundary == "horizontal":
            reflected = (vx, -vy)
        else:
            reflected = (-vx, -vy)
        return [passing, reflected]

    return [(vx, vy)]  # 默认直行（无块）


def _block_across_vertical_edge(board: Board, mx: int, y: int, vy: int) -> Optional[str]:
    # mx is odd if crossing vertical edge between column (mx-1)//2 and (mx+1)//2
    if mx % 2 != 1:
        return None
    c = (mx - 1) // 2
    up_r = (y - 1) // 2
    down_r = (y + 1) // 2
    # prioritize according to movement vertical direction when available
    candidates = []
    if vy > 0:
        candidates = [(down_r, c), (up_r, c)]
    elif vy < 0:
        candidates = [(up_r, c), (down_r, c)]
    else:
        candidates = [(up_r, c), (down_r, c)]
    for r, cc in candidates:
        ch = _block_ch_at(board, r, cc)
        if ch:
            return ch
    return None


def _block_across_horizontal_edge(board: Board, x: int, my: int, vx: int) -> Optional[str]:
    if my % 2 != 1:
        return None
    r = (my - 1) // 2
    left_c = (x - 1) // 2
    right_c = (x + 1) // 2
    candidates = []
    if vx > 0:
        candidates = [(r, right_c), (r, left_c)]
    elif vx < 0:
        candidates = [(r, left_c), (r, right_c)]
    else:
        candidates = [(r, left_c), (r, right_c)]
    for rr, cc in candidates:
        ch = _block_ch_at(board, rr, cc)
        if ch:
            return ch
    return None


def _step_and_collide(board: Board, x: int, y: int, vx: int, vy: int) -> Tuple[int, int, List[Tuple[int, int]]]:
    nx, ny = x + vx, y + vy
    mx = (x + nx) // 2
    my = (y + ny) // 2
    interactions: List[Tuple[str, str]] = []  # (boundary, block_ch)

    hit_vertical = (mx % 2 == 1)
    hit_horizontal = (my % 2 == 1)

    if hit_vertical and hit_horizontal:
        corner_block = _block_ch_at(board, (my - 1) // 2, (mx - 1) // 2)
        if not corner_block:
            # 若无法直接获取角点方块，则退回边界检测结果
            blk_v = _block_across_vertical_edge(board, mx, y, vy)
            blk_h = _block_across_horizontal_edge(board, x, my, vx)
            if blk_v:
                interactions.append(("vertical", blk_v))
            if blk_h:
                interactions.append(("horizontal", blk_h))
        else:
            interactions.append(("corner", corner_block))
    else:
        if hit_vertical:
            blk_v = _block_across_vertical_edge(board, mx, y, vy)
            if blk_v:
                interactions.append(("vertical", blk_v))
        if hit_horizontal:
            blk_h = _block_across_horizontal_edge(board, x, my, vx)
            if blk_h:
                interactions.append(("horizontal", blk_h))

    # apply interactions sequentially, could branch (for refract)
    beams: List[Tuple[int, int]] = [(vx, vy)]
    for boundary, block_ch in interactions:
        next_beams: List[Tuple[int, int]] = []
        for bvx, bvy in beams:
            next_beams.extend(_interact(block_ch, bvx, bvy, boundary))
        beams = next_beams
        if not beams:
            break

    return nx, ny, beams


def simulate_board(board: Board) -> Set[Tuple[int, int]]:
    """
    模拟所有激光在棋盘上的路径，返回被击中的点集合。
    
    这是 Stage 3 的核心函数，实现完整的激光物理引擎。
    
    简化实现：将 half-block 坐标视为网格坐标进行模拟。
    
    参数:
        board: 完整的棋盘配置（包含所有已放置的方块）
    
    返回:
        被激光击中的所有目标点的集合 (half-block 坐标)
    """
    hit_points: Set[Tuple[int, int]] = set()
    
    # 使用队列模拟所有活动激光
    from collections import deque
    active_lasers = deque(board.lasers)
    
    # 用于检测循环（防止无限递归）
    visited_states: Set[Tuple[int, int, int, int]] = set()
    
    max_iterations = 5000  # 防止无限循环的安全阀（含分束更稳）
    
    iteration = 0
    while active_lasers and iteration < max_iterations:
        iteration += 1
        laser = active_lasers.popleft()
        
        # 注意：我们不在起点记录 hit_points，因为起点可能不是目标点
        # 记录当前点（但跳过初始激光的起点）
        if iteration > len(board.lasers) or (laser.x, laser.y) != (board.lasers[0].x, board.lasers[0].y):
            hit_points.add((laser.x, laser.y))
        
        # 推进一步并在半步中点判定碰撞（边界）
        new_x, new_y, out_dirs = _step_and_collide(board, laser.x, laser.y, laser.vx, laser.vy)

        # 记录新位置为命中点
        hit_points.add((new_x, new_y))

        # 边界检查（基于棋盘大小的宽松范围）
        # 一旦离开棋盘区域，立即终止这条光束，不再入队
        if new_y < -10 or new_y > board.nrows * 2 + 10 or new_x < -10 or new_x > board.ncols * 2 + 10:
            continue  # 已离开棋盘，不再处理

        # 分支后的光束入队（只在棋盘内）
        for vx, vy in out_dirs:
            # 如果新方向也会立即离开棋盘，跳过
            next_x, next_y = new_x + vx, new_y + vy
            if next_y < -10 or next_y > board.nrows * 2 + 10 or next_x < -10 or next_x > board.ncols * 2 + 10:
                continue
            
            state_key = (new_x, new_y, vx, vy)
            if state_key in visited_states:
                continue
            visited_states.add(state_key)
            active_lasers.append(Laser(x=new_x, y=new_y, vx=vx, vy=vy))
    
    if iteration >= max_iterations:
        print(f"警告: 模拟达到最大迭代次数 ({max_iterations})")
    
    return hit_points

