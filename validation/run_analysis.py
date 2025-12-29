# -*- coding: utf-8 -*-
"""
================================================================================
Auto-PHSSCW: Validation Analysis Script
================================================================================

Automated FE analysis for built-up H-section steel members under shear loading.
Validated against Scandella et al. (2020) experimental results.

Features:
  - Eigenvalue buckling analysis with geometric imperfection
  - Nonlinear Riks (arc-length) analysis for post-buckling behavior
  - Multi-load-case support: LC1_Axial, LC2-LC3_Combined, LC4-LC5_Shear
  - Automated result extraction and visualization

Usage:
  # Quick-start (single specimen G1, ~10 min):
  abaqus cae noGUI=run_analysis.py -- parameters_quickstart_G1.csv
  
  # Full validation (G1-G4, ~40 min):
  abaqus cae noGUI=run_analysis.py -- parameters_full_validation.csv

Output:
  results/{model_name}/{case_name}/
    - riks_curve.csv      : Load-displacement history
    - buckling_eigen.csv  : Eigenvalue results
    - *.png               : Contour plots

Requirements: Abaqus 2020+, mm-N-MPa unit system

Author: Li Jian (Inner Mongolia University of Technology)
License: Apache 2.0
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
executeOnCaeStartup()

import os
import csv
import re
import time
import subprocess
import platform

import regionToolset
from odbAccess import openOdb


# =============================================================================
# 目录设置
# =============================================================================
try:
    import inspect
    script_path = inspect.getfile(inspect.currentframe())
    WORK_DIR = os.path.dirname(os.path.abspath(script_path))  # 指向shearcode目录
except:
    WORK_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()

if not WORK_DIR or not os.path.exists(WORK_DIR):
    WORK_DIR = os.getcwd()

os.chdir(WORK_DIR)

# 重构后的目录结构（临时工作区 + 永久结果区）
WORK_ROOT = os.path.join(WORK_DIR, 'work')      # 临时计算区，跑完就删（ODB/INP/DAT/MSG等）
RESULTS_ROOT = os.path.join(WORK_DIR, 'results') # 最终保留（CSV + PNG）
LOGS_DIR = os.path.join(WORK_DIR, 'logs')        # 日志（可选保留）

# 向后兼容（保留旧变量名，指向新目录）
TEMP_DIR = WORK_ROOT  # work目录作为临时工作区
OUTPUT_DIR = RESULTS_ROOT  # results目录作为输出
CASE_WORK_DIR = WORK_ROOT  # 使用WORK_ROOT作为case工作目录

# 配置选项
KEEP_WORK_FILES = True  # 保留工作文件（ODB/INP/DAT/MSG等）用于检查
SAVE_CAE = False  # 不保存CAE文件

# 创建必要的目录
def _ensure_dir(path):
    """确保目录存在"""
    if path and not os.path.exists(path):
        os.makedirs(path)

for d in (WORK_ROOT, RESULTS_ROOT, LOGS_DIR):
    _ensure_dir(d)
    if os.path.exists(d):
        print("[init] Directory ready: %s" % d)

# 图像导出：使用科研版（peakLPF帧 + legend + U1位移）
# 注意：已简化为仅使用科研版，不再支持基础版切换

# Parameter file configuration
# Default: full validation (G1-G4 specimens)
# Can be overridden via command line: abaqus cae noGUI=run_analysis.py -- your_params.csv
PARAM_FILE = os.path.join(WORK_DIR, 'parameters_full_validation.csv')


# =============================================================================
# 坐标系统定义 (全局统一)
# =============================================================================
"""
全局坐标系 (右手系):
    Y ↑ (截面高度, 拼接方向)
    |
    +--→ X (截面宽度, 翼缘方向)
   /
  ↙ Z (构件轴向, 挤出方向)

几何:
- 腹板: x=0 平面
- 翼缘: x=±bFlange/2
- 总高度: H_total = nSeg * hSeg
- 构件长度: Lmember (Z方向)

荷载方向:
- cf1/U1: X方向 (面外剪切)
- cf2/U2: Y方向 (面内剪切, 拼接向)
- cf3/U3: Z方向 (轴压)
"""


# =============================================================================
# 参数定义
# =============================================================================
DEFAULT_PARAMS = {
    # geometry
    'hSeg': 300.0,           # 单段高度 (旧A)
    'nSeg': 2,               # 段数 (旧E)
    'bFlange': 20.0,         # 翼缘宽度 (旧B)
    'tWeb': 15.0,            # 腹板厚度 (旧C)
    'tFlangeSingle': 5.0,    # 单侧翼缘厚度 (旧D)
    'Lmember': 3000.0,       # 构件长度 (旧L)
    'autoPlate': 1,          # 自动退化为平板
    'bfPlateTol': 0.0,
    # mesh
    'meshSize': 20.0,
    # buckling
    'numEigen': 10,
    # material (Web - backward compatibility)
    'fy': 355.61,              # Web yield strength (legacy, maps to fy_web)
    'eps_y_plateau': 0.023,   # Web yield plateau strain
    'fu': 444.0,              # Web ultimate strength (legacy, maps to fu_web)
    'eps_u': 0.1576,          # Web ultimate strain (legacy, maps to eps_u_web)
    # material (Web - new keys)
    'fy_web': None,           # Web yield strength (MPa)
    'fu_web': None,           # Web ultimate strength (MPa)
    'eps_u_web': None,        # Web ultimate strain
    'E_web': None,            # Web Young's modulus (MPa), default 210184
    'eps_y_plateau_web': 0.023,  # Web yield plateau strain
    # material (Flange - new keys)
    'fy_flg': None,           # Flange yield strength (MPa)
    'fu_flg': None,           # Flange ultimate strength (MPa)
    'eps_u_flg': None,        # Flange ultimate strain
    'E_flg': None,            # Flange Young's modulus (MPa), default 211551
    'eps_y_plateau_flg': 0.020,  # Flange yield plateau strain
    # imperfection
    'imperfMode': 1,         # 固定一阶模态
    'imperfAmp': 6.0,
    # BC
    'endFixityTop': 'ROTATION_FIXED',  # 剪切分析：只固定转动，位移自由
    'endFixityBot': 'FIXED',
    # job
    'numCpus': 4,
    # load cases (新增)
    # 'enableCases': 'LC1'  # 冒烟测试只运行LC1
    'enableCases': 'LC4'  # 运行纯剪切工况
}

LEGACY_MAP = {
    'A': 'hSeg', 'E': 'nSeg', 'B': 'bFlange', 'C': 'tWeb', 'D': 'tFlangeSingle', 'L': 'Lmember',
    'meshsz': 'meshSize', 'cf1f': 'FrefX', 'cf2f': 'FrefY', 'cf3f': 'FrefZ',
    'u1u': 'UctrlX', 'u2u': 'UctrlY', 'u3u': 'UctrlZ', 'trueu3': 'maxCtrlDisp',
    'nodedeform': 'imperfAmp', 'numCpus': 'numCpus',
    'yfss': 'fy', 'yfsn': 'eps_y_plateau', 'yuss': 'fu', 'yusn': 'eps_u',
}

def _to_number(x):
    try:
        if isinstance(x, (int, float)):
            return x
        s = str(x).strip()
        if s == '':
            return x
        if re.match(r'^-?\d+\.\d*$', s):
            return float(s)
        if re.match(r'^-?\d+$', s):
            return int(s)
        return x
    except:
        return x

def normalize_params(row_dict):
    p = DEFAULT_PARAMS.copy()
    for k, v in row_dict.items():
        if k in p:
            p[k] = _to_number(v)
        elif k in LEGACY_MAP:
            p[LEGACY_MAP[k]] = _to_number(v)
    
    # Backward compatibility: map old fy/fu/eps_u to Web if new keys not provided
    if p.get('fy_web') is None and p.get('fy') is not None:
        p['fy_web'] = p['fy']
    if p.get('fu_web') is None and p.get('fu') is not None:
        p['fu_web'] = p['fu']
    if p.get('eps_u_web') is None and p.get('eps_u') is not None:
        p['eps_u_web'] = p['eps_u']
    
    # Fallback to G1 experimental values for Flange if not provided
    if p.get('fy_flg') is None:
        p['fy_flg'] = 325.2  # G1 experimental value for 20mm plate
    if p.get('fu_flg') is None:
        p['fu_flg'] = 474.3  # G1 experimental value for 20mm plate
    if p.get('eps_u_flg') is None:
        p['eps_u_flg'] = 0.200  # Default for flange
    
    # Set default Young's modulus if not provided
    if p.get('E_web') is None:
        p['E_web'] = 210184.0  # G1 experimental value
    if p.get('E_flg') is None:
        p['E_flg'] = 211551.0  # G1 experimental value
    
    # 强制类型
    p['nSeg'] = int(p['nSeg'])
    p['numEigen'] = int(p['numEigen'])
    p['imperfMode'] = int(p['imperfMode'])
    p['autoPlate'] = int(p['autoPlate'])
    return p

def read_parameters_from_csv(csv_file):
    if not os.path.exists(csv_file):
        return [DEFAULT_PARAMS.copy()]
    params_list = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            params_list.append(normalize_params(row))
    if not params_list:
        params_list = [DEFAULT_PARAMS.copy()]
    return params_list

def generate_model_name(p):
    H = p['hSeg'] * p['nSeg']
    # 简化模型名称以缩短路径（避免Windows 260字符限制）
    # 使用更短的格式：H{int}_b{int}_t{int}_L{int}
    name = 'H%d_b%d_t%d_L%d' % (int(H), int(p['bFlange']), int(p['tWeb']), int(p['Lmember']))
    return name


# =============================================================================
# 工况定义
# =============================================================================
LOAD_CASES = {
    'LC1_Axial': {
        'name': 'LC1_Axial',
        'description': 'Pure Axial Compression',
        'bucklingRef': (0.0, 0.0, -1.0),  # (FrefX, FrefY, FrefZ)
        'riksControl': {'dof': 3, 'dir': 'Z', 'maxDisp': 30.0, 'sign': -1},  # U3 control
    },
    'LC2_Axial_ShearY': {
        'name': 'LC2_Axial_ShearY',
        'description': 'Axial + Shear-Y (in-plane)',
        'bucklingRef': (0.0, 1.0, -0.5),  # Y shear dominant
        'riksControl': {'dof': 2, 'dir': 'Y', 'maxDisp': 60.0, 'sign': 1},  # U2 control
        'hasAxial': True,
    },
    'LC3_Axial_ShearX': {
        'name': 'LC3_Axial_ShearX',
        'description': 'Axial + Shear-X (out-of-plane)',
        'bucklingRef': (1.0, 0.0, -0.5),  # X shear dominant
        'riksControl': {'dof': 1, 'dir': 'X', 'maxDisp': 60.0, 'sign': 1},  # U1 control
        'hasAxial': True,
    },
    'LC4_ShearY': {
        'name': 'LC4_ShearY',
        'description': 'Pure Shear-Y',
        'bucklingRef': (0.0, 1.0, 0.0),
        'riksControl': {'dof': 2, 'dir': 'Y', 'maxDisp': 60.0, 'sign': 1},
    },
    'LC5_ShearX': {
        'name': 'LC5_ShearX',
        'description': 'Pure Shear-X (out-of-plane)',
        'bucklingRef': (1.0, 0.0, 0.0),
        'riksControl': {'dof': 1, 'dir': 'X', 'maxDisp': 30.0, 'sign': 1},
    },
    'LC6_Axial_ShearXY': {
        'name': 'LC6_Axial_ShearXY',
        'description': 'Axial + Biaxial shear (X+Y)',
        'bucklingRef': (1.0, 1.0, -0.5),
        'riksControl': {'dof': 2, 'dir': 'Y', 'maxDisp': 30.0, 'sign': 1},  # Default control Y
        'hasAxial': True,
    },
    'LC7_AxialOnly_High': {
        'name': 'LC7_AxialOnly_High',
        'description': 'High axial compression (sensitivity)',
        'bucklingRef': (0.0, 0.0, -2.0),
        'riksControl': {'dof': 3, 'dir': 'Z', 'maxDisp': 50.0, 'sign': -1},
    },
}

def get_enabled_cases(params):
    """解析enableCases参数,返回工况列表"""
    # 如果enableCases明确指定，使用它
    if 'enableCases' in params and params['enableCases']:
        enable_str = str(params.get('enableCases', 'LC1,LC2,LC3,LC4'))
        case_keys = [c.strip() for c in enable_str.split(',')]
        cases = []
        for key in case_keys:
            if key in LOAD_CASES:
                cases.append(LOAD_CASES[key])
            elif key.replace('_', '') in LOAD_CASES:
                cases.append(LOAD_CASES[key.replace('_', '')])
        if cases:
            return cases
    
    # 否则根据荷载参数自动判断（用于测试）
    # 检测荷载类型：从旧CSV格式的cf1f, cf2f, cf3f或新格式的荷载参数
    cf1 = params.get('cf1f', 0.0) or params.get('FrefX', 0.0) or 0.0
    cf2 = params.get('cf2f', 0.0) or params.get('FrefY', 0.0) or 0.0
    cf3 = params.get('cf3f', 0.0) or params.get('FrefZ', 0.0) or 0.0
    
    # 根据荷载组合自动选择工况
    if abs(cf3) > 0.1 and abs(cf2) < 0.1 and abs(cf1) < 0.1:
        # 纯轴压
        return [LOAD_CASES['LC1_Axial']]
    elif abs(cf2) > 0.1 and abs(cf3) < 0.1 and abs(cf1) < 0.1:
        # 纯剪切Y
        return [LOAD_CASES['LC4_ShearY']]
    elif abs(cf3) > 0.1 and abs(cf2) > 0.1:
        # 轴压+剪切Y
        return [LOAD_CASES['LC2_Axial_ShearY']]
    elif abs(cf3) > 0.1 and abs(cf1) > 0.1:
        # 轴压+剪切X
        return [LOAD_CASES['LC3_Axial_ShearX']]
    else:
        # 默认轴压
        return [LOAD_CASES['LC1_Axial']]


# =============================================================================
# 几何生成
# =============================================================================
def build_sketch_builtup_I(s, hSeg, nSeg, bFlange, autoPlate, tWeb, bfPlateTol):
    """一次性绘制完整截面骨架"""
    H = hSeg * nSeg
    flange_on = True
    if autoPlate == 1 and bFlange <= (tWeb + bfPlateTol):
        flange_on = False

    # 腹板(连续)
    s.Line(point1=(0.0, 0.0), point2=(0.0, H))

    if flange_on:
        # (nSeg+1)条翼缘线
        for k in range(0, nSeg + 1):
            yk = k * hSeg
            s.Line(point1=(-bFlange/2.0, yk), point2=(bFlange/2.0, yk))
    return flange_on, H

def create_part(model, p):
    hSeg, nSeg, bFlange = p['hSeg'], p['nSeg'], p['bFlange']
    tWeb, tFlangeSingle, Lmember = p['tWeb'], p['tFlangeSingle'], p['Lmember']
    
    s = model.ConstrainedSketch(name='__profile__', sheetSize=max(1000.0, Lmember))
    flange_on, H = build_sketch_builtup_I(
        s, hSeg=hSeg, nSeg=nSeg, bFlange=bFlange,
        autoPlate=p['autoPlate'], tWeb=tWeb, bfPlateTol=p['bfPlateTol']
    )

    part = model.Part(name='Part-1', dimensionality=THREE_D, type=DEFORMABLE_BODY)
    part.BaseShellExtrude(sketch=s, depth=Lmember)
    s.unsetPrimaryObject()
    del model.sketches['__profile__']
    part.regenerate()
    
    geo_info = {
        'H_total': H,
        'flange_on': flange_on,
        'Lmember': Lmember,
        'hSeg': hSeg,
        'nSeg': nSeg,
        'bFlange': bFlange,
    }
    return part, geo_info

def define_material_sections(model, p, elastic_only=False):
    """定义材料和截面 - 支持Web和Flange两种材料"""
    if elastic_only:
        # Elastic analysis: use single elastic material
        model.Material(name='MatElastic')
        E_elastic = p.get('E_web', 210184.0)  # Use Web E as default
        model.materials['MatElastic'].Elastic(table=((E_elastic, 0.3),))
        model.materials['MatElastic'].Density(table=((7.85e-09,),))
        mat_web_name = 'MatElastic'
        mat_flg_name = 'MatElastic'
    else:
        # Plastic analysis: create separate materials for Web and Flange
        # Web Material
        model.Material(name='MatWeb')
        E_web = p.get('E_web', 210184.0)
        fy_web = p.get('fy_web', 270.7)
        fu_web = p.get('fu_web', 352.5)
        eps_u_web = p.get('eps_u_web', 0.234)
        eps_y_plateau_web = p.get('eps_y_plateau_web', 0.023)
        
        model.materials['MatWeb'].Elastic(table=((E_web, 0.3),))
        model.materials['MatWeb'].Plastic(table=(
            (fy_web, 0.0),
            (fy_web, eps_y_plateau_web),
            (fu_web, eps_u_web)
        ))
        model.materials['MatWeb'].Density(table=((7.85e-09,),))
        
        # Flange Material
        model.Material(name='MatFlange')
        E_flg = p.get('E_flg', 211551.0)
        fy_flg = p.get('fy_flg', 325.2)
        fu_flg = p.get('fu_flg', 474.3)
        eps_u_flg = p.get('eps_u_flg', 0.200)
        eps_y_plateau_flg = p.get('eps_y_plateau_flg', 0.020)
        
        model.materials['MatFlange'].Elastic(table=((E_flg, 0.3),))
        model.materials['MatFlange'].Plastic(table=(
            (fy_flg, 0.0),
            (fy_flg, eps_y_plateau_flg),
            (fu_flg, eps_u_flg)
        ))
        model.materials['MatFlange'].Density(table=((7.85e-09,),))
        
        mat_web_name = 'MatWeb'
        mat_flg_name = 'MatFlange'
        
        print("[define_material_sections] Web material: E=%.1f, fy=%.1f, fu=%.1f, eps_u=%.3f" % 
              (E_web, fy_web, fu_web, eps_u_web))
        print("[define_material_sections] Flange material: E=%.1f, fy=%.1f, fu=%.1f, eps_u=%.3f" % 
              (E_flg, fy_flg, fu_flg, eps_u_flg))

    suffix = '_EL' if elastic_only else '_PL'
    # Web section uses MatWeb
    model.HomogeneousShellSection(name='SEC_WEB'+suffix, preIntegrate=OFF, material=mat_web_name,
                                  thicknessType=UNIFORM, thickness=p['tWeb'],
                                  idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,
                                  integrationRule=SIMPSON, numIntPts=5)
    # Flange sections use MatFlange
    model.HomogeneousShellSection(name='SEC_FLG_EDGE'+suffix, preIntegrate=OFF, material=mat_flg_name,
                                  thicknessType=UNIFORM, thickness=p['tFlangeSingle'],
                                  idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,
                                  integrationRule=SIMPSON, numIntPts=5)
    model.HomogeneousShellSection(name='SEC_FLG_INNER'+suffix, preIntegrate=OFF, material=mat_flg_name,
                                  thicknessType=UNIFORM, thickness=2.0*p['tFlangeSingle'],
                                  idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,
                                  integrationRule=SIMPSON, numIntPts=5)

def assign_sections(part, p, geo_info, elastic_only=False):
    """
    Assign sections: FULL COVERAGE first (web), then LOCAL OVERRIDE (flanges).
    Strategy: 1) Assign web section to ALL faces (100% coverage).
              2) Use getByBoundingBox to select flange faces by y-coordinate.
              3) Overwrite flange faces with flange sections.
    """
    H = geo_info['H_total']
    hSeg = geo_info['hSeg']
    nSeg = geo_info['nSeg']
    L = geo_info['Lmember']
    bFlange = geo_info['bFlange']
    meshSize = geo_info.get('meshSize', 30.0)
    
    suffix = '_EL' if elastic_only else '_PL'
    
    # Self-check
    totalFaces = len(part.faces)
    print(("[assign_sections%s] Total faces:" % suffix, totalFaces))
    if totalFaces == 0:
        raise Exception("[assign_sections] No faces found in part!")
    
    # STEP 1: Full coverage with web section (100% guarantee)
    region_all = regionToolset.Region(faces=part.faces[:])
    part.SectionAssignment(
        region=region_all,
        sectionName='SEC_WEB' + suffix,
        offset=0.0,
        offsetType=MIDDLE_SURFACE,
        offsetField='',
        thicknessAssignment=FROM_SECTION
    )
    print("[assign_sections%s] Full coverage: assigned SEC_WEB to all %d faces." % (suffix, totalFaces))
    
    # If flange disabled, stop here
    if not geo_info.get('flange_on', True):
        print("[assign_sections%s] Flange disabled, web-only mode complete." % suffix)
        return
    
    # STEP 2: Select and override flange faces by y-coordinate
    tolY = max(1.0, 0.05*meshSize, 0.02*hSeg)
    print("[assign_sections%s] Flange selection tolerance tolY=%.2f" % (suffix, tolY))
    
    bottomFlangeCount = 0
    topFlangeCount = 0
    midFlangeCount = 0
    
    # Bottom flange (y ~ 0)
    try:
        faces_bottom = part.faces.getByBoundingBox(
            xMin=-bFlange, xMax=bFlange,
            yMin=-tolY, yMax=tolY,
            zMin=-1.0, zMax=L+1.0
        )
        if len(faces_bottom) > 0:
            region_bottom = regionToolset.Region(faces=faces_bottom)
            part.SectionAssignment(
                region=region_bottom,
                sectionName='SEC_FLG_EDGE' + suffix,
                offset=0.0,
                offsetType=MIDDLE_SURFACE,
                offsetField='',
                thicknessAssignment=FROM_SECTION
            )
            bottomFlangeCount = len(faces_bottom)
            print("[assign_sections%s] Bottom flange (y~0): %d faces -> SEC_FLG_EDGE" % (suffix, bottomFlangeCount))
    except Exception as e:
        print("[WARN] Bottom flange selection failed: %s" % str(e))
    
    # Top flange (y ~ H)
    try:
        faces_top = part.faces.getByBoundingBox(
            xMin=-bFlange, xMax=bFlange,
            yMin=H-tolY, yMax=H+tolY,
            zMin=-1.0, zMax=L+1.0
        )
        if len(faces_top) > 0:
            region_top = regionToolset.Region(faces=faces_top)
            part.SectionAssignment(
                region=region_top,
                sectionName='SEC_FLG_EDGE' + suffix,
                offset=0.0,
                offsetType=MIDDLE_SURFACE,
                offsetField='',
                thicknessAssignment=FROM_SECTION
            )
            topFlangeCount = len(faces_top)
            print("[assign_sections%s] Top flange (y~H): %d faces -> SEC_FLG_EDGE" % (suffix, topFlangeCount))
    except Exception as e:
        print("[WARN] Top flange selection failed: %s" % str(e))
    
    # Middle flanges (y ~ k*hSeg, k=1..nSeg-1)
    for k in range(1, nSeg):
        y_mid = k * hSeg
        try:
            faces_mid = part.faces.getByBoundingBox(
                xMin=-bFlange, xMax=bFlange,
                yMin=y_mid-tolY, yMax=y_mid+tolY,
                zMin=-1.0, zMax=L+1.0
            )
            if len(faces_mid) > 0:
                region_mid = regionToolset.Region(faces=faces_mid)
                part.SectionAssignment(
                    region=region_mid,
                    sectionName='SEC_FLG_INNER' + suffix,
                    offset=0.0,
                    offsetType=MIDDLE_SURFACE,
                    offsetField='',
                    thicknessAssignment=FROM_SECTION
                )
                midFlangeCount += len(faces_mid)
                print("[assign_sections%s] Mid flange k=%d (y~%.1f): %d faces -> SEC_FLG_INNER" % (suffix, k, y_mid, len(faces_mid)))
        except Exception as e:
            print("[WARN] Mid flange k=%d selection failed: %s" % (k, str(e)))
    
    # Final check
    totalFlangeCount = bottomFlangeCount + topFlangeCount + midFlangeCount
    print("[assign_sections%s] Summary: bottom=%d, top=%d, mid=%d, total_flange=%d" % 
          (suffix, bottomFlangeCount, topFlangeCount, midFlangeCount, totalFlangeCount))
    
    if totalFlangeCount == 0:
        raise Exception(
            "[assign_sections] No flange faces selected! Possible reasons:\n"
            "  1) tolY=%.2f too small (try increasing meshSize or hSeg)\n"
            "  2) Geometry issue: flanges not extruded correctly\n"
            "  3) Bounding box coordinates mismatch" % tolY
        )


# =============================================================================
# 端部耦合与边界条件
# =============================================================================
def create_reference_points(model, geo_info):
    """创建参考点"""
    a = model.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    H = geo_info['H_total']
    L = geo_info['Lmember']
    
    # RP位置稍微偏离端面,避免与耦合边重合
    offset = 0.01 * L  # 偏移1%构件长度
    rp_bot = a.ReferencePoint(point=(0.0, H/2.0, -offset))
    rp_top = a.ReferencePoint(point=(0.0, H/2.0, L+offset))
    
    a.Set(referencePoints=(a.referencePoints[rp_bot.id],), name='RP_BOT')
    a.Set(referencePoints=(a.referencePoints[rp_top.id],), name='RP_TOP')

def get_end_edges(instance, geo_info, z):
    """
    Get edges at z~0 or z~L for coupling using bounding box.
    More robust against edge subdivision and mesh variations.
    """
    H = geo_info['H_total']
    bFlange = geo_info['bFlange']
    L = geo_info['Lmember']
    meshSize = geo_info.get('meshSize', 5.0)  # Fallback to 5.0 if not available
    
    # Tolerance: max of (0.001, 0.001*L, 0.2*meshSize)
    tolZ = max(1e-3, 0.001*L, 0.2*meshSize)
    
    # Bounding box for end section
    if abs(z) < 1.0:  # z ~ 0 (start)
        zMin, zMax = -tolZ, tolZ
        zTarget = 0.0
    else:  # z ~ L (end)
        zMin, zMax = L - tolZ, L + tolZ
        zTarget = L
    
    edges = instance.edges.getByBoundingBox(
        xMin=-bFlange, xMax=bFlange,
        yMin=-1.0, yMax=H+1.0,
        zMin=zMin, zMax=zMax
    )
    
    edgeCount = len(edges)
    print("[get_end_edges] z=%.1f (target=%.1f, tolZ=%.3f): found %d edges" % (z, zTarget, tolZ, edgeCount))
    
    if edgeCount == 0:
        raise Exception(
            "[get_end_edges] No edges found at z=%.1f! Check:\n"
            "  1) Mesh generated correctly?\n"
            "  2) tolZ=%.3f sufficient?\n"
            "  3) Instance coordinates match part coordinates?" % (zTarget, tolZ)
        )
    
    return edges

def create_end_couplings(model, instance, geo_info):
    """创建端部耦合"""
    a = model.rootAssembly
    L = geo_info['Lmember']
    
    edges_top = get_end_edges(instance, geo_info, z=L)
    edges_bot = get_end_edges(instance, geo_info, z=0.0)
    
    a.Set(edges=edges_top, name='END_TOP_EDGES')
    a.Set(edges=edges_bot, name='END_BOT_EDGES')
    
    model.MultipointConstraint(name='MPC_TOP', controlPoint=a.sets['RP_TOP'],
                               surface=a.sets['END_TOP_EDGES'], mpcType=BEAM_MPC,
                               userMode=DOF_MODE_MPC, userType=0, csys=None)
    model.MultipointConstraint(name='MPC_BOT', controlPoint=a.sets['RP_BOT'],
                               surface=a.sets['END_BOT_EDGES'], mpcType=BEAM_MPC,
                               userMode=DOF_MODE_MPC, userType=0, csys=None)

def _fixity_to_dofs(fixity):
    """BC类型转DOF字典"""
    fx = str(fixity).upper().strip()
    if fx == 'FIXED':
        return dict(u1=SET, u2=SET, u3=SET, ur1=SET, ur2=SET, ur3=SET)
    if fx == 'PINNED':
        return dict(u1=SET, u2=SET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=SET)
    if fx == 'ROLLER_X':
        return dict(u1=UNSET, u2=SET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET)
    if fx == 'ROLLER_Y':
        return dict(u1=SET, u2=UNSET, u3=SET, ur1=UNSET, ur2=UNSET, ur3=UNSET)
    if fx == 'ROLLER_Z':
        return dict(u1=SET, u2=SET, u3=UNSET, ur1=UNSET, ur2=UNSET, ur3=UNSET)
    if fx == 'ROTATION_FIXED':
        # 只固定转动自由度，位移自由（用于剪切分析）
        return dict(u1=UNSET, u2=UNSET, u3=UNSET, ur1=SET, ur2=SET, ur3=SET)
    return dict(u1=SET, u2=SET, u3=SET, ur1=SET, ur2=SET, ur3=SET)

def apply_end_bcs(model, p, case_info):
    """应用端部边界条件"""
    a = model.rootAssembly
    top = a.sets['RP_TOP']
    bot = a.sets['RP_BOT']
    
    dof_top = _fixity_to_dofs(p['endFixityTop'])
    dof_bot = _fixity_to_dofs(p['endFixityBot'])
    
    # 约束顶部面外位移（U1 - X方向），防止面外变形
    dof_top['u1'] = SET
    
    # 确保顶部轴向位移（U3）不被约束（用于剪切分析）
    # 对于剪切工况，顶部U3应该自由，允许轴向变形
        dof_top['u3'] = UNSET
    
    # 轴压工况也需要释放U3（已在上面处理）
    # if case_info.get('hasAxial') or 'Axial' in case_info['name']:
    #     dof_top['u3'] = UNSET
    
    model.DisplacementBC(name='BC_TOP', createStepName='Initial', region=top,
                         amplitude=UNSET, distributionType=UNIFORM, **dof_top)
    model.DisplacementBC(name='BC_BOT', createStepName='Initial', region=bot,
                         amplitude=UNSET, distributionType=UNIFORM, **dof_bot)


# =============================================================================
# 智能keyword注入
# =============================================================================
def insert_keyword_smart(model, anchor_text, new_content, position='after'):
    """智能查找锚点并插入keyword"""
    kb = model.keywordBlock
    kb.synchVersions(storeNodesAndElements=False)
    
    inserted = False
    for i, blk in enumerate(kb.sieBlocks):
        if anchor_text.upper() in blk.upper():
            if position == 'after':
                kb.insert(i + 1, new_content)
            elif position == 'before':
                kb.insert(i, new_content)
            else:  # replace
                kb.insert(i, new_content)
                kb.delete(i + 1)
            inserted = True
            break
    
    if not inserted:
        # 找不到锚点,尝试追加到末尾
        print("Warning: Anchor '%s' not found, appending to end" % anchor_text)
        kb.insert(len(kb.sieBlocks), new_content)

# =============================================================================
# 弹性屈曲分析
# =============================================================================
def run_buckling_analysis(p, model_name, case_info, geo_info, case_work_dir=None, case_results_dir=None):
    """运行弹性屈曲分析"""
    case_name = case_info['name']
    print("\n" + "="*70)
    print("Buckling: %s - %s" % (model_name, case_name))
    print("="*70)
    
    # 使用WORK_ROOT作为工作目录
    if case_work_dir is None:
        case_work_dir = os.path.join(WORK_ROOT, model_name, case_name)
    if case_results_dir is None:
        case_results_dir = os.path.join(RESULTS_ROOT, model_name, case_name)
    _ensure_dir(case_work_dir)
    _ensure_dir(case_results_dir)
    
    buckle_model_name = model_name + '_' + case_name + '_Buckle'
    mdb.Model(name=buckle_model_name)
    model = mdb.models[buckle_model_name]
    
    # 几何
    part, geo_info = create_part(model, p)
    define_material_sections(model, p, elastic_only=True)
    assign_sections(part, p, geo_info, elastic_only=True)
    
    # 装配
    a = model.rootAssembly
    inst = a.Instance(name='Part-1-1', part=part, dependent=ON)
    
    # 分析步
    model.BuckleStep(name='Step-1', previous='Initial', numEigen=p['numEigen'],
                     eigensolver=LANCZOS, minEigen=None)
    
    # 端部设置
    create_reference_points(model, geo_info)
    create_end_couplings(model, inst, geo_info)
    apply_end_bcs(model, p, case_info)
    
    # 荷载
    ref_loads = case_info['bucklingRef']
    model.ConcentratedForce(name='Load_REF', createStepName='Step-1',
                            region=a.sets['RP_TOP'],
                            cf1=ref_loads[0], cf2=ref_loads[1], cf3=ref_loads[2],
                            distributionType=UNIFORM)
    
    # 屈曲步释放DOF
    bc = model.boundaryConditions['BC_TOP']
    if abs(ref_loads[0]) > 0:
        bc.setValuesInStep(stepName='Step-1', u1=FREED, buckleCase=PERTURBATION_AND_BUCKLING)
    if abs(ref_loads[1]) > 0:
        bc.setValuesInStep(stepName='Step-1', u2=FREED, buckleCase=PERTURBATION_AND_BUCKLING)
    if abs(ref_loads[2]) > 0:
        bc.setValuesInStep(stepName='Step-1', u3=FREED, buckleCase=PERTURBATION_AND_BUCKLING)
    
    # 网格
    part.seedPart(size=p['meshSize'], deviationFactor=0.1, minSizeFactor=0.1)
    part.generateMesh()
    
    # 提交job（在独立工作目录中）
    job_name = 'Job_Buckle_' + model_name + '_' + case_name
    print("[run_buckling_analysis] Job name: %s, case_work_dir: %s" % (job_name, case_work_dir))
    
    # 确保工作目录存在且可写
    if not os.path.exists(case_work_dir):
        os.makedirs(case_work_dir)
    
    # 切换到工作目录并创建job（使用try-finally确保目录切换正确恢复）
    original_cwd = os.getcwd()
    try:
        os.chdir(case_work_dir)
        print("[run_buckling_analysis] Changed to work dir: %s" % os.getcwd())
        
        mdb.Job(name=job_name, model=buckle_model_name, type=ANALYSIS,
                description='Buckling', memory=90, memoryUnits=PERCENTAGE,
                explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE,
                echoPrint=OFF, modelPrint=OFF, contactPrint=OFF, historyPrint=OFF,
                resultsFormat=ODB, numCpus=1, numGPUs=0)
        
        mdb.jobs[job_name].submit(consistencyChecking=OFF)
        mdb.jobs[job_name].waitForCompletion()
    finally:
        os.chdir(original_cwd)
        print("[run_buckling_analysis] Returned to original dir: %s" % os.getcwd())
    
    # 提取结果（保存到results目录）
    _ensure_dir(case_results_dir)
    
    # 查找ODB文件（实际位置：case_work_dir即work/{model}/{case}/）
    odb_path = os.path.join(case_work_dir, job_name + '.odb')
    
    if os.path.exists(odb_path):
        print("[run_buckling_analysis] Found ODB at: %s" % odb_path)
        extract_buckling_results(odb_path, case_results_dir, geo_info)
    else:
        print("[WARN] ODB not found for job: %s" % job_name)
        print("[WARN] Expected path: %s (exists: %s)" % (odb_path, os.path.exists(odb_path)))
    
    # 保存CAE（仅在需要时）
    if SAVE_CAE:
        try:
            mdb.saveAs(pathName=os.path.join(case_work_dir, buckle_model_name + '.cae'))
        except:
            pass
    
    return job_name

def extract_buckling_results(odb_path, output_dir, geo_info):
    """
    Extract buckling eigenvalues from ODB.
    Priority: frame.frameValue > frame.description regex > .dat file parsing
    """
    import re
    eigenvalues = []
    extraction_method = 'unknown'
    
    # 检查ODB文件是否存在
    if not os.path.exists(odb_path):
        print("[extract_buckling] ERROR: ODB file not found: %s" % odb_path)
        return
    
    print("[extract_buckling] Opening ODB: %s" % odb_path)
    
    # Method 1: Try ODB extraction
    odb = None
    try:
        odb = openOdb(odb_path, readOnly=True)
        print("[extract_buckling] ODB opened successfully")
        step = odb.steps['Step-1']
        frames = step.frames
        
        # Try method 1a: frameValue (most reliable)
        # Note: frameValue may return frame index instead of eigenvalue in some cases
        # We need to validate that the value is reasonable (should be >> 1 for buckling)
        for i in range(1, len(frames)):
            frame = frames[i]
            try:
                eigenvalue = frame.frameValue
                # Validate: eigenvalue should be much larger than 1 for buckling analysis
                # If it's exactly i or very small, it's likely wrong (frame index, not eigenvalue)
                if eigenvalue is not None and eigenvalue != 0.0 and abs(eigenvalue) > 1e-6:
                    # Check if it's suspiciously close to frame index (likely wrong)
                    if abs(eigenvalue - float(i)) < 0.1 or abs(eigenvalue) < 100.0:
                        # Skip this - likely frame index, not eigenvalue
                        continue
                    eigenvalues.append((i, eigenvalue))
                    extraction_method = 'frameValue'
            except:
                pass
        
        # Try method 1b: description regex
        if len(eigenvalues) == 0:
            for i in range(1, len(frames)):
                frame = frames[i]
                try:
                    desc = frame.description or ''
                    m = re.search(r'Eigenvalue\s*=\s*([0-9Ee\+\-\.]+)', desc, re.IGNORECASE)
                    if m:
                        eigen_val = float(m.group(1))
                        if abs(eigen_val) > 1e-6:
                            eigenvalues.append((i, eigen_val))
                            extraction_method = 'description_regex'
                except:
                    pass
        
        if odb:
            odb.close()
            odb = None
        
        # Validate extracted eigenvalues: check if they look reasonable
        # If all eigenvalues are close to their mode numbers (1, 2, 3...) or too small, they're likely wrong
        if len(eigenvalues) > 0:
            suspicious = True
            for mode, eigen in eigenvalues:
                # Eigenvalues should be much larger than mode number for buckling
                if abs(eigen) > 100.0 and abs(eigen - float(mode)) > 10.0:
                    suspicious = False
                    break
            if suspicious:
                print("[extract_buckling_results] ODB eigenvalues look suspicious (too small or close to mode numbers), trying .dat file")
                eigenvalues = []  # Clear and try .dat file
        
    except Exception as e:
        print("[extract_buckling_results] ODB extraction failed: %s" % str(e))
        if odb:
            try:
                odb.close()
            except:
                pass
        odb = None
    
    # Method 2: If ODB failed or values are suspicious, try reading from .dat file
    if len(eigenvalues) == 0:
        try:
            dat_path = odb_path.replace('.odb', '.dat')
            if os.path.exists(dat_path):
                with open(dat_path, 'r') as f:
                    content = f.read()
                    # Find the eigenvalue section
                    # Pattern: MODE NO followed by eigenvalues
                    pattern = r'MODE NO\s+EIGENVALUE\s+(?:\n\s+\d+\s+([0-9Ee\+\-\.]+))+'
                    # Simpler pattern: find all lines after "MODE NO      EIGENVALUE"
                    lines = content.split('\n')
                    in_eigen_section = False
                    for line in lines:
                        # Check if we've entered the eigenvalue section
                        if 'MODE NO' in line.upper() and 'EIGENVALUE' in line.upper():
                            in_eigen_section = True
                            continue
                        
                        # Process eigenvalue lines
                        if in_eigen_section:
                            line_stripped = line.strip()
                            # Skip empty lines
                            if not line_stripped:
                                continue
                            # Match lines like "       1      1.52398E+05" or "       1       82310."
                            # Pattern: optional spaces + mode_number + spaces + eigenvalue
                            m = re.match(r'^\s*(\d+)\s+([0-9Ee\+\-\.]+)', line_stripped)
                            if m:
                                try:
                                    mode_num = int(m.group(1))
                                    eigen_str = m.group(2).strip()
                                    eigen_val = float(eigen_str)
                                    if abs(eigen_val) > 1e-6:
                                        eigenvalues.append((mode_num, eigen_val))
                                        extraction_method = 'dat_file'
                                except (ValueError, IndexError):
                                    pass
                            # Check if we've reached the end
                            elif 'THE ANALYSIS' in line.upper() or 'ANALYSIS COMPLETE' in line.upper():
                                break
                
                if len(eigenvalues) > 0:
                    print("[extract_buckling_results] Extracted %d eigenvalues from .dat file" % len(eigenvalues))
        except Exception as e:
            print("[extract_buckling_results] .dat file extraction failed: %s" % str(e))
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print("[extract_buckling] Created output directory: %s" % output_dir)
    
    # Write CSV
    csv_path = os.path.join(output_dir, 'buckling_eigen.csv')
    print("[extract_buckling] Writing CSV: %s" % csv_path)
    if len(eigenvalues) > 0:
        with open(csv_path, 'w') as f:
            f.write('Mode,Eigenvalue,CriticalFactor\n')
            for mode, eigen in eigenvalues:
                f.write('%d,%.6e,%.6e\n' % (mode, eigen, eigen))
        print("[extract_buckling_results] Extracted %d eigenvalues using %s" % (len(eigenvalues), extraction_method))
    else:
        # Write warning file
        warning_path = os.path.join(output_dir, 'buckling_extract_warning.txt')
        with open(warning_path, 'w') as f:
            f.write('WARNING: No eigenvalues extracted\n')
            f.write('ODB path: %s\n' % odb_path)
            f.write('Tried methods: ODB frameValue, ODB description, .dat file\n')
        print("[extract_buckling_results] WARNING: No eigenvalues found")
    
    # Note: Image export is handled separately by export_images_auto.py
    # (run with: abaqus viewer noGUI=export_images_auto.py)
    # Skipping image export in CAE noGUI mode to avoid viewport errors


# =============================================================================
# 弹塑性Riks分析
# =============================================================================
def run_riks_analysis(p, model_name, case_info, geo_info, buckle_job_name, case_work_dir=None, case_results_dir=None):
    """运行弹塑性Riks分析"""
    case_name = case_info['name']
    print("\n" + "="*70)
    print("Riks: %s - %s" % (model_name, case_name))
    print("="*70)
    
    # 使用WORK_ROOT作为工作目录
    if case_work_dir is None:
        case_work_dir = os.path.join(WORK_ROOT, model_name, case_name)
    if case_results_dir is None:
        case_results_dir = os.path.join(RESULTS_ROOT, model_name, case_name)
    _ensure_dir(case_work_dir)
    _ensure_dir(case_results_dir)
    
    # 更新buckle_job路径（如果在独立目录中）
    buckle_odb_in_case_dir = os.path.join(case_work_dir, buckle_job_name + '.odb')
    if os.path.exists(buckle_odb_in_case_dir):
        buckle_job_path = buckle_odb_in_case_dir
    else:
        buckle_job_path = os.path.join(TEMP_DIR, buckle_job_name + '.odb')
    
    riks_model_name = model_name + '_' + case_name + '_Riks'
    mdb.Model(name=riks_model_name)
    model = mdb.models[riks_model_name]
    
    # 几何
    part, geo_info = create_part(model, p)
    define_material_sections(model, p, elastic_only=False)
    assign_sections(part, p, geo_info, elastic_only=False)
    
    # 装配
    a = model.rootAssembly
    inst = a.Instance(name='Part-1-1', part=part, dependent=ON)
    
    # 端部设置
    create_reference_points(model, geo_info)
    create_end_couplings(model, inst, geo_info)
    apply_end_bcs(model, p, case_info)
    
    # Riks步
    riksCtrl = case_info['riksControl']
    dof = riksCtrl['dof']
    maxDisp = riksCtrl['maxDisp']
    
    model.StaticRiksStep(name='Step-1', previous='Initial',
                         nodeOn=ON, maximumDisplacement=maxDisp,
                         region=a.sets['RP_TOP'], dof=dof,
                         maxNumInc=1000, initialArcInc=0.001, maxArcInc=0.2,
                         minArcInc=1e-06, nlgeom=ON)
    
    # 位移边界条件
    bc_top = model.boundaryConditions['BC_TOP']
    if dof == 1:
        bc_top.setValuesInStep(stepName='Step-1', u1=maxDisp)
    elif dof == 2:
        bc_top.setValuesInStep(stepName='Step-1', u2=maxDisp)
    elif dof == 3:
        bc_top.setValuesInStep(stepName='Step-1', u3=-maxDisp)  # 轴压负向
    
    # 网格
    part.seedPart(size=p['meshSize'], deviationFactor=0.1, minSizeFactor=0.1)
    part.generateMesh()
    
    # FORCE imperfMode=1 regardless of CSV parameter
    imperfMode = 1
    imperfAmp = p.get('imperfAmp', 3.0)
    print("[run_riks_analysis] Imperfection mode FIXED to 1 (amp=%.2f mm)" % imperfAmp)
    
    # 添加*IMPERFECTION（使用独立目录中的ODB文件）
    # 如果ODB在独立目录中，使用完整路径；否则使用旧路径
    if os.path.exists(buckle_job_path):
        imperfection_file = os.path.basename(buckle_job_name)  # 只使用文件名，Abaqus会在当前工作目录查找
    else:
        imperfection_file = buckle_job_name
    insert_keyword_smart(
        model,
        anchor_text='** STEP: Step-1',
        new_content=("** ----------------------------------------------------------------\n"
                     "*IMPERFECTION, FILE=%s, STEP=1\n"
                     "%d, %g\n**\n") % (imperfection_file, imperfMode, imperfAmp),
        position='before'
    )
    
    # History output (include rotations for top reference point)
    try:
        model.HistoryOutputRequest(name='H_RP', createStepName='Step-1',
                                   region=a.sets['RP_TOP'],
                                   variables=('U1','U2','U3','UR1','UR2','UR3','RF1','RF2','RF3'))
    except:
        print("[WARN] Failed to create history output request")
    
    # 提交job（在独立工作目录中）
    job_name = 'Job_Riks_' + model_name + '_' + case_name
    print("[run_riks_analysis] Job name: %s, case_work_dir: %s" % (job_name, case_work_dir))
    
    # 确保工作目录存在且可写
    if not os.path.exists(case_work_dir):
        os.makedirs(case_work_dir)
    
    # 切换到工作目录并创建job（使用try-finally确保目录切换正确恢复）
    original_cwd = os.getcwd()
    try:
        os.chdir(case_work_dir)
        print("[run_riks_analysis] Changed to work dir: %s" % os.getcwd())
        
        mdb.Job(name=job_name, model=riks_model_name, type=ANALYSIS,
                description='Riks', memory=90, memoryUnits=PERCENTAGE,
                explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE,
                echoPrint=OFF, modelPrint=OFF, contactPrint=OFF, historyPrint=OFF,
                resultsFormat=ODB, multiprocessingMode=THREADS,
                numCpus=int(p['numCpus']), numDomains=int(p['numCpus']), numGPUs=0)
        
        mdb.jobs[job_name].writeInput(consistencyChecking=OFF)
        mdb.jobs[job_name].submit(consistencyChecking=OFF)
        mdb.jobs[job_name].waitForCompletion()
    finally:
        os.chdir(original_cwd)
        print("[run_riks_analysis] Returned to original dir: %s" % os.getcwd())
    
    # 提取结果（保存到results目录）
    _ensure_dir(case_results_dir)
    
    # 查找ODB文件（实际位置：case_work_dir即work/{model}/{case}/）
    odb_path = os.path.join(case_work_dir, job_name + '.odb')
    
    if os.path.exists(odb_path):
        print("[run_riks_analysis] Found ODB at: %s" % odb_path)
        results = extract_riks_results(odb_path, case_results_dir, geo_info, case_info)
    else:
        print("[WARN] ODB not found for job: %s" % job_name)
        print("[WARN] Expected path: %s (exists: %s)" % (odb_path, os.path.exists(odb_path)))
        results = {'case': case_info['name'], 'max_U': 0, 'max_RF': 0, 'max_LPF': 0}
    
    # 保存CAE（仅在需要时）
    if SAVE_CAE:
        try:
            mdb.saveAs(pathName=os.path.join(case_work_dir, riks_model_name + '.cae'))
        except:
            pass
    
    return results

def extract_riks_results(odb_path, output_dir, geo_info, case_info):
    """提取Riks曲线和云图"""
    # 检查ODB文件是否存在
    if not os.path.exists(odb_path):
        print("[extract_riks] ERROR: ODB file not found: %s" % odb_path)
        return {'case': case_info['name'], 'max_U': 0, 'max_RF': 0, 'max_LPF': 0}
    
    print("[extract_riks] Opening ODB: %s" % odb_path)
    try:
        odb = openOdb(odb_path, readOnly=True)
        print("[extract_riks] ODB opened successfully")
    except Exception as e:
        print("[extract_riks] ERROR opening ODB: %s" % str(e))
        return {'case': case_info['name'], 'max_U': 0, 'max_RF': 0, 'max_LPF': 0}
    step = odb.steps['Step-1']
    
    # 找RP节点 (避免使用.label属性，直接搜索history regions)
    try:
        rp_nodes = odb.rootAssembly.nodeSets['RP_TOP'].nodes
        # Try to get label, fallback to searching all regions
        try:
            rp_label = rp_nodes[0].label
        except:
            rp_label = None
    except:
        rp_label = None
    
    # 找history region - 搜索所有包含RP_TOP或NODE的region
    target_key = None
    for k in step.historyRegions.keys():
        k_upper = k.upper()
        # Look for regions with RP_TOP or NODE references
        if 'RP_TOP' in k_upper or ('NODE' in k_upper and 'ASSEMBLY' in k_upper):
            target_key = k
            break
    
    hr_rp = step.historyRegions[target_key] if target_key else None
    
    # LPF - search in assembly regions
    lpf_key = None
    for k in step.historyRegions.keys():
        if k.upper().startswith('ASSEMBLY'):
            try:
                if 'LPF' in step.historyRegions[k].historyOutputs.keys():
                    lpf_key = k
                    break
            except:
                pass
    hr_glb = step.historyRegions[lpf_key] if lpf_key else None
    
    def _series(hr, key):
        if hr is None or key not in hr.historyOutputs.keys():
            return []
        return hr.historyOutputs[key].data
    
    lpf = _series(hr_glb, 'LPF')
    u1 = _series(hr_rp, 'U1'); u2 = _series(hr_rp, 'U2'); u3 = _series(hr_rp, 'U3')
    ur1 = _series(hr_rp, 'UR1'); ur2 = _series(hr_rp, 'UR2'); ur3 = _series(hr_rp, 'UR3')
    rf1 = _series(hr_rp, 'RF1'); rf2 = _series(hr_rp, 'RF2'); rf3 = _series(hr_rp, 'RF3')
    
    n = min(len(lpf) if lpf else 10**9, len(u1), len(rf1))
    if n == 10**9:
        n = min(len(u1), len(rf1))
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print("[extract_riks] Created output directory: %s" % output_dir)
    
    # 写CSV (include rotations)
    csv_path = os.path.join(output_dir, 'riks_curve.csv')
    print("[extract_riks] Writing CSV: %s" % csv_path)
    with open(csv_path, 'w') as f:
        f.write('i,time,LPF,U1,U2,U3,UR1,UR2,UR3,RF1,RF2,RF3\n')
        for i in range(n):
            t = u1[i][0] if u1 else i
            lpfv = lpf[i][1] if lpf and i < len(lpf) else ''
            f.write('%d,%g,%s,%g,%g,%g,%g,%g,%g,%g,%g,%g\n' % (
                i+1, t, str(lpfv),
                u1[i][1] if u1 else 0, u2[i][1] if u2 else 0, u3[i][1] if u3 else 0,
                ur1[i][1] if ur1 else 0, ur2[i][1] if ur2 else 0, ur3[i][1] if ur3 else 0,
                rf1[i][1] if rf1 else 0, rf2[i][1] if rf2 else 0, rf3[i][1] if rf3 else 0
            ))
    
    # 计算峰值
    ctrl_dir = case_info['riksControl']['dir']
    if ctrl_dir == 'X':
        u_vals = [abs(x[1]) for x in u1] if u1 else [0]
        rf_vals = [abs(x[1]) for x in rf1] if rf1 else [0]
    elif ctrl_dir == 'Y':
        u_vals = [abs(x[1]) for x in u2] if u2 else [0]
        rf_vals = [abs(x[1]) for x in rf2] if rf2 else [0]
    else:  # Z
        u_vals = [abs(x[1]) for x in u3] if u3 else [0]
        rf_vals = [abs(x[1]) for x in rf3] if rf3 else [0]
    
    max_u = max(u_vals) if u_vals else 0
    max_rf = max(rf_vals) if rf_vals else 0
    max_lpf = max([x[1] for x in lpf]) if lpf else 0
    
    results = {
        'case': case_info['name'],
        'max_U': max_u,
        'max_RF': max_rf,
        'max_LPF': max_lpf,
    }
    
    odb.close()
    
    # Note: Image export is handled separately by export_images_auto.py
    # (run with: abaqus viewer noGUI=export_images_auto.py)
    # Skipping image export in CAE noGUI mode to avoid viewport errors
    
    return results


# =============================================================================
# 视图设置和图像导出功能
# =============================================================================
def setup_viewport(geo_info):
    try:
        H = geo_info['H_total']
        L = geo_info['Lmember']
        session.graphicsOptions.setValues(backgroundStyle=SOLID, backgroundColor='#FFFFFF')
        session.viewports['Viewport: 1'].view.setValues(
            cameraPosition=(L+H, -H, L*1.5),
            cameraUpVector=(0, 0, 50),
            cameraTarget=(0, H/2.0, L/2.0))
        session.viewports['Viewport: 1'].view.fitView()
    except:
        pass


# =============================================================================
# 图像导出功能已移至独立的export_images_auto.py脚本
# 使用方法：abaqus viewer noGUI=export_images_auto.py 或运行 export_images.bat
# =============================================================================


# =============================================================================
# 图像导出调用（带进程锁）
# =============================================================================
def wait_for_viewer_lock(max_wait_sec=300, check_interval=5):
    """等待Abaqus Viewer进程锁释放"""
    system = platform.system()
    
    for attempt in range(max_wait_sec // check_interval):
        if system == 'Windows':
            try:
                # 修复：使用正确的Viewer进程名 ABQvwr.exe
                result = subprocess.run(
                    ['tasklist', '/FI', 'IMAGENAME eq ABQvwr.exe'],
                    capture_output=True, text=True, timeout=5
                )
                # 如果找到ABQvwr.exe进程，说明Viewer正在运行
                viewer_running = 'ABQvwr.exe' in result.stdout
            except:
                viewer_running = False
        else:
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'abaqus.*viewer'],
                    capture_output=True, timeout=5
                )
                viewer_running = (result.returncode == 0)
            except:
                viewer_running = False
        
        if not viewer_running:
            print("[image_export] Viewer not running, proceeding...")
            return True
        
        print("[image_export] Viewer running, waiting %d sec (attempt %d/%d)..." % 
              (check_interval, attempt+1, max_wait_sec // check_interval))
        time.sleep(check_interval)
    
    print("[image_export] WARNING: Timeout waiting for Viewer lock, proceeding anyway...")
    return False


def export_case_images(buckle_odb_path, riks_odb_path, output_dir, model_name, case_name):
    """
    调用科研版导出脚本导出单个算例的图像（使用GUI模式script=，执行完自动关闭）
    科研版功能：peakLPF帧 + legend + U1位移
    """
    print("\n" + "="*70)
    print("Starting image export for: %s / %s" % (model_name, case_name))
    print("="*70)
    
    # 等待Viewer锁
    wait_for_viewer_lock(max_wait_sec=300, check_interval=5)
    
    # 使用整合版图像导出脚本（优先级1+2：peakLPF + legend + U1）
    # Note: export_images.py is for manual GUI use, export_images_auto.py is for batch processing
    export_script = os.path.join(WORK_DIR, 'export_images_auto.py')
    if not os.path.exists(export_script):
        print("[image_export] ERROR: export_images_auto.py not found!")
        print("[image_export] Skipping image export for %s / %s" % (model_name, case_name))
        return False
    
    # 检查ODB文件是否存在
    buckle_odb = buckle_odb_path if buckle_odb_path and os.path.exists(buckle_odb_path) else ""
    riks_odb = riks_odb_path if riks_odb_path and os.path.exists(riks_odb_path) else ""
    
    if not buckle_odb and not riks_odb:
        print("[image_export] WARNING: Both ODB files not found, skipping export")
        return False
    
    # 构建命令行参数（使用GUI模式script=，执行完自动关闭）
    # 注意：使用script=而不是noGUI=，这样会打开GUI窗口进行图像导出
    cmd = ['abaqus', 'viewer', 'noSavedOptions', 'noSavedGuiPrefs', 'noStartupDialog', 
           'script=' + export_script, '--', buckle_odb, riks_odb, output_dir, '1']
    
    print("[image_export] Running: abaqus viewer script=%s (GUI mode)" % export_script)
    print("[image_export] Mode: Research (Priority 1+2: peakLPF + legend + U1)")
    print("[image_export] Note: GUI mode will automatically close after export completes")
    os.chdir(WORK_DIR)
    
    timeout_sec = 600  # 10分钟超时
    success = False
    
    try:
        # Python 2.7兼容：使用Popen代替run
        # 使用shell=True让Windows通过PATH找到abaqus命令
        # 将命令列表转换为字符串
        cmd_str = ' '.join('"%s"' % c if ' ' in c else c for c in cmd)
        print("[image_export] Command: %s" % cmd_str)
        
        proc = subprocess.Popen(
            cmd_str,
            cwd=WORK_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        
        # 手动实现超时
        import time
        start_time = time.time()
        while proc.poll() is None:
            if time.time() - start_time > timeout_sec:
                print("[image_export] ERROR: Viewer timeout (%ds), killing process..." % timeout_sec)
                proc.kill()
                proc.wait()
                break
            time.sleep(1)
        
        returncode = proc.returncode
        stdout, stderr = proc.communicate()
        
        print("[image_export] Viewer exit code: %s" % str(returncode))
        if stdout:
            stdout_str = stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout
            print("[image_export] Viewer stdout (last 300 chars):\n%s" % stdout_str[-300:])
        if stderr:
            stderr_str = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else stderr
            print("[image_export] Viewer stderr (last 300 chars):\n%s" % stderr_str[-300:])
        
        # 检查完成标志文件
        done_flag = os.path.join(output_dir, '_EXPORT_DONE.txt')
        if os.path.exists(done_flag):
            print("[image_export] Export completed (flag file found)")
            success = True
        else:
            success = (returncode == 0)
            
    except Exception as e:
        print("[image_export] ERROR: %s" % str(e))
        import traceback
        traceback.print_exc()
        success = False
    
    print("[image_export] Export %s for %s / %s" % 
          ("completed" if success else "failed", model_name, case_name))
    return success


# =============================================================================
# 主流程
# =============================================================================
def run_multicase_analysis(p):
    """对单组参数运行所有工况"""
    print("\n" + "#"*80)
    print("Multi-Case Analysis for Parameter Set")
    print("#"*80)
    
    model_name = generate_model_name(p)
    cases = get_enabled_cases(p)
    
    print("Model: %s" % model_name)
    print("Enabled Cases: %s" % ', '.join([c['name'] for c in cases]))
    
    # 几何信息(所有case共用)
    temp_model = mdb.Model(name='_temp_geo_')
    part, geo_info = create_part(temp_model, p)
    del mdb.models['_temp_geo_']
    
    all_results = []
    
    for case_info in cases:
        case_name = case_info['name']
        # 新目录结构：work/{model}/{case}/ (临时工作区) 和 results/{model}/{case}/ (永久结果区)
        case_work_dir = os.path.join(WORK_ROOT, model_name, case_name)
        case_results_dir = os.path.join(RESULTS_ROOT, model_name, case_name)
        _ensure_dir(case_work_dir)
        _ensure_dir(case_results_dir)
        
        try:
            # 弹性屈曲（CSV直接保存到results目录）
            buckle_job = run_buckling_analysis(p, model_name, case_info, geo_info, case_work_dir, case_results_dir)
            # 查找buckling ODB（实际位置：case_work_dir即temp_process/{model}/{case}/）
            buckle_job_name = 'Job_Buckle_' + model_name + '_' + case_name
            buckle_odb_path = os.path.join(case_work_dir, buckle_job_name + '.odb')
            if not os.path.exists(buckle_odb_path):
                print("[main] WARNING: Buckling ODB not found: %s" % buckle_odb_path)
                buckle_odb_path = None
            
            # 弹塑性Riks（CSV直接保存到results目录）
            riks_results = run_riks_analysis(p, model_name, case_info, geo_info, buckle_job, case_work_dir, case_results_dir)
            all_results.append(riks_results)
            # 查找riks ODB（实际位置：case_work_dir即work/{model}/{case}/）
            riks_job_name = 'Job_Riks_' + model_name + '_' + case_name
            riks_odb_path = os.path.join(case_work_dir, riks_job_name + '.odb')
            if not os.path.exists(riks_odb_path):
                print("[main] WARNING: Riks ODB not found: %s" % riks_odb_path)
                riks_odb_path = None
            
            # 每个算例完成后立即导出图像（保存到results目录）
            print("\n[main] Exporting images for case: %s / %s" % (model_name, case_name))
            export_case_images(buckle_odb_path, riks_odb_path, case_results_dir, model_name, case_name)
            
            # 清理工作目录（仅在成功时）
            if not KEEP_WORK_FILES:
                try:
                    import cleanup_helper
                    cleanup_helper.cleanup_case_work_dir(case_work_dir, case_results_dir, min_png_count=1, keep_work_files=KEEP_WORK_FILES)
                except Exception as e:
                    print("[main] WARNING: Cleanup failed: %s" % str(e))
            
        except Exception as e:
            print("Error in case %s: %s" % (case_name, str(e)))
            import traceback
            traceback.print_exc()
            continue
    
    # 写summary
    write_summary(model_name, all_results, geo_info, p)
    
    return all_results

def write_summary(model_name, results, geo_info, p):
    """写汇总文件（保存到results目录）"""
    summary_path = os.path.join(RESULTS_ROOT, model_name, 'summary.txt')
    _ensure_dir(os.path.dirname(summary_path))
    
    with open(summary_path, 'w') as f:
        f.write("="*70 + "\n")
        f.write("Multi-Case Analysis Summary\n")
        f.write("="*70 + "\n\n")
        
        f.write("Model: %s\n" % model_name)
        f.write("Geometry:\n")
        f.write("  H_total = %.2f mm\n" % geo_info['H_total'])
        f.write("  bFlange = %.2f mm\n" % geo_info['bFlange'])
        f.write("  tWeb = %.2f mm\n" % p['tWeb'])
        f.write("  tFlange = %.2f mm\n" % p['tFlangeSingle'])
        f.write("  Lmember = %.2f mm\n" % geo_info['Lmember'])
        f.write("  nSeg = %d\n" % geo_info['nSeg'])
        f.write("\n")
        
        f.write("Material:\n")
        f.write("  Web: E=%.1f MPa, fy=%.2f MPa, fu=%.2f MPa, eps_u=%.3f\n" % 
                (p.get('E_web', 210184.0), p.get('fy_web', 270.7), 
                 p.get('fu_web', 352.5), p.get('eps_u_web', 0.234)))
        f.write("  Flange: E=%.1f MPa, fy=%.2f MPa, fu=%.2f MPa, eps_u=%.3f\n" % 
                (p.get('E_flg', 211551.0), p.get('fy_flg', 325.2), 
                 p.get('fu_flg', 474.3), p.get('eps_u_flg', 0.200)))
        f.write("\n")
        
        f.write("Imperfection: mode=1 (FIXED), amp=%.2f mm\n" % p.get('imperfAmp', 3.0))
        f.write("\n")
        
        f.write("Load Cases:\n")
        for res in results:
            case_key = res['case']
            if case_key in LOAD_CASES:
                case_info = LOAD_CASES[case_key]
                rc = case_info['riksControl']
                f.write("  %s:\n" % case_key)
                f.write("    Description: %s\n" % case_info['description'])
                f.write("    Buckling Ref: Fx=%.2f, Fy=%.2f, Fz=%.2f\n" % case_info['bucklingRef'])
                f.write("    Riks Control: DOF=%d, dir=%s, maxDisp=%.1f mm, sign=%d\n" % 
                        (rc['dof'], rc['dir'], rc['maxDisp'], rc.get('sign', 1)))
        f.write("\n")
        
        f.write("Analysis Results:\n")
        f.write("-"*70 + "\n")
        f.write("%-25s %15s %15s %15s\n" % ("Case", "Max_U (mm)", "Max_RF (N)", "Max_LPF"))
        f.write("-"*70 + "\n")
        
        for res in results:
            f.write("%-25s %15.4f %15.2f %15.4f\n" % (
                res['case'], res['max_U'], res['max_RF'], res['max_LPF']
            ))
        
        f.write("-"*70 + "\n")
        f.write("\nAnalysis completed at: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))


def main():
    """
    Main entry point.
    
    Usage:
        # Default (uses PARAM_FILE defined above):
        abaqus cae noGUI=Abaqus_FullAnalysis_v3_MultiCase.py
        
        # With custom parameter file:
        abaqus cae noGUI=Abaqus_FullAnalysis_v3_MultiCase.py -- parameters_quickstart_G1.csv
        
        # Full validation:
        abaqus cae noGUI=Abaqus_FullAnalysis_v3_MultiCase.py -- parameters_scandella_corrected.csv
    """
    import sys
    
    print("\n" + "="*80)
    print("Built-up H-section: Multi-Load-Case Analysis (v3)")
    print("WORK_DIR: %s" % WORK_DIR)
    print("OUTPUT_DIR: %s" % OUTPUT_DIR)
    print("="*80)
    
    # Check for command-line parameter file argument
    # Format: abaqus cae noGUI=script.py -- param_file.csv
    param_file = PARAM_FILE  # Default
    
    # In Abaqus, arguments after '--' are passed to the script
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.endswith('.csv'):
                # Check if it's an absolute path or relative to WORK_DIR
                if os.path.isabs(arg):
                    param_file = arg
                else:
                    param_file = os.path.join(WORK_DIR, arg)
                break
    
    print("Parameter file: %s" % param_file)
    
    if not os.path.exists(param_file):
        print("[ERROR] Parameter file not found: %s" % param_file)
        print("[INFO] Using default parameter file: %s" % PARAM_FILE)
        param_file = PARAM_FILE
    
    params_list = read_parameters_from_csv(param_file)
    print("\nTotal parameter sets: %d" % len(params_list))
    
    for i, p in enumerate(params_list):
        print("\n" + "+"*80)
        print("Parameter Set %d / %d" % (i+1, len(params_list)))
        print("+"*80)
        
        try:
            run_multicase_analysis(p)
        except Exception as e:
            print("Error in parameter set %d: %s" % (i+1, str(e)))
            continue
    
    print("\n" + "="*80)
    print("All analyses completed!")
    print("Results saved in: %s" % OUTPUT_DIR)
    print("="*80)

if __name__ == '__main__':
    main()
