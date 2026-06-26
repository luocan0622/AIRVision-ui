"""
点云 → 多视角深度图 / 灰度图 批量生成

功能：
  - 自动分析点云结构（OBB、PCA、平面 RANSAC、聚类、关键点）
  - 基于结构生成多方位观察位姿，去重后按信息量筛选
  - 每个位姿一组：depth.tiff（16-bit 真实深度）+ gray.tiff（仿真强度，≠ 深度）
  - 可选 depth_vis.png / mask.png

位姿定义：观察方向 view_dir（相机位于 +view_dir 侧看向点云），正交投影 + Z-buffer。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import open3d as o3d
from PIL import Image

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ============================================================
# 配置
# ============================================================

INPUT_PATH = r"C:\saferword\ceshi-data\motorcycle-crankcase-ply\1.ply"
OUT_DIR = r"C:\saferword\ceshi-data\motorcycle-crankcase-ply\multi_view"

TARGET_WIDTH = 3200
PIXEL_SIZE_MM: Optional[float] = None
SPLAT_RADIUS = 2

# 自动位姿发现
AUTO_AXIS_VIEWS = True
AUTO_PCA_VIEWS = True
AUTO_OBB_VIEWS = True
AUTO_PLANE_VIEWS = True
AUTO_CLUSTER_VIEWS = True
AUTO_KEYPOINT_VIEWS = True
AUTO_TILT_VIEWS = True
AUTO_SPHERE_FILL = True

PCA_EIGEN_RATIO_MIN = 0.08
MIN_VALID_RATIO = 0.03
MIN_DEPTH_SPAN_MM = 0.5
VIEW_DEDUP_COS = 0.985          # 同半球内方向余弦 > 此阈值视为重复（不用 abs，保留 ± 方向）
MAX_VIEWS = 24                  # 最多输出视角数（按得分选取）
MIN_VIEW_ANGLE_DEG = 12.0       # 最终选集中任意两视角最小夹角
EVAL_SUBSAMPLE = 120_000        # 位姿评估时下采样点数（仅筛选，不影响最终渲染）

# 结构分析
PLANE_RANSAC_DIST = 1.5         # mm（非 mm 单位时自动缩放）
PLANE_RANSAC_MAX = 5
PLANE_MIN_POINTS = 500
CLUSTER_EPS = 3.0               # DBSCAN eps（mm）
CLUSTER_MIN_POINTS = 200
KEYPOINT_COUNT = 8
SPHERE_FILL_COUNT = 12
TILT_ANGLES_DEG = (35.0, 55.0)

CUSTOM_VIEWS: List[Tuple[str, Tuple[float, float, float]]] = []

SAVE_DEPTH_VIS = False
SAVE_MASK = False

INPAINT_RADIUS = 3
INPAINT_GAPS = True
PERCENTILE_LOW = 0.5
PERCENTILE_HIGH = 99.5
USE_CLAHE = True
CLAHE_CLIP = 2.5
CLAHE_TILE = 8

LIGHT_DIR_CAM = (0.15, 0.25, 0.95)
WEIGHT_SHADING = 0.50
WEIGHT_HIGHPASS = 0.35
WEIGHT_EDGE = 0.15


@dataclass
class ViewPose:
    name: str
    view_dir: Tuple[float, float, float]
    source: str = "manual"
    score: float = 0.0

    def direction(self) -> np.ndarray:
        d = np.array(self.view_dir, dtype=np.float64)
        n = np.linalg.norm(d)
        return d / n if n > 0 else np.array([0.0, 0.0, 1.0])


@dataclass
class ProjectionMeta:
    view_name: str
    view_dir: Tuple[float, float, float]
    width: int
    height: int
    pixel_size_u: float
    pixel_size_v: float
    units_mm: bool
    valid_ratio: float
    depth_span: float
    view_score: float = 0.0
    view_source: str = ""


@dataclass
class CloudStructure:
    center: np.ndarray
    units_mm: bool
    scale: float
    obb_axes: np.ndarray = field(default_factory=lambda: np.eye(3))
    obb_extents: np.ndarray = field(default_factory=lambda: np.ones(3))
    pca_axes: np.ndarray = field(default_factory=lambda: np.eye(3))
    pca_evals: np.ndarray = field(default_factory=lambda: np.ones(3))
    planes: List[Tuple[np.ndarray, np.ndarray, int]] = field(default_factory=list)
    cluster_centroids: List[np.ndarray] = field(default_factory=list)
    key_points: List[np.ndarray] = field(default_factory=list)


def detect_units_mm(points: np.ndarray) -> bool:
    return float(np.max(points.max(axis=0) - points.min(axis=0))) > 20.0


def unit_vec(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else np.array([0.0, 0.0, 1.0])


def make_view_basis(view_dir: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = unit_vec(view_dir)
    ref = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(n, ref))) > 0.95:
        ref = np.array([0.0, 1.0, 0.0])
    u_ax = np.cross(ref, n)
    u_ax /= max(np.linalg.norm(u_ax), 1e-12)
    v_ax = np.cross(n, u_ax)
    return u_ax, v_ax, n


def project_coords(
    points: np.ndarray, center: np.ndarray, view_dir: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    u_ax, v_ax, n = make_view_basis(view_dir)
    p = points - center
    return p @ u_ax, p @ v_ax, p @ n


def compute_image_size(
    u_min: float, u_max: float, v_min: float, v_max: float,
    target_width: int, pixel_size_mm: Optional[float],
) -> Tuple[int, int, float, float]:
    u_span = max(u_max - u_min, 1e-6)
    v_span = max(v_max - v_min, 1e-6)
    if pixel_size_mm and pixel_size_mm > 0:
        w = max(int(np.ceil(u_span / pixel_size_mm)), 1)
        h = max(int(np.ceil(v_span / pixel_size_mm)), 1)
        return w, h, pixel_size_mm, pixel_size_mm
    w = max(target_width, 1)
    h = max(int(round(w * v_span / u_span)), 1)
    return w, h, u_span / w, v_span / h


def world_to_pixel(
    u: np.ndarray, v: np.ndarray,
    u_min: float, u_max: float, v_min: float, v_max: float,
    width: int, height: int,
) -> Tuple[np.ndarray, np.ndarray]:
    u_span = max(u_max - u_min, 1e-6)
    v_span = max(v_max - v_min, 1e-6)
    col = np.floor((u - u_min) / u_span * (width - 1)).astype(np.int32)
    row = np.floor((v_max - v) / v_span * (height - 1)).astype(np.int32)
    return col, row


def build_depth_buffer(
    col: np.ndarray, row: np.ndarray, depth: np.ndarray,
    width: int, height: int, splat_radius: int,
) -> np.ndarray:
    in_bounds = (col >= 0) & (col < width) & (row >= 0) & (row < height)
    col, row, depth = col[in_bounds], row[in_bounds], depth[in_bounds]
    if depth.size == 0:
        return np.full((height, width), np.nan, dtype=np.float64)

    buf = np.full((height, width), -np.inf, dtype=np.float64)
    r = max(splat_radius, 0)
    loops = [(0, 0)] if r == 0 else [
        (dr, dc) for dr in range(-r, r + 1) for dc in range(-r, r + 1)
    ]
    for dr, dc in loops:
        rr, cc = row + dr, col + dc
        ok = (rr >= 0) & (rr < height) & (cc >= 0) & (cc < width)
        if ok.any():
            np.maximum.at(buf, (rr[ok], cc[ok]), depth[ok])

    buf[~np.isfinite(buf) | (buf == -np.inf)] = np.nan
    return buf


def inpaint_near_gaps(values: np.ndarray, valid: np.ndarray, radius: int) -> np.ndarray:
    if not HAS_CV2 or radius <= 0 or not valid.any():
        return values
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    near = cv2.dilate(valid.astype(np.uint8), kernel).astype(bool)
    mask = (~valid & near).astype(np.uint8)
    if not mask.any():
        return values
    src = np.nan_to_num(values, nan=0.0).astype(np.float32)
    filled = cv2.inpaint(src, mask, radius, cv2.INPAINT_TELEA)
    out = values.copy()
    out[mask.astype(bool)] = filled[mask.astype(bool)]
    return out


def percentile_normalize(values: np.ndarray, valid: np.ndarray, lo: float, hi: float) -> np.ndarray:
    out = np.zeros_like(values, dtype=np.float64)
    if not valid.any():
        return out
    p0, p1 = np.percentile(values[valid], lo), np.percentile(values[valid], hi)
    if p1 <= p0:
        out[valid] = 0.5
    else:
        out[valid] = np.clip((values[valid] - p0) / (p1 - p0), 0.0, 1.0)
    return out


def apply_clahe(gray_u8: np.ndarray, valid: np.ndarray) -> np.ndarray:
    if not USE_CLAHE or not HAS_CV2 or not valid.any():
        return gray_u8
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(CLAHE_TILE, CLAHE_TILE))
    enhanced = clahe.apply(gray_u8)
    out = gray_u8.copy()
    out[valid] = enhanced[valid]
    return out


def depth_to_16bit(depth: np.ndarray) -> np.ndarray:
    valid = np.isfinite(depth)
    out = np.zeros(depth.shape, dtype=np.uint16)
    if not valid.any():
        return out
    vals = depth[valid].astype(np.float64)
    v0, v1 = vals.min(), vals.max()
    if v1 > v0:
        out[valid] = np.clip(np.round((vals - v0) / (v1 - v0) * 65535.0), 0, 65535).astype(np.uint16)
    else:
        out[valid] = 32768
    return out


def depth_to_preview_8bit(depth: np.ndarray) -> np.ndarray:
    valid = np.isfinite(depth)
    norm = percentile_normalize(depth, valid, PERCENTILE_LOW, PERCENTILE_HIGH)
    vis = np.zeros(depth.shape, dtype=np.uint8)
    vis[valid] = np.round(norm[valid] * 255.0).astype(np.uint8)
    return vis


def depth_to_intensity_gray(
    depth: np.ndarray, pixel_size_u: float, pixel_size_v: float,
) -> np.ndarray:
    valid = np.isfinite(depth)
    if not valid.any():
        return np.zeros(depth.shape, dtype=np.uint8)
    if not HAS_CV2:
        return depth_to_preview_8bit(depth)

    z = inpaint_near_gaps(depth.copy(), valid, INPAINT_RADIUS)
    z_f = np.where(valid, z, 0.0).astype(np.float64)
    du = pixel_size_u if pixel_size_u > 0 else 1.0
    dv = pixel_size_v if pixel_size_v > 0 else 1.0
    dz_du = cv2.Sobel(z_f, cv2.CV_64F, 1, 0, ksize=3) / (8.0 * du)
    dz_dv = cv2.Sobel(z_f, cv2.CV_64F, 0, 1, ksize=3) / (8.0 * dv)

    nx, ny = -dz_du, -dz_dv
    nz = np.ones_like(nx)
    nlen = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-9)
    nx, ny, nz = nx / nlen, ny / nlen, nz / nlen

    lx, ly, lz = LIGHT_DIR_CAM
    ln = max(np.sqrt(lx * lx + ly * ly + lz * lz), 1e-9)
    shading = np.clip(nx * lx / ln + ny * ly / ln + nz * lz / ln, 0.0, 1.0)

    blur = cv2.GaussianBlur(z_f, (0, 0), sigmaX=1.5, sigmaY=1.5)
    highpass = z_f - blur
    edge = np.sqrt(dz_du * dz_du + dz_dv * dz_dv)

    intensity = (
        WEIGHT_SHADING * percentile_normalize(shading, valid, PERCENTILE_LOW, PERCENTILE_HIGH)
        + WEIGHT_HIGHPASS * percentile_normalize(highpass, valid, PERCENTILE_LOW, PERCENTILE_HIGH)
        + WEIGHT_EDGE * percentile_normalize(edge, valid, PERCENTILE_LOW, PERCENTILE_HIGH)
    )
    intensity = np.clip(intensity, 0.0, 1.0)
    gray = np.zeros(depth.shape, dtype=np.uint8)
    gray[valid] = np.round(intensity[valid] * 255.0).astype(np.uint8)

    if INPAINT_GAPS:
        gray = inpaint_near_gaps(gray.astype(np.float64), valid, INPAINT_RADIUS)
        gray = np.clip(np.round(gray), 0, 255).astype(np.uint8)
        gray[~valid] = 0
    return apply_clahe(gray, valid)


def gray_from_point_colors(
    colors: np.ndarray, col: np.ndarray, row: np.ndarray,
    width: int, height: int, splat_radius: int,
) -> np.ndarray:
    intensity = (0.299 * colors[:, 0] + 0.587 * colors[:, 1] + 0.114 * colors[:, 2]) * 255.0
    acc = np.zeros((height, width), dtype=np.float64)
    r = max(splat_radius, 0)
    loops = [(0, 0)] if r == 0 else [
        (dr, dc) for dr in range(-r, r + 1) for dc in range(-r, r + 1)
    ]
    for dr, dc in loops:
        rr, cc = row + dr, col + dc
        ok = (rr >= 0) & (rr < height) & (cc >= 0) & (cc < width)
        if ok.any():
            np.maximum.at(acc, (rr[ok], cc[ok]), intensity[ok])
    valid = acc > 0
    gray = np.zeros((height, width), dtype=np.uint8)
    if valid.any():
        norm = percentile_normalize(acc, valid, PERCENTILE_LOW, PERCENTILE_HIGH)
        gray[valid] = np.round(norm[valid] * 255.0).astype(np.uint8)
    return apply_clahe(gray, valid)


def render_view(
    points: np.ndarray,
    colors: Optional[np.ndarray],
    center: np.ndarray,
    pose: ViewPose,
    units_mm: bool,
) -> Tuple[np.ndarray, np.ndarray, ProjectionMeta]:
    view_dir = pose.direction()
    u, v, d = project_coords(points, center, view_dir)
    ok = np.isfinite(u) & np.isfinite(v) & np.isfinite(d)
    u, v, d = u[ok], v[ok], d[ok]
    cols = colors[ok] if colors is not None else None

    u_min, u_max = float(u.min()), float(u.max())
    v_min, v_max = float(v.min()), float(v.max())
    w, h, psu, psv = compute_image_size(u_min, u_max, v_min, v_max, TARGET_WIDTH, PIXEL_SIZE_MM)
    col, row = world_to_pixel(u, v, u_min, u_max, v_min, v_max, w, h)
    depth = build_depth_buffer(col, row, d, w, h, SPLAT_RADIUS)
    valid = np.isfinite(depth)

    if cols is not None:
        gray = gray_from_point_colors(cols, col, row, w, h, SPLAT_RADIUS)
    else:
        gray = depth_to_intensity_gray(depth, psu, psv)

    d_valid = depth[valid]
    depth_span = float(d_valid.max() - d_valid.min()) if d_valid.size else 0.0
    meta = ProjectionMeta(
        view_name=pose.name,
        view_dir=tuple(view_dir.tolist()),
        width=w,
        height=h,
        pixel_size_u=psu,
        pixel_size_v=psv,
        units_mm=units_mm,
        valid_ratio=float(valid.mean()),
        depth_span=depth_span,
        view_score=pose.score,
        view_source=pose.source,
    )
    return depth, gray, meta


def quick_evaluate_view(
    points: np.ndarray, center: np.ndarray, view_dir: np.ndarray,
) -> Tuple[float, float, float]:
    """返回 (有效覆盖率, 深度跨度, 轮廓填充率近似)。"""
    if len(points) > EVAL_SUBSAMPLE:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(points), EVAL_SUBSAMPLE, replace=False)
        points = points[idx]
    u, v, d = project_coords(points, center, view_dir)
    ok = np.isfinite(u) & np.isfinite(v) & np.isfinite(d)
    if not ok.any():
        return 0.0, 0.0, 0.0
    u, v, d = u[ok], v[ok], d[ok]
    u_min, u_max = float(u.min()), float(u.max())
    v_min, v_max = float(v.min()), float(v.max())
    w, h, _, _ = compute_image_size(u_min, u_max, v_min, v_max, TARGET_WIDTH, PIXEL_SIZE_MM)
    col, row = world_to_pixel(u, v, u_min, u_max, v_min, v_max, w, h)
    in_bounds = (col >= 0) & (col < w) & (row >= 0) & (row < h)
    col, row, d = col[in_bounds], row[in_bounds], d[in_bounds]
    if d.size == 0:
        return 0.0, 0.0, 0.0
    buf = build_depth_buffer(col, row, d, w, h, max(SPLAT_RADIUS - 1, 0))
    valid = np.isfinite(buf)
    ratio = float(valid.mean())
    if not valid.any():
        return ratio, 0.0, 0.0
    dv = buf[valid]
    span = float(dv.max() - dv.min())
    hull_fill = ratio
    if HAS_CV2 and valid.sum() > 100:
        mask = valid.astype(np.uint8) * 255
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            hull = np.zeros_like(mask)
            cv2.drawContours(hull, cnts, -1, 255, thickness=cv2.FILLED)
            hull_fill = float((valid & (hull > 0)).sum() / max(hull.sum() // 255, 1))
    return ratio, span, hull_fill


def view_quality_score(ratio: float, span: float, hull_fill: float, scale: float) -> float:
    span_norm = span / max(scale, 1e-6)
    return 0.45 * ratio + 0.35 * min(span_norm, 1.0) + 0.20 * hull_fill


# ---------------------------------------------------------------------------
# 点云结构分析
# ---------------------------------------------------------------------------

def analyze_pca(points: np.ndarray, center: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    p = points - center
    if len(p) < 10:
        return np.eye(3), np.ones(3)
    cov = np.cov(p.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    return evecs[:, order], evals[order]


def analyze_obb(pcd: o3d.geometry.PointCloud) -> Tuple[np.ndarray, np.ndarray]:
    obb = pcd.get_oriented_bounding_box()
    R = np.asarray(obb.R, dtype=np.float64)
    extents = np.asarray(obb.extent, dtype=np.float64)
    return R, extents


def detect_planes(
    pcd: o3d.geometry.PointCloud, dist_thresh: float, max_planes: int, min_points: int,
) -> List[Tuple[np.ndarray, np.ndarray, int]]:
    work = pcd
    if len(work.points) > 200_000:
        work = work.voxel_down_sample(voxel_size=dist_thresh * 0.5)
    remaining = work
    planes: List[Tuple[np.ndarray, np.ndarray, int]] = []
    for _ in range(max_planes):
        if len(remaining.points) < min_points:
            break
        model, inliers = remaining.segment_plane(
            distance_threshold=dist_thresh, ransac_n=3, num_iterations=2000,
        )
        if len(inliers) < min_points:
            break
        a, b, c, d = model
        normal = unit_vec(np.array([a, b, c], dtype=np.float64))
        pts = np.asarray(remaining.points)[inliers]
        centroid = pts.mean(axis=0)
        planes.append((normal, centroid, len(inliers)))
        remaining = remaining.select_by_index(inliers, invert=True)
    planes.sort(key=lambda x: x[2], reverse=True)
    return planes


def _kmeans_fallback(points: np.ndarray, k: int, iters: int = 15) -> List[np.ndarray]:
    rng = np.random.default_rng(1)
    seeds = points[rng.choice(len(points), min(k, len(points)), replace=False)]
    for _ in range(iters):
        dists = np.linalg.norm(points[:, None, :] - seeds[None, :, :], axis=2)
        labels = np.argmin(dists, axis=1)
        new_seeds = []
        for i in range(len(seeds)):
            grp = points[labels == i]
            new_seeds.append(grp.mean(axis=0) if len(grp) else seeds[i])
        seeds = np.array(new_seeds)
    return [seeds[i] for i in range(len(seeds))]


def detect_clusters(
    pcd: o3d.geometry.PointCloud, eps: float, min_points: int,
) -> List[np.ndarray]:
    work = pcd
    if len(work.points) > 300_000:
        work = work.voxel_down_sample(voxel_size=eps * 0.4)
    labels = np.array(work.cluster_dbscan(eps=eps, min_points=min_points, print_progress=False))
    if labels.size == 0 or labels.max() < 0:
        pts = np.asarray(work.points)
        if len(pts) < min_points * 2:
            return []
        k = min(4, max(2, len(pts) // 5000))
        sample = pts
        if len(sample) > 50_000:
            sample = sample[np.random.default_rng(1).choice(len(sample), 50_000, replace=False)]
        centroids = _kmeans_fallback(sample, k)
        centroids.sort(key=lambda c: np.linalg.norm(c - pts.mean(axis=0)), reverse=True)
        return centroids[:6]
    points = np.asarray(work.points)
    centroids: List[np.ndarray] = []
    for lid in range(labels.max() + 1):
        mask = labels == lid
        if mask.sum() < min_points:
            continue
        centroids.append(points[mask].mean(axis=0))
    centroids.sort(key=lambda c: np.linalg.norm(c - points.mean(axis=0)), reverse=True)
    return centroids[:6]


def detect_key_points(points: np.ndarray, center: np.ndarray, count: int) -> List[np.ndarray]:
    """最远点采样 + 包围盒角点，提取结构关键点。"""
    if len(points) < count:
        return [points[i] for i in range(len(points))]

    work = points
    if len(work) > 80_000:
        idx = np.random.default_rng(42).choice(len(work), 80_000, replace=False)
        work = work[idx]

    fps_indices = [0]
    dists = np.linalg.norm(work - work[0], axis=1)
    for _ in range(min(count - 1, len(work) - 1)):
        i = int(np.argmax(dists))
        fps_indices.append(i)
        dists = np.minimum(dists, np.linalg.norm(work - work[i], axis=1))

    key_pts = [work[i] for i in fps_indices]

    bb_min = points.min(axis=0)
    bb_max = points.max(axis=0)
    for sx in (0.0, 1.0):
        for sy in (0.0, 1.0):
            for sz in (0.0, 1.0):
                key_pts.append(np.array([bb_min[0] if sx < 0.5 else bb_max[0],
                                         bb_min[1] if sy < 0.5 else bb_max[1],
                                         bb_min[2] if sz < 0.5 else bb_max[2]]))

    unique: List[np.ndarray] = []
    for kp in key_pts:
        if all(np.linalg.norm(kp - u) > 1e-3 for u in unique):
            unique.append(kp)
    unique.sort(key=lambda p: np.linalg.norm(p - center), reverse=True)
    return unique[:count + 4]


def analyze_cloud_structure(
    pcd: o3d.geometry.PointCloud, points: np.ndarray,
) -> CloudStructure:
    center = points.mean(axis=0)
    units_mm = detect_units_mm(points)
    scale = float(np.max(points.max(axis=0) - points.min(axis=0)))
    pca_axes, pca_evals = analyze_pca(points, center)
    obb_axes, obb_extents = analyze_obb(pcd)

    dist = PLANE_RANSAC_DIST if units_mm else PLANE_RANSAC_DIST / 1000.0
    eps = CLUSTER_EPS if units_mm else CLUSTER_EPS / 1000.0
    planes = detect_planes(pcd, dist, PLANE_RANSAC_MAX, PLANE_MIN_POINTS) if AUTO_PLANE_VIEWS else []
    clusters = detect_clusters(pcd, eps, CLUSTER_MIN_POINTS) if AUTO_CLUSTER_VIEWS else []
    key_points = detect_key_points(points, center, KEYPOINT_COUNT) if AUTO_KEYPOINT_VIEWS else []

    return CloudStructure(
        center=center,
        units_mm=units_mm,
        scale=scale,
        obb_axes=obb_axes,
        obb_extents=obb_extents,
        pca_axes=pca_axes,
        pca_evals=pca_evals,
        planes=planes,
        cluster_centroids=clusters,
        key_points=key_points,
    )


def print_structure_summary(struct: CloudStructure) -> None:
    print(f"  OBB 尺寸 (L≥M≥S): {np.sort(struct.obb_extents)[::-1].round(2).tolist()}")
    print(f"  PCA 特征值比: {(struct.pca_evals / max(struct.pca_evals[0], 1e-12)).round(3).tolist()}")
    print(f"  检测到平面: {len(struct.planes)}")
    for i, (n, c, cnt) in enumerate(struct.planes):
        print(f"    plane_{i}: 法向={np.round(n, 3).tolist()}  内点={cnt:,}")
    print(f"  聚类中心: {len(struct.cluster_centroids)}")
    print(f"  关键点: {len(struct.key_points)}")


# ---------------------------------------------------------------------------
# 位姿候选生成
# ---------------------------------------------------------------------------

def _pose_from_dir(name: str, direction: np.ndarray, source: str) -> ViewPose:
    return ViewPose(name=name, view_dir=tuple(unit_vec(direction).tolist()), source=source)


def axis_view_candidates() -> List[ViewPose]:
    axes = [
        ("axis_x_pos", (1, 0, 0)), ("axis_x_neg", (-1, 0, 0)),
        ("axis_y_pos", (0, 1, 0)), ("axis_y_neg", (0, -1, 0)),
        ("axis_z_pos", (0, 0, 1)), ("axis_z_neg", (0, 0, -1)),
    ]
    return [_pose_from_dir(n, np.array(d), "world_axis") for n, d in axes]


def pca_view_candidates(struct: CloudStructure) -> List[ViewPose]:
    poses: List[ViewPose] = []
    e0 = max(float(struct.pca_evals[0]), 1e-12)
    labels = ["pca_major", "pca_mid", "pca_minor"]
    for i in range(3):
        if float(struct.pca_evals[i]) / e0 < PCA_EIGEN_RATIO_MIN:
            continue
        axis = struct.pca_axes[:, i]
        for sign, suffix in ((1.0, "pos"), (-1.0, "neg")):
            poses.append(_pose_from_dir(f"{labels[i]}_{suffix}", axis * sign, "pca"))
    return poses


def obb_view_candidates(struct: CloudStructure) -> List[ViewPose]:
    poses: List[ViewPose] = []
    order = np.argsort(struct.obb_extents)[::-1]
    labels = ["obb_long", "obb_mid", "obb_short"]
    for rank, i in enumerate(order):
        axis = struct.obb_axes[:, i]
        for sign, suffix in ((1.0, "pos"), (-1.0, "neg")):
            poses.append(_pose_from_dir(f"{labels[rank]}_{suffix}", axis * sign, "obb"))
    return poses


def plane_view_candidates(struct: CloudStructure) -> List[ViewPose]:
    poses: List[ViewPose] = []
    for i, (normal, _centroid, _cnt) in enumerate(struct.planes):
        for sign, suffix in ((1.0, "pos"), (-1.0, "neg")):
            poses.append(_pose_from_dir(f"plane_{i}_{suffix}", normal * sign, "plane"))
    return poses


def cluster_view_candidates(struct: CloudStructure) -> List[ViewPose]:
    poses: List[ViewPose] = []
    for i, centroid in enumerate(struct.cluster_centroids):
        direction = centroid - struct.center
        if np.linalg.norm(direction) < 1e-6:
            continue
        poses.append(_pose_from_dir(f"cluster_{i}_toward", direction, "cluster"))
        poses.append(_pose_from_dir(f"cluster_{i}_away", -direction, "cluster"))
    return poses


def keypoint_view_candidates(struct: CloudStructure) -> List[ViewPose]:
    poses: List[ViewPose] = []
    for i, kp in enumerate(struct.key_points):
        direction = kp - struct.center
        if np.linalg.norm(direction) < 1e-6:
            continue
        poses.append(_pose_from_dir(f"key_{i:02d}_toward", direction, "keypoint"))
    return poses


def tilt_view_candidates(struct: CloudStructure) -> List[ViewPose]:
    """在主轴之间插值，覆盖棱边/角落视角。"""
    axes = [struct.obb_axes[:, i] for i in np.argsort(struct.obb_extents)[::-1]]
    if len(axes) < 2:
        return []
    pairs = [(0, 1), (0, 2), (1, 2)]
    poses: List[ViewPose] = []
    for ai, bi in pairs:
        a, b = unit_vec(axes[ai]), unit_vec(axes[bi])
        for deg in TILT_ANGLES_DEG:
            t = np.deg2rad(deg)
            for s1, s2 in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                v = unit_vec(np.cos(t) * a + np.sin(t) * b * s2)
                if s1 < 0:
                    v = -v
                name = f"tilt_{ai}{bi}_{int(deg)}_{'p' if s1 > 0 else 'n'}{'p' if s2 > 0 else 'n'}"
                poses.append(_pose_from_dir(name, v, "tilt"))
    return poses


def sphere_fill_candidates(count: int) -> List[ViewPose]:
    """斐波那契球面均匀采样，填补结构未覆盖的方向。"""
    poses: List[ViewPose] = []
    golden = np.pi * (3.0 - np.sqrt(5.0))
    for i in range(count):
        y = 1.0 - (2.0 * i + 1.0) / count
        r = np.sqrt(max(1.0 - y * y, 0.0))
        theta = golden * i
        x, z = np.cos(theta) * r, np.sin(theta) * r
        poses.append(_pose_from_dir(f"sphere_{i:02d}", np.array([x, y, z]), "sphere"))
    return poses


def dedupe_poses(poses: List[ViewPose]) -> List[ViewPose]:
    """同半球内去重；+d 与 -d 视为不同视角。"""
    kept: List[ViewPose] = []
    dirs: List[np.ndarray] = []
    for p in poses:
        d = p.direction()
        duplicate = False
        for kd in dirs:
            dot = float(np.dot(d, kd))
            if dot >= VIEW_DEDUP_COS:
                duplicate = True
                break
        if not duplicate:
            kept.append(p)
            dirs.append(d)
    return kept


def select_diverse_poses(
    scored: List[ViewPose], max_views: int, min_angle_deg: float,
) -> List[ViewPose]:
    if len(scored) <= max_views:
        return scored
    min_cos = np.cos(np.deg2rad(min_angle_deg))
    selected: List[ViewPose] = [scored[0]]
    sel_dirs = [scored[0].direction()]
    for pose in scored[1:]:
        if len(selected) >= max_views:
            break
        d = pose.direction()
        if all(float(np.dot(d, sd)) < min_cos and float(np.dot(d, -sd)) < min_cos for sd in sel_dirs):
            selected.append(pose)
            sel_dirs.append(d)
    return selected


def discover_view_poses(
    points: np.ndarray, struct: CloudStructure,
) -> List[ViewPose]:
    candidates: List[ViewPose] = []

    if AUTO_AXIS_VIEWS:
        candidates.extend(axis_view_candidates())
    if AUTO_PCA_VIEWS:
        candidates.extend(pca_view_candidates(struct))
    if AUTO_OBB_VIEWS:
        candidates.extend(obb_view_candidates(struct))
    if AUTO_PLANE_VIEWS:
        candidates.extend(plane_view_candidates(struct))
    if AUTO_CLUSTER_VIEWS:
        candidates.extend(cluster_view_candidates(struct))
    if AUTO_KEYPOINT_VIEWS:
        candidates.extend(keypoint_view_candidates(struct))
    if AUTO_TILT_VIEWS:
        candidates.extend(tilt_view_candidates(struct))
    if AUTO_SPHERE_FILL:
        candidates.extend(sphere_fill_candidates(SPHERE_FILL_COUNT))
    for name, d in CUSTOM_VIEWS:
        candidates.append(ViewPose(name, d, source="custom"))

    print(f"  候选位姿（去重前）: {len(candidates)}")
    candidates = dedupe_poses(candidates)
    print(f"  去重后: {len(candidates)}")

    min_span = MIN_DEPTH_SPAN_MM if struct.units_mm else MIN_DEPTH_SPAN_MM / 1000.0
    evaluated: List[ViewPose] = []

    for pose in candidates:
        ratio, span, hull_fill = quick_evaluate_view(points, struct.center, pose.direction())
        if ratio < MIN_VALID_RATIO or span < min_span:
            print(f"  [SKIP] {pose.name:22s} ({pose.source:8s})  覆盖={ratio*100:5.1f}%  跨度={span:.3f}")
            continue
        pose.score = view_quality_score(ratio, span, hull_fill, struct.scale)
        evaluated.append(pose)
        print(f"  [OK]   {pose.name:22s} ({pose.source:8s})  覆盖={ratio*100:5.1f}%  跨度={span:.3f}  得分={pose.score:.3f}")

    evaluated.sort(key=lambda p: p.score, reverse=True)
    selected = select_diverse_poses(evaluated, MAX_VIEWS, MIN_VIEW_ANGLE_DEG)
    selected.sort(key=lambda p: p.name)
    print(f"\n  最终选取 {len(selected)} / {len(evaluated)} 个有效视角（上限 {MAX_VIEWS}）")
    return selected


def save_group(
    group_idx: int,
    depth: np.ndarray,
    gray: np.ndarray,
    meta: ProjectionMeta,
    out_root: str,
) -> str:
    folder = os.path.join(out_root, f"group_{group_idx:02d}_{meta.view_name}")
    os.makedirs(folder, exist_ok=True)

    depth_path = os.path.join(folder, "depth.tiff")
    gray_path = os.path.join(folder, "gray.tiff")
    Image.fromarray(depth_to_16bit(depth)).save(depth_path)
    Image.fromarray(gray, mode="L").save(gray_path)

    if SAVE_DEPTH_VIS:
        Image.fromarray(depth_to_preview_8bit(depth), mode="L").save(
            os.path.join(folder, "depth_vis.png")
        )
    if SAVE_MASK:
        valid = np.isfinite(depth)
        mask = np.zeros(depth.shape, dtype=np.uint8)
        mask[valid] = 255
        Image.fromarray(mask, mode="L").save(os.path.join(folder, "mask.png"))

    meta_path = os.path.join(folder, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, indent=2, ensure_ascii=False)

    return folder


def main() -> None:
    if not os.path.isfile(INPUT_PATH):
        raise SystemExit(f"点云文件不存在: {INPUT_PATH}\n请修改脚本顶部 INPUT_PATH 为实际 .ply 路径。")

    print(f"读取点云: {INPUT_PATH}")
    pcd = o3d.io.read_point_cloud(INPUT_PATH)
    points = np.asarray(pcd.points, dtype=np.float64)
    colors = np.asarray(pcd.colors) if pcd.has_colors() else None
    print(f"点数: {len(points):,}")
    if len(points) == 0:
        raise SystemExit("点云为空")

    print("\n分析点云结构...")
    struct = analyze_cloud_structure(pcd, points)
    print_structure_summary(struct)

    print("\n自动发现有效位姿...")
    poses = discover_view_poses(points, struct)
    if not poses:
        raise SystemExit(
            "未发现有效位姿。可调低 MIN_VALID_RATIO / MIN_DEPTH_SPAN_MM，或在 CUSTOM_VIEWS 中手动指定。"
        )

    print(f"\n共 {len(poses)} 组位姿，开始生成（每组 depth.tiff + gray.tiff）...\n")
    os.makedirs(OUT_DIR, exist_ok=True)

    manifest: Dict = {
        "input": INPUT_PATH,
        "units_mm": struct.units_mm,
        "structure": {
            "obb_extents": struct.obb_extents.tolist(),
            "pca_evals": struct.pca_evals.tolist(),
            "plane_count": len(struct.planes),
            "cluster_count": len(struct.cluster_centroids),
            "keypoint_count": len(struct.key_points),
        },
        "group_count": len(poses),
        "groups": [],
    }

    for i, pose in enumerate(poses, start=1):
        print(f"[{i}/{len(poses)}] {pose.name} ({pose.source})  score={pose.score:.3f}")
        print(f"       dir={np.round(pose.direction(), 3).tolist()}")
        depth, gray, meta = render_view(points, colors, struct.center, pose, struct.units_mm)
        folder = save_group(i, depth, gray, meta, OUT_DIR)
        manifest["groups"].append({
            "index": i,
            "folder": folder,
            "view_name": meta.view_name,
            "view_source": meta.view_source,
            "view_score": meta.view_score,
            "view_dir": meta.view_dir,
            "resolution": [meta.width, meta.height],
            "valid_ratio": meta.valid_ratio,
            "depth_span": meta.depth_span,
            "depth_tiff": os.path.join(folder, "depth.tiff"),
            "gray_tiff": os.path.join(folder, "gray.tiff"),
        })
        print(f"       → {folder}")

    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n完成: {len(poses)} 组 × 2 张 = {len(poses)*2} 张主图")
    print(f"输出目录: {OUT_DIR}")
    print(f"清单文件: {manifest_path}")


if __name__ == "__main__":
    main()
