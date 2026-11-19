# Python Script, API Version = V261
# Run inside SpaceClaim 2026 R1 on step03_named_selections_v261.scdocx.
# Shares coincident topology for the 15-body CHT model and saves a new file.

import os
from System.Collections.Generic import List
from SpaceClaim.Api.V261 import IDesignBody, ShareTopologyType, Window
from SpaceClaim.Api.V261.Scripting.Selection import BodySelection
from SpaceClaim.Api.V261.Scripting.Commands import DocumentSave, ShareTopology
from SpaceClaim.Api.V261.Scripting.Commands.CommandOptions import ShareTopologyOptions


CELL_NX = 6
CELL_NY = 2
OUTPUT_PATH = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step04a_shared_topology_v261.scdocx')
REPORT_PATH = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step04a_shared_topology_report.txt')
VOLUME_TOL_MM3 = 0.1
AREA_REL_TOL = 1e-5
SHARE_TOLERANCE_MM = 0.02  # Exact CAD interfaces; far below the 2 mm cell gap.


def expected_names():
    cells = ["Cell_R%d_C%d" % (row, col)
             for row in range(1, CELL_NY + 1)
             for col in range(1, CELL_NX + 1)]
    bodies = ["ColdPlate_Base_Al", "ColdPlate_Lid_Al", "Fluid_Water"] + cells
    groups = ["water_volume", "plate_base_al", "plate_lid_al"]
    groups += ["cell_r%d_c%d" % (row, col)
               for row in range(1, CELL_NY + 1)
               for col in range(1, CELL_NX + 1)]
    face_groups = ["water_inlet", "water_outlet", "water_wall_base",
                   "water_wall_lid", "cell_bottoms"]
    return bodies, groups, face_groups


def face_group_area_mm2(group):
    return sum(member.Shape.Area * 1e6 for member in group.Members)


def main():
    part = Window.ActiveWindow.ActiveContext.ActivePart
    bodies = list(part.Bodies)
    body_names, body_group_names, face_group_names = expected_names()
    by_name = dict((body.Name, body) for body in bodies)
    groups = dict((group.Name, group) for group in part.Groups)
    if len(bodies) != len(body_names) or sorted(by_name) != sorted(body_names):
        raise RuntimeError("Expected the 15-body Step 3 geometry; reopen that file.")
    required_groups = body_group_names + face_group_names
    if not set(required_groups).issubset(set(groups)):
        raise RuntimeError("Step 3 Named Selections are missing; reopen the Step 3 file.")
    if any(groups[name].Members.Count != 1 for name in body_group_names):
        raise RuntimeError("A body Named Selection has the wrong member count.")
    if groups["water_inlet"].Members.Count != 1 or groups["water_outlet"].Members.Count != 1:
        raise RuntimeError("Expected one face at each water port.")
    if groups["cell_bottoms"].Members.Count != CELL_NX * CELL_NY:
        raise RuntimeError("Expected one bottom face per cell.")

    volumes_before = dict((name, by_name[name].Shape.Volume * 1e9)
                          for name in body_names)
    face_areas_before = dict((name, face_group_area_mm2(groups[name]))
                             for name in face_group_names)

    # A typed body selection includes all 15 bodies even if some are hidden.
    selected_bodies = List[IDesignBody]()
    for name in body_names:
        selected_bodies.Add(by_name[name])
    options = ShareTopologyOptions()
    options.Tolerance = SHARE_TOLERANCE_MM / 1000.0  # API length unit: m.
    part.ShareTopology = ShareTopologyType.Share
    result = ShareTopology.FindAndFix(BodySelection.Create(selected_bodies), options)
    if not result.Success:
        raise RuntimeError("SpaceClaim ShareTopology.FindAndFix failed; no output saved.")

    bodies_after = dict((body.Name, body) for body in part.Bodies)
    groups_after = dict((group.Name, group) for group in part.Groups)
    if len(bodies_after) != len(body_names) or sorted(bodies_after) != sorted(body_names):
        raise RuntimeError("Body count or names changed during topology sharing.")
    if not set(required_groups).issubset(set(groups_after)):
        raise RuntimeError("A Named Selection disappeared during topology sharing.")
    for name in body_names:
        change = abs(bodies_after[name].Shape.Volume * 1e9 - volumes_before[name])
        if change > VOLUME_TOL_MM3:
            raise RuntimeError("Body volume changed after sharing: " + name)
    for name in face_group_names:
        area_after = face_group_area_mm2(groups_after[name])
        area_before = face_areas_before[name]
        if abs(area_after - area_before) > max(0.01, area_before * AREA_REL_TOL):
            raise RuntimeError("Named Selection area changed after sharing: " + name)
    if part.ShareTopology != ShareTopologyType.Share:
        raise RuntimeError("The part is not marked with Share topology.")

    lines = ["Step 4A shared-topology preparation (SpaceClaim V261)",
             "ShareTopology.FindAndFix: SUCCESS",
             "Bodies retained: %d" % len(bodies_after),
             "Named Selections retained: %d" % len(required_groups)]
    for name in face_group_names:
        group = groups_after[name]
        lines.append("%s: %d faces; %.3f mm^2" %
                     (name, group.Members.Count, face_group_area_mm2(group)))
    lines.append("CAD checks: PASS; conformal mesh must still be checked in Meshing")
    DocumentSave.Execute(OUTPUT_PATH)
    with open(REPORT_PATH, "w") as output:
        output.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("Saved: " + OUTPUT_PATH)
    print("Report: " + REPORT_PATH)


main()
