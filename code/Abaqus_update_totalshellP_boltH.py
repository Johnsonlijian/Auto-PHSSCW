# -*- coding: utf-8 -*-
"""
Abaqus/CAE Script for Nonlinear Buckling Analysis of Bolted Steel Connections
Author: Lijian REN
Date: March 15, 2023
Affiliation: Structural Engineering Research Group
Description: Nonlinear buckling analysis of bolted H-section steel columns
             with geometric imperfections and material plasticity
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os

# =============================================================================
# ANALYSIS PARAMETERS
# =============================================================================
# Geometric dimensions
COLUMN_HEIGHT = 1000.0      # H (mm)
FLANGE_WIDTH = 300.0        # B (mm)  
WEB_THICKNESS = 19.0        # t1 (mm)
FLANGE_THICKNESS = 36.0     # t2 (mm)
COLUMN_LENGTH = 3000.0      # L (mm)

# Connection configuration  
NUMBER_OF_SPLICES = 6       # E - Number of bolted splices
VERTICAL_BOLT_ROWS = 1      # F - Number of bolt rows in vertical direction
BOLT_DIAMETER = 20.0        # Bolt diameter (mm)
BOLT_GAUGE = 56.0           # Bolt gauge distance from centerline (mm)

# Material properties
FRICTION_COEFFICIENT = 0.35 # Tangential contact friction coefficient
BOLT_PRETENSION = 125000.0  # Bolt preload force (N)
YIELD_STRESS = 355.61       # Yield stress (MPa)
YIELD_STRAIN = 0.023        # Strain at yield plateau end
ULTIMATE_STRESS = 444.0     # Ultimate stress (MPa)  
ULTIMATE_STRAIN = 0.1576    # Ultimate strain

# Mesh parameters
MESH_SIZE_GLOBAL = 40.0     # Global mesh size (mm)
MESH_SIZE_BOLTS = 4.0       # Bolt region mesh size (mm)

# Loading parameters  
LOAD_FACTOR_X = 1.0         # X-direction load factor
LOAD_FACTOR_Y = 1.0         # Y-direction load factor  
LOAD_FACTOR_Z = 0.0         # Z-direction load factor
IMPERFECTION_FACTOR = 0.01  # Geometric imperfection factor
MAX_DISPLACEMENT = 60.0     # Maximum displacement in Riks analysis (mm)

# =============================================================================
# FILE MANAGEMENT
# =============================================================================
# Generate unique analysis identifier
analysis_id = (f'H{COLUMN_HEIGHT:.0f}_B{FLANGE_WIDTH:.0f}_'
               f'tw{WEB_THICKNESS:.1f}_tf{FLANGE_THICKNESS:.1f}_'
               f'L{COLUMN_LENGTH:.0f}_S{NUMBER_OF_SPLICES}_'
               f'R{VERTICAL_BOLT_ROWS}_D{BOLT_DIAMETER:.0f}')

# Set working directory (GitHub repository structure)
project_root = os.path.dirname(os.path.abspath(__file__))
results_dir = os.path.join(project_root, 'results', analysis_id)
os.makedirs(results_dir, exist_ok=True)
os.chdir(results_dir)

# =============================================================================
# MODEL SETUP
# =============================================================================
# Open base model for elastic analysis
openMdb(pathName=os.path.join(project_root, 'base_models', 'Elastic.cae'))

# Initialize viewport
session.Viewport(name='Viewport: 1', origin=(0.0, 0.0), 
                 width=400, height=300)
session.viewports['Viewport: 1'].maximize()
executeOnCaeStartup()

# Copy base model for nonlinear analysis
mdb.Model(name='Nonlinear-Analysis', objectToCopy=mdb.models['Model-1'])

# =============================================================================
# MATERIAL DEFINITION
# =============================================================================
# Define nonlinear material with plasticity
mdb.models['Nonlinear-Analysis'].Material(name='Steel-S355')
mdb.models['Nonlinear-Analysis'].materials['Steel-S355'].Elastic(
    table=((205000.0, 0.3), ))  # Young's modulus and Poisson's ratio

mdb.models['Nonlinear-Analysis'].materials['Steel-S355'].Plastic(
    table=((YIELD_STRESS, 0.0), 
           (YIELD_STRESS, YIELD_STRAIN), 
           (ULTIMATE_STRESS, ULTIMATE_STRAIN)))

# Define shell sections
mdb.models['Nonlinear-Analysis'].HomogeneousShellSection(
    name='WebSection', preIntegrate=OFF, material='Steel-S355', 
    thicknessType=UNIFORM, thickness=WEB_THICKNESS, 
    integrationRule=SIMPSON, numIntPts=5)

mdb.models['Nonlinear-Analysis'].HomogeneousShellSection(
    name='FlangeSection', preIntegrate=OFF, material='Steel-S355', 
    thicknessType=UNIFORM, thickness=FLANGE_THICKNESS*2, 
    integrationRule=SIMPSON, numIntPts=5)

# =============================================================================
# ANALYSIS STEP DEFINITION
# =============================================================================
# Remove existing steps and define Riks analysis for buckling
del mdb.models['Nonlinear-Analysis'].steps['Step-1']
del mdb.models['Nonlinear-Analysis'].steps['Step-2']

# Determine control degree of freedom based on loading
control_dof = 1 if LOAD_FACTOR_X != 0 else 2

region_def = mdb.models['Nonlinear-Analysis'].rootAssembly.sets['TopNode']
mdb.models['Nonlinear-Analysis'].StaticRiksStep(
    name='Buckling-Analysis', previous='Initial', nodeOn=ON,
    maximumDisplacement=MAX_DISPLACEMENT, region=region_def, dof=control_dof,
    maxNumInc=1000, initialArcInc=0.0001, maxArcInc=1.0, nlgeom=ON)

mdb.models['Nonlinear-Analysis'].steps['Buckling-Analysis'].setValues(
    minArcInc=1e-06)

# =============================================================================
# BOUNDARY CONDITIONS AND LOADS
# =============================================================================
mdb.models['Nonlinear-Analysis'].boundaryConditions['BC-1'].setValuesInStep(
    stepName='Buckling-Analysis', 
    u1=LOAD_FACTOR_X, u2=LOAD_FACTOR_Y)

# Configure output requests
mdb.models['Nonlinear-Analysis'].historyOutputRequests['H-Output-1'].setValues(
    variables=('ALLAE', ))

mdb.models['Nonlinear-Analysis'].fieldOutputRequests['F-Output-1'].setValues(
    variables=('S', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF'))

# =============================================================================
# GEOMETRIC IMPERFECTIONS
# =============================================================================
mdb.models['Nonlinear-Analysis'].keywordBlock.synchVersions(
    storeNodesAndElements=False)

# Apply imperfections based on linear buckling modes
imperfection_block = """
** ----------------------------------------------------------------
*IMPERFECTION, FILE=Job-1, STEP=2
1, 30.0
**
** STEP: Buckling-Analysis
**"""

# Position imperfection command based on connection configuration
if NUMBER_OF_SPLICES == 1:
    line_number = 54
elif NUMBER_OF_SPLICES == 2:
    line_number = 94 + (VERTICAL_BOLT_ROWS - 1) * 30
else:
    line_number = 145 + 37 * (NUMBER_OF_SPLICES - 3) + \
                 (VERTICAL_BOLT_ROWS - 1) * (60 + 30 * (NUMBER_OF_SPLICES - 3))

mdb.models['Nonlinear-Analysis'].keywordBlock.replace(
    line_number, imperfection_block)

# =============================================================================
# BOLT REGION OUTPUT REQUESTS
# =============================================================================
request_number = 1
if NUMBER_OF_SPLICES >= 2:
    for splice in range(NUMBER_OF_SPLICES - 1):
        for bolt_row in range(VERTICAL_BOLT_ROWS):
            assembly = mdb.models['Nonlinear-Analysis'].rootAssembly
            edges = assembly.edges
            
            # Left bolt set
            left_edges = edges.findAt(((-BOLT_GAUGE, 
                                      (splice + 1) * COLUMN_HEIGHT,
                                      (bolt_row + 1) * (COLUMN_LENGTH / (VERTICAL_BOLT_ROWS + 1))), ))
            assembly.Set(edges=left_edges, name=f'BoltSet-{request_number}')
            
            region_def = assembly.sets[f'BoltSet-{request_number}']
            mdb.models['Nonlinear-Analysis'].FieldOutputRequest(
                name=f'BoltOutput-{request_number}', 
                createStepName='Buckling-Analysis',
                variables=('S', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF', 
                          'SF', 'CSTRESS', 'CSTRESSETOS', 'CLINELOAD', 
                          'CPOINTLOAD', 'CDISP', 'CFORCE', 'CSTATUS', 
                          'CTF', 'CEF', 'CU', 'CUE', 'CUP'),
                region=region_def, sectionPoints=DEFAULT, rebar=EXCLUDE)
            
            # Right bolt set  
            right_edges = edges.findAt(((BOLT_GAUGE,
                                       (splice + 1) * COLUMN_HEIGHT,
                                       (bolt_row + 1) * (COLUMN_LENGTH / (VERTICAL_BOLT_ROWS + 1))), ))
            assembly.Set(edges=right_edges, name=f'BoltSet-{request_number + 1}')
            
            request_number += 2

# =============================================================================
# JOB SUBMISSION
# =============================================================================
mdb.Job(name='Nonlinear-Analysis', model='Nonlinear-Analysis', 
        type=ANALYSIS, memory=90, memoryUnits=PERCENTAGE, 
        multiprocessingMode=THREADS, numCpus=16, numDomains=16)

print("Submitting nonlinear analysis job...")
mdb.jobs['Nonlinear-Analysis'].submit(consistencyChecking=OFF)
mdb.jobs['Nonlinear-Analysis'].waitForCompletion()

# =============================================================================
# RESULTS PROCESSING
# =============================================================================
# Open results database
odb_path = os.path.join(results_dir, 'Nonlinear-Analysis.odb')
odb = session.openOdb(name=odb_path)
session.viewports['Viewport: 1'].setValues(displayedObject=odb)

# Extract reaction forces and displacements from top node
top_node_id = 2 + (NUMBER_OF_SPLICES - 1) * 4 + 4 * (NUMBER_OF_SPLICES - 1) * (VERTICAL_BOLT_ROWS - 1)

session.xyDataListFromField(
    odb=odb, outputPosition=NODAL, 
    variable=(('RF', NODAL), ('RM', NODAL), ('U', NODAL), ('UR', NODAL)), 
    nodeSets=("TopNode",))

# Generate comprehensive results report
session.xyReportOptions.setValues(xyData=ON, totals=OFF, minMax=OFF)
session.writeXYReport(
    fileName=os.path.join(results_dir, f'CompleteResults_{analysis_id}.csv'),
    appendMode=OFF,
    xyData=(
        session.xyDataObjects[f'RF:Magnitude PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'RF:RF1 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'RF:RF2 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'RF:RF3 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'U:U1 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'U:U2 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'U:U3 PI: ASSEMBLY N: {top_node_id}']
    ))

# Generate simplified results for column curves
session.xyReportOptions.setValues(xyData=OFF, totals=OFF, minMax=ON)
session.writeXYReport(
    fileName=os.path.join(results_dir, f'ColumnCurve_{analysis_id}.rpt'),
    appendMode=OFF,
    xyData=(
        session.xyDataObjects[f'RF:RF1 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'RF:RF2 PI: ASSEMBLY N: {top_node_id}'],
        session.xyDataObjects[f'RF:RF3 PI: ASSEMBLY N: {top_node_id}']
    ))

# =============================================================================
# VISUALIZATION AND PLOTTING
# =============================================================================
# Configure visualization settings
session.graphicsOptions.setValues(
    backgroundStyle=SOLID, backgroundColor='#FFFFFF')

session.viewports['Viewport: 1'].viewportAnnotationOptions.setValues(
    triadPosition=(8, 9), legendBox=ON, legendPosition=(2, 98), 
    title=ON, statePosition=(13, 12), annotations=ON, compass=ON,
    legendFont='-*-times new roman-medium-r-normal-*-*-120-*-*-p-*-*-*',
    triadFont='-*-times new roman-bold-r-normal-*-*-120-*-*-p-*-*-*')

session.viewports['Viewport: 1'].odbDisplay.display.setValues(
    plotState=(CONTOURS_ON_DEF,))

# Set appropriate view
session.viewports['Viewport: 1'].view.setValues(
    nearPlane=1000, farPlane=1001, 
    cameraPosition=(COLUMN_LENGTH + NUMBER_OF_SPLICES * COLUMN_HEIGHT,
                   -NUMBER_OF_SPLICES * COLUMN_HEIGHT, COLUMN_LENGTH * 1.5),
    cameraUpVector=(0, 0, 50),
    cameraTarget=(0, NUMBER_OF_SPLICES * COLUMN_HEIGHT / 2, COLUMN_LENGTH / 2))
session.viewports['Viewport: 1'].view.fitView()

# Save visualization
session.printToFile(
    fileName=os.path.join(results_dir, f'DeformationPlot_{analysis_id}.tiff'),
    format=TIFF, canvasObjects=(session.viewports['Viewport: 1'],))

print(f"Analysis completed successfully. Results saved in: {results_dir}")

# =============================================================================
# END OF SCRIPT
# =============================================================================
