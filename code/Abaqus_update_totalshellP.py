# -*- coding: utf-8 -*-
"""
Abaqus/CAE Script for Steel Column Buckling Analysis
Author: Lijian REN
Date: March 22, 2022
Organization: Structural Engineering Research Group
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os

# =============================================================================
# ANALYSIS CONFIGURATION
# =============================================================================

# Geometric parameters
COLUMN_HEIGHT = 200        # H (mm)
FLANGE_WIDTH = 50          # B (mm)  
WEB_THICKNESS = 15         # t1 (mm)
FLANGE_THICKNESS = 5       # t2 (mm)
COLUMN_LENGTH = 3000       # L (mm)
SPLICE_COUNT = 5           # Number of splices
BOLT_ROWS = 4              # Number of bolt rows (vertical direction)

# Fastener parameters
BOLT_DIAMETER = 20         # Bolt diameter (mm)
BOLT_OFFSET = 0.0          # Bolt center offset from y=0
FRICTION_COEFF = 0.0       # Tangential contact friction coefficient
BOLT_PRETENSION = 90.0     # Bolt preload (MPa)

# Material properties
YIELD_STRESS = 355.61      # Yield stress (MPa)
YIELD_STRAIN = 0.023       # Strain at yield plateau end
ULTIMATE_STRESS = 444      # Ultimate stress (MPa)  
ULTIMATE_STRAIN = 0.1576   # Ultimate strain

# Mesh parameters
MESH_SIZE = 20             # Global mesh size (mm)
BOLT_MESH_SIZE = 4         # Bolt region mesh size (mm)

# Loading parameters
LOAD_DIRECTION_X = 1.0     # X-direction loading factor
LOAD_DIRECTION_Y = 1.0     # Y-direction loading factor  
LOAD_DIRECTION_Z = 0.0     # Z-direction loading factor
MAX_DISPLACEMENT = 60.0    # Maximum displacement (mm)
IMPERFECTION_FACTOR = 6.0  # Initial imperfection factor

# =============================================================================
# FILE MANAGEMENT
# =============================================================================

# Generate unique identifier for current analysis
analysis_id = (f'H{COLUMN_HEIGHT}B{FLANGE_WIDTH}C{WEB_THICKNESS}'
               f'D{FLANGE_THICKNESS}L{COLUMN_LENGTH}E{SPLICE_COUNT}'
               f'F{BOLT_ROWS}D{BOLT_DIAMETER}O{BOLT_OFFSET}'
               f'F{FRICTION_COEFF}P{BOLT_PRETENSION}'
               f'YS{YIELD_STRESS}US{ULTIMATE_STRESS}')

# Set working directory (replace with your actual project path)
PROJECT_DIR = "/path/to/your/project/SteelColumnAnalysis"
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.chdir(PROJECT_DIR)

# =============================================================================
# MODEL SETUP
# =============================================================================

# Initialize Abaqus session
session.Viewport(name='Viewport: 1', origin=(0.0, 0.0), 
                 width=92.94, height=126.41)
session.viewports['Viewport: 1'].makeCurrent()
session.viewports['Viewport: 1'].maximize()
executeOnCaeStartup()

# Set display options
session.viewports['Viewport: 1'].partDisplay.geometryOptions.setValues(
    referenceRepresentation=ON)

# Open base model
try:
    openMdb(pathName=os.path.join(PROJECT_DIR, 'base_models', 'Elastic.cae'))
    session.viewports['Viewport: 1'].setValues(displayedObject=None)
    base_part = mdb.models['Model-1'].parts['Part-1']
    session.viewports['Viewport: 1'].setValues(displayedObject=base_part)
except:
    print("Warning: Base model file not found, proceeding with new model")

# Create model copy for nonlinear analysis
mdb.Model(name='BucklingAnalysis', objectToCopy=mdb.models['Model-1'])
mdb.models['BucklingAnalysis'].keywordBlock.synchVersions(
    storeNodesAndElements=False)

# =============================================================================
# MATERIAL DEFINITION
# =============================================================================

# Define steel material with elastic-plastic properties
mdb.models['BucklingAnalysis'].Material(name='StructuralSteel')
mdb.models['BucklingAnalysis'].materials['StructuralSteel'].Elastic(
    table=((205000.0, 0.3), ))  # Young's modulus and Poisson's ratio

mdb.models['BucklingAnalysis'].materials['StructuralSteel'].Plastic(
    table=((YIELD_STRESS, 0.0), 
           (YIELD_STRESS, YIELD_STRAIN), 
           (ULTIMATE_STRESS, ULTIMATE_STRAIN)))

# Define shell sections for different components
mdb.models['BucklingAnalysis'].HomogeneousShellSection(
    name='WebSection', preIntegrate=OFF, material='StructuralSteel',
    thicknessType=UNIFORM, thickness=WEB_THICKNESS, 
    integrationRule=SIMPSON, numIntPts=5)

mdb.models['BucklingAnalysis'].HomogeneousShellSection(
    name='FlangeSection', preIntegrate=OFF, material='StructuralSteel', 
    thicknessType=UNIFORM, thickness=FLANGE_THICKNESS*2,
    integrationRule=SIMPSON, numIntPts=5)

mdb.models['BucklingAnalysis'].HomogeneousShellSection(
    name='EdgeFlangeSection', preIntegrate=OFF, material='StructuralSteel',
    thicknessType=UNIFORM, thickness=FLANGE_THICKNESS,
    integrationRule=SIMPSON, numIntPts=5)

# =============================================================================
# ANALYSIS STEP
# =============================================================================

# Set degree of freedom based on loading
if LOAD_DIRECTION_X != 0:
    controlled_dof = 1  # X-direction
else:
    controlled_dof = 2  # Y-direction

# Define static Riks step for buckling analysis
reference_point = mdb.models['BucklingAnalysis'].rootAssembly.sets['ReferencePoint']
mdb.models['BucklingAnalysis'].StaticRiksStep(
    name='BucklingStep', previous='Initial', nodeOn=ON,
    maximumDisplacement=MAX_DISPLACEMENT, region=reference_point, 
    dof=controlled_dof, maxNumInc=1000, initialArcInc=0.001, 
    maxArcInc=0.2, nlgeom=ON)

mdb.models['BucklingAnalysis'].steps['BucklingStep'].setValues(minArcInc=1e-06)

# Apply boundary conditions
mdb.models['BucklingAnalysis'].boundaryConditions['BC-1'].setValuesInStep(
    stepName='BucklingStep', u1=LOAD_DIRECTION_X, u2=LOAD_DIRECTION_Y)

# Configure output requests
mdb.models['BucklingAnalysis'].historyOutputRequests['H-Output-1'].setValues(
    variables=('ALLAE', ))

mdb.models['BucklingAnalysis'].fieldOutputRequests['F-Output-1'].setValues(
    variables=('S', 'PE', 'PEEQ', 'PEMAG', 'LE', 'U', 'RF', 'CF'))

# =============================================================================
# JOB SUBMISSION
# =============================================================================

# Create and submit analysis job
mdb.Job(name='BucklingAnalysis', model='BucklingAnalysis', 
        description='Steel column buckling analysis', type=ANALYSIS,
        memory=90, memoryUnits=PERCENTAGE, 
        multiprocessingMode=THREADS, numCpus=24, numDomains=24)

mdb.jobs['BucklingAnalysis'].submit(consistencyChecking=OFF)

# Display assembly
assembly = mdb.models['Model-1'].rootAssembly
session.viewports['Viewport: 1'].setValues(displayedObject=assembly)

# Wait for analysis completion
mdb.jobs['BucklingAnalysis'].waitForCompletion()

# =============================================================================
# POST-PROCESSING
# =============================================================================

# Open results database
results_path = os.path.join(PROJECT_DIR, 'BucklingAnalysis.odb')
odb = session.openOdb(name=results_path)
session.viewports['Viewport: 1'].setValues(displayedObject=odb)
session.viewports['Viewport: 1'].odbDisplay.display.setValues(
    plotState=(CONTOURS_ON_DEF, ))

# Extract nodal results
session.xyDataListFromField(
    odb=odb, outputPosition=NODAL, 
    variable=(('RF', NODAL), ('RM', NODAL), ('U', NODAL), ('UR', NODAL)), 
    nodeSets=("REFERENCEPOINT", ))

# Save comprehensive results to CSV
output_data = []
for var in ['RF:Magnitude', 'RF:RF1', 'RF:RF2', 'RF:RF3', 
            'RM:Magnitude', 'RM:RM1', 'RM:RM2', 'RM:RM3',
            'U:Magnitude', 'U:U1', 'U:U2', 'U:U3',
            'UR:Magnitude', 'UR:UR1', 'UR:UR2', 'UR:UR3']:
    output_data.append(session.xyDataObjects[f'{var} PI: ASSEMBLY N: 2'])

csv_filename = os.path.join(RESULTS_DIR, f'buckling_analysis_{analysis_id}.csv')
session.writeXYReport(fileName=csv_filename, appendMode=OFF, 
                     xyData=tuple(output_data))

# Save simplified results for column curve
reaction_forces = [session.xyDataObjects[f'RF:RF{i} PI: ASSEMBLY N: 2'] 
                   for i in range(1, 4)]
session.xyReportOptions.setValues(xyData=OFF, minMax=ON)

summary_filename = os.path.join(RESULTS_DIR, 'column_curve_summary.rpt')
session.writeXYReport(fileName=summary_filename, appendMode=OFF,
                     xyData=tuple(reaction_forces))

# =============================================================================
# VISUALIZATION AND PLOTTING
# =============================================================================

# Configure visualization settings
session.graphicsOptions.setValues(backgroundStyle=SOLID, 
                                 backgroundColor='#FFFFFF')

session.viewports['Viewport: 1'].viewportAnnotationOptions.setValues(
    triadPosition=(8, 9), legendBox=ON, legendPosition=(2, 98), 
    title=ON, statePosition=(13, 12), annotations=ON, compass=ON,
    triadFont='-*-verdana-bold-r-normal-*-*-120-*-*-p-*-*-*',
    stateFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*-*-*',
    titleFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*-*-*',
    legendFont='-*-times new roman-medium-r-normal-*-*-120-*-*-p-*-*-*')

# Set appropriate view
session.viewports['Viewport: 1'].view.setValues(
    nearPlane=1000, farPlane=1001, width=1000, height=1000,
    cameraPosition=(COLUMN_LENGTH + SPLICE_COUNT * COLUMN_HEIGHT, 
                   -SPLICE_COUNT * COLUMN_HEIGHT, 
                   COLUMN_LENGTH * 1.5),
    cameraUpVector=(0, 0, 50),
    cameraTarget=(0, SPLICE_COUNT * COLUMN_HEIGHT / 2, 
                 COLUMN_LENGTH / 2))
session.viewports['Viewport: 1'].view.fitView()

# Export visualization
image_filename = os.path.join(RESULTS_DIR, f'deformation_plot_{analysis_id}.tiff')
session.printToFile(fileName=image_filename, format=TIFF,
                   canvasObjects=(session.viewports['Viewport: 1'],))

print(f"Analysis completed successfully. Results saved to: {RESULTS_DIR}")
print(f"Analysis ID: {analysis_id}")
