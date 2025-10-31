# -*- coding: utf-8 -*-
"""
Abaqus Script for Shell Structure Buckling Analysis
Author: Lijian REN
Date: March 22, 2023
GitHub Repository: Structural-Analysis-Scripts
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os

# Initialize viewport
session.Viewport(name='Viewport: 1', origin=(0.0, 0.0), 
                 width=92.94, height=126.41)
session.viewports['Viewport: 1'].makeCurrent()
session.viewports['Viewport: 1'].maximize()
executeOnCaeStartup()
session.viewports['Viewport: 1'].partDisplay.geometryOptions.setValues(
    referenceRepresentation=ON)

# =============================================================================
# PARAMETERS DEFINITION
# =============================================================================
A = 300       # Section height (mm)
B = 20        # Flange width (mm)  
C = 15        # Web thickness (mm)
D = 5         # Flange thickness (mm)
L = 3000      # Column length (mm)
E = 2         # Number of segments
F = 1         # Number of bolts in transverse direction
BoltD = 20    # Bolt diameter (mm)
BoltB = 0.0   # Bolt center offset from y=0
sfricn = 0.0  # Friction coefficient
pbol = 90.0   # Bolt preload (MPa)
yfss = 355.61 # Yield stress (MPa)
yfsn = 0.023  # Yield strain at plateau end
yuss = 444    # Ultimate stress (MPa)  
yusn = 0.1576 # Ultimate strain
meshsz = 20   # Global mesh size (mm)
meshszb = 4   # Bolt mesh size (mm)

# Load factors
cf1f = 1.0    # Force in X direction
cf2f = 1.0    # Force in Y direction  
cf3f = 0.0    # Force in Z direction

# Displacement factors
u1u = 1.0     # Displacement in X
u2u = 1.0     # Displacement in Y
u3u = 0.0     # Displacement in Z
trueu3 = 10.0 # True displacement in Z
nodedeform = 6.0 # Node deformation limit

# Generate print name for file identification
printname = (f'A{A}B{B}C{C}D{D}L{L}E{E}F{F}BoltD{BoltD}BoltB{BoltB}'
             f'sfricn{sfricn}pbol{pbol}yfss{yfss}yuss{yuss}yusn{yusn}'
             f'meshsz{meshsz}cf1f{cf1f}cf2f{cf2f}cf3f{cf3f}'
             f'nodedeform{nodedeform}')

# Set working directory
working_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                          'analysis_results')
os.makedirs(working_dir, exist_ok=True)
os.chdir(working_dir)

# =============================================================================
# GEOMETRY CREATION
# =============================================================================
session.viewports['Viewport: 1'].setValues(displayedObject=None)

# Create base sketch
s = mdb.models['Model-1'].ConstrainedSketch(name='__profile__', sheetSize=200.0)
g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
s.setPrimaryObject(option=STANDALONE)

# Sketch geometry definition
s.Line(point1=(0.0, 0), point2=(B/2, 0))
s.HorizontalConstraint(entity=g[2], addUndoState=False)
s.Line(point1=(0.0, 0), point2=(-B/2, 0))
s.HorizontalConstraint(entity=g[3], addUndoState=False)
s.ParallelConstraint(entity1=g[2], entity2=g[3], addUndoState=False)
s.Line(point1=(0.0, 0), point2=(0.0, A))
s.VerticalConstraint(entity=g[4], addUndoState=False)
s.PerpendicularConstraint(entity1=g[2], entity2=g[4], addUndoState=False)
s.Line(point1=(0.0, A), point2=(B/2, A))
s.HorizontalConstraint(entity=g[5], addUndoState=False)
s.PerpendicularConstraint(entity1=g[4], entity2=g[5], addUndoState=False)
s.Line(point1=(0.0, A), point2=(-B/2, A))
s.HorizontalConstraint(entity=g[6], addUndoState=False)
s.PerpendicularConstraint(entity1=g[4], entity2=g[6], addUndoState=False)

# Create 3D shell part
p = mdb.models['Model-1'].Part(name='ShellPart', dimensionality=THREE_D,
                              type=DEFORMABLE_BODY)
p = mdb.models['Model-1'].parts['ShellPart']
p.BaseShellExtrude(sketch=s, depth=L)
s.unsetPrimaryObject()
session.viewports['Viewport: 1'].setValues(displayedObject=p)
del mdb.models['Model-1'].sketches['__profile__']

# Pattern creation for multiple segments
if E != 1:
    p = mdb.models['Model-1'].parts['ShellPart']
    s1 = p.features['Shell extrude-1'].sketch
    mdb.models['Model-1'].ConstrainedSketch(name='__edit__', objectToCopy=s1)
    s2 = mdb.models['Model-1'].sketches['__edit__']
    g, v, d, c = s2.geometry, s2.vertices, s2.dimensions, s2.constraints
    s2.setPrimaryObject(option=SUPERIMPOSE)
    p.projectReferencesOntoSketch(sketch=s2,
        upToFeature=p.features['Shell extrude-1'], filter=COPLANAR_EDGES)
    
    s2.linearPattern(geomList=(g[4], g[5], g[6]), vertexList=(),
        number1=1, spacing1=20.0, angle1=0.0, number2=E, spacing2=A,
        angle2=90.0)
    s2.unsetPrimaryObject()
    p = mdb.models['Model-1'].parts['ShellPart']
    p.features['Shell extrude-1'].setValues(sketch=s2)
    del mdb.models['Model-1'].sketches['__edit__']

p = mdb.models['Model-1'].parts['ShellPart']
p.regenerate()

# =============================================================================
# MATERIALS AND SECTIONS
# =============================================================================
session.viewports['Viewport: 1'].partDisplay.setValues(
    sectionAssignments=ON, engineeringFeatures=ON)
session.viewports['Viewport: 1'].partDisplay.geometryOptions.setValues(
    referenceRepresentation=OFF)

# Material definition
mdb.models['Model-1'].Material(name='StructuralSteel')
mdb.models['Model-1'].materials['StructuralSteel'].Elastic(
    table=((205000.0, 0.3),))
mdb.models['Model-1'].materials['StructuralSteel'].Density(table=((7.85e-09,),))

# Section definitions
mdb.models['Model-1'].HomogeneousShellSection(name='WebSection',
    preIntegrate=OFF, material='StructuralSteel', thicknessType=UNIFORM,
    thickness=C, thicknessField='', nodalThicknessField='',
    idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,
    thicknessModulus=None, temperature=GRADIENT, useDensity=OFF,
    integrationRule=SIMPSON, numIntPts=5)

mdb.models['Model-1'].HomogeneousShellSection(name='FlangeSection',
    preIntegrate=OFF, material='StructuralSteel', thicknessType=UNIFORM,
    thickness=D*2, thicknessField='', nodalThicknessField='',
    idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,
    thicknessModulus=None, temperature=GRADIENT, useDensity=OFF,
    integrationRule=SIMPSON, numIntPts=5)

mdb.models['Model-1'].HomogeneousShellSection(name='EdgeFlangeSection',
    preIntegrate=OFF, material='StructuralSteel', thicknessType=UNIFORM,
    thickness=D, thicknessField='', nodalThicknessField='',
    idealization=NO_IDEALIZATION, poissonDefinition=DEFAULT,
    thicknessModulus=None, temperature=GRADIENT, useDensity=OFF,
    integrationRule=SIMPSON, numIntPts=5)

# Section assignments (web sections)
p = mdb.models['Model-1'].parts['ShellPart']
f = p.faces

# Web section assignment based on number of segments
face_locations = []
for i in range(1, E + 1):
    if i == 1:
        face_locations.append(((0.0, A/2, L/2),))
    else:
        face_locations.append(((0.0, A*i - A/2, L/2),))

faces = f.findAt(*face_locations)
region = regionToolset.Region(faces=faces)
p.SectionAssignment(region=region, sectionName='WebSection', offset=0.0,
    offsetType=MIDDLE_SURFACE, offsetField='',
    thicknessAssignment=FROM_SECTION)

# Flange section assignments (similar pattern as original code, but simplified)
# ... [Section assignment code continues with similar structure] ...

# =============================================================================
# ASSEMBLY AND BOUNDARY CONDITIONS
# =============================================================================
a = mdb.models['Model-1'].rootAssembly
session.viewports['Viewport: 1'].setValues(displayedObject=a)
a.DatumCsysByDefault(CARTESIAN)
p = mdb.models['Model-1'].parts['ShellPart']
a.Instance(name='ShellPart-1', part=p, dependent=ON)

# Analysis step
session.viewports['Viewport: 1'].assemblyDisplay.setValues(
    adaptiveMeshConstraints=ON)
mdb.models['Model-1'].BuckleStep(name='BucklingAnalysis', previous='Initial',
    numEigen=10, eigensolver=LANCZOS, minEigen=None, blockSize=DEFAULT,
    maxBlocks=DEFAULT)
session.viewports['Viewport: 1'].assemblyDisplay.setValues(step='BucklingAnalysis')

# Create sets for boundary conditions
a1 = mdb.models['Model-1'].rootAssembly

# Top attachment point
a1.AttachmentPoints(name='TopAttachment', points=((0, A*E/2, L),))
verts1 = a1.vertices.findAt(((0, A*E/2, L),))
a1.Set(vertices=verts1, name='TopPoint')

# Bottom attachment point  
a1.AttachmentPoints(name='BottomAttachment', points=((0, A*E/2, 0),))
verts1 = a1.vertices.findAt(((0, A*E/2, 0),))
a1.Set(vertices=verts1, name='BottomPoint')

# Create surface sets for MPC constraints
# ... [Surface set creation code] ...

# Multipoint constraints
a = mdb.models['Model-1'].rootAssembly
region1 = a.sets['TopPoint']
region2 = a.sets['TopSurface']
mdb.models['Model-1'].MultipointConstraint(name='TopMPC',
    controlPoint=region1, surface=region2, mpcType=BEAM_MPC,
    userMode=DOF_MODE_MPC, userType=0, csys=None)

region1 = a.sets['BottomPoint']
region2 = a.sets['BottomSurface']
mdb.models['Model-1'].MultipointConstraint(name='BottomMPC',
    controlPoint=region1, surface=region2, mpcType=BEAM_MPC,
    userMode=DOF_MODE_MPC, userType=0, csys=None)

# Boundary conditions
region = a1.sets['TopPoint']
mdb.models['Model-1'].DisplacementBC(name='TopBC', createStepName='Initial',
    region=region, u1=SET, u2=SET, u3=UNSET, ur1=SET, ur2=SET, ur3=SET,
    amplitude=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)

# Apply boundary conditions based on load factors
if cf1f != 0:
    mdb.models['Model-1'].boundaryConditions['TopBC'].setValuesInStep(
        stepName='BucklingAnalysis', u1=FREED, buckleCase=PERTURBATION_AND_BUCKLING)
if cf2f != 0:
    mdb.models['Model-1'].boundaryConditions['TopBC'].setValuesInStep(
        stepName='BucklingAnalysis', u2=FREED, buckleCase=PERTURBATION_AND_BUCKLING)

# Bottom boundary condition
region = a1.sets['BottomPoint']
mdb.models['Model-1'].DisplacementBC(name='BottomBC', createStepName='Initial',
    region=region, u1=SET, u2=SET, u3=SET, ur1=SET, ur2=SET, ur3=SET,
    amplitude=UNSET, distributionType=UNIFORM, fieldName='', localCsys=None)

# Load application
region = a1.sets['TopPoint']
mdb.models['Model-1'].ConcentratedForce(name='AppliedLoad', 
    createStepName='BucklingAnalysis', region=region, cf1=cf1f, cf2=cf2f, 
    cf3=cf3f, distributionType=UNIFORM, field='', localCsys=None)

# =============================================================================
# MESHING
# =============================================================================
p = mdb.models['Model-1'].parts['ShellPart']
session.viewports['Viewport: 1'].setValues(displayedObject=p)
p.seedPart(size=meshsz, deviationFactor=0.1, minSizeFactor=0.1)
p.generateMesh()

# =============================================================================
# ANALYSIS EXECUTION
# =============================================================================
# Configure output
mdb.models['Model-1'].keywordBlock.synchVersions(storeNodesAndElements=False)
if E != 1:
    mdb.models['Model-1'].keywordBlock.replace(67, """
    *Output, field, variable=PRESELECT
    *NODE FILE,GLOBAL=YES
    U,""")
else:
    mdb.models['Model-1'].keywordBlock.replace(59, """
    *Output, field, variable=PRESELECT
    *NODE FILE,GLOBAL=YES
    U,""")

# Create and submit job
mdb.Job(name='BucklingAnalysis', model='Model-1', description='Shell Buckling Analysis',
    type=ANALYSIS, atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90,
    memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
    explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
    modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine='',
    scratch='', resultsFormat=ODB, multiprocessingMode=DEFAULT, numCpus=1,
    numGPUs=0)

mdb.jobs['BucklingAnalysis'].submit(consistencyChecking=OFF)
mdb.jobs['BucklingAnalysis'].waitForCompletion()

# =============================================================================
# RESULTS PROCESSING
# =============================================================================
a = mdb.models['Model-1'].rootAssembly
session.viewports['Viewport: 1'].setValues(displayedObject=a)

# Open results database
odb_path = os.path.join(working_dir, 'BucklingAnalysis.odb')
o3 = session.openOdb(name=odb_path)
session.viewports['Viewport: 1'].setValues(displayedObject=o3)
session.viewports['Viewport: 1'].makeCurrent()
session.viewports['Viewport: 1'].odbDisplay.display.setValues(
    plotState=(CONTOURS_ON_DEF,))

# Generate field report
odb = session.odbs[odb_path]
session.fieldReportOptions.setValues(printXYData=OFF, printTotal=OFF)

# Write results to file
results_file = os.path.join(working_dir, f'buckling_results_{printname}.csv')
session.writeFieldReport(
    fileName=results_file, append=OFF, sortItem='NodeLabel', odb=odb, 
    step=0, frame=1, outputPosition=NODAL, 
    variable=(('U', NODAL), ('UR', NODAL),), stepFrame=SPECIFY)

# Visualization settings
session.graphicsOptions.setValues(backgroundStyle=SOLID, backgroundColor='#FFFFFF')
session.viewports['Viewport: 1'].viewportAnnotationOptions.setValues(
    triadPosition=(8, 9), legendBox=ON, legendPosition=(2, 98), title=ON,
    statePosition=(13, 12), annotations=ON, compass=ON)

# Save visualization
image_file = os.path.join(working_dir, f'buckling_contour_{printname}.tiff')
session.printToFile(fileName=image_file, format=TIFF, 
                   canvasObjects=(session.viewports['Viewport: 1'],))

# Save model
model_file = os.path.join(working_dir, 'BucklingAnalysis.cae')
mdb.saveAs(pathName=model_file)

print("Analysis completed successfully.")
print(f"Results saved to: {working_dir}")
