"""
点云交互式查看器

功能：
  - 加载 PLY / PCD / XYZ / PTS 等 Open3D 支持的格式
  - 鼠标旋转 / 滚轮缩放 / 右键平移
  - 无颜色时按 Z 轴高度着色
  - 大点云可选体素下采样
  - 导出 AIRVision ROI 裁剪参数（planning.bounding_boxes）
  - 快捷键：R 重置视角、S 截图、+/- 点大小、I 打印信息、E 导出 ROI

用法：
  python dianyun_view.py
  python dianyun_view.py C:\\data\\cloud.ply
  python dianyun_view.py cloud.ply --voxel 5.0
  python dianyun_view.py cloud.ply --output roi.json --export-only
  python dianyun_view.py cloud.ply --use-obb --padding 2.0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import open3d as o3d

# 默认点云路径（无命令行参数时使用）
DEFAULT_INPUT = r"C:\Users\luoca\Desktop\6\tranfrom\out.ply"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="点云交互式查看器")
    parser.add_argument(
        "input",
        nargs="?",
        default=DEFAULT_INPUT,
        help="点云文件路径（默认使用脚本内 DEFAULT_INPUT）",
    )
    parser.add_argument(
        "--voxel",
        type=float,
        default=0.0,
        metavar="SIZE",
        help="体素下采样尺寸，>0 时启用（数值越大点越少）",
    )
    parser.add_argument(
        "--point-size",
        type=float,
        default=0.0,
        help="渲染点大小（0 表示按包围盒自动估算）",
    )
    parser.add_argument(
        "--bg",
        type=float,
        nargs=3,
        default=(0.12, 0.12, 0.14),
        metavar=("R", "G", "B"),
        help="背景色 RGB，范围 0~1（默认深灰）",
    )
    parser.add_argument(
        "--no-axis",
        action="store_true",
        help="不显示坐标轴",
    )
    parser.add_argument(
        "--no-bbox",
        action="store_true",
        help="不显示包围盒线框",
    )
    parser.add_argument(
        "--screenshot-dir",
        default=".",
        help="按 S 键截图保存目录（默认当前目录）",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="",
        help="ROI 参数 JSON 输出路径（默认同目录 <文件名>_roi.json）",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="仅导出 ROI 参数，不打开可视化窗口",
    )
    parser.add_argument(
        "--use-obb",
        action="store_true",
        help="使用有向包围盒（OBB）而非轴对齐包围盒（AABB）",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.0,
        help="ROI 包围盒各方向外扩余量（与点云单位一致）",
    )
    parser.add_argument(
        "--box-id",
        default="1",
        help="bounding_boxes 中的键名（默认 \"1\"）",
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=2,
        help="JSON 数值小数位数",
    )
    return parser.parse_args()


def load_point_cloud(path: str) -> o3d.geometry.PointCloud:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"点云文件不存在: {path}")

    pcd = o3d.io.read_point_cloud(path)
    if len(pcd.points) == 0:
        raise ValueError(f"点云为空或格式无法识别: {path}")
    return pcd


def sanitize_point_cloud(pcd: o3d.geometry.PointCloud) -> Tuple[o3d.geometry.PointCloud, int]:
    """移除 NaN / Inf 无效点（深度相机常见，会导致包围盒与相机失效）。"""
    points = np.asarray(pcd.points)
    valid = np.isfinite(points).all(axis=1)
    removed = int((~valid).sum())
    if removed == 0:
        return pcd, 0

    cleaned = o3d.geometry.PointCloud()
    cleaned.points = o3d.utility.Vector3dVector(points[valid])
    if pcd.has_colors():
        colors = np.asarray(pcd.colors)
        cleaned.colors = o3d.utility.Vector3dVector(colors[valid])
    if pcd.has_normals():
        normals = np.asarray(pcd.normals)
        cleaned.normals = o3d.utility.Vector3dVector(normals[valid])

    print(f"已过滤无效点 (NaN/Inf): {removed:,} 个，保留 {len(cleaned.points):,} 个")
    return cleaned, removed


def normalize_colors(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """将颜色归一化到 0~1；全黑或无效颜色时改按高度着色。"""
    if not pcd.has_colors():
        return color_by_height(pcd)

    colors = np.asarray(pcd.colors, dtype=np.float64)
    if colors.max() > 1.0 + 1e-6:
        colors = colors / 255.0

    brightness = colors.max(axis=1)
    if float(brightness.mean()) < 0.02:
        print("颜色过暗（多为无效点残留），改用高度着色")
        return color_by_height(pcd)

    normalized = o3d.geometry.PointCloud(pcd)
    normalized.colors = o3d.utility.Vector3dVector(np.clip(colors, 0.0, 1.0))
    return normalized


def auto_point_size(pcd: o3d.geometry.PointCloud, requested: float) -> float:
    """根据包围盒尺寸自动估算合适的点大小。"""
    if requested > 0:
        return requested

    extent = np.asarray(pcd.get_axis_aligned_bounding_box().get_extent())
    span = float(np.max(extent))
    if span <= 0 or not np.isfinite(span):
        return 2.0

    # 经验值：场景越大、点越多，渲染点略大
    n = len(pcd.points)
    base = span / 400.0
    if n > 2_000_000:
        base *= 1.8
    elif n > 500_000:
        base *= 1.3
    return float(np.clip(base, 1.0, 8.0))


def color_by_height(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """无颜色时按 Z 轴归一化映射为伪彩色。"""
    points = np.asarray(pcd.points)
    z = points[:, 2]
    z_min, z_max = float(z.min()), float(z.max())
    span = z_max - z_min
    if span < 1e-9:
        normalized = np.zeros(len(z))
    else:
        normalized = (z - z_min) / span

    # 蓝 → 青 → 黄 → 红
    colors = np.zeros((len(normalized), 3))
    colors[:, 0] = np.clip(1.5 - np.abs(normalized * 2 - 1.5), 0, 1)
    colors[:, 1] = np.clip(1.0 - np.abs(normalized - 0.5) * 2, 0, 1)
    colors[:, 2] = np.clip(1.5 - normalized * 2, 0, 1)

    colored = o3d.geometry.PointCloud(pcd)
    colored.colors = o3d.utility.Vector3dVector(colors)
    return colored


def maybe_downsample(pcd: o3d.geometry.PointCloud, voxel_size: float) -> Tuple[o3d.geometry.PointCloud, int]:
    if voxel_size <= 0:
        return pcd, len(pcd.points)

    before = len(pcd.points)
    down = pcd.voxel_down_sample(voxel_size=voxel_size)
    after = len(down.points)
    print(f"体素下采样 (voxel={voxel_size}): {before:,} → {after:,} "
          f"(保留 {after / before * 100:.1f}%)")
    return down, before


def print_cloud_info(path: str, pcd: o3d.geometry.PointCloud, orig_count: Optional[int] = None) -> None:
    points = np.asarray(pcd.points)
    bbox = pcd.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    pmin = points.min(axis=0)
    pmax = points.max(axis=0)

    print("\n========== 点云信息 ==========")
    print(f"文件:     {path}")
    print(f"点数:     {len(points):,}", end="")
    if orig_count and orig_count != len(points):
        print(f"  (原始 {orig_count:,})", end="")
    print()
    print(f"有颜色:   {'是' if pcd.has_colors() else '否（已按高度着色）'}")
    print(f"有法线:   {'是' if pcd.has_normals() else '否'}")
    print(f"中心:     ({center[0]:.4f}, {center[1]:.4f}, {center[2]:.4f})")
    print(f"尺寸:     ({extent[0]:.4f}, {extent[1]:.4f}, {extent[2]:.4f})")
    print(f"最小点:   ({pmin[0]:.4f}, {pmin[1]:.4f}, {pmin[2]:.4f})")
    print(f"最大点:   ({pmax[0]:.4f}, {pmax[1]:.4f}, {pmax[2]:.4f})")
    print(f"Z 范围:   [{points[:, 2].min():.4f}, {points[:, 2].max():.4f}]")
    print("==============================\n")


def _round_list(values: np.ndarray, precision: int) -> List[float]:
    return [round(float(v), precision) for v in values]


def rotation_matrix_to_quaternion(r: np.ndarray) -> Tuple[float, float, float, float]:
    """3x3 旋转矩阵 → 四元数 (qx, qy, qz, qw)。"""
    m = np.asarray(r, dtype=np.float64)
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (m[2, 1] - m[1, 2]) / s
        qy = (m[0, 2] - m[2, 0]) / s
        qz = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        qw = (m[2, 1] - m[1, 2]) / s
        qx = 0.25 * s
        qy = (m[0, 1] + m[1, 0]) / s
        qz = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        qw = (m[0, 2] - m[2, 0]) / s
        qx = (m[0, 1] + m[1, 0]) / s
        qy = 0.25 * s
        qz = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        qw = (m[1, 0] - m[0, 1]) / s
        qx = (m[0, 2] + m[2, 0]) / s
        qy = (m[1, 2] + m[2, 1]) / s
        qz = 0.25 * s
    q = np.array([qx, qy, qz, qw])
    q /= np.linalg.norm(q) + 1e-12
    return float(q[0]), float(q[1]), float(q[2]), float(q[3])


def compute_bounding_box(
    pcd: o3d.geometry.PointCloud,
    *,
    use_obb: bool,
    padding: float,
) -> Tuple[np.ndarray, np.ndarray, Tuple[float, float, float, float]]:
    """返回 center, dimension, rotation(quaternion)。"""
    pad = max(padding, 0.0)
    if use_obb:
        box = pcd.get_oriented_bounding_box()
        center = np.asarray(box.center, dtype=np.float64)
        dimension = np.asarray(box.extent, dtype=np.float64) + 2.0 * pad
        rotation = rotation_matrix_to_quaternion(np.asarray(box.R))
    else:
        box = pcd.get_axis_aligned_bounding_box()
        center = np.asarray(box.get_center(), dtype=np.float64)
        dimension = np.asarray(box.get_extent(), dtype=np.float64) + 2.0 * pad
        rotation = (0.0, 0.0, 0.0, 1.0)
    return center, dimension, rotation


def build_roi_payload(
    path: str,
    pcd: o3d.geometry.PointCloud,
    *,
    box_id: str,
    use_obb: bool,
    padding: float,
    precision: int,
    orig_count: Optional[int] = None,
) -> Dict[str, Any]:
    """构建 AIRVision 3D ROI 裁剪工具可用的 JSON 结构。"""
    points = np.asarray(pcd.points)
    pmin = points.min(axis=0)
    pmax = points.max(axis=0)
    mean = points.mean(axis=0)
    center, dimension, rotation = compute_bounding_box(pcd, use_obb=use_obb, padding=padding)

    return {
        "input": path,
        "point_count": len(points),
        "original_point_count": orig_count if orig_count and orig_count != len(points) else len(points),
        "spatial": {
            "min": _round_list(pmin, precision),
            "max": _round_list(pmax, precision),
            "mean": _round_list(mean, precision),
            "center": _round_list(center, precision),
            "extent": _round_list(dimension, precision),
        },
        "planning": {
            "bounding_boxes": {
                box_id: {
                    "center": _round_list(center, precision),
                    "dimension": _round_list(dimension, precision),
                    "rotation": _round_list(np.array(rotation), precision),
                }
            }
        },
    }


def default_output_path(input_path: str) -> str:
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(os.path.dirname(input_path) or ".", f"{stem}_roi.json")


def save_roi_json(payload: Dict[str, Any], output_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return output_path


def print_roi_summary(payload: Dict[str, Any], output_path: str) -> None:
    box = next(iter(payload["planning"]["bounding_boxes"].values()))
    spatial = payload["spatial"]
    print("\n========== ROI 参数（3D ROI 裁剪） ==========")
    print(f"输出文件: {output_path}")
    print(f"点数:     {payload['point_count']:,}")
    print(f"空间范围: min={spatial['min']}  max={spatial['max']}")
    print(f"ROI 中心: {box['center']}")
    print(f"ROI 尺寸: {box['dimension']}")
    print(f"ROI 旋转: {box['rotation']}  (qx, qy, qz, qw)")
    print("============================================\n")


def build_geometries(
    pcd: o3d.geometry.PointCloud,
    show_axis: bool,
    show_bbox: bool,
) -> List[o3d.geometry.Geometry]:
    items: List[o3d.geometry.Geometry] = [pcd]

    if show_bbox:
        bbox = pcd.get_axis_aligned_bounding_box()
        bbox.color = (0.2, 0.8, 1.0)
        items.append(bbox)

    if show_axis:
        points = np.asarray(pcd.points)
        extent = pcd.get_axis_aligned_bounding_box().get_extent()
        axis_size = max(float(np.max(extent)) * 0.15, 1e-3)
        axis = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=axis_size,
            origin=points.mean(axis=0),
        )
        items.append(axis)

    return items


def run_viewer(
    path: str,
    pcd: o3d.geometry.PointCloud,
    *,
    point_size: float,
    bg_color: Tuple[float, float, float],
    show_axis: bool,
    show_bbox: bool,
    screenshot_dir: str,
    roi_payload: Dict[str, Any],
    roi_output_path: str,
    orig_count: Optional[int] = None,
) -> None:
    print_cloud_info(path, pcd, orig_count)

    print("操作说明:")
    print("  鼠标左键拖拽  旋转")
    print("  鼠标滚轮      缩放")
    print("  鼠标右键拖拽  平移")
    print("  R             重置视角")
    print("  S             截图")
    print("  E             重新导出 ROI JSON")
    print("  +/-           增大/减小点大小")
    print("  I             打印点云信息")
    print("  Q / Esc       退出\n")

    vis = o3d.visualization.VisualizerWithKeyCallback()
    vis.create_window(
        window_name=f"点云查看 - {os.path.basename(path)} ({len(pcd.points):,} 点)",
        width=1280,
        height=800,
    )

    state = {"point_size": point_size}

    for geom in build_geometries(pcd, show_axis, show_bbox):
        vis.add_geometry(geom)

    opt = vis.get_render_option()
    opt.background_color = np.asarray(bg_color)
    opt.point_size = state["point_size"]
    opt.show_coordinate_frame = False

    # 必须重置视角，否则 NaN 过滤前遗留的默认相机可能对准空场景
    vis.reset_view_point(True)
    ctr = vis.get_view_control()
    ctr.set_zoom(0.7)

    def _reset_view(_vis):
        _vis.reset_view_point(True)
        return False

    def _screenshot(_vis):
        os.makedirs(screenshot_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(screenshot_dir, f"{base}_view.png")
        _vis.capture_screen_image(out, do_render=True)
        print(f"截图已保存: {out}")
        return False

    def _print_info(_vis):
        print_cloud_info(path, pcd, orig_count)
        return False

    def _export_roi(_vis):
        save_roi_json(roi_payload, roi_output_path)
        print_roi_summary(roi_payload, roi_output_path)
        return False

    def _point_larger(_vis):
        state["point_size"] = min(state["point_size"] + 0.5, 20.0)
        opt.point_size = state["point_size"]
        print(f"点大小: {state['point_size']:.1f}")
        return False

    def _point_smaller(_vis):
        state["point_size"] = max(state["point_size"] - 0.5, 0.5)
        opt.point_size = state["point_size"]
        print(f"点大小: {state['point_size']:.1f}")
        return False

    vis.register_key_callback(ord("R"), _reset_view)
    vis.register_key_callback(ord("S"), _screenshot)
    vis.register_key_callback(ord("E"), _export_roi)
    vis.register_key_callback(ord("I"), _print_info)
    vis.register_key_callback(ord("+"), _point_larger)
    vis.register_key_callback(ord("="), _point_larger)
    vis.register_key_callback(ord("-"), _point_smaller)

    vis.run()
    vis.destroy_window()


def main() -> None:
    args = parse_args()

    print(f"读取点云: {args.input}")
    pcd = load_point_cloud(args.input)
    orig_count = len(pcd.points)

    pcd, _ = sanitize_point_cloud(pcd)
    if len(pcd.points) == 0:
        raise ValueError("过滤无效点后点云为空，请检查源文件")

    pcd, _ = maybe_downsample(pcd, args.voxel)
    pcd = normalize_colors(pcd)
    point_size = auto_point_size(pcd, args.point_size)
    if args.point_size <= 0:
        print(f"自动点大小: {point_size:.1f}")

    roi_output = args.output or default_output_path(args.input)
    roi_payload = build_roi_payload(
        args.input,
        pcd,
        box_id=args.box_id,
        use_obb=args.use_obb,
        padding=args.padding,
        precision=args.precision,
        orig_count=orig_count if args.voxel > 0 else None,
    )
    save_roi_json(roi_payload, roi_output)
    print_roi_summary(roi_payload, roi_output)

    if args.export_only:
        return

    run_viewer(
        args.input,
        pcd,
        point_size=point_size,
        bg_color=tuple(args.bg),
        show_axis=not args.no_axis,
        show_bbox=not args.no_bbox,
        screenshot_dir=args.screenshot_dir,
        roi_payload=roi_payload,
        roi_output_path=roi_output,
        orig_count=orig_count if args.voxel > 0 else None,
    )


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
