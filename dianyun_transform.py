"""
点云空间坐标变换工具

支持平移、旋转、缩放、镜像、轴交换、居中、4x4 矩阵等操作，可组合使用。

用法：
  python dianyun_transform.py input.ply -o output.ply --translate 10 0 0
  python dianyun_transform.py input.ply -o out.ply --center --scale 0.001
  python dianyun_transform.py input.ply -o out.ply --rotate-xyz 0 0 90
  python dianyun_transform.py input.ply -o out.ply --flip z --translate 0 0 1600
  python dianyun_transform.py input.ply --info-only
  python dianyun_transform.py input.ply -o out.ply --matrix-file transform.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np
import open3d as o3d

INPUT_PATH = r"C:\Users\luoca\Desktop\6\1.ply"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="点云空间坐标变换",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  平移 10mm：       --translate 10 0 0
  绕 Z 轴转 90°：   --rotate-xyz 0 0 90
  缩放到米：        --scale 0.001
  居中到原点：      --center
  AABB 最小点归零： --set-min-origin
  组合：            --center --scale 2 --translate 0 0 100 -o out.ply
        """,
    )
    parser.add_argument("input", nargs="?", default=INPUT_PATH, help="输入点云路径")
    parser.add_argument("-o", "--output", default="", help="输出路径（默认 <原名>_transformed.ply）")

    parser.add_argument("--translate", "--offset", type=float, nargs=3, metavar=("X", "Y", "Z"),
                        help="平移 (dx, dy, dz)")
    parser.add_argument("--rotate-xyz", type=float, nargs=3, metavar=("RX", "RY", "RZ"),
                        help="绕 X/Y/Z 轴旋转（度），按 X→Y→Z 顺序")
    parser.add_argument("--rotate-axis", type=float, nargs=4, metavar=("AX", "AY", "AZ", "DEG"),
                        help="绕任意轴旋转（轴向量 + 角度°）")
    parser.add_argument("--scale", type=float, nargs="+", metavar="S",
                        help="缩放：1 个值为均匀缩放；3 个值为各轴 sx sy sz")
    parser.add_argument("--flip", choices=["x", "y", "z"], action="append",
                        help="沿指定轴镜像（可重复）")
    parser.add_argument("--swap", choices=["xy", "xz", "yz"], action="append",
                        help="交换坐标轴（可重复）")

    parser.add_argument("--center", action="store_true", help="平移使点云质心到原点")
    parser.add_argument("--center-aabb", action="store_true", help="平移使 AABB 中心到原点")
    parser.add_argument("--set-min-origin", action="store_true", help="平移使 AABB 最小角到原点")

    parser.add_argument("--matrix", type=float, nargs=16, metavar="M",
                        help="4x4 变换矩阵（行优先 16 个数）")
    parser.add_argument("--matrix-file", default="", help="从 JSON 读取 4x4 矩阵（键名 matrix）")

    parser.add_argument("--info-only", action="store_true", help="仅打印坐标信息，不写文件")
    parser.add_argument("--precision", type=int, default=4, help="打印小数位数")
    return parser.parse_args()


def load_cloud(path: str) -> o3d.geometry.PointCloud:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"点云文件不存在: {path}")
    pcd = o3d.io.read_point_cloud(path)
    pts = np.asarray(pcd.points)
    if len(pts) == 0:
        raise ValueError(f"点云为空: {path}")
    valid = np.isfinite(pts).all(axis=1)
    removed = int((~valid).sum())
    if removed:
        pcd = pcd.select_by_index(np.where(valid)[0])
        print(f"已过滤无效点: {removed:,} 个")
    return pcd


def cloud_stats(pcd: o3d.geometry.PointCloud) -> dict:
    pts = np.asarray(pcd.points)
    pmin = pts.min(axis=0)
    pmax = pts.max(axis=0)
    center = (pmin + pmax) / 2.0
    extent = pmax - pmin
    return {
        "count": len(pts),
        "min": pmin,
        "max": pmax,
        "mean": pts.mean(axis=0),
        "center": center,
        "extent": extent,
    }


def print_stats(label: str, stats: dict, precision: int) -> None:
    fmt = lambda v: [round(float(x), precision) for x in v]
    print(f"\n--- {label} ---")
    print(f"  点数:   {stats['count']:,}")
    print(f"  最小:   {fmt(stats['min'])}")
    print(f"  最大:   {fmt(stats['max'])}")
    print(f"  均值:   {fmt(stats['mean'])}")
    print(f"  中心:   {fmt(stats['center'])}")
    print(f"  尺寸:   {fmt(stats['extent'])}")


def rot_x(deg: float) -> np.ndarray:
    r = np.deg2rad(deg)
    c, s = np.cos(r), np.sin(r)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rot_y(deg: float) -> np.ndarray:
    r = np.deg2rad(deg)
    c, s = np.cos(r), np.sin(r)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rot_z(deg: float) -> np.ndarray:
    r = np.deg2rad(deg)
    c, s = np.cos(r), np.sin(r)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def rot_axis(axis: Sequence[float], deg: float) -> np.ndarray:
    v = np.asarray(axis, dtype=np.float64)
    n = np.linalg.norm(v)
    if n < 1e-12:
        raise ValueError("旋转轴不能为零向量")
    v /= n
    r = np.deg2rad(deg)
    c, s = 1.0 - np.cos(r), np.sin(r)
    x, y, z = v
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ], dtype=np.float64)


def apply_linear(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return points @ matrix.T


def load_matrix_file(path: str) -> np.ndarray:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "matrix" in data:
        mat = np.asarray(data["matrix"], dtype=np.float64)
    else:
        mat = np.asarray(data, dtype=np.float64)
    if mat.shape != (4, 4):
        mat = mat.reshape(4, 4)
    return mat


def default_output(input_path: str) -> str:
    stem, ext = os.path.splitext(input_path)
    return f"{stem}_transformed{ext or '.ply'}"


def build_transform_plan(args: argparse.Namespace) -> List[Tuple[str, Callable[[np.ndarray], np.ndarray]]]:
    """返回 (描述, 变换函数) 列表，按顺序执行。"""
    steps: List[Tuple[str, Callable[[np.ndarray], np.ndarray]]] = []

    if args.matrix_file:
        mat = load_matrix_file(args.matrix_file)

        def _mat(p: np.ndarray) -> np.ndarray:
            homo = np.hstack([p, np.ones((len(p), 1))])
            out = (mat @ homo.T).T
            return out[:, :3]

        steps.append((f"矩阵文件 {args.matrix_file}", _mat))

    if args.matrix:
        mat = np.asarray(args.matrix, dtype=np.float64).reshape(4, 4)

        def _mat2(p: np.ndarray) -> np.ndarray:
            homo = np.hstack([p, np.ones((len(p), 1))])
            return (mat @ homo.T).T[:, :3]

        steps.append(("4x4 矩阵", _mat2))

    if args.swap:
        for pair in args.swap:
            idx = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}[pair]

            def _swap(p, i=idx):
                q = p.copy()
                q[:, i[0]], q[:, i[1]] = p[:, i[1]].copy(), p[:, i[0]].copy()
                return q

            steps.append((f"交换轴 {pair.upper()}", _swap))

    if args.flip:
        for axis in args.flip:
            col = {"x": 0, "y": 1, "z": 2}[axis]

            def _flip(p, c=col):
                q = p.copy()
                q[:, c] *= -1.0
                return q

            steps.append((f"镜像 {axis.upper()}", _flip))

    if args.scale:
        if len(args.scale) == 1:
            s = args.scale[0]
            mat = np.diag([s, s, s])
            steps.append((f"均匀缩放 ×{s}", lambda p, m=mat: apply_linear(p, m)))
        elif len(args.scale) == 3:
            sx, sy, sz = args.scale
            mat = np.diag([sx, sy, sz])
            steps.append((f"缩放 [{sx}, {sy}, {sz}]", lambda p, m=mat: apply_linear(p, m)))
        else:
            raise ValueError("--scale 需要 1 个或 3 个数值")

    if args.rotate_xyz:
        rx, ry, rz = args.rotate_xyz
        mat = rot_z(rz) @ rot_y(ry) @ rot_x(rx)
        steps.append((f"旋转 XYZ ({rx}°, {ry}°, {rz}°)", lambda p, m=mat: apply_linear(p, m)))

    if args.rotate_axis:
        ax, ay, az, deg = args.rotate_axis
        mat = rot_axis([ax, ay, az], deg)
        steps.append((f"绕轴 [{ax},{ay},{az}] 转 {deg}°", lambda p, m=mat: apply_linear(p, m)))

    if args.center:
        steps.append(("质心居中", lambda p: p - p.mean(axis=0)))

    if args.center_aabb:
        def _center_aabb(p: np.ndarray) -> np.ndarray:
            pmin, pmax = p.min(axis=0), p.max(axis=0)
            return p - (pmin + pmax) / 2.0

        steps.append(("AABB 中心居中", _center_aabb))

    if args.set_min_origin:
        steps.append(("最小点归零", lambda p: p - p.min(axis=0)))

    if args.translate:
        t = np.asarray(args.translate, dtype=np.float64)
        steps.append((f"平移 {list(t)}", lambda p, v=t: p + v))

    return steps


def apply_steps(
    pcd: o3d.geometry.PointCloud,
    steps: List[Tuple[str, Callable[[np.ndarray], np.ndarray]]],
) -> o3d.geometry.PointCloud:
    if not steps:
        raise ValueError("未指定任何变换，请至少提供一个参数（见 --help）")

    out = o3d.geometry.PointCloud(pcd)
    points = np.asarray(out.points, dtype=np.float64).copy()

    print("\n变换步骤:")
    for i, (desc, fn) in enumerate(steps, 1):
        before = cloud_stats(out)
        points = fn(points)
        out.points = o3d.utility.Vector3dVector(points)
        after = cloud_stats(out)
        print(f"  {i}. {desc}")
        print(f"     中心: {np.round(before['center'], 4).tolist()} → {np.round(after['center'], 4).tolist()}")

    return out


def main() -> None:
    args = parse_args()

    print(f"读取点云: {args.input}")
    pcd = load_cloud(args.input)
    before = cloud_stats(pcd)
    print_stats("变换前", before, args.precision)

    steps = build_transform_plan(args)
    if not steps and not args.info_only:
        raise ValueError("未指定任何变换。使用 --help 查看可用参数，或 --info-only 仅查看信息。")

    if args.info_only:
        return

    result = apply_steps(pcd, steps)
    after = cloud_stats(result)
    print_stats("变换后", after, args.precision)

    output = args.output or default_output(args.input)
    os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)
    o3d.io.write_point_cloud(output, result)
    print(f"\n已保存: {output}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
