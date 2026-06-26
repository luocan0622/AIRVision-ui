"""
点云 → 多视角深度图 / 灰度图 批量生成

功能：
  - 自动根据点云几何发现有效投影位姿（6 主轴 + PCA 主方向，去重、过滤空视角）
  - 每个位姿一组：depth.tiff（16-bit 真实深度）+ gray.tiff（仿真强度，≠ 深度）
  - 可选 depth_vis.png / mask.png

位姿定义：观察方向 view_dir（相机位于 +view_dir 侧看向点云），正交投影 + Z-buffer。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

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

INPUT_PATH = r"C:\saferword\ceshi-data\motorcycle-crankcase-ply\Motorcycle Crankcase.ply"
OUT_DIR = r"C:\saferword\ceshi-data\motorcycle-crankcase-ply\multi_view"

TARGET_WIDTH = 3200
PIXEL_SIZE_MM: Optional[float] = None
SPLAT_RADIUS = 2

# 自动位姿发现
AUTO_AXIS_VIEWS = True          # ±X ±Y ±Z 共 6 个候选
AUTO_PCA_VIEWS = True           # PCA 三主轴 ± 方向
PCA_EIGEN_RATIO_MIN = 0.08      # 主轴相对最大特征值比例，低于则跳过
MIN_VALID_RATIO = 0.03          # 有效像素占比下限（相对投影画布）
MIN_DEPTH_SPAN_MM = 0.5         # 该视角下深度跨度下限（mm 点云）
VIEW_DEDUP_COS = 0.985          # 方向余弦 > 此阈值视为重复视角

# 也可手动追加位姿：[(名称, (dx,dy,dz)), ...]，方向不必单位化
CUSTOM_VIEWS: List[Tuple[str, Tuple[float, float, float]]] = []

SAVE_DEPTH_VIS = True
SAVE_MASK = True

INPAINT_RADIUS = 3
INPAINT_GAPS = True
PERCENTILE_LOW = 0.5
PERCENTILE_HIGH = 99.5
USE_CLAHE = True
CLAHE_CLIP = 2.5
CLAHE_TILE = 8

LIGHT_DIR_CAM = (0.15, 0.25, 0.95)  # 相机坐标系下光照
WEIGHT_SHADING = 0.50
WEIGHT_HIGHPASS = 0.35
WEIGHT_EDGE = 0.15


@dataclass
class ViewPose:
    name: str
    view_dir: Tuple[float, float, float]  # 观察方向（单位向量）

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


def detect_units_mm(points: np.ndarray) -> bool:
    return float(np.max(points.max(axis=0) - points.min(axis=0))) > 20.0


def make_view_basis(view_dir: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = view_dir / max(np.linalg.norm(view_dir), 1e-12)
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
    )
    return depth, gray, meta


def quick_evaluate_view(
    points: np.ndarray, center: np.ndarray, view_dir: np.ndarray,
) -> Tuple[float, float]:
    """快速估计有效覆盖率与深度跨度（用于筛选位姿）。"""
    u, v, d = project_coords(points, center, view_dir)
    ok = np.isfinite(u) & np.isfinite(v) & np.isfinite(d)
    if not ok.any():
        return 0.0, 0.0
    u, v, d = u[ok], v[ok], d[ok]
    u_min, u_max = float(u.min()), float(u.max())
    v_min, v_max = float(v.min()), float(v.max())
    w, h, _, _ = compute_image_size(u_min, u_max, v_min, v_max, TARGET_WIDTH, PIXEL_SIZE_MM)
    col, row = world_to_pixel(u, v, u_min, u_max, v_min, v_max, w, h)
    in_bounds = (col >= 0) & (col < w) & (row >= 0) & (row < h)
    col, row, d = col[in_bounds], row[in_bounds], d[in_bounds]
    if d.size == 0:
        return 0.0, 0.0
    buf = build_depth_buffer(col, row, d, w, h, max(SPLAT_RADIUS - 1, 0))
    valid = np.isfinite(buf)
    ratio = float(valid.mean())
    if not valid.any():
        return ratio, 0.0
    dv = buf[valid]
    span = float(dv.max() - dv.min())
    return ratio, span


def axis_view_candidates() -> List[ViewPose]:
    names_dirs = [
        ("axis_x_pos", (1.0, 0.0, 0.0)),
        ("axis_x_neg", (-1.0, 0.0, 0.0)),
        ("axis_y_pos", (0.0, 1.0, 0.0)),
        ("axis_y_neg", (0.0, -1.0, 0.0)),
        ("axis_z_pos", (0.0, 0.0, 1.0)),
        ("axis_z_neg", (0.0, 0.0, -1.0)),
    ]
    return [ViewPose(n, d) for n, d in names_dirs]


def pca_view_candidates(points: np.ndarray, center: np.ndarray) -> List[ViewPose]:
    p = points - center
    if len(p) < 10:
        return []
    cov = np.cov(p.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals = evals[order]
    evecs = evecs[:, order]
    poses: List[ViewPose] = []
    e0 = max(float(evals[0]), 1e-12)
    labels = ["pca_major", "pca_mid", "pca_minor"]
    for i in range(3):
        if float(evals[i]) / e0 < PCA_EIGEN_RATIO_MIN:
            continue
        axis = evecs[:, i]
        for sign, suffix in ((1.0, "pos"), (-1.0, "neg")):
            d = axis * sign
            name = f"{labels[i]}_{suffix}"
            poses.append(ViewPose(name, tuple(d.tolist())))
    return poses


def dedupe_poses(poses: List[ViewPose]) -> List[ViewPose]:
    kept: List[ViewPose] = []
    dirs: List[np.ndarray] = []
    for p in poses:
        d = p.direction()
        duplicate = False
        for kd in dirs:
            if abs(float(np.dot(d, kd))) >= VIEW_DEDUP_COS:
                duplicate = True
                break
        if not duplicate:
            kept.append(p)
            dirs.append(d)
    return kept


def discover_view_poses(points: np.ndarray, center: np.ndarray, units_mm: bool) -> List[ViewPose]:
    candidates: List[ViewPose] = []

    if AUTO_AXIS_VIEWS:
        candidates.extend(axis_view_candidates())
    if AUTO_PCA_VIEWS:
        candidates.extend(pca_view_candidates(points, center))
    for name, d in CUSTOM_VIEWS:
        candidates.append(ViewPose(name, d))

    candidates = dedupe_poses(candidates)
    min_span = MIN_DEPTH_SPAN_MM if units_mm else MIN_DEPTH_SPAN_MM / 1000.0

    selected: List[ViewPose] = []
    for pose in candidates:
        ratio, span = quick_evaluate_view(points, center, pose.direction())
        if ratio >= MIN_VALID_RATIO and span >= min_span:
            selected.append(pose)
            print(f"  [OK] {pose.name:16s}  覆盖={ratio*100:5.1f}%  深度跨度={span:.3f}")
        else:
            print(f"  [SKIP] {pose.name:16s}  覆盖={ratio*100:5.1f}%  深度跨度={span:.3f}")

    selected.sort(key=lambda p: p.name)
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
    print(f"读取点云: {INPUT_PATH}")
    pcd = o3d.io.read_point_cloud(INPUT_PATH)
    points = np.asarray(pcd.points, dtype=np.float64)
    colors = np.asarray(pcd.colors) if pcd.has_colors() else None
    print(f"点数: {len(points):,}")
    if len(points) == 0:
        raise SystemExit("点云为空")

    center = points.mean(axis=0)
    units_mm = detect_units_mm(points)
    print(f"坐标单位: {'毫米' if units_mm else '米'}  包围盒中心: {center}")

    print("\n自动发现有效位姿...")
    poses = discover_view_poses(points, center, units_mm)
    if not poses:
        raise SystemExit(
            "未发现有效位姿。可调低 MIN_VALID_RATIO / MIN_DEPTH_SPAN_MM，或在 CUSTOM_VIEWS 中手动指定。"
        )

    print(f"\n共 {len(poses)} 组位姿，开始生成（每组 depth.tiff + gray.tiff）...\n")
    os.makedirs(OUT_DIR, exist_ok=True)

    manifest = {
        "input": INPUT_PATH,
        "units_mm": units_mm,
        "group_count": len(poses),
        "groups": [],
    }

    for i, pose in enumerate(poses, start=1):
        print(f"[{i}/{len(poses)}] {pose.name}  dir={np.round(pose.direction(), 3).tolist()}")
        depth, gray, meta = render_view(points, colors, center, pose, units_mm)
        folder = save_group(i, depth, gray, meta, OUT_DIR)
        manifest["groups"].append({
            "index": i,
            "folder": folder,
            "view_name": meta.view_name,
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
