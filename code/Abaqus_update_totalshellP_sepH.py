# -*- coding: utf-8 -*-
"""
Nonlinear Finite Element Analysis of Steel Structures
Abaqus/CAE Script for Nonlinear Static Analysis

Author: Lijian REN
Date: March 22, 2022
Organization: Structural Engineering Research Group
Project: Steel Column Stability Analysis
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os

# Initialize Abaqus session
session.Viewport(name='Viewport: 1', origin=(0.0, 0.0), 
                 width=92.94, height=126.41)
session.viewports['Viewport: 1'].makeCurrent()
session.viewports['Viewport: 1'].maximize()
executeOnCaeStartup()

# Geometry parameters
SECTION_HEIGHT = 400  # H (mm)
SECTION_WIDTH = 400   # B (mm)
WEB_THICKNESS = 13.0  # t1 (mm)
FLANGE_THICKNESS = 21.0  # t2 (mm)
MEMBER_LENGTH = 3000  # L (mm)
NUMBER_OF_SPLICES = 1
NUMBER_OF_BOLTS = 4
BOLT_DIAMETER = 20
BOLT_OFFSET = 0.0
FRICTION_COEFFICIENT = 0.35
BOLT_PRETENSION = 90.0  # (kN)

# Material properties
YIELD_STRESS = 355.61  # (MPa)
YIELD_STRAIN = 0.023
ULTIMATE_STRESS = 444.0  # (MPa)
ULTIMATE_STRAIN = 0.1576

# Mesh parameters
MESH_SIZE = 20
BOLT_MESH_SIZE = 4

# Analysis parameters
LOAD_FACTOR_1 = 0.0
LOAD_FACTOR_2 = 1.0
LOAD_FACTOR_3 = 381462.847
DISPLACEMENT_1 = 0.0
DISPLACEMENT_2 = 1.0
DISPLACEMENT_3 = 381462.847
MAX_DISPLACEMENT = 60.0
IMPERFECTION_MAGNITUDE = 6.0

def generate_case_name():
    """Generate descriptive case name for output files"""
    return (f"H{SECTION_HEIGHT}B{SECTION_WIDTH}t{WEB_THICKNESS}"
            f"tf{FLANGE_THICKNESS}L{MEMBER_LENGTH}S{NUMBER_OF_SPLICES}"
            f"B{NUMBER_OF_BOLTS}D{BOLT_DIAMETER}")

# Set working directory
CASE_NAME = generate_case_name()
WORK_DIR = os.path.join("research_data", "nonlinear_analysis", CASE_NAME)
RESULTS_DIR = os.path.join(WORK_DIR, "results")

if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

os.chdir(WORK_DIR)

# Open base model
base_model_path = os.path.join(WORK_DIR, "Elastic.cae")
openMdb(pathName=base_model_path)

session.viewports['Viewport: 1'].setValues(displayedObject=None)
model_part = mdb.models['Model-1'].parts['Part-1']
session.viewports['Viewport: 1'].setValues(displayedObject=model_part)

# Create model copy for nonlinear analysis
mdb.Model(name='Nonlinear-Model', objectToCopy=mdb.models['Model-1'])

# Define material with nonlinear properties
nonlinear_model = mdb.models['Nonlinear-Model']
nonlinear_model.Material(name='Steel-Material')
nonlinear_model.materials['Steel-Material'].Elastic(table=((205000.0, 0.3),))
nonlinear_model.materials['Steel-Material'].Plastic(
    table=((YIELD_STRESS, 0.0), 
           (YIELD_STRESS, YIELD_STRAIN), 
           (ULTIMATE_STRESS, ULTIMATE_STRAIN))
)

# Define shell sections
nonlinear_model.HomogeneousShellSection(
    name='WebSection',
    preIntegrate=OFF,
    material='Steel-Material',
    thicknessType=UNIFORM,
    thickness=WEB_THICKNESS,
    integrationRule=SIMPSON,
    numIntPts=5
)

nonlinear_model.HomogeneousShellSection(
    name='FlangeSection',
    preIntegrate=OFF,
    material='Steel-Material',
    thicknessType=UNIFORM,
    thickness=FLANGE_THICKNESS*2,
    integrationRule=SIMPSON,
    numIntPts=5
)

# Configure analysis steps
if DISPLACEMENT_1 != 0:
    degree_of_freedom = 1
else:
    degree_of_freedom = 2

reference_region = nonlinear_model.rootAssembly.sets['ReferencePoint']
nonlinear_model.steps['Step-2'].setValues(nlgeom=ON)

# Create Riks step for nonlinear analysis
nonlinear_model.StaticRiksStep(
    name='Nonlinear-Step',
    previous='Step-2',
    nodeOn=ON,
    maximumDisplacement=MAX_DISPLACEMENT,
    region=reference_region,
    dof=degree_of_freedom,
    maxNumInc=1000,
    initialArcInc=0.0001,
    maxArcInc=1,
    nlgeom=ON
)

nonlinear_model.steps['Nonlinear-Step'].setValues(minArcInc=1e-06)

# Apply boundary conditions
nonlinear_model.boundaryConditions['BC-1'].setValuesInStep(
    stepName='Nonlinear-Step',
    u1=DISPLACEMENT_1,
    u2=DISPLACEMENT_2
)

# Configure output requests
nonlinear_model.historyOutputRequests['H-Output-1'].setValues(
    variables=('ALLAE',)
)

nonlinear_model.fieldOutputRequests['F-Output-1'].setValues(
    variables=('S', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF')
)

# Configure imperfections
nonlinear_model.keywordBlock.synchVersions(storeNodesAndElements=False)
nonlinear_model.keywordBlock.setValues(edited=0)

imperfection_command = """
** ----------------------------------------------------------------
*IMPERFECTION,FILE=Base-Analysis, STEP=2
1,{0}
**
** STEP: Step-2
**""".format(IMPERFECTION_MAGNITUDE)

# Apply imperfections based on number of splices
imperfection_line = 52 + (NUMBER_OF_SPLICES - 1) * 7
nonlinear_model.keywordBlock.replace(imperfection_line, imperfection_command)

# Create and submit job
nonlinear_job = mdb.Job(
    name='Nonlinear-Analysis',
    model='Nonlinear-Model',
    description='Nonlinear static analysis with imperfections',
    type=ANALYSIS,
    memory=90,
    memoryUnits=PERCENTAGE,
    multiprocessingMode=THREADS,
    numCpus=24,
    numDomains=24
)

nonlinear_job.submit(consistencyChecking=OFF)

# Monitor analysis progress
assembly = mdb.models['Model-1'].rootAssembly
session.viewports['Viewport: 1'].setValues(displayedObject=assembly)

nonlinear_job.waitForCompletion()

# Post-processing
results_path = os.path.join(WORK_DIR, 'Nonlinear-Analysis.odb')
output_database = session.openOdb(name=results_path)

session.viewports['Viewport: 1'].setValues(displayedObject=output_database)
session.viewports['Viewport: 1'].odbDisplay.display.setValues(
    plotState=(CONTOURS_ON_DEF,)
)

# Extract reaction forces and displacements
odb = session.odbs[results_path]
session.xyDataListFromField(
    odb=odb,
    outputPosition=NODAL,
    variable=(
        ('RF', NODAL),
        ('RM', NODAL),
        ('U', NODAL),
        ('UR', NODAL),
    ),
    nodeSets=("REFERENCE_POINT",)
)

# Collect XY data objects
reaction_data = {}
for component in ['Magnitude', 'RF1', 'RF2', 'RF3']:
    reaction_data[f'RF_{component}'] = session.xyDataObjects[
        f'RF:{component} PI: ASSEMBLY N: 2'
    ]

for component in ['Magnitude', 'RM1', 'RM2', 'RM3']:
    reaction_data[f'RM_{component}'] = session.xyDataObjects[
        f'RM:{component} PI: ASSEMBLY N: 2'
    ]

for component in ['Magnitude', 'U1', 'U2', 'U3']:
    reaction_data[f'U_{component}'] = session.xyDataObjects[
        f'U:{component} PI: ASSEMBLY N: 2'
    ]

for component in ['Magnitude', 'UR1', 'UR2', 'UR3']:
    reaction_data[f'UR_{component}'] = session.xyDataObjects[
        f'UR:{component} PI: ASSEMBLY N: 2'
    ]

# Write comprehensive results
session.writeXYReport(
    fileName=os.path.join(RESULTS_DIR, f'NonlinearResults_{CASE_NAME}.csv'),
    appendMode=OFF,
    xyData=tuple(reaction_data.values())
)

# Write simplified results for curve plotting
session.xyReportOptions.setValues(xyData=OFF, minMax=ON)
session.writeXYReport(
    fileName=os.path.join(RESULTS_DIR, 'LoadDisplacementCurve.csv'),
    appendMode=OFF,
    xyData=(
        reaction_data['RF_RF1'],
        reaction_data['RF_RF2'],
        reaction_data['RF_RF3']
    )
)

# Configure visualization settings
session.graphicsOptions.setValues(
    backgroundStyle=SOLID,
    backgroundColor='#FFFFFF'
)

session.viewports['Viewport: 1'].viewportAnnotationOptions.setValues(
    triadPosition=(8, 9),
    legendBox=ON,
    legendPosition=(2, 98),
    title=ON,
    statePosition=(13, 12),
    annotations=ON,
    compass=ON,
    triadFont='-*-verdana-bold-r-normal-*-*-120-*-*-p-*-*-*',
    stateFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*-*-*',
    titleFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*-*-*',
    legendFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*-*-*'
)

# Adjust view
session.viewports['Viewport: 1'].view.setValues(
    nearPlane=1000,
    farPlane=1001,
    width=1000,
    height=1000,
    cameraPosition=(
        MEMBER_LENGTH + NUMBER_OF_SPLICES * SECTION_HEIGHT,
        -NUMBER_OF_SPLICES * SECTION_HEIGHT,
        MEMBER_LENGTH * 1.5
    ),
    cameraUpVector=(0, 0, 50),
    cameraTarget=(0, NUMBER_OF_SPLICES * SECTION_HEIGHT / 2, MEMBER_LENGTH / 2)
)

session.viewports['Viewport: 1'].view.fitView()

# Export visualization
session.printToFile(
    fileName=os.path.join(RESULTS_DIR, f'DeformationPlot_{CASE_NAME}.tiff'),
    format=TIFF,
    canvasObjects=(session.viewports['Viewport: 1'],)
)

print("Nonlinear analysis completed successfully.")
print(f"Results saved in: {RESULTS_DIR}")
