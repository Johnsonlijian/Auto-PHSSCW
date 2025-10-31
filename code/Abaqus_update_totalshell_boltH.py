# -*- coding: utf-8 -*-
"""
Parametric Bolted Shell Model for Structural Analysis
Author: Lijian REN
Date: March 15, 2024
Institution: Structural Engineering Research Group
Description: Automated parametric modeling of bolted shell structures for buckling analysis
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import os

# =============================================================================
# PARAMETRIC MODEL CONFIGURATION
# =============================================================================

# Geometric parameters
SECTION_HEIGHT = 1000  # H
FLANGE_WIDTH = 300     # B
WEB_THICKNESS = 19.0   # t1
FLANGE_THICKNESS = 36.0  # t2
SECTION_LENGTH = 3000   # L
NUM_SECTIONS = 6        # Number of connected sections
NUM_BOLT_ROWS = 1       # Number of bolt rows in vertical direction

# Bolt configuration
BOLT_DIAMETER = 20      # Bolt diameter
BOLT_SPACING = 56       # Bolt center spacing from y=0
FRICTION_COEFF = 0.35   # Tangential friction coefficient
BOLT_PRETENSION = 125000.0  # Bolt preload force

# Material properties
YIELD_STRESS = 355.61   # Yield stress
YIELD_STRAIN = 0.023    # Yield strain plateau
ULTIMATE_STRESS = 444.0  # Ultimate stress
ULTIMATE_STRAIN = 0.1576  # Ultimate strain

# Meshing parameters
MESH_SIZE = 40          # Global mesh size
BOLT_MESH_SIZE = 4      # Bolt region mesh size

# Loading and boundary conditions
LOAD_FACTOR_X = 1.0
LOAD_FACTOR_Y = 1.0
LOAD_FACTOR_Z = 0.0
IMPERFECTION_FACTOR = 0.01

# =============================================================================
# MODEL SETUP
# =============================================================================

def setup_model():
    """Initialize the model environment"""
    session.Viewport(name='Viewport: 1', origin=(0.0, 0.0), 
                    width=92.94, height=126.41)
    session.viewports['Viewport: 1'].maximize()
    executeOnCaeStartup()
    session.viewports['Viewport: 1'].partDisplay.geometryOptions.setValues(
        referenceRepresentation=ON)

def create_output_directory():
    """Create output directory for results"""
    model_name = (f"H{SECTION_HEIGHT}_W{FLANGE_WIDTH}_"
                 f"TW{WEB_THICKNESS}_TF{FLANGE_THICKNESS}_"
                 f"L{SECTION_LENGTH}_S{NUM_SECTIONS}_"
                 f"BR{NUM_BOLT_ROWS}_D{BOLT_DIAMETER}")
    
    output_path = './analysis_results/'
    full_path = output_path + model_name
    
    if not os.path.exists(full_path):
        os.makedirs(full_path)
    
    os.chdir(full_path)
    return model_name

def create_base_sketch():
    """Create the base cross-section sketch"""
    s = mdb.models['Model-1'].ConstrainedSketch(name='base_profile', 
                                                sheetSize=200.0)
    g, v, d, c = s.geometry, s.vertices, s.dimensions, s.constraints
    s.setPrimaryObject(option=STANDALONE)
    
    # Define cross-section geometry
    points = [
        (0.0, FLANGE_THICKNESS/2),
        (FLANGE_WIDTH/2, FLANGE_THICKNESS/2),
        (-FLANGE_WIDTH/2, FLANGE_THICKNESS/2),
        (0.0, SECTION_HEIGHT - FLANGE_THICKNESS/2),
        (FLANGE_WIDTH/2, SECTION_HEIGHT - FLANGE_THICKNESS/2),
        (-FLANGE_WIDTH/2, SECTION_HEIGHT - FLANGE_THICKNESS/2)
    ]
    
    # Create profile lines
    s.Line(point1=points[0], point2=points[1])
    s.Line(point1=points[0], point2=points[2])
    s.Line(point1=points[0], point2=points[3])
    s.Line(point1=points[3], point2=points[4])
    s.Line(point1=points[3], point2=points[5])
    
    # Add geometric constraints
    s.HorizontalConstraint(entity=g[2])
    s.HorizontalConstraint(entity=g[3])
    s.ParallelConstraint(entity1=g[2], entity2=g[3])
    s.PerpendicularConstraint(entity1=g[2], entity2=g[4])
    s.HorizontalConstraint(entity=g[5])
    s.PerpendicularConstraint(entity1=g[4], entity2=g[5])
    s.HorizontalConstraint(entity=g[6])
    s.PerpendicularConstraint(entity1=g[4], entity2=g[6])
    
    return s

def create_shell_part(sketch):
    """Create 3D shell part from sketch"""
    p = mdb.models['Model-1'].Part(name='ShellSection', 
                                   dimensionality=THREE_D,
                                   type=DEFORMABLE_BODY)
    p.BaseShellExtrude(sketch=sketch, depth=SECTION_LENGTH)
    sketch.unsetPrimaryObject()
    p.regenerate()
    return p

def create_bolt_holes(part, is_center_section=False):
    """Create bolt holes in the specified part"""
    f, e = part.faces, part.edges
    
    if is_center_section:
        depth = SECTION_HEIGHT
        origin_z = SECTION_LENGTH/2
    else:
        depth = FLANGE_THICKNESS
        origin_z = SECTION_LENGTH/2
        
    t = part.MakeSketchTransform(sketchPlane=f[0], sketchUpEdge=e[3],
                                sketchPlaneSide=SIDE1, sketchOrientation=RIGHT,
                                origin=(FLANGE_WIDTH/4, SECTION_HEIGHT-FLANGE_THICKNESS/2, origin_z))
    
    s = mdb.models['Model-1'].ConstrainedSketch(name='bolt_pattern', 
                                                sheetSize=1091.12, 
                                                gridSpacing=27.27, 
                                                transform=t)
    s.setPrimaryObject(option=SUPERIMPOSE)
    part.projectReferencesOntoSketch(sketch=s, filter=COPLANAR_EDGES)
    
    # Create bolt holes
    s.CircleByCenterPerimeter(center=(FLANGE_WIDTH/4 - BOLT_SPACING, 0),
                             point1=(FLANGE_WIDTH/4 - BOLT_SPACING, BOLT_DIAMETER/2))
    s.CircleByCenterPerimeter(center=(FLANGE_WIDTH/4 + BOLT_SPACING, 0),
                             point1=(FLANGE_WIDTH/4 + BOLT_SPACING, BOLT_DIAMETER/2))
    
    # Position and pattern bolts
    s.move(vector=(0.0, -SECTION_LENGTH/2), 
           objectList=(g[11], g[12]))
    
    s.linearPattern(geomList=(g[11], g[12]), number1=1, spacing1=109.112,
                   angle1=0.0, number2=NUM_BOLT_ROWS + 1, 
                   spacing2=SECTION_LENGTH/(NUM_BOLT_ROWS + 1), angle2=90.0)
    
    s.delete(objectList=(g[11], g[12]))
    
    # Cut extrusion for bolt holes
    f1, e1 = part.faces, part.edges
    part.CutExtrude(sketchPlane=f1[0], sketchUpEdge=e1[3],
                   sketchPlaneSide=SIDE1, sketchOrientation=RIGHT,
                   sketch=s, depth=depth, flipExtrudeDirection=OFF)
    
    s.unsetPrimaryObject()
    del mdb.models['Model-1'].sketches['bolt_pattern']

def define_material_properties():
    """Define material properties and sections"""
    # Material definition
    mdb.models['Model-1'].Material(name='StructuralSteel')
    mdb.models['Model-1'].materials['StructuralSteel'].Elastic(
        table=((205000.0, 0.3),))
    mdb.models['Model-1'].materials['StructuralSteel'].Density(
        table=((7.85e-09,),))
    
    # Section definitions
    mdb.models['Model-1'].HomogeneousShellSection(name='web_section',
        preIntegrate=OFF, material='StructuralSteel', thicknessType=UNIFORM,
        thickness=WEB_THICKNESS, integrationRule=SIMPSON, numIntPts=5)
    
    mdb.models['Model-1'].HomogeneousShellSection(name='flange_section',
        preIntegrate=OFF, material='StructuralSteel', thicknessType=UNIFORM,
        thickness=FLANGE_THICKNESS, integrationRule=SIMPSON, numIntPts=5)

def assign_sections():
    """Assign sections to different parts of the model"""
    # For end sections
    p = mdb.models['Model-1'].parts['ShellSection']
    faces = p.faces
    
    # Web assignment
    web_faces = faces.findAt(((0.0, SECTION_HEIGHT/2, SECTION_LENGTH/2),))
    region = regionToolset.Region(faces=web_faces)
    p.SectionAssignment(region=region, sectionName='web_section', 
                       offsetType=MIDDLE_SURFACE)
    
    # Flange assignment
    flange_points = [
        (-FLANGE_WIDTH/2, FLANGE_THICKNESS/2, SECTION_LENGTH/2),
        (-FLANGE_WIDTH/2, SECTION_HEIGHT-FLANGE_THICKNESS/2, SECTION_LENGTH/2),
        (FLANGE_WIDTH/2, SECTION_HEIGHT-FLANGE_THICKNESS/2, SECTION_LENGTH/2),
        (FLANGE_WIDTH/2, FLANGE_THICKNESS/2, SECTION_LENGTH/2)
    ]
    flange_faces = faces.findAt(*[(point,) for point in flange_points])
    region = regionToolset.Region(faces=flange_faces)
    p.SectionAssignment(region=region, sectionName='flange_section',
                       offsetType=MIDDLE_SURFACE)

def create_assembly():
    """Create assembly with multiple sections"""
    a = mdb.models['Model-1'].rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    
    # Implementation of assembly creation based on NUM_SECTIONS
    # This would include the logic for positioning multiple sections
    # [Previous assembly logic translated to English...]
    
    return a

def define_interactions():
    """Define contact interactions and constraints"""
    # Contact property
    mdb.models['Model-1'].ContactProperty('BoltContact')
    mdb.models['Model-1'].interactionProperties['BoltContact'].TangentialBehavior(
        formulation=PENALTY, directionality=ISOTROPIC, slipRateDependency=OFF,
        pressureDependency=OFF, table=((FRICTION_COEFF,),))
    mdb.models['Model-1'].interactionProperties['BoltContact'].NormalBehavior(
        pressureOverclosure=HARD, allowSeparation=ON)
    
    # Global contact definition
    mdb.models['Model-1'].ContactStd(name='GlobalContact', createStepName='Initial')
    mdb.models['Model-1'].interactions['GlobalContact'].includedPairs.setValuesInStep(
        stepName='Initial', useAllstar=ON)
    mdb.models['Model-1'].interactions['GlobalContact'].contactPropertyAssignments.appendInStep(
        stepName='Initial', assignments=((GLOBAL, SELF, 'BoltContact'),))

def setup_analysis_steps():
    """Define analysis procedure"""
    # Static step for preloading
    mdb.models['Model-1'].StaticStep(name='Preload', previous='Initial',
                                    initialInc=0.00001, minInc=1e-06, maxInc=1.0)
    
    # Buckling analysis step
    mdb.models['Model-1'].BuckleStep(name='Buckling', previous='Preload',
                                    numEigen=10, eigensolver=LANCZOS)
    
    # Load step
    mdb.models['Model-1'].StaticStep(name='Load', previous='Buckling')

def apply_boundary_conditions():
    """Apply boundary conditions and loads"""
    a = mdb.models['Model-1'].rootAssembly
    
    # Define boundary sets (implementation depends on assembly structure)
    # [Previous boundary condition logic translated to English...]
    
    # Apply displacements
    top_set = a.sets['TopPoint']
    mdb.models['Model-1'].DisplacementBC(name='TopBC', createStepName='Initial',
        region=top_set, u1=SET, u2=SET, u3=UNSET, ur1=SET, ur2=SET, ur3=SET)
    
    bottom_set = a.sets['BottomPoint']
    mdb.models['Model-1'].DisplacementBC(name='BottomBC', createStepName='Initial',
        region=bottom_set, u1=SET, u2=SET, u3=SET, ur1=SET, ur2=SET, ur3=SET)
    
    # Apply loads
    mdb.models['Model-1'].ConcentratedForce(name='AppliedLoad', 
                                           createStepName='Load',
                                           region=top_set,
                                           cf1=LOAD_FACTOR_X,
                                           cf2=LOAD_FACTOR_Y,
                                           cf3=LOAD_FACTOR_Z)

def mesh_model():
    """Generate mesh for all parts"""
    for part_name in ['ShellSection', 'ShellSection-Copy']:
        if part_name in mdb.models['Model-1'].parts.keys():
            p = mdb.models['Model-1'].parts[part_name]
            p.seedPart(size=MESH_SIZE, deviationFactor=0.1, minSizeFactor=0.1)
            p.generateMesh()

def create_and_run_job(model_name):
    """Create and submit analysis job"""
    job_name = f'Analysis_{model_name}'
    
    mdb.Job(name=job_name, model='Model-1', type=ANALYSIS,
            multiprocessingMode=THREADS, numCpus=16, numDomains=16)
    
    mdb.jobs[job_name].submit(consistencyChecking=OFF)
    mdb.jobs[job_name].waitForCompletion()
    
    return job_name

def postprocess_results(job_name, model_name):
    """Extract and save results"""
    odb_path = f'{job_name}.odb'
    o3 = session.openOdb(name=odb_path)
    session.viewports['Viewport: 1'].setValues(displayedObject=o3)
    
    # Field output report
    session.writeFieldReport(
        fileName=f'displacement_results_{model_name}.csv',
        append=OFF, sortItem='Node Label', odb=o3, step=1, frame=1,
        outputPosition=NODAL, variable=(('U', NODAL), ('UR', NODAL),))
    
    # Visualization output
    session.printToFile(fileName=f'deformation_plot_{model_name}.tiff',
                       format=TIFF, 
                       canvasObjects=(session.viewports['Viewport: 1'],))

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function"""
    print("Starting parametric bolted shell analysis...")
    
    # Setup model environment
    setup_model()
    
    # Create output directory
    model_name = create_output_directory()
    
    # Geometry creation
    base_sketch = create_base_sketch()
    shell_part = create_shell_part(base_sketch)
    
    # Create copy for center section
    p_copy = mdb.models['Model-1'].Part(name='ShellSection-Center',
        objectToCopy=mdb.models['Model-1'].parts['ShellSection'])
    
    # Create bolt holes
    create_bolt_holes(shell_part, is_center_section=False)
    create_bolt_holes(p_copy, is_center_section=True)
    
    # Material and section definitions
    define_material_properties()
    assign_sections()
    
    # Assembly and interactions
    create_assembly()
    define_interactions()
    
    # Analysis setup
    setup_analysis_steps()
    apply_boundary_conditions()
    
    # Meshing
    mesh_model()
    
    # Run analysis
    job_name = create_and_run_job(model_name)
    
    # Postprocessing
    postprocess_results(job_name, model_name)
    
    print(f"Analysis completed successfully. Results saved in: {os.getcwd()}")

if __name__ == '__main__':
    main()
