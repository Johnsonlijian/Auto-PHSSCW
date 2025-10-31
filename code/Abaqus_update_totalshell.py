# -*- coding: mbcs -*-
"""
Finite Element Analysis Script for Buckling-to-Collapse Behavior of H-Shaped Steel Composite Walls

Author: Lijian Ren
Affiliation: College of Civil and Transportation Engineering, Hohai University; 
             College of Civil Engineering, Inner Mongolia University of Technology
Email: renlijian@imut.edu.cn
Created: March 22, 2022
Last Modified: March 22, 2022
Software: Abaqus/CAE 2020

Description: This script automates the finite element modeling and buckling analysis 
of H-shaped steel composite walls (PHSSCWs) as described in the manuscript. It includes:
- Parametric geometry creation with configurable segment numbers
- Material property definition and section assignments
- Mesh generation with controlled element size
- Boundary condition application and load setup
- Eigenvalue buckling analysis execution
- Result extraction and visualization

The script follows the methodology outlined in Section 2.1 and 2.2 of the manuscript,
enabling reproducible analysis of structural behavior under various geometric parameters.
"""

# ------------------------------------------------------
# 1. Import Required Modules
# ------------------------------------------------------
from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeGraphicsStartup, executeOnCaeStartup
import os
import regionToolset

# ------------------------------------------------------
# 2. Initialize Visualization Environment
# ------------------------------------------------------
# Create and configure main viewport
session.Viewport(
    name='Viewport: 1', 
    origin=(0.0, 0.0), 
    width=92.9427032470703, 
    height=126.414352416992
)
session.viewports['Viewport: 1'].makeCurrent()
session.viewports['Viewport: 1'].maximize()

# Execute startup procedures and set visualization options
executeOnCaeGraphicsStartup()
executeOnCaeStartup()
session.viewports['Viewport: 1'].partDisplay.geometryOptions.setValues(
    referenceRepresentation=ON
)

# ------------------------------------------------------
# 3. Define Geometric and Material Parameters
#    (Corresponding to Section 2.1 of the manuscript)
# ------------------------------------------------------
# Geometric parameters (all dimensions in mm)
A = 300       # Height of single segment (H)
B = 20        # Width of cross-section (B)
C = 15        # Web thickness (t1)
D = 5         # Flange thickness (t2)
L = 3000      # Length of the member (L')
E = 2         # Number of segments (E)
F = 1         # Number of transverse bolts (vertical direction)
BoltD = 20    # Bolt diameter
BoltB = 0.0   # Bolt horizontal distance from y=0 axis

# Material and analysis parameters
sfricn = 0.0      # Tangential contact friction coefficient
pbol = 90.0       # Bolt pretension force (kN)
yfss = 355.61     # Yield stress (MPa)
yfsn = 0.023      # Strain at end of yield plateau
yuss = 444        # Ultimate stress (MPa)
yusn = 0.1576     # Ultimate strain
meshsz = 20       # Element size for main structure (mm)
meshszb = 4       # Element size for bolts (mm)

# Load and boundary condition parameters
cf1f = 1.0    # x-direction concentrated force factor
cf2f = 1.0    # y-direction concentrated force factor
cf3f = 0.0    # z-direction concentrated force factor
u1u = 1.0     # x-direction displacement factor
u2u = 1.0     # y-direction displacement factor
u3u = 0.0     # z-direction displacement factor
trueu3 = 10.0 # Actual z-direction displacement (mm)
nodedeform = 6.0 # Node deformation parameter

# ------------------------------------------------------
# 4. Define Output File Naming and Directories
# ------------------------------------------------------
# Generate unique filename with key parameters for result tracking
printname = (
    f'A{A}B{B}C{C}D{D}L{L}E{E}F{F}BoltD{BoltD}BoltB{BoltB}'
    f'sfricn{sfricn}pbol{pbol}yfss{yfss}yuss{yuss}yusn{yusn}'
    f'meshsz{meshsz}cf1f{cf1f}cf2f{cf2f}cf3f{cf3f}nodedeform{nodedeform}'
)

# Set working directory and ensure output directories exist
work_dir = r"C:\Users\HPC\Desktop\Isight_Catia_Abaqus\Abaqus_dataTE"
os.chdir(work_dir)

# Create output subdirectory if it doesn't exist
output_dir = os.path.join(work_dir, 'picandcsv')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# ------------------------------------------------------
# 5. Create Base Geometry
#    (Implementation of Section 2.2: Geometric Modeling)
# ------------------------------------------------------
# Clear current view
session.viewports['Viewport: 1'].setValues(displayedObject=None)

# Create 2D sketch for extrusion
s = mdb.models['Model-1'].ConstrainedSketch(name='__profile__', sheetSize=200.0)
g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
s.setPrimaryObject(option=STANDALONE)

# Draw cross-section profile
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

# Create 3D deformable part by extruding the sketch
p = mdb.models['Model-1'].Part(name='Part-1', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p = mdb.models['Model-1'].parts['Part-1']
p.BaseShellExtrude(sketch=s, depth=L)  # Extrude along length (L)
s.unsetPrimaryObject()

# Update view and clean up temporary sketch
session.viewports['Viewport: 1'].setValues(displayedObject=p)
del mdb.models['Model-1'].sketches['__profile__']

# ------------------------------------------------------
# 6. Adjust Cross-Section for Multiple Segments
# ------------------------------------------------------
if E != 1:  # Modify geometry for segmented configuration
    p = mdb.models['Model-1'].parts['Part-1']
    s1 = p.features['Shell extrude-1'].sketch
    mdb.models['Model-1'].ConstrainedSketch(name='__edit__', objectToCopy=s1)
    s2 = mdb.models['Model-1'].sketches['__edit__']
    g, v, d, c = s2.geometry, s2.vertices, s2.dimensions, s2.constraints
    s2.setPrimaryObject(option=SUPERIMPOSE)
    
    # Project reference geometry onto sketch
    p.projectReferencesOntoSketch(
        sketch=s2,
        upToFeature=p.features['Shell extrude-1'], 
        filter=COPLANAR_EDGES
    )
    
    # Adjust view parameters
    session.viewports['Viewport: 1'].view.setValues(
        nearPlane=32.0238, farPlane=946.037, width=4902.41, height=2124.32,
        cameraPosition=(60.4493, 532.114, 499.03), 
        cameraTarget=(60.4493, 532.114, 0)
    )
    
    # Create linear pattern for multiple segments
    s2.linearPattern(
        geomList=(g[4], g[5], g[6]), 
        vertexList=(),
        number1=1, spacing1=20.0, angle1=0.0, 
        number2=E, spacing2=A, angle2=90.0
    )
    
    s2.unsetPrimaryObject()
    p = mdb.models['Model-1'].parts['Part-1']
    p.features['Shell extrude-1'].setValues(sketch=s2)
    del mdb.models['Model-1'].sketches['__edit__']

# Regenerate part with new geometry
p = mdb.models['Model-1'].parts['Part-1']
p.regenerate()

# ------------------------------------------------------
# 7. Define Material Properties and Section Assignments
#    (Corresponding to Section 2.2: Material Modeling)
# ------------------------------------------------------
# Update visualization settings
session.viewports['Viewport: 1'].partDisplay.setValues(
    sectionAssignments=ON, engineeringFeatures=ON
)
session.viewports['Viewport: 1'].partDisplay.geometryOptions.setValues(
    referenceRepresentation=OFF
)

# Create material (Steel)
mdb.models['Model-1'].Material(name='Material-1')
mdb.models['Model-1'].materials['Material-1'].Elastic(
    table=((205000.0, 0.3),)  # Young's modulus (MPa) and Poisson's ratio
)
mdb.models['Model-1'].materials['Material-1'].Density(
    table=((7.85e-09,),)  # Density (tonne/mm³)
)

# Create section definitions
mdb.models['Model-1'].HomogeneousShellSection(
    name='websection',
    preIntegrate=OFF, 
    material='Material-1', 
    thicknessType=UNIFORM,
    thickness=C,  # Web thickness
    integrationRule=SIMPSON, 
    numIntPts=5
)

mdb.models['Model-1'].HomogeneousShellSection(
    name='flangesection',
    preIntegrate=OFF, 
    material='Material-1', 
    thicknessType=UNIFORM,
    thickness=D*2,  # Flange thickness
    integrationRule=SIMPSON, 
    numIntPts=5
)

mdb.models['Model-1'].HomogeneousShellSection(
    name='edgeflangesection',
    preIntegrate=OFF, 
    material='Material-1', 
    thicknessType=UNIFORM,
    thickness=D,  # Edge flange thickness
    integrationRule=SIMPSON, 
    numIntPts=5
)

# ------------------------------------------------------
# 8. Assign Sections to Geometry
# ------------------------------------------------------
# Function to assign sections to web based on number of segments
def assign_web_sections():
    p = mdb.models['Model-1'].parts['Part-1']
    f = p.faces
    faces = []
    
    # Select web faces based on number of segments (E)
    if E == 1:
        faces = f.findAt(((0.0, A/2*1, L/2), ))
    elif E == 2:
        faces = f.findAt(((0.0, A/2*1, L/2), ), ((0.0, A*2-A/2, L/2), ))
    elif 3 <= E <= 10:
        # Generate face selection points programmatically
        face_points = [(0.0, A*i - A/2, L/2) for i in range(1, E+1)]
        faces = f.findAt(*face_points)
    
    # Assign web section
    region = regionToolset.Region(faces=faces)
    p.SectionAssignment(
        region=region, 
        sectionName='websection', 
        offset=0.0,
        offsetType=MIDDLE_SURFACE
    )

# Function to assign sections to flanges based on number of segments
def assign_flange_sections():
    p = mdb.models['Model-1'].parts['Part-1']
    f = p.faces
    
    # Assign middle flanges (x-positive)
    if E != 1:
        faces = []
        if 2 <= E <= 10:
            face_points = [(B/4, A*i, L/2) for i in range(1, E)]
            faces = f.findAt(*face_points)
        
        region = regionToolset.Region(faces=faces)
        p.SectionAssignment(
            region=region, 
            sectionName='flangesection', 
            offset=0.0,
            offsetType=MIDDLE_SURFACE
        )
    
    # Assign middle flanges (x-negative)
    if E != 1:
        faces = []
        if 2 <= E <= 10:
            face_points = [(-B/4, A*i, L/2) for i in range(1, E)]
            faces = f.findAt(*face_points)
        
        region = regionToolset.Region(faces=faces)
        p.SectionAssignment(
            region=region, 
            sectionName='flangesection', 
            offset=0.0,
            offsetType=MIDDLE_SURFACE
        )
    
    # Assign edge flanges (x-positive)
    faces = f.findAt(((B/4, 0, L/2), ), ((B/4, E*A, L/2), ))
    region = regionToolset.Region(faces=faces)
    p.SectionAssignment(
        region=region, 
        sectionName='edgeflangesection', 
        offset=0.0,
        offsetType=MIDDLE_SURFACE
    )
    
    # Assign edge flanges (x-negative)
    faces = f.findAt(((-B/4, 0, L/2), ), ((-B/4, E*A, L/2), ))
    region = regionToolset.Region(faces=faces)
    p.SectionAssignment(
        region=region, 
        sectionName='edgeflangesection', 
        offset=0.0,
        offsetType=MIDDLE_SURFACE
    )

# Execute section assignments
assign_web_sections()
assign_flange_sections()
session.viewports['Viewport: 1'].view.fitView()

# ------------------------------------------------------
# 9. Create Assembly
# ------------------------------------------------------
a = mdb.models['Model-1'].rootAssembly
session.viewports['Viewport: 1'].setValues(displayedObject=a)
session.viewports['Viewport: 1'].assemblyDisplay.setValues(
    optimizationTasks=OFF, geometricRestrictions=OFF, stopConditions=OFF
)
a.DatumCsysByDefault(CARTESIAN)

# Create instance of the part
p = mdb.models['Model-1'].parts['Part-1']
a.Instance(name='Part-1-1', part=p, dependent=ON)

# ------------------------------------------------------
# 10. Define Analysis Step (Buckling Analysis)
#     (Corresponding to Section 2.2: Buckling Analysis)
# ------------------------------------------------------
session.viewports['Viewport: 1'].assemblyDisplay.setValues(
    adaptiveMeshConstraints=ON
)

# Create buckling step
mdb.models['Model-1'].BuckleStep(
    name='Step-1', 
    previous='Initial',
    numEigen=10,  # Number of eigenvalues to calculate
    eigensolver=LANCZOS,
    minEigen=None, 
    blockSize=DEFAULT,
    maxBlocks=DEFAULT
)
session.viewports['Viewport: 1'].assemblyDisplay.setValues(step='Step-1')

# ------------------------------------------------------
# 11. Define Sets for Loads and Boundary Conditions
# ------------------------------------------------------
# Create top reference point and set
a1 = mdb.models['Model-1'].rootAssembly
a1.AttachmentPoints(name='RPR1', points=((0, A*E/2, L), ))
v1 = a1.vertices
verts1 = v1.findAt(((0, A*E/2, L), ))
a1.Set(vertices=verts1, name='TTpoint')

# Create bottom reference point and set
a1.AttachmentPoints(name='RPR2', points=((0, A*E/2, 0), ))
v1 = a1.vertices
verts1 = v1.findAt(((0, A*E/2, 0), ))
a1.Set(vertices=verts1, name='BBpoint')

# ------------------------------------------------------
# 12. Define Top and Bottom Surface Sets
# ------------------------------------------------------
def create_surface_sets(surface_name, z_position):
    """Create sets for top or bottom surfaces based on z-coordinate"""
    a = mdb.models['Model-1'].rootAssembly
    e1 = a.instances['Part-1-1'].edges
    edges = []
    
    if E == 1:
        edges = e1.findAt(
            ((+B/4, 0, z_position), ), 
            ((0.0, A/2, z_position), ),
            ((-B/4, 0, z_position),),
            ((+B/4, A, z_position), ),
            ((-B/4, A, z_position),)
        )
    elif 2 <= E <= 10:
        # Collect edges for each segment
        edge_groups = []
        for i in range(E):
            group = e1.findAt(
                ((+B/4, A*i, z_position), ), 
                ((0.0, A*i + A/2, z_position), ),
                ((-B/4, A*i, z_position),)
            )
            edge_groups.append(group)
        
        # Add edges for last segment's top
        edge_groups.append(e1.findAt(
            ((+B/4, A*E, z_position), ), 
            ((-B/4, A*E, z_position),)
        ))
        
        # Combine all edge groups
        edges = []
        for group in edge_groups:
            edges.extend(group)
    
    # Create the surface set
    a.Set(edges=edges, name=surface_name)

# Create top and bottom surface sets
create_surface_sets('Tsurface', L)  # Top surface (z = L)
create_surface_sets('Bsurface', 0)  # Bottom surface (z = 0)

# ------------------------------------------------------
# 13. Define Multipoint Constraints
# ------------------------------------------------------
# Connect top surface to top reference point
a = mdb.models['Model-1'].rootAssembly
region1 = a.sets['TTpoint']
region2 = a.sets['Tsurface']
mdb.models['Model-1'].MultipointConstraint(
    name='Constraint-1',
    controlPoint=region1, 
    surface=region2, 
    mpcType=BEAM_MPC,
    userMode=DOF_MODE_MPC, 
    userType=0, 
    csys=None
)

# Connect bottom surface to bottom reference point
region1 = a.sets['BBpoint']
region2 = a.sets['Bsurface']
mdb.models['Model-1'].MultipointConstraint(
    name='Constraint-2',
    controlPoint=region1, 
    surface=region2, 
    mpcType=BEAM_MPC,
    userMode=DOF_MODE_MPC, 
    userType=0, 
    csys=None
)

# ------------------------------------------------------
# 14. Apply Boundary Conditions
# ------------------------------------------------------
# Top boundary condition
a1 = mdb.models['Model-1'].rootAssembly
region = a1.sets['TTpoint']
mdb.models['Model-1'].DisplacementBC(
    name='BC-1', 
    createStepName='Initial',
    region=region, 
    u1=SET, u2=SET, u3=UNSET, 
    ur1=SET, ur2=SET, ur3=SET,
    amplitude=UNSET, 
    distributionType=UNIFORM
)

# Release degrees of freedom based on load factors
if cf1f != 0:
    mdb.models['Model-1'].boundaryConditions['BC-1'].setValuesInStep(
        stepName='Step-1', 
        u1=FREED, 
        buckleCase=PERTURBATION_AND_BUCKLING
    )
if cf2f != 0:
    mdb.models['Model-1'].boundaryConditions['BC-1'].setValuesInStep(
        stepName='Step-1', 
        u2=FREED, 
        buckleCase=PERTURBATION_AND_BUCKLING
    )

# Bottom boundary condition (fully fixed)
region = a1.sets['BBpoint']
mdb.models['Model-1'].DisplacementBC(
    name='BC-2', 
    createStepName='Initial',
    region=region, 
    u1=SET, u2=SET, u3=SET, 
    ur1=SET, ur2=SET, ur3=SET,
    amplitude=UNSET, 
    distributionType=UNIFORM
)

# ------------------------------------------------------
# 15. Apply Loads
# ------------------------------------------------------
a1 = mdb.models['Model-1'].rootAssembly
region = a1.sets['TTpoint']
mdb.models['Model-1'].ConcentratedForce(
    name='Load-1', 
    createStepName='Step-1',
    region=region, 
    cf1=cf1f, cf2=cf2f, cf3=cf3f, 
    distributionType=UNIFORM,
    field=''
)

# ------------------------------------------------------
# 16. Mesh Generation
#     (Corresponding to Section 2.2: Meshing Strategy)
# ------------------------------------------------------
p = mdb.models['Model-1'].parts['Part-1']
session.viewports['Viewport: 1'].setValues(displayedObject=p)

# Seed part with specified element size
p.seedPart(
    size=meshsz, 
    deviationFactor=0.1, 
    minSizeFactor=0.1
)

# Generate mesh
p.generateMesh()

# ------------------------------------------------------
# 17. Configure Analysis Output
# ------------------------------------------------------
# Modify keyword block to ensure proper result output
if E != 1:
    mdb.models['Model-1'].keywordBlock.synchVersions(storeNodesAndElements=False)
    mdb.models['Model-1'].keywordBlock.replace(67, """
    *Output, field, variable=PRESELECT
    *NODE FILE,GLOBAL=YES
    U,""")
else:
    mdb.models['Model-1'].keywordBlock.synchVersions(storeNodesAndElements=False)
    mdb.models['Model-1'].keywordBlock.replace(59, """
    *Output, field, variable=PRESELECT
    *NODE FILE,GLOBAL=YES
    U,""")

# ------------------------------------------------------
# 18. Create and Run Analysis Job
# ------------------------------------------------------
# Create job definition
mdb.Job(
    name='Job-1', 
    model='Model-1', 
    description='Buckling analysis of H-shaped composite wall',
    type=ANALYSIS,
    memory=90,
    memoryUnits=PERCENTAGE,
    getMemoryFromAnalysis=True,
    explicitPrecision=SINGLE,
    nodalOutputPrecision=SINGLE,
    echoPrint=OFF,
    modelPrint=OFF,
    contactPrint=OFF,
    historyPrint=OFF,
    resultsFormat=ODB,
    numCpus=1,
    numGPUs=0
)

# Submit job and wait for completion
mdb.jobs['Job-1'].submit(consistencyChecking=OFF)
mdb.jobs['Job-1'].waitForCompletion()

# ------------------------------------------------------
# 19. Extract and Visualize Results
#     (Corresponding to Section 3.1: Result Analysis)
# ------------------------------------------------------
# Open results database
odb_path = os.path.join(work_dir, 'Job-1.odb')
o3 = session.openOdb(name=odb_path)
session.viewports['Viewport: 1'].setValues(displayedObject=o3)
session.viewports['Viewport: 1'].makeCurrent()
session.viewports['Viewport: 1'].odbDisplay.display.setValues(
    plotState=(CONTOURS_ON_DEF, )
)

# Write numerical results to report file
session.writeFieldReport(
    fileName=os.path.join(work_dir, 'Result1.rpt'),
    append=OFF, 
    sortItem='nodenumber', 
    odb=o3, 
    step=0, 
    frame=1,
    outputPosition=NODAL, 
    variable=(('U', NODAL), ('UR', NODAL), ), 
    stepFrame=SPECIFY
)

# Write detailed results to CSV file
csv_path = os.path.join(output_dir, f'Elasticdata{printname}.csv')
session.writeFieldReport(
    fileName=csv_path,
    append=OFF, 
    sortItem='结点编号', 
    odb=o3, 
    step=0, 
    frame=1,
    outputPosition=NODAL, 
    variable=(('U', NODAL), ('UR', NODAL), ), 
    stepFrame=SPECIFY
)

# Configure visualization for result image
session.graphicsOptions.setValues(backgroundStyle=SOLID, backgroundColor='#FFFFFF')
session.viewports['Viewport: 1'].viewportAnnotationOptions.setValues(
    triadPosition=(8, 9), 
    legendBox=ON, 
    legendPosition=(2, 98), 
    title=ON,
    statePosition=(13, 12), 
    annotations=ON, 
    compass=ON,
    triadFont='-*-verdana-bold-r-normal-*-*-120-*-*-p-*',
    stateFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*',
    titleFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*',
    legendFont='-*-verdana-medium-r-normal-*-*-120-*-*-p-*'
)

# Adjust view parameters for better visualization
session.viewports['Viewport: 1'].view.setValues(
    nearPlane=1000, farPlane=1001, width=1000, height=1000,
    cameraPosition=(L+E*A, -E*A, L*1.5), 
    cameraUpVector=(0, 0, 50),
    cameraTarget=(0, E*A/2, L/2)
)
session.viewports['Viewport: 1'].view.fitView()

# Save visualization as TIFF image
image_path = os.path.join(output_dir, f'Elastic{printname}.tiff')
session.printToFile(
    fileName=image_path,
    format=TIFF, 
    canvasObjects=(session.viewports['Viewport: 1'], )
)

# Save the model database
mdb.saveAs(pathName=os.path.join(work_dir, 'Elastic'))
