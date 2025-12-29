# -*- coding: utf-8 -*-
"""
清理辅助函数：用于在算例完成后删除工作目录
"""
import os
import shutil

# 配置选项（从主脚本导入或定义）
try:
    from Abaqus_FullAnalysis_v3_MultiCase import KEEP_WORK_FILES
except:
    KEEP_WORK_FILES = False  # 默认不保留

def cleanup_case_work_dir(case_work_dir, case_results_dir, min_png_count=1, keep_work_files=None):
    """
    清理算例工作目录（仅在结果验证成功时）
    
    参数:
        case_work_dir: 工作目录路径（将被删除）
        case_results_dir: 结果目录路径（用于验证）
        min_png_count: 最少PNG文件数量（默认1）
    
    返回:
        bool: 是否成功清理
    """
    if keep_work_files is None:
        keep_work_files = KEEP_WORK_FILES
    
    if keep_work_files:
        print("[cleanup] KEEP_WORK_FILES=True, skipping cleanup of %s" % case_work_dir)
        return False
    
    # 验证结果文件是否存在
    buckle_csv = os.path.join(case_results_dir, 'buckling_eigen.csv')
    riks_csv = os.path.join(case_results_dir, 'riks_curve.csv')
    
    csv_ok = os.path.exists(buckle_csv) and os.path.exists(riks_csv)
    
    # 检查PNG文件
    png_count = 0
    if os.path.exists(case_results_dir):
        png_files = [f for f in os.listdir(case_results_dir) if f.endswith('.png')]
        png_count = len(png_files)
    
    if not csv_ok:
        print("[cleanup] WARNING: CSV files missing, NOT cleaning up work dir")
        print("[cleanup]   buckle_csv exists: %s" % os.path.exists(buckle_csv))
        print("[cleanup]   riks_csv exists: %s" % os.path.exists(riks_csv))
        return False
    
    if png_count < min_png_count:
        print("[cleanup] WARNING: PNG count (%d) < minimum (%d), NOT cleaning up work dir" % 
              (png_count, min_png_count))
        return False
    
    # 验证通过，删除工作目录
    if os.path.exists(case_work_dir):
        try:
            print("[cleanup] Removing work directory: %s" % case_work_dir)
            shutil.rmtree(case_work_dir)
            print("[cleanup] Successfully removed work directory")
            return True
        except Exception as e:
            print("[cleanup] ERROR: Failed to remove work directory: %s" % str(e))
            return False
    else:
        print("[cleanup] Work directory does not exist: %s" % case_work_dir)
        return False

