# -*- coding: utf-8 -*-
"""
================================================================================
Auto-PHSSCW: Validation Figure Generator
================================================================================

Generate publication-quality figures for Scandella et al. (2020) validation.

Output files:
  - Figure_Validation_Journal.pdf/png  : Single-column scatter plot
  - Figure_Validation_TwoPanel.pdf/png : Two-panel comparison figure
  - Figure_Validation_Color.png        : Color version for presentations
  - Table_Validation.png               : Summary table figure

Usage:
    python plot_figures.py

Requirements: Python 3.x, matplotlib, numpy

Author: Li Jian (Inner Mongolia University of Technology)
License: Apache 2.0
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# =============================================================================
# 数据定义 - Scandella et al. (2020) 验证结果
# =============================================================================

# 试件标识
specimens = ['G1', 'G2', 'G3', 'G4']

# FE预测值 (kN)
fe_values = [703.87, 513.21, 604.67, 697.70]

# 实验值 (kN) - Table 4 from Scandella et al. (2020)
exp_values = [685.4, 479.1, 598.5, 693.2]

# 误差 (%)
errors = [(fe - exp) / exp * 100 for fe, exp in zip(fe_values, exp_values)]

# 试件描述
descriptions = [
    'Reference (β=143, α=1.0)',
    'Slender web (β=215)',
    'Wide panel (α=1.5)',
    'Stiff flange (tf=25mm)'
]

# =============================================================================
# 图表样式设置
# =============================================================================

def setup_journal_style():
    """设置期刊论文风格"""
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 10,
        'axes.linewidth': 0.8,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.major.width': 0.8,
        'ytick.major.width': 0.8,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 9,
        'figure.dpi': 150,
        'savefig.dpi': 600,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1
    })

# =============================================================================
# 图1: 单栏散点图 (适合期刊单栏宽度)
# =============================================================================

def plot_single_column_figure(output_dir='.'):
    """
    创建单栏散点图 - FE预测值 vs 实验值
    适合期刊单栏宽度 (约3.5英寸)
    """
    setup_journal_style()
    
    fig, ax = plt.subplots(figsize=(5, 4.5))
    
    # 绘制数据点
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    for i, (exp, fe, sp) in enumerate(zip(exp_values, fe_values, specimens)):
        ax.scatter(exp, fe, s=100, c=colors[i], edgecolors='black', 
                   linewidths=1, zorder=5, label=sp)
    
    # 添加1:1线和±10%边界线
    line_range = [400, 750]
    ax.plot(line_range, line_range, 'k-', linewidth=1.5, label='1:1 line')
    ax.plot(line_range, [x * 1.1 for x in line_range], 'k--', 
            linewidth=0.8, alpha=0.7)
    ax.plot(line_range, [x * 0.9 for x in line_range], 'k--', 
            linewidth=0.8, alpha=0.7, label='±10% bounds')
    ax.fill_between(line_range, 
                    [x * 0.9 for x in line_range], 
                    [x * 1.1 for x in line_range],
                    alpha=0.1, color='gray')
    
    # 标注各数据点
    offsets = [(12, -5), (12, -5), (12, -5), (12, 8)]
    for i, (exp, fe, sp, err) in enumerate(zip(exp_values, fe_values, specimens, errors)):
        ax.annotate(f'{sp}\n({err:+.1f}%)', 
                    xy=(exp, fe), 
                    xytext=offsets[i],
                    textcoords='offset points', 
                    fontsize=9, 
                    ha='left')
    
    # 坐标轴设置
    ax.set_xlabel('Experimental Shear Capacity $V_{R,exp}$ (kN)')
    ax.set_ylabel('FE Predicted Shear Capacity $V_{R,FE}$ (kN)')
    ax.set_xlim([420, 740])
    ax.set_ylim([420, 740])
    ax.set_aspect('equal')
    ax.legend(loc='lower right', framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    
    # 添加统计信息文本框
    mean_err = np.mean([abs(e) for e in errors])
    max_err = max([abs(e) for e in errors])
    stats_text = f'Mean error: {mean_err:.1f}%\nMax error: {max_err:.1f}%\n$n$ = {len(specimens)} specimens'
    ax.text(0.05, 0.95, stats_text, 
            transform=ax.transAxes, 
            fontsize=9,
            verticalalignment='top', 
            bbox=dict(boxstyle='round,pad=0.3', 
                      facecolor='white',
                      edgecolor='gray', 
                      alpha=0.9))
    
    plt.tight_layout()
    
    # 保存图片
    fig.savefig(os.path.join(output_dir, 'Figure_Validation_Journal.pdf'))
    fig.savefig(os.path.join(output_dir, 'Figure_Validation_Journal.png'))
    print(f"[OK] Single column figure saved: Figure_Validation_Journal.pdf/png")
    
    plt.close(fig)

# =============================================================================
# 图2: 双栏图 (柱状图 + 散点图)
# =============================================================================

def plot_two_panel_figure(output_dir='.'):
    """
    创建双栏对比图
    (a) 柱状图: 实验值 vs FE预测值
    (b) 散点图: FE vs Exp 相关性
    适合期刊双栏宽度 (约7英寸)
    """
    setup_journal_style()
    
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    
    # -------------------------------------------------------------------------
    # 图(a): 柱状对比图
    # -------------------------------------------------------------------------
    ax1 = axes[0]
    x = np.arange(len(specimens))
    width = 0.35
    
    # 绘制柱状图 (黑白打印友好)
    bars1 = ax1.bar(x - width/2, exp_values, width, 
                    label='Experimental',
                    color='white', 
                    edgecolor='black', 
                    hatch='///',
                    linewidth=1)
    bars2 = ax1.bar(x + width/2, fe_values, width, 
                    label='FE Prediction',
                    color='gray', 
                    edgecolor='black',
                    linewidth=1)
    
    # 添加误差标签
    for i, (exp, fe, err) in enumerate(zip(exp_values, fe_values, errors)):
        ax1.annotate(f'{err:+.1f}%', 
                     xy=(i + width/2, fe + 15), 
                     ha='center', 
                     fontsize=9)
    
    # 坐标轴设置
    ax1.set_ylabel('Shear Capacity $V_R$ (kN)')
    ax1.set_xlabel('Specimen')
    ax1.set_xticks(x)
    ax1.set_xticklabels(specimens)
    ax1.legend(loc='upper right')
    ax1.set_ylim([0, 1000])
    ax1.grid(axis='y', alpha=0.3, linestyle='-', linewidth=0.5)
    
    # 子图标签和图名放在图下方（更往下一点）
    ax1.text(0.5, -0.18, '(a) Comparison of Shear Capacity', transform=ax1.transAxes, 
             fontsize=12, fontweight='bold', ha='center')
    
    # -------------------------------------------------------------------------
    # 图(b): 散点图
    # -------------------------------------------------------------------------
    ax2 = axes[1]
    
    # 绘制数据点
    ax2.scatter(exp_values, fe_values, s=100, c='black', marker='o', zorder=5)
    
    # 添加1:1线和±10%边界线
    line_range = [400, 750]
    ax2.plot(line_range, line_range, 'k-', linewidth=1.5)
    ax2.plot(line_range, [x * 1.1 for x in line_range], 'k--', 
             linewidth=0.8, alpha=0.7)
    ax2.plot(line_range, [x * 0.9 for x in line_range], 'k--', 
             linewidth=0.8, alpha=0.7)
    ax2.fill_between(line_range,
                     [x * 0.9 for x in line_range],
                     [x * 1.1 for x in line_range],
                     alpha=0.1, color='gray')
    
    # 标注各数据点
    for i, (exp, fe, sp) in enumerate(zip(exp_values, fe_values, specimens)):
        ax2.annotate(sp, xy=(exp, fe), xytext=(8, 5), 
                     textcoords='offset points', fontsize=10)
    
    # 坐标轴设置
    ax2.set_xlabel('$V_{R,exp}$ (kN)')
    ax2.set_ylabel('$V_{R,FE}$ (kN)')
    ax2.set_xlim([420, 740])
    ax2.set_ylim([420, 740])
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    
    # 添加统计信息
    mean_err = np.mean([abs(e) for e in errors])
    max_err = max([abs(e) for e in errors])
    stats_text = f'Mean: {mean_err:.1f}%\nMax: {max_err:.1f}%'
    ax2.text(0.05, 0.95, stats_text, 
             transform=ax2.transAxes, 
             fontsize=9,
             verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.3', 
                       facecolor='white',
                       edgecolor='gray', 
                       alpha=0.9))
    
    # 子图标签和图名放在图下方（更往下一点）
    ax2.text(0.5, -0.18, '(b) FE Prediction vs Experimental Results', transform=ax2.transAxes, 
             fontsize=12, fontweight='bold', ha='center')
    
    # 调整布局，为子图标签留出更多空间
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    
    # 保存图片
    fig.savefig(os.path.join(output_dir, 'Figure_Validation_TwoPanel.pdf'))
    fig.savefig(os.path.join(output_dir, 'Figure_Validation_TwoPanel.png'))
    print(f"[OK] Two-panel figure saved: Figure_Validation_TwoPanel.pdf/png")
    
    plt.close(fig)

# =============================================================================
# 图3: 彩色版本 (PPT/演示用)
# =============================================================================

def plot_color_figure(output_dir='.'):
    """
    创建彩色版本图表 (适合PPT演示)
    """
    setup_journal_style()
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # -------------------------------------------------------------------------
    # 图(a): 彩色柱状图
    # -------------------------------------------------------------------------
    ax1 = axes[0]
    x = np.arange(len(specimens))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, exp_values, width, 
                    label='Experimental',
                    color='#2E86AB', 
                    edgecolor='black')
    bars2 = ax1.bar(x + width/2, fe_values, width, 
                    label='FE Prediction',
                    color='#E94F37', 
                    edgecolor='black')
    
    for i, (exp, fe, err) in enumerate(zip(exp_values, fe_values, errors)):
        ax1.annotate(f'+{abs(err):.1f}%', 
                     xy=(i + width/2, fe + 15), 
                     ha='center', 
                     fontsize=10,
                     color='#E94F37',
                     fontweight='bold')
    
    ax1.set_ylabel('Shear Capacity $V_R$ (kN)', fontsize=12)
    ax1.set_xlabel('Specimen', fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(specimens)
    ax1.legend(loc='upper right')
    ax1.set_ylim([0, 1000])
    ax1.grid(axis='y', alpha=0.3)
    
    # 子图标签和图名放在图下方（更往下一点）
    ax1.text(0.5, -0.18, '(a) Comparison of Shear Capacity', transform=ax1.transAxes, 
             fontsize=12, fontweight='bold', ha='center')
    
    # -------------------------------------------------------------------------
    # 图(b): 彩色散点图
    # -------------------------------------------------------------------------
    ax2 = axes[1]
    
    colors = ['#2E86AB', '#E94F37', '#28A745', '#FFC107']
    for i, (exp, fe, sp) in enumerate(zip(exp_values, fe_values, specimens)):
        ax2.scatter(exp, fe, s=150, c=colors[i], edgecolors='black', 
                    linewidths=1.5, zorder=5, label=sp)
    
    line_range = [400, 750]
    ax2.plot(line_range, line_range, 'k-', linewidth=2, label='Perfect agreement')
    ax2.plot(line_range, [x * 1.1 for x in line_range], 'k--', 
             linewidth=1, alpha=0.5, label='±10% bounds')
    ax2.plot(line_range, [x * 0.9 for x in line_range], 'k--', 
             linewidth=1, alpha=0.5)
    ax2.fill_between(line_range,
                     [x * 0.9 for x in line_range],
                     [x * 1.1 for x in line_range],
                     alpha=0.1, color='gray')
    
    # 为每个点设置不同的标签偏移量，避免重叠
    offsets = [(8, 15), (8, 8), (8, 16), (8, -1)]  # G1上移, G2不变, G3上移, G4下移
    for i, (exp, fe, sp) in enumerate(zip(exp_values, fe_values, specimens)):
        ax2.annotate(sp, xy=(exp, fe), xytext=offsets[i],
                     textcoords='offset points', fontsize=11, fontweight='bold')
    
    ax2.set_xlabel('Experimental $V_R$ (kN)', fontsize=12)
    ax2.set_ylabel('FE Predicted $V_R$ (kN)', fontsize=12)
    ax2.set_xlim([400, 750])
    ax2.set_ylim([400, 750])
    ax2.set_aspect('equal')
    ax2.legend(loc='lower right')
    ax2.grid(True, alpha=0.3)
    
    # 子图标签和图名放在图下方（更往下一点）
    ax2.text(0.5, -0.18, '(b) FE Prediction vs Experimental Results', transform=ax2.transAxes, 
             fontsize=12, fontweight='bold', ha='center')
    
    mean_err = np.mean([abs(e) for e in errors])
    max_err = max([abs(e) for e in errors])
    stats_text = f'Mean Error: {mean_err:.1f}%\nMax Error: {max_err:.1f}%\nAll within ±10%'
    ax2.text(0.05, 0.95, stats_text, 
             transform=ax2.transAxes, 
             fontsize=10,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 调整布局，为子图标签留出更多空间
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    
    fig.savefig(os.path.join(output_dir, 'Figure_Validation_Color.png'), dpi=300)
    print(f"[OK] Color figure saved: Figure_Validation_Color.png")
    
    plt.close(fig)

# =============================================================================
# 表格图 (用于论文插入)
# =============================================================================

def plot_validation_table(output_dir='.'):
    """
    创建验证结果表格图
    """
    setup_journal_style()
    
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.axis('off')
    
    # 表格数据
    table_data = [
        ['G1', 'Reference (β=143, α=1.0)', '6.31', '20.80', '880', 
         '685.4', '703.87', '+2.7%', 'PASS'],
        ['G2', 'Slender web (β=215)', '4.24', '20.70', '880', 
         '479.1', '513.21', '+7.1%', 'PASS'],
        ['G3', 'Wide panel (α=1.5)', '6.18', '20.67', '1320', 
         '598.5', '604.67', '+1.0%', 'PASS'],
        ['G4', 'Stiff flange (tf=25mm)', '6.18', '25.55', '875', 
         '693.2', '697.70', '+0.6%', 'PASS'],
    ]
    
    columns = ['Specimen', 'Description', '$t_w$ (mm)', '$t_f$ (mm)', 
               '$a$ (mm)', '$V_{R,exp}$ (kN)', '$V_{R,FE}$ (kN)', 
               'Error', 'Status']
    
    table = ax.table(cellText=table_data, 
                     colLabels=columns, 
                     loc='center', 
                     cellLoc='center')
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)
    
    # 设置表头样式
    for i in range(len(columns)):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(color='white', fontweight='bold')
    
    # 设置数据行样式
    for i in range(1, len(table_data) + 1):
        for j in range(len(columns)):
            if j == 7:  # Error列
                table[(i, j)].set_text_props(fontweight='bold')
            if j == 8:  # Status列
                table[(i, j)].set_text_props(color='green', fontweight='bold')
    
    plt.title('Table: Validation against Scandella et al. (2020) Experimental Results',
              fontsize=12, fontweight='bold', pad=20)
    
    fig.savefig(os.path.join(output_dir, 'Table_Validation.png'), 
                dpi=300, facecolor='white', edgecolor='none')
    print(f"[OK] Table figure saved: Table_Validation.png")
    
    plt.close(fig)

# =============================================================================
# 打印验证结果摘要
# =============================================================================

def print_validation_summary():
    """打印验证结果摘要"""
    print("\n" + "=" * 60)
    print("  Scandella et al. (2020) FE Validation Summary")
    print("=" * 60)
    
    print("\n%-10s %-25s %10s %10s %8s" % 
          ("Specimen", "Description", "VR,exp", "VR,FE", "Error"))
    print("-" * 60)
    
    for sp, desc, exp, fe, err in zip(specimens, descriptions, 
                                       exp_values, fe_values, errors):
        status = "OK" if abs(err) <= 10 else "FAIL"
        print("%-10s %-25s %10.1f %10.2f %+7.1f%% %s" % 
              (sp, desc, exp, fe, err, status))
    
    print("-" * 60)
    mean_err = np.mean([abs(e) for e in errors])
    max_err = max([abs(e) for e in errors])
    print(f"\nMean error: {mean_err:.1f}%")
    print(f"Max error: {max_err:.1f}%")
    print(f"Validation status: {'PASS (all within 10%)' if max_err <= 10 else 'FAIL (exceeds 10%)'}")
    print("=" * 60 + "\n")

# =============================================================================
# 主函数
# =============================================================================

def main():
    """主函数 - 生成所有图表"""
    
    # 设置输出目录
    output_dir = '.'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print("\n" + "=" * 60)
    print("  Generating Scandella et al. (2020) Validation Figures")
    print("=" * 60 + "\n")
    
    # 打印验证结果摘要
    print_validation_summary()
    
    # 生成图表
    print("Generating figures...\n")
    
    plot_single_column_figure(output_dir)  # 期刊单栏图
    plot_two_panel_figure(output_dir)      # 期刊双栏图
    plot_color_figure(output_dir)          # 彩色演示图
    plot_validation_table(output_dir)      # 表格图
    
    print("\n" + "=" * 60)
    print("  All figures generated successfully!")
    print("=" * 60)
    print("\nGenerated files:")
    print("  - Figure_Validation_Journal.pdf/png  (Single column figure)")
    print("  - Figure_Validation_TwoPanel.pdf/png (Two-panel figure)")
    print("  - Figure_Validation_Color.png        (Color figure)")
    print("  - Table_Validation.png               (Validation table)")
    print("")

if __name__ == '__main__':
    main()

