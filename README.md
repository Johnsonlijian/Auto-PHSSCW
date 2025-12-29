# Auto-PHSSCW ABAQUS: Code + Manuscript

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXX)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

This repo hosts the **open-source code** and supporting `Manuscript.docx` for the research: *"Auto-PHSSCW ABAQUS: An Integrated, Python-Based Workflow for Automated Buckling-to-Collapse Analysis of H-Shaped Steel Composite Walls"*.

---

## 🚀 Quick Start: Reproduce Key Result

**Reproduce the G1 specimen validation from Scandella et al. (2020) in 3 steps:**

### Prerequisites
- Abaqus 2020+ (with Python 2.7 interpreter)
- Windows or Linux

### Step 1: Clone and Navigate
```bash
git clone https://github.com/Johnsonlijian/Auto-PHSSCW.git
cd Auto-PHSSCW/validation
```

### Step 2: Run Single Specimen Analysis (~10 min)
```bash
abaqus cae noGUI=Abaqus_FullAnalysis_v3_MultiCase.py -- parameters_quickstart_G1.csv
```

### Step 3: Verify Result
```bash
cat results/H900_b202_t6_L880/summary.txt
```

**Expected Output:**
| Metric | Value |
|--------|-------|
| FE Predicted Shear Capacity | 703.87 kN |
| Experimental (Scandella et al., 2020) | 685.4 kN |
| Error | +2.7% ✓ |

> 📝 For full validation (G1-G4, ~40 min): `abaqus cae noGUI=Abaqus_FullAnalysis_v3_MultiCase.py`

---

## Core Connection: Code ↔ Manuscript

All code scripts map directly to the software architecture/chapters in `manuscript/Manuscript.docx`:

| Code File | Manuscript Reference | Key Function |
|-----------|---------------------|--------------|
| `code/Abaqus_update_totalshell.py` | Section 2.1 (totalshell.py module) | Continuous H-shaped walls: eigen-buckling → Riks collapse |
| `code/Abaqus_update_totalshell_sepH.py` | Section 2.1 (sepH.py module) | Separated walls: surface contact + friction (configurable) |
| `code/Abaqus_update_totalshell_boltH.py` | Section 2.1 (boltH.py module) | Bolted splices: hole generation + pretension + frictional contact |
| `code/Abaqus_update_totalshellP.py` | Section 2.1 (totalshellP.py module) | Parametric batch runs: loop over geometry/load + organize outputs |
| `code/Abaqus_update_totalshellP_sepH.py` | Section 2.2 (Advanced Connections) | Separated walls (plastic analysis): elastic-plastic material model |
| `code/Abaqus_update_totalshellP_boltH.py` | Section 2.2 (Advanced Connections) | Bolted walls (plastic analysis): post-buckling collapse |
| `validation/Abaqus_FullAnalysis_v3_MultiCase.py` | Section 3 (Validation) | **Scandella et al. (2020) validation** |

---

## Repository Structure

```
Auto-PHSSCW/
├── code/                                    # Main analysis modules
│   ├── Abaqus_update_totalshell.py          # Continuous walls
│   ├── Abaqus_update_totalshell_sepH.py     # Separated walls
│   ├── Abaqus_update_totalshell_boltH.py    # Bolted connections
│   ├── Abaqus_update_totalshellP.py         # Parametric batch (continuous)
│   ├── Abaqus_update_totalshellP_sepH.py    # Parametric batch (separated)
│   └── Abaqus_update_totalshellP_boltH.py   # Parametric batch (bolted)
│
├── validation/                              # Reproducible validation example
│   ├── Abaqus_FullAnalysis_v3_MultiCase.py  # Validation analysis script
│   ├── parameters_quickstart_G1.csv         # Quick-start (single specimen)
│   ├── parameters_scandella_corrected.csv   # Full validation (G1-G4)
│   ├── plot_validation_figures.py           # Generate validation plots
│   ├── export_images_auto.py                # Image export utility
│   └── results/                             # Pre-computed results (reference)
│
├── manuscript/
│   └── Manuscript.docx                      # Full research paper
│
├── example-results/                         # Example outputs
├── requirements.md                          # Environment setup guide
├── CITATION.cff                             # Citation file
├── LICENSE                                  # Apache 2.0
└── README.md                                # This file
```

---

## Validation Results Summary

Full validation against Scandella et al. (2020) experimental data:

| Specimen | Description | V<sub>R,exp</sub> (kN) | V<sub>R,FE</sub> (kN) | Error |
|----------|-------------|------------------------|----------------------|-------|
| G1 | Reference (β=143, α=1.0) | 685.4 | 703.87 | +2.7% |
| G2 | Slender web (β=215) | 479.1 | 513.21 | +7.1% |
| G3 | Wide panel (α=1.5) | 598.5 | 604.67 | +1.0% |
| G4 | Stiff flange (t<sub>f</sub>=25mm) | 693.2 | 697.70 | +0.6% |

**Statistics:** Mean error = 2.9%, Max error = 7.1% — All within ±10% criterion ✓

---

## How to Use the Code

### Option 1: Quick Validation (Recommended First)
```bash
cd validation
abaqus cae noGUI=Abaqus_FullAnalysis_v3_MultiCase.py -- parameters_quickstart_G1.csv
```

### Option 2: Full Software Modules
1. **Env Setup**: Follow `requirements.md` (Abaqus 2020+, Windows/Linux, Python 2.7 built-in)
2. **Run Scripts**:
   - For single continuous walls: Run `code/Abaqus_update_totalshell.py` in Abaqus CAE
   - For batch parametric studies: Modify parameters in `code/Abaqus_update_totalshellP.py` and run
3. **Check Results**: Outputs (CSV/TIFF) save to auto-created folders

### Option 3: Generate Validation Figures
```bash
cd validation
python plot_validation_figures.py  # Requires Python 3.x + matplotlib
```

---

## Parameter File Format (Validation)

CSV format for `validation/` scripts:

| Parameter | Description | Unit | Example |
|-----------|-------------|------|---------|
| hSeg | Segment height | mm | 900 |
| nSeg | Number of segments | - | 1 |
| bFlange | Flange width | mm | 202.83 |
| tWeb | Web thickness | mm | 6.31 |
| tFlangeSingle | Flange thickness | mm | 20.80 |
| Lmember | Member length | mm | 880.0 |
| fy_web | Web yield strength | MPa | 247.8 |
| fu_web | Web ultimate strength | MPa | 352.5 |
| imperfAmp | Imperfection amplitude | mm | 2.71 |
| enableCases | Load case | - | LC4_ShearY |

---

## Citation

If you use this software, please cite:

```bibtex
@software{auto_phsscw_2025,
  author       = {Ren, Lijian},
  title        = {Auto-PHSSCW ABAQUS: Automated Buckling-to-Collapse Analysis},
  year         = 2025,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.XXXXXX},
  url          = {https://github.com/Johnsonlijian/Auto-PHSSCW}
}
```

Also cite using `CITATION.cff` for GitHub integration.

---

## References

- Scandella, C., Neuenschwander, M., Mosalam, K. M., & Stojadinovic, B. (2020). *Shear capacity of slender stiffened steel panels*. Thin-Walled Structures, 146, 106435.

---

## Manuscript Access

Find the full research context in `manuscript/Manuscript.docx`:
- **Section 1**: Motivation and background
- **Section 2**: Software architecture and design
- **Section 3**: Validation examples (including Scandella et al.)

---

## License

Apache License 2.0 (consistent with manuscript metadata, Section "Metadata" → C4)

---

## Contact

**Author**: Lijian Ren  
**Email**: renlijian@imut.edu.cn  
**Institution**: Inner Mongolia University of Technology

