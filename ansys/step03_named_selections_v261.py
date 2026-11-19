# Python Script, API Version = V261
# Run inside SpaceClaim 2026 R1 with the validated Step 1 model open.
# This script creates Named Selections; it does not set up Fluent physics.

import os
from System.Collections.Generic import List
from SpaceClaim.Api.V261 import Geometry, IDesignBody, IDesignFace, Window
from SpaceClaim.Api.V261.Scripting.Selection import BodySelection, FaceSelection, Selection
from SpaceClaim.Api.V261.Scripting.Commands import NamedSelection, PartLocation, DocumentSave


# Keep these consistent with the Step 1 geometry parameters.
CELL_NX = 6
CELL_NY = 2
CHANNEL_WIDTH_MM = 8.0
CHANNEL_HEIGHT_MM = 4.0
CELL_X_MM = 27.0
CELL_Y_MM = 91.0
TOL_MM = 0.01
TOL_AREA_MM2 = 0.02
OUTPUT_PATH = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step03_named_selections_v261.scdocx')
REPORT_PATH = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step03_named_selections_report.txt')


def near(a, b, tolerance=TOL_MM):
    return abs(a - b) <= tolerance


def bounds_mm(shape):
    box = shape.GetBoundingBox(Geometry.Matrix.Identity)
    a, b = box.MinCorner, box.MaxCorner
    return (a.X * 1000.0, a.Y * 1000.0, a.Z * 1000.0,
            b.X * 1000.0, b.Y * 1000.0, b.Z * 1000.0)


def face_area_mm2(face):
    return face.Shape.Area * 1e6


def body_selection(bodies):
    items = List[IDesignBody]()
    for body in bodies:
        items.Add(body)
    return BodySelection.Create(items)


def face_selection(faces):
    items = List[IDesignFace]()
    for face in faces:
        items.Add(face)
    return FaceSelection.Create(items)


def add_group(name, objects, is_face, report):
    if not objects:
        raise RuntimeError("Cannot create empty Named Selection: " + name)
    selected = face_selection(objects) if is_face else body_selection(objects)
    result = NamedSelection.Create(selected, Selection.Empty(), name,
                                   PartLocation.Root, None)
    group = result.CreatedNamedSelection
    if group is None or group.Name != name or group.Members.Count != len(objects):
        raise RuntimeError("Named Selection failed or has wrong members: " + name)
    report.append("PASS - %-24s %3d %s" %
                  (name, len(objects), "faces" if is_face else "bodies"))


def classify_fluid_faces(fluid, lid, plate_x0, plate_x1):
    inlet, outlet, base_walls, lid_walls = [], [], [], []
    fluid_z0, fluid_z1 = bounds_mm(fluid.Shape)[2], bounds_mm(fluid.Shape)[5]
    lid_bottom = bounds_mm(lid.Shape)[2]
    if not near(fluid_z1, lid_bottom):
        raise RuntimeError("Fluid top and lid bottom are not coincident.")

    for face in fluid.Faces:
        q = bounds_mm(face.Shape)
        area = face_area_mm2(face)
        port_size_ok = (near(q[4] - q[1], CHANNEL_WIDTH_MM)
                        and near(q[5] - q[2], CHANNEL_HEIGHT_MM)
                        and near(q[2], fluid_z0)
                        and near(q[5], fluid_z1)
                        and near(area, CHANNEL_WIDTH_MM * CHANNEL_HEIGHT_MM,
                                 TOL_AREA_MM2))
        if near(q[0], plate_x0) and near(q[3], plate_x0) and port_size_ok:
            inlet.append(face)
        elif near(q[0], plate_x1) and near(q[3], plate_x1) and port_size_ok:
            outlet.append(face)
        elif near(q[2], lid_bottom) and near(q[5], lid_bottom):
            lid_walls.append(face)
        else:
            base_walls.append(face)

    if len(inlet) != 1 or len(outlet) != 1:
        raise RuntimeError("Expected one 8 x 4 mm face at each port; got %d/%d."
                           % (len(inlet), len(outlet)))
    if not base_walls or not lid_walls:
        raise RuntimeError("A fluid-solid wall group is empty.")
    if sum(map(len, (inlet, outlet, base_walls, lid_walls))) != fluid.Faces.Count:
        raise RuntimeError("Fluid face classification is incomplete.")
    if not (max(bounds_mm(f.Shape)[4] for f in inlet)
            < min(bounds_mm(f.Shape)[1] for f in outlet)):
        raise RuntimeError("Inlet and outlet Y positions are reversed or overlap.")
    return inlet, outlet, base_walls, lid_walls


def cell_bottom_faces(cells, plate_top):
    bottoms = []
    for cell in cells:
        matches = []
        for face in cell.Faces:
            q = bounds_mm(face.Shape)
            if (near(q[2], plate_top) and near(q[5], plate_top)
                    and near(face_area_mm2(face), CELL_X_MM * CELL_Y_MM,
                             TOL_AREA_MM2)):
                matches.append(face)
        if len(matches) != 1:
            raise RuntimeError("Expected one lid-contacting bottom face on " + cell.Name)
        bottoms.append(matches[0])
    return bottoms


def main():
    part = Window.ActiveWindow.ActiveContext.ActivePart
    bodies = list(part.Bodies)
    by_name = dict((body.Name, body) for body in bodies)
    cell_names = ["Cell_R%d_C%d" % (row, col)
                  for row in range(1, CELL_NY + 1)
                  for col in range(1, CELL_NX + 1)]
    body_names = ["ColdPlate_Base_Al", "ColdPlate_Lid_Al", "Fluid_Water"] + cell_names
    if len(bodies) != len(body_names) or sorted(by_name) != sorted(body_names):
        raise RuntimeError("Open the validated Step 1 file: expected %d unique bodies."
                           % len(body_names))

    base = by_name["ColdPlate_Base_Al"]
    lid = by_name["ColdPlate_Lid_Al"]
    fluid = by_name["Fluid_Water"]
    cells = [by_name[name] for name in cell_names]
    base_box, lid_box = bounds_mm(base.Shape), bounds_mm(lid.Shape)
    if not near(base_box[5], lid_box[2]):
        raise RuntimeError("Base/lid contact plane is not coincident.")
    if any(not near(bounds_mm(cell.Shape)[2], lid_box[5]) for cell in cells):
        raise RuntimeError("At least one cell does not touch the lid top.")

    inlet, outlet, base_walls, lid_walls = classify_fluid_faces(
        fluid, lid, lid_box[0], lid_box[3])
    bottoms = cell_bottom_faces(cells, lid_box[5])

    body_groups = [("water_volume", [fluid]),
                   ("plate_base_al", [base]),
                   ("plate_lid_al", [lid])]
    body_groups.extend(("cell_r%d_c%d" % (row, col),
                        [by_name["Cell_R%d_C%d" % (row, col)]])
                       for row in range(1, CELL_NY + 1)
                       for col in range(1, CELL_NX + 1))
    face_groups = [("water_inlet", inlet),
                   ("water_outlet", outlet),
                   ("water_wall_base", base_walls),
                   ("water_wall_lid", lid_walls),
                   ("cell_bottoms", bottoms)]
    requested_names = [name for name, _ in body_groups + face_groups]
    existing_names = set(group.Name for group in part.Groups)
    conflicts = sorted(existing_names.intersection(requested_names))
    if conflicts:
        raise RuntimeError("Named Selections already exist: %s. Reopen the clean Step 1 file."
                           % ", ".join(conflicts))

    report = ["Step 3 Named Selections (SpaceClaim V261)",
              "Preflight: %d bodies; %d fluid faces; no target-name conflicts" %
              (len(bodies), fluid.Faces.Count)]
    for name, objects in body_groups:
        add_group(name, objects, False, report)
    for name, objects in face_groups:
        add_group(name, objects, True, report)

    actual_names = set(group.Name for group in part.Groups)
    if not set(requested_names).issubset(actual_names):
        raise RuntimeError("Named Selection names did not persist in the part.")
    report.append("Overall: PASS (%d new groups)" % len(requested_names))
    DocumentSave.Execute(OUTPUT_PATH)
    with open(REPORT_PATH, "w") as output:
        output.write("\n".join(report) + "\n")
    print("\n".join(report))
    print("Saved: " + OUTPUT_PATH)
    print("Report: " + REPORT_PATH)


main()
