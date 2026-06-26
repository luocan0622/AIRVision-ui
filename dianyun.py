import open3d as o3d

# ============================================================
# 点云轻量化脚本 —— 减少点数以便 AIRVision 可视化
# 思路：体素下采样(均匀抽稀) + 可选均匀下采样(每N点取1)
# voxel_size 越大 → 点越少；every_k_points 越大 → 点越少
# ============================================================

# --- 配置 ---
INPUT_PATH = r"C:\saferword\ceshi-data\0512biaoding\1\1.ply"
OUTPUT_PATH = r"C:\saferword\ceshi-data\0512biaoding\1\1_small.ply"

# 体素尺寸（单位与点云一致，数值越大点越少，常用 1.0 ~ 20.0）
VOXEL_SIZE = 5.0

# 均匀下采样：每 N 个点保留 1 个（0 表示跳过此步）
EVERY_K_POINTS = 0

# --- 主流程 ---
print(f"读取点云: {INPUT_PATH}")
pcd = o3d.io.read_point_cloud(INPUT_PATH)
orig_count = len(pcd.points)
print(f"原始点数: {orig_count:,}")

# 步骤1：体素下采样
if VOXEL_SIZE > 0:
    pcd = pcd.voxel_down_sample(voxel_size=VOXEL_SIZE)
    after_voxel = len(pcd.points)
    print(f"体素下采样 (voxel={VOXEL_SIZE}): {orig_count:,} → {after_voxel:,} "
          f"(保留 {after_voxel/orig_count*100:.1f}%)")

# 步骤2：均匀下采样
if EVERY_K_POINTS > 1:
    before_uniform = len(pcd.points)
    pcd = pcd.uniform_down_sample(every_k_points=EVERY_K_POINTS)
    after_uniform = len(pcd.points)
    print(f"均匀下采样 (每{EVERY_K_POINTS}取1): {before_uniform:,} → {after_uniform:,} "
          f"(保留 {after_uniform/before_uniform*100:.1f}%)")

# --- 保存 & 汇总 ---
final_count = len(pcd.points)
o3d.io.write_point_cloud(OUTPUT_PATH, pcd)
print(f"\n保存: {OUTPUT_PATH}")
print(f"最终点数: {final_count:,}  (原始 {orig_count:,} → 缩小至 {final_count/orig_count*100:.1f}%)")