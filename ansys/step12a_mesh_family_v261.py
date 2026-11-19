# Ansys Meshing / Mechanical Python 2026 R1, executed by Workbench journal.
# Workbench prepends LEVEL and SCALE. Never run this in Fluent or SpaceClaim.
import os
import traceback
import json

ROOT = os.environ["COLDPLATE_RUN_DIR"]
REPORT = ROOT + "/step12_" + LEVEL + "_meshing.txt"
MESH_FILE = ROOT + "/step12_" + LEVEL + ".msh"

def log(value):
    with open(REPORT, "a") as stream:
        stream.write(str(value) + "\n")

with open(REPORT, "w") as stream:
    stream.write("START Step12 " + LEVEL + "\n")
try:
    assert SCALE in (1.25, 0.8)
    mesh = Model.Mesh
    controls = dict((child.Name, child) for child in mesh.Children)
    sizes = {"water_volume": 0.8, "plate_base_al": 2.0, "plate_lid_al": 1.5}
    for row in (1, 2):
        for col in range(1, 7):
            sizes["cell_r%d_c%d" % (row, col)] = 5.0
    mesh.ElementSize = Quantity("%g [mm]" % (5.0 * SCALE))
    for zone, baseline_mm in sizes.items():
        control = controls["size_" + zone]
        control.ElementSize = Quantity("%g [mm]" % (baseline_mm * SCALE))
        log("%s size=%s" % (zone, control.ElementSize))
    inflation = controls["water_wet_walls_12_layers"]
    inflation.FirstLayerHeight = Quantity("%g [mm]" % (0.01 * SCALE))
    inflation.MaximumLayers = 12
    inflation.GrowthRate = 1.2
    log("Inflation first=%s layers=12 growth=1.2" % inflation.FirstLayerHeight)
    bodies = list(Model.Geometry.GetChildren(DataModelObjectCategory.Body, True))
    assert len(bodies) == 15
    for body in bodies:
        phase = type(body.FluidSolidPhase)
        body.FluidSolidPhase = phase.LiquidGas if body.Name == "Fluid_Water" else phase.Solid
    assert len(Model.NamedSelections.Children) == 20
    mesh.GenerateMesh()
    data = ExtAPI.DataModel.MeshDataByName("Global")
    log("State=%s nodes=%s elements=%s" % (mesh.State, data.NodeCount, data.ElementCount))
    mesh.MeshMetric = MeshMetricType.Skewness
    log("Skewness maximum=%s" % mesh.Maximum)
    counts = {}
    for assembly in ExtAPI.DataModel.GeoData.Assemblies:
        for part in assembly.Parts:
            for body in part.Bodies:
                counts[body.Name] = len(data.MeshRegionById(body.Id).ElementIds)
    log("Body counts=" + str(counts))
    mesh.InternalObject.WriteFluentInputFile(MESH_FILE)
    with open(ROOT + "/step12_" + LEVEL + "_mesh_stats.json", "w") as stream:
        json.dump({"level": LEVEL, "nominal_scale": SCALE,
                   "nodes": int(data.NodeCount), "elements": int(data.ElementCount),
                   "skewness_max": float(str(mesh.Maximum)), "body_elements": counts,
                   "mesh_file": MESH_FILE}, stream, indent=2)
    log("Export=" + MESH_FILE)
    log("SUCCESS")
except Exception:
    log("ERROR\n" + traceback.format_exc())
