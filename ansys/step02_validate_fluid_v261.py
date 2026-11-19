# Python Script, API Version = V261
# Read-only fluid-domain checks for the open Step 1 SpaceClaim document.
# Run this in SpaceClaim 2026 R1 with step01_geometry_v261.scdocx open.

import os
from SpaceClaim.Api.V261 import Window, Geometry

REPORT_PATH = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step02_fluid_validation.txt')
TOL_MM = 0.01
TOL_MM3 = 0.5


def near(a, b, tolerance=TOL_MM):
    return abs(a - b) <= tolerance


def bounds_mm(shape):
    box = shape.GetBoundingBox(Geometry.Matrix.Identity)
    a, b = box.MinCorner, box.MaxCorner
    return (a.X * 1000.0, a.Y * 1000.0, a.Z * 1000.0,
            b.X * 1000.0, b.Y * 1000.0, b.Z * 1000.0)


def port_faces(fluid_shape, x, y0, y1, z0, z1):
    matches = []
    for face in fluid_shape.Faces:
        q = bounds_mm(face)
        area_mm2 = face.Area * 1e6
        if (near(q[0], x) and near(q[3], x)
                and near(q[1], y0) and near(q[4], y1)
                and near(q[2], z0) and near(q[5], z1)
                and near(area_mm2, 32.0, 0.01)):
            matches.append(face)
    return matches


def main():
    part = Window.ActiveWindow.ActiveContext.ActivePart
    bodies = list(part.Bodies)
    by_name = dict((body.Name, body) for body in bodies)
    expected_names = (["ColdPlate_Base_Al", "ColdPlate_Lid_Al", "Fluid_Water"]
                      + ["Cell_R%d_C%d" % (r, c)
                         for r in range(1, 3) for c in range(1, 7)])
    if len(bodies) != 15 or sorted(by_name) != sorted(expected_names):
        raise RuntimeError("Expected exactly 15 uniquely named Step 1 bodies; found %d." % len(bodies))

    fluid = by_name["Fluid_Water"].Shape
    base = by_name["ColdPlate_Base_Al"].Shape
    lid = by_name["ColdPlate_Lid_Al"].Shape
    fluid_volume = fluid.Volume * 1e9  # m^3 -> mm^3
    base_volume = base.Volume * 1e9
    lid_volume = lid.Volume * 1e9
    pieces = fluid.Copy().SeparatePieces()
    fluid_box = bounds_mm(fluid)
    lid_box = bounds_mm(lid)

    checks = [
        ("All 15 bodies are closed solids", all(body.Shape.IsClosed for body in bodies)),
        ("Fluid is one connected piece", len(pieces) == 1),
        ("Fluid volume is 53098.48 mm^3", near(fluid_volume, 53098.477193, TOL_MM3)),
        ("Base volume plus fluid volume equals uncut 7 mm base",
         near(base_volume + fluid_volume, 192.0 * 204.0 * 7.0, TOL_MM3)),
        ("Lid volume is 192 x 204 x 3 mm^3",
         near(lid_volume, 192.0 * 204.0 * 3.0, TOL_MM3)),
        ("Fluid Z limits are 3..7 mm", near(fluid_box[2], 3.0) and near(fluid_box[5], 7.0)),
        ("Lid Z limits are 7..10 mm", near(lid_box[2], 7.0) and near(lid_box[5], 10.0)),
        ("One 8 x 4 mm inlet face exists at x=0, y=18..26 mm",
         len(port_faces(fluid, 0.0, 18.0, 26.0, 3.0, 7.0)) == 1),
        ("One 8 x 4 mm outlet face exists at x=192, y=178..186 mm",
         len(port_faces(fluid, 192.0, 178.0, 186.0, 3.0, 7.0)) == 1),
        ("All cell bottoms touch the lid top at z=10 mm",
         all(near(bounds_mm(by_name["Cell_R%d_C%d" % (r, c)].Shape)[2], 10.0)
             for r in range(1, 3) for c in range(1, 7))),
    ]

    lines = ["Step 2 fluid-domain validation (SpaceClaim V261)",
             "Bodies: %d; connected fluid pieces: %d" % (len(bodies), len(pieces)),
             "Fluid volume: %.3f mm^3; base: %.3f mm^3; lid: %.3f mm^3" %
             (fluid_volume, base_volume, lid_volume)]
    for label, passed in checks:
        lines.append(("PASS" if passed else "FAIL") + " - " + label)
    lines.append("Overall: " + ("PASS" if all(passed for _, passed in checks) else "FAIL"))
    with open(REPORT_PATH, "w") as report:
        report.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("Report: " + REPORT_PATH)
    if any(not passed for _, passed in checks):
        raise RuntimeError("Step 2 validation failed; see the report.")


main()
