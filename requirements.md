# Runtime Requirements for Auto-PHSSCW ABAQUS Code  
Aligned with Section 2.1 ("Software architecture") of `manuscript/Manuscript.docx`:

1. **Software**: Abaqus/CAE 2020 or later (required for Python API compatibility).  
2. **OS**: Windows 10/11 or Linux (tested on Ubuntu 20.04).  
3. **Python**: Abaqus built-in Python 2.7 (no external Python installation needed).  
4. **Hardware**: ≥16GB RAM (for batch runs via `Abaqus_update_totalshellP.py`); ≥4 CPU cores (for multiprocessing).  
5. **Permissions**: Run Abaqus CAE as administrator (to write output files).
