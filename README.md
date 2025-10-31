# Auto-PHSSCW ABAQUS: Code + Manuscript  
This repo hosts the **open-source code** and supporting `Manuscript.docx` for the research: *"Auto-PHSSCW ABAQUS: An Integrated, Python-Based Workflow for Automated Buckling-to-Collapse Analysis of H-Shaped Steel Composite Walls"*.

## Core Connection: Code ↔ Manuscript  
All code scripts map directly to the software architecture/chapters in `manuscript/Manuscript.docx`:

| Code File                          | Manuscript Reference                          | Key Function                                                                 |
|------------------------------------|-----------------------------------------------|-----------------------------------------------------------------------------|
| `code/Abaqus_update_totalshell.py` | Section 2.1 (totalshell.py module)            | Continuous H-shaped walls: eigen-buckling → Riks collapse                  |
| `code/Abaqus_update_totalshell_sepH.py` | Section 2.1 (sepH.py module)             | Separated walls: surface contact + friction (configurable)                  |
| `code/Abaqus_update_totalshell_boltH.py` | Section 2.1 (boltH.py module)            | Bolted splices: hole generation + pretension + frictional contact           |
| `code/Abaqus_update_totalshellP.py` | Section 2.1 (totalshellP.py module)          | Parametric batch runs: loop over geometry/load + organize outputs           |
| `code/Abaqus_update_totalshellP_sepH.py` | Section 2.2 (Advanced Connections)       | Separated walls (plastic analysis): elastic-plastic material model          |
| `code/Abaqus_update_totalshellP_boltH.py` | Section 2.2 (Advanced Connections)       | Bolted walls (plastic analysis): post-buckling collapse                     |

## How to Use the Code  
1. **Env Setup**: Follow `requirements.md` (Abaqus 2020+, Windows/Linux, Python 2.7 (Abaqus built-in)).  
2. **Run Scripts**:  
   - For single continuous walls: Run `Abaqus_update_totalshell.py` in Abaqus CAE (File → Run Script).  
   - For batch parametric studies: Modify parameters in `Abaqus_update_totalshellP.py` (e.g., H=200–500 mm) and run.  
3. **Check Results**: Outputs (CSV/TIFF) save to auto-created folders (matches `example-results/` structure).

## Manuscript Access  
Find the full research context in `manuscript/Manuscript.docx`—it includes motivation (Section 1), software design (Section 2), and validation examples (Section 3) for the code here.

## License  
Apache License 2.0 (consistent with the manuscript’s metadata, Section "Metadata" → C4).

## Citation  
Cite both the code and manuscript using `CITATION.cff`.

## Contact  
Author: Lijian Ren (renlijian@imut.edu.cn, as listed in the manuscript).
