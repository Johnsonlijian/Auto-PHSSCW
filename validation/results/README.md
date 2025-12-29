# Example Results

This directory contains pre-computed example results for reference.

## Directory Structure

```
results/
└── H900_b202_t6_L880/           # G1 specimen (H=900mm, b=202mm, t=6mm, L=880mm)
    ├── summary.txt              # Peak shear capacity summary
    └── LC4_ShearY/              # Pure shear load case
        ├── riks_curve.csv       # Load-displacement history
        └── buckling_eigen.csv   # Eigenvalue results
```

## Expected Results

After running `run_analysis.py`, you should see similar output files generated automatically.

**G1 Specimen Key Result:**
- FE Predicted Shear Capacity: **703.87 kN**
- Experimental Value: **685.4 kN**
- Error: **+2.7%**

