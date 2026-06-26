"""
3D 圆检测脚本

算法流程（适用于孔洞、凸台等圆形特征）：
  1. 加载点云并过滤无效点
  2. RANSAC 拟合主平面，截取平面附近工作区域
  3. 投影到 2D，在边缘图上做 Hough 圆检测（孔洞=圆形边界）
  4. 3D 验证：检查圆周附近是否有足够点云支撑
  5. 去重合并，输出圆心 / 半径 / 法向

用法：
  python d3_circle_detect.py
  python d3_circle_detect.py cloud.ply --visualize
  python d3_circle_detect.py cloud.ply --max-circles 20 --circle-threshold 1.5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
import open3d as o3d

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# --- 默认配置 ---
INPUT_PATH = r"C:\saferword\ceshi-data\motorcycle-crankcase-ply\1.ply"
OUTPUT_JSON = ""

PLANE_DISTANCE = 0.0        # 0=按点云尺寸自动
PLANE_BAND = 0.0             # 平面切片厚度，0=自动
CIRCLE_DISTANCE = 0.0        # 圆周验证距离，0=自动
MIN_RADIUS = 0.0
MAX_RADIUS = 0.0
MIN_RIM_SUPPORT = 0.30       # 圆周采样点中至少 30% 附近有实际点云
MAX_CIRCLES = 20
VOXEL_SIZE = 0.0
AUTO_VOXEL_ABOVE = 800_000   # 超过此点数自动下采样
IMAGE_SIZE = 1400
SEED = 42


@dataclass
class Circle3DResult:
    index: int
    center: Tuple[float, float, float]
    radius: float
    normal: Tuple[float, float, float]
    inlier_count: int
    mean_residual: float
    max_residual: float
    support_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _PlaneFrame:
    origin: np.ndarray
    normal: np.ndarray
    u: np.ndarray
    v: np.ndarray
    slice_points: np.ndarray
    uv: np.ndarray
    pixel_scale: float
    uv_pcd: o3d.geometry.PointCloud


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3D 圆检测")
    parser.add_argument("input", nargs="?", default=INPUT_PATH, help="输入点云路径")
    parser.add_argument("--output", default=OUTPUT_JSON, help="结果 JSON 路径")
    parser.add_argument("--plane-threshold", type=float, default=PLANE_DISTANCE, help="平面 RANSAC 阈值（0=自动）")
    parser.add_argument("--plane-band", type=float, default=PLANE_BAND, help="平面切片厚度（0=自动）")
    parser.add_argument("--circle-threshold", type=float, default=CIRCLE_DISTANCE, help="圆周验证距离（0=自动）")
    parser.add_argument("--min-radius", type=float, default=MIN_RADIUS, help="最小半径（0=自动）")
    parser.add_argument("--max-radius", type=float, default=MAX_RADIUS, help="最大半径（0=自动）")
    parser.add_argument(
        "--min-rim-support",
        type=float,
        default=MIN_RIM_SUPPORT,
        help="圆周支撑比例下限（孔洞边缘检测用）",
    )
    parser.add_argument("--max-circles", type=int, default=MAX_CIRCLES, help="最多输出圆数量")
    parser.add_argument("--voxel", type=float, default=VOXEL_SIZE, help="体素下采样尺寸")
    parser.add_argument("--image-size", type=int, default=IMAGE_SIZE, help="2D 投影分辨率")
    parser.add_argument("--visualize", action="store_true", help="显示检测结果")
    parser.add_argument("--seed", type=int, default=SEED, help="随机种子")
    return parser.parse_args()


def load_and_clean(path: str, voxel_size: float) -> o3d.geometry.PointCloud:
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

    if voxel_size > 0:
        before = len(pcd.points)
        pcd = pcd.voxel_down_sample(voxel_size)
        print(f"体素下采样 (voxel={voxel_size}): {before:,} → {len(pcd.points):,}")
    elif len(pcd.points) > AUTO_VOXEL_ABOVE:
        span = auto_scale(np.asarray(pcd.points))
        voxel_size = max(span / 600.0, 0.3)
        before = len(pcd.points)
        pcd = pcd.voxel_down_sample(voxel_size)
        print(f"大点云自动下采样 (voxel={voxel_size:.2f}): {before:,} → {len(pcd.points):,}")

    return pcd


def auto_scale(values: np.ndarray) -> float:
    extent = values.max(axis=0) - values.min(axis=0)
    return float(np.max(extent))


def plane_basis(normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    n = normal / (np.linalg.norm(normal) + 1e-12)
    ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(n, ref)
    u /= np.linalg.norm(u) + 1e-12
    v = np.cross(n, u)
    return u, v


def project_to_plane(points: np.ndarray, origin: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    rel = points - origin
    return np.column_stack([rel @ u, rel @ v])


def lift_to_3d(cx: float, cy: float, frame: _PlaneFrame) -> np.ndarray:
    return frame.origin + cx * frame.u + cy * frame.v


def fit_dominant_plane(
    pcd: o3d.geometry.PointCloud,
    distance: float,
) -> Tuple[np.ndarray, np.ndarray]:
    plane_model, inliers = pcd.segment_plane(
        distance_threshold=distance,
        ransac_n=3,
        num_iterations=3000,
    )
    coeff = np.asarray(plane_model, dtype=np.float64)
    points = np.asarray(pcd.points)
    return coeff, points[np.asarray(inliers, dtype=int)]


def build_plane_frame(
    pcd: o3d.geometry.PointCloud,
    plane_threshold: float,
    plane_band: float,
) -> _PlaneFrame:
    points = np.asarray(pcd.points)
    span = auto_scale(points)

    if plane_threshold <= 0:
        plane_threshold = max(span * 0.008, 0.5)
    if plane_band <= 0:
        plane_band = max(span * 0.02, 2.0)

    coeff, plane_pts = fit_dominant_plane(pcd, plane_threshold)
    normal = coeff[:3]
    normal /= np.linalg.norm(normal) + 1e-12

    # 取法向正方向一侧、且靠近外表面的点（孔洞检测的工作面）
    signed_dist = points @ normal + coeff[3]
    side = plane_pts.mean(axis=0)
    if (side @ normal + coeff[3]) < 0:
        normal = -normal
        coeff = np.array([-normal[0], -normal[1], -normal[2], -coeff[3]])

    dist = np.abs(points @ normal + coeff[3])
    near_plane = dist < plane_band

    # 在平面附近点中，优先取法向同侧且 Z/深度较外的点
    aligned = points @ normal + coeff[3]
    outer_cut = np.percentile(aligned[near_plane], 85) if near_plane.any() else aligned.max()
    slice_mask = near_plane & (aligned >= outer_cut - plane_band)
    if slice_mask.sum() < 500:
        slice_mask = near_plane

    slice_points = points[slice_mask]
    origin = slice_points.mean(axis=0)
    u, v = plane_basis(normal)
    uv = project_to_plane(slice_points, origin, u, v)
    pixel_scale = max(float(uv[:, 0].ptp()), float(uv[:, 1].ptp())) / IMAGE_SIZE

    print(
        f"主平面法向: ({normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f})  "
        f"切片点数: {len(slice_points):,}  厚度: {plane_band:.2f}"
    )
    uv_tree_pcd = o3d.geometry.PointCloud()
    uv_tree_pcd.points = o3d.utility.Vector3dVector(
        np.column_stack([uv, np.zeros(len(uv), dtype=np.float64)])
    )
    return _PlaneFrame(origin, normal, u, v, slice_points, uv, pixel_scale, uv_tree_pcd)


def rasterize_slice(frame: _PlaneFrame, image_size: int) -> Tuple[np.ndarray, float, float, float, float]:
    uv = frame.uv
    u_min, u_max = float(uv[:, 0].min()), float(uv[:, 0].max())
    v_min, v_max = float(uv[:, 1].min()), float(uv[:, 1].max())

    cols = ((uv[:, 0] - u_min) / (u_max - u_min + 1e-9) * (image_size - 1)).astype(np.int32)
    rows = ((v_max - uv[:, 1]) / (v_max - v_min + 1e-9) * (image_size - 1)).astype(np.int32)

    count = np.zeros((image_size, image_size), dtype=np.int32)
    for r, c in zip(rows, cols):
        if 0 <= r < image_size and 0 <= c < image_size:
            count[r, c] += 1

    return count, u_min, u_max, v_min, v_max


def hough_circle_candidates(
    count: np.ndarray,
    pixel_scale: float,
    min_radius: float,
    max_radius: float,
) -> List[Tuple[float, float, float]]:
    if not HAS_CV2:
        raise RuntimeError("需要安装 opencv-python: pip install opencv-python")

    occupancy = (count > 0).astype(np.uint8) * 255
    edges = cv2.Canny(occupancy, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    min_r_px = max(5, int(min_radius / pixel_scale))
    max_r_px = max(min_r_px + 1, int(max_radius / pixel_scale))
    min_dist_px = max(15, int(min_radius * 0.8 / pixel_scale))

    raw = cv2.HoughCircles(
        edges,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_dist_px,
        param1=80,
        param2=22,
        minRadius=min_r_px,
        maxRadius=max_r_px,
    )
    if raw is None:
        return []

    h, w = count.shape
    candidates: List[Tuple[float, float, float]] = []
    for x, y, r in raw[0]:
        candidates.append((float(x), float(y), float(r)))
    return candidates


def pixel_to_uv(
    px: float,
    py: float,
    pr: float,
    image_size: int,
    u_min: float,
    u_max: float,
    v_min: float,
    v_max: float,
) -> Tuple[float, float, float]:
    cx = u_min + (px / (image_size - 1)) * (u_max - u_min)
    cy = v_max - (py / (image_size - 1)) * (v_max - v_min)
    scale = (u_max - u_min) / image_size
    radius = pr * scale
    return cx, cy, radius


def verify_circle(
    cx: float,
    cy: float,
    radius: float,
    frame: _PlaneFrame,
    kdtree: o3d.geometry.KDTreeFlann,
    verify_dist: float,
    min_rim_support: float,
) -> Optional[Tuple[int, float, float, float]]:
    if radius <= 0:
        return None

    uv = frame.uv
    dists = np.abs(np.hypot(uv[:, 0] - cx, uv[:, 1] - cy) - radius)
    rim_mask = dists < verify_dist
    inlier_count = int(rim_mask.sum())
    if inlier_count < 15:
        return None

    residuals = dists[rim_mask]
    mean_residual = float(residuals.mean())
    max_residual = float(residuals.max())

    angles = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    ring_uv = np.column_stack([
        cx + radius * np.cos(angles),
        cy + radius * np.sin(angles),
    ])
    ring_pts = np.column_stack([ring_uv, np.zeros(len(ring_uv), dtype=np.float64)])
    hits = 0
    thresh2 = (verify_dist * 1.5) ** 2
    for pt in ring_pts:
        _, _, dist2 = kdtree.search_knn_vector_3d(pt, 1)
        if dist2[0] < thresh2:
            hits += 1
    support = hits / len(ring_pts)
    if support < min_rim_support:
        return None

    return inlier_count, mean_residual, max_residual, support


def select_diverse_candidates(
    candidates: List[Tuple[float, float, float]],
    max_count: int,
) -> List[Tuple[float, float, float]]:
    """按半径均匀抽样，避免只验证最小圆而漏掉大孔。"""
    if len(candidates) <= max_count:
        return candidates
    order = sorted(range(len(candidates)), key=lambda i: candidates[i][2])
    picks = np.linspace(0, len(order) - 1, max_count, dtype=int)
    return [candidates[order[i]] for i in picks]


def dedupe_circles(
    items: List[Tuple[float, float, float, int, float, float, float]],
) -> List[Tuple[float, float, float, int, float, float, float]]:
    if not items:
        return []

    items = sorted(items, key=lambda x: (x[6], x[3]), reverse=True)
    kept: List[Tuple[float, float, float, int, float, float, float]] = []

    for cx, cy, r, n, mean_r, max_r, support in items:
        duplicate = False
        for kx, ky, kr, *_ in kept:
            center_dist = float(np.hypot(cx - kx, cy - ky))
            if center_dist < min(r, kr) * 0.55 and abs(r - kr) < max(r, kr) * 0.3:
                duplicate = True
                break
        if not duplicate:
            kept.append((cx, cy, r, n, mean_r, max_r, support))
    return kept


def detect_circles_3d(
    pcd: o3d.geometry.PointCloud,
    *,
    plane_threshold: float,
    plane_band: float,
    circle_threshold: float,
    min_radius: float,
    max_radius: float,
    min_rim_support: float,
    max_circles: int,
    image_size: int,
) -> Tuple[List[Circle3DResult], o3d.geometry.PointCloud, np.ndarray]:
    frame = build_plane_frame(pcd, plane_threshold, plane_band)
    span = max(float(frame.uv[:, 0].ptp()), float(frame.uv[:, 1].ptp()))

    r_min = min_radius if min_radius > 0 else span * 0.02
    r_max = max_radius if max_radius > 0 else span * 0.45
    verify_dist = circle_threshold if circle_threshold > 0 else max(frame.pixel_scale * 2.5, span * 0.004)

    print(f"半径范围: [{r_min:.2f}, {r_max:.2f}]  圆周验证距离: {verify_dist:.3f}")

    count, u_min, u_max, v_min, v_max = rasterize_slice(frame, image_size)
    candidates = hough_circle_candidates(count, frame.pixel_scale, r_min, r_max)
    print(f"Hough 候选圆: {len(candidates)} 个，开始 3D 验证...")

    kdtree = o3d.geometry.KDTreeFlann(frame.uv_pcd)
    candidates = select_diverse_candidates(candidates, 400)

    verified: List[Tuple[float, float, float, int, float, float, float]] = []
    for px, py, pr in candidates:
        cx, cy, radius = pixel_to_uv(px, py, pr, image_size, u_min, u_max, v_min, v_max)
        if radius < r_min or radius > r_max:
            continue
        result = verify_circle(cx, cy, radius, frame, kdtree, verify_dist, min_rim_support)
        if result is None:
            continue
        inlier_count, mean_r, max_r, support = result
        verified.append((cx, cy, radius, inlier_count, mean_r, max_r, support))

    deduped = dedupe_circles(verified)
    deduped.sort(key=lambda x: x[2], reverse=True)
    deduped = deduped[:max_circles]
    print(f"验证通过: {len(verified)} 个，去重后: {len(deduped)} 个")

    results: List[Circle3DResult] = []
    for idx, (cx, cy, radius, inlier_count, mean_r, max_r, support) in enumerate(deduped, start=1):
        center_3d = lift_to_3d(cx, cy, frame)
        results.append(
            Circle3DResult(
                index=idx,
                center=(float(center_3d[0]), float(center_3d[1]), float(center_3d[2])),
                radius=float(radius),
                normal=(float(frame.normal[0]), float(frame.normal[1]), float(frame.normal[2])),
                inlier_count=inlier_count,
                mean_residual=mean_r,
                max_residual=max_r,
                support_score=float(support),
            )
        )

    plane_cloud = o3d.geometry.PointCloud()
    plane_cloud.points = o3d.utility.Vector3dVector(frame.slice_points)
    return results, plane_cloud, frame.normal


def make_circle_wireframe(
    center: np.ndarray,
    normal: np.ndarray,
    radius: float,
    segments: int = 96,
    color: Tuple[float, float, float] = (1.0, 0.2, 0.2),
) -> o3d.geometry.LineSet:
    n = normal / (np.linalg.norm(normal) + 1e-12)
    u, v = plane_basis(n)
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ring = center + radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
    closed = np.vstack([ring, ring[0]])
    lines = [[i, i + 1] for i in range(segments)]
    ls = o3d.geometry.LineSet()
    ls.points = o3d.utility.Vector3dVector(closed)
    ls.lines = o3d.utility.Vector2iVector(lines)
    ls.colors = o3d.utility.Vector3dVector([color] * len(lines))
    return ls


def make_center_sphere(center: np.ndarray, radius: float) -> o3d.geometry.TriangleMesh:
    sphere = o3d.geometry.TriangleMesh.create_sphere(radius=max(radius * 0.04, 0.8))
    sphere.translate(center)
    sphere.paint_uniform_color([0.1, 1.0, 0.2])
    return sphere


def print_results(results: Sequence[Circle3DResult]) -> None:
    if not results:
        print("\n未检测到圆。可尝试：--min-rim-support 0.2 或 --circle-threshold 2.0")
        return

    print(f"\n检测到 {len(results)} 个圆：")
    print("-" * 80)
    for c in results:
        print(f"圆 #{c.index}")
        print(f"  圆心:   ({c.center[0]:.4f}, {c.center[1]:.4f}, {c.center[2]:.4f})")
        print(f"  半径:   {c.radius:.4f}")
        print(f"  法向:   ({c.normal[0]:.4f}, {c.normal[1]:.4f}, {c.normal[2]:.4f})")
        print(f"  边缘点: {c.inlier_count:,}  支撑: {c.support_score * 100:.1f}%")
        print(f"  残差:   均值 {c.mean_residual:.4f}  最大 {c.max_residual:.4f}")
    print("-" * 80)


def save_results(path: str, input_path: str, results: Sequence[Circle3DResult]) -> None:
    payload = {
        "input": input_path,
        "circle_count": len(results),
        "circles": [c.to_dict() for c in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {path}")


def visualize(
    pcd: o3d.geometry.PointCloud,
    plane_cloud: o3d.geometry.PointCloud,
    results: Sequence[Circle3DResult],
) -> None:
    plane_cloud.paint_uniform_color([0.3, 0.6, 1.0])
    geometries: List[o3d.geometry.Geometry] = [pcd, plane_cloud]

    colors = [(1, 0.2, 0.2), (1, 0.8, 0.1), (0.2, 1, 0.5), (1, 0.2, 1), (0.2, 0.8, 1)]
    for i, c in enumerate(results):
        center = np.asarray(c.center)
        normal = np.asarray(c.normal)
        color = colors[i % len(colors)]
        geometries.append(make_circle_wireframe(center, normal, c.radius, color=color))
        geometries.append(make_center_sphere(center, c.radius))

    print("\n可视化：彩色圆环=检测圆，绿色球=圆心，蓝色=工作面点")
    o3d.visualization.draw_geometries(
        geometries,
        window_name=f"3D 圆检测 ({len(results)} 个)",
        width=1280,
        height=800,
    )


def default_output_path(input_path: str) -> str:
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(os.path.dirname(input_path), f"{stem}_circles.json")


def main() -> None:
    if not HAS_CV2:
        raise RuntimeError("缺少 opencv-python，请执行: pip install opencv-python")

    args = parse_args()

    print(f"读取点云: {args.input}")
    pcd = load_and_clean(args.input, args.voxel)
    print(f"有效点数: {len(pcd.points):,}")

    results, plane_cloud, _ = detect_circles_3d(
        pcd,
        plane_threshold=args.plane_threshold,
        plane_band=args.plane_band,
        circle_threshold=args.circle_threshold,
        min_radius=args.min_radius,
        max_radius=args.max_radius,
        min_rim_support=args.min_rim_support,
        max_circles=args.max_circles,
        image_size=args.image_size,
    )

    print_results(results)

    out = args.output or default_output_path(args.input)
    save_results(out, args.input, results)

    if args.visualize:
        visualize(pcd, plane_cloud, results)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
