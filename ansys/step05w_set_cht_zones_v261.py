# Ansys Meshing Python (2026 R1): define CFD phase per imported body.
# Run through step05w_set_cht_zones_v261.wbjn, not in Fluent or SpaceClaim.
import os
import traceback

REPORT = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step05w_cht_zone_meshing.txt')

def log(message):
    with open(REPORT, "a") as output:
        output.write(str(message) + "\n")

with open(REPORT, "w") as output:
    output.write("START CHT phase classification\n")

try:
    bodies = list(Model.Geometry.GetChildren(DataModelObjectCategory.Body, True))
    if len(bodies) != 15:
        raise RuntimeError("Expected 15 bodies, found %s" % len(bodies))
    fluid_count = 0
    solid_count = 0
    for body in bodies:
        phase_enum = type(body.FluidSolidPhase)
        if body.Name == "Fluid_Water":
            body.FluidSolidPhase = phase_enum.LiquidGas
            fluid_count += 1
        elif body.Name.startswith("Cell_") or body.Name in ("ColdPlate_Base_Al", "ColdPlate_Lid_Al"):
            body.FluidSolidPhase = phase_enum.Solid
            solid_count += 1
        else:
            raise RuntimeError("Unexpected body: " + body.Name)
        log("%s = %s" % (body.Name, body.FluidSolidPhase))
    if fluid_count != 1 or solid_count != 14:
        raise RuntimeError("Wrong classification: fluid=%s solid=%s" % (fluid_count, solid_count))
    Model.Mesh.GenerateMesh()
    mesh_data = ExtAPI.DataModel.MeshDataByName("Global")
    log("Mesh state=%s nodes=%s elements=%s" % (Model.Mesh.State, mesh_data.NodeCount, mesh_data.ElementCount))
    log("SUCCESS")
except Exception:
    log("ERROR\n" + traceback.format_exc())
