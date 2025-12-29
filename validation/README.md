# Validation: Scandella et al. (2020) Experimental Verification

This directory contains scripts and data to reproduce the experimental validation cases presented in the paper.

## 🚀 Quick Start (Single Specimen G1)

```bash
# Run analysis (~10 minutes)
abaqus cae noGUI=run_analysis.py -- parameters_quickstart_G1.csv

# Check result
cat results/H900_b202_t6_L880/summary.txt
```

**Expected:** FE = 703.87 kN vs. Exp = 685.4 kN (error: +2.7%)

## 📁 File Description

| File | Description |
|------|-------------|
| `run_analysis.py` | Main analysis script (eigenvalue buckling → Riks collapse) |
| `parameters_quickstart_G1.csv` | Quick-start: single specimen G1 (~10 min) |
| `parameters_full_validation.csv` | Full validation: all 4 specimens G1-G4 (~40 min) |
| `plot_figures.py` | Generate validation figures (requires Python 3 + matplotlib) |
| `export_images.py` | Export contour plots from ODB files |
| `cleanup.py` | Clean up temporary analysis files |

## 📊 Full Validation Results

| Specimen | Description | V_exp (kN) | V_FE (kN) | Error |
|----------|-------------|------------|-----------|-------|
| G1 | Reference (β=143, α=1.0) | 685.4 | 703.87 | +2.7% |
| G2 | Slender web (β=215) | 479.1 | 513.21 | +7.1% |
| G3 | Wide panel (α=1.5) | 598.5 | 604.67 | +1.0% |
| G4 | Stiff flange (tf=25mm) | 693.2 | 697.70 | +0.6% |

**Mean error: 2.9% | Max error: 7.1% | All within ±10% ✓**

## 🔧 Requirements

- Abaqus 2020 or later (with built-in Python 2.7)
- Python 3.x with matplotlib, numpy (for post-processing only)

## 📚 Reference

Scandella, C., Neuenschwander, M., Mosalam, K. M., & Stojadinovic, B. (2020). 
*Shear capacity of slender stiffened steel panels*. Thin-Walled Structures, 146, 106435.

