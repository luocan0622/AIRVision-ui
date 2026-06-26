"""
点云扩增脚本 —— 将较少点数的模型扩增到指定规模

思路：保留全部原始点 + 随机复制并施加微小抖动（模拟更密采样）
适用于性能测试、可视化压力测试等场景。

用法：
  python dianyun_upsample.py
  python dianyun_upsample.py input.ply --targets 1000000 2000000
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Sequence, Tuple

import numpy as np
import open3d as o3d

# --- 默认配置 ---
INPUT_PATH = r"C:\saferword\ceshi-data\metal-nut-ply\Metal Nut,ply\Meetal nut.ply"
TARGET_COUNTS = [1_000_000, 1_500_000, 2_000_000, 2_500_000, 3_000_000]
JITTER_RATIO = 0.001  # 抖动幅度 = 包围盒最大边长 × 此比例
SEED = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="点云扩增到指定点数")
    parser.add_argument("input", nargs="?", default=INPUT_PATH, help="输入点云路径")
    parser.add_argument(
        "--targets",
        type=int,
        nargs="+",
        default=TARGET_COUNTS,
        help="目标点数列表",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="输出目录（默认与输入文件同目录）",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=JITTER_RATIO,
        help="复制点时的抖动比例（相对包围盒最大边长）",
    )
    parser.add_argument("--seed", type=int, default=SEED, help="随机种子")
    return parser.parse_args()


def load_valid_cloud(path: str) -> o3d.geometry.PointCloud:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"点云文件不存在: {path}")

    pcd = o3d.io.read_point_cloud(path)
    points = np.asarray(pcd.points)
    if len(points) == 0:
        raise ValueError(f"点云为空: {path}")

    valid = np.isfinite(points).all(axis=1)
    removed = int((~valid).sum())
    if removed:
        pcd = pcd.select_by_index(np.where(valid)[0])
        print(f"已过滤无效点: {removed:,} 个")

    return pcd


def upsample_arrays(
    points: np.ndarray,
    colors: Optional[np.ndarray],
    target_count: int,
    jitter: float,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """将点云扩增/缩减到精确的目标点数。"""
    n = len(points)
    if target_count == n:
        return points, colors

    if target_count < n:
        idx = rng.choice(n, target_count, replace=False)
        new_colors = colors[idx] if colors is not None else None
        return points[idx], new_colors

    extra = target_count - n
    pick = rng.integers(0, n, extra)
    extent = points.max(axis=0) - points.min(axis=0)
    sigma = float(extent.max()) * jitter
    noise = rng.normal(0.0, sigma, (extra, 3)) if sigma > 0 else 0.0

    new_points = np.vstack([points, points[pick] + noise])
    if colors is not None:
        new_colors = np.vstack([colors, colors[pick]])
    else:
        new_colors = None

    perm = rng.permutation(target_count)
    return new_points[perm], (new_colors[perm] if new_colors is not None else None)


def to_point_cloud(points: np.ndarray, colors: Optional[np.ndarray]) -> o3d.geometry.PointCloud:
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    if colors is not None:
        pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd


def output_path(input_path: str, target_count: int, out_dir: str) -> str:
    stem = os.path.splitext(os.path.basename(input_path))[0]
    directory = out_dir or os.path.dirname(input_path)
    return os.path.join(directory, f"{stem}_{target_count}.ply")


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    print(f"读取点云: {args.input}")
    pcd = load_valid_cloud(args.input)
    orig_count = len(pcd.points)
    points = np.asarray(pcd.points, dtype=np.float64)
    colors = np.asarray(pcd.colors) if pcd.has_colors() else None

    print(f"原始点数: {orig_count:,}")
    print(f"目标规模: {', '.join(f'{t:,}' for t in args.targets)}\n")

    os.makedirs(args.out_dir or os.path.dirname(args.input), exist_ok=True)

    for target in args.targets:
        if target <= 0:
            print(f"[跳过] 无效目标点数: {target}")
            continue

        out = output_path(args.input, target, args.out_dir)
        print(f"生成 {target:,} 点 ...", end=" ", flush=True)

        new_pts, new_cols = upsample_arrays(
            points, colors, target, args.jitter, rng,
        )
        out_pcd = to_point_cloud(new_pts, new_cols)
        o3d.io.write_point_cloud(out, out_pcd)

        ratio = target / orig_count
        action = "扩增" if target > orig_count else ("缩减" if target < orig_count else "复制")
        print(f"完成 → {out}")
        print(f"       {orig_count:,} → {len(new_pts):,}  ({action} {ratio:.2f}x)")

    print("\n全部完成。")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
