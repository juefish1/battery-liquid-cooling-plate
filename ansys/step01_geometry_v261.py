# Python Script, API Version = V261
# Run inside a NEW, EMPTY Ansys SpaceClaim / Discovery 2026 R1 document.
# All editable dimensions below are in mm. The geometry kernel uses metres.

import os
import math
from System.Collections.Generic import List
from SpaceClaim.Api.V261 import Geometry, Modeler, DesignBody, Window
from SpaceClaim.Api.V261.Scripting.Commands import DocumentSave


# ---- User parameters (mm) ----
CELL_NX = 6
CELL_NY = 2
CELL_X = 27.0                 # upright cell thickness, along X
CELL_Y = 91.0                 # upright cell width, along Y
CELL_Z = 148.0                # upright cell height, along Z
GAP_X = 2.0
GAP_Y = 2.0
PLATE_MARGIN_X = 10.0        # each side of the cell footprint
PLATE_MARGIN_Y = 10.0
PLATE_THICKNESS = 10.0
FLOOR_THICKNESS = 3.0
CHANNEL_HEIGHT = 4.0
LID_THICKNESS = 3.0
CHANNEL_WIDTH = 8.0
CHANNEL_PITCH = 20.0
CHANNEL_LEGS = 9              # odd: inlet at left, outlet at right
END_WALL = 6.0                # minimum aluminium beyond bend outer edge
OUTPUT_PATH = os.path.join(os.environ["COLDPLATE_RUN_DIR"], 'step01_geometry_v261.scdocx')


def metres(mm_value):
    return mm_value / 1000.0


def point(x_mm, y_mm, z_mm):
    return Geometry.Point.Create(metres(x_mm), metres(y_mm), metres(z_mm))


def box_shape(x0, y0, z0, dx, dy, dz):
    centre = point(x0 + dx / 2.0, y0 + dy / 2.0, z0)
    frame = Geometry.Frame.Create(centre, Geometry.Direction.DirX, Geometry.Direction.DirY)
    plane = Geometry.Plane.Create(frame)
    profile = Geometry.RectangleProfile(
        plane, metres(dx), metres(dy), Geometry.PointUV.Create(0, 0), 0)
    return Modeler.Body.ExtrudeProfile(profile, metres(dz))


def add_line(path, x0, y0, x1, y1, z):
    path.Add(Geometry.CurveSegment.Create(point(x0, y0, z), point(x1, y1, z)))


def add_turn(path, x_centre, y_centre, radius, bulge_right, z):
    x_dir = Geometry.Direction.DirX if bulge_right else -Geometry.Direction.DirX
    frame = Geometry.Frame.Create(point(x_centre, y_centre, z),
                                  x_dir, Geometry.Direction.DirY)
    circle = Geometry.Circle.Create(frame, metres(radius))
    path.Add(Geometry.CurveSegment.Create(
        circle, Geometry.Interval.Create(-math.pi / 2.0, math.pi / 2.0)))


def make_channel_shape(plate_x, plate_y):
    # All path segments meet tangentially. The rectangular section stays
    # normal to the XY-plane centreline during the sweep.
    radius = CHANNEL_PITCH / 2.0
    outer_radius = radius + CHANNEL_WIDTH / 2.0
    x_left = END_WALL + outer_radius
    x_right = plate_x - x_left
    y_first = (plate_y - (CHANNEL_LEGS - 1) * CHANNEL_PITCH) / 2.0
    z_mid = FLOOR_THICKNESS + CHANNEL_HEIGHT / 2.0

    path = List[Geometry.ITrimmedCurve]()
    for i in range(CHANNEL_LEGS):
        y = y_first + i * CHANNEL_PITCH
        x_start = 0.0 if i == 0 else (x_left if i % 2 == 0 else x_right)
        x_finish = plate_x if i == CHANNEL_LEGS - 1 else (
            x_right if i % 2 == 0 else x_left)
        add_line(path, x_start, y, x_finish, y, z_mid)
        if i < CHANNEL_LEGS - 1:
            add_turn(path, x_finish, y + radius, radius, i % 2 == 0, z_mid)

    section_frame = Geometry.Frame.Create(
        point(0.0, y_first, z_mid), Geometry.Direction.DirY, Geometry.Direction.DirZ)
    section = Geometry.RectangleProfile(
        Geometry.Plane.Create(section_frame),
        metres(CHANNEL_WIDTH), metres(CHANNEL_HEIGHT),
        Geometry.PointUV.Create(0, 0), 0)
    return Modeler.Body.SweepProfile(section, path), x_left, x_right, y_first


def validate_dimensions(plate_x, plate_y, x_left, x_right, y_first):
    radius = CHANNEL_PITCH / 2.0
    outer_radius = radius + CHANNEL_WIDTH / 2.0
    assert CELL_NX > 0 and CELL_NY > 0 and CHANNEL_LEGS >= 3
    assert CHANNEL_LEGS % 2 == 1, "This port layout requires an odd leg count."
    assert min(CELL_X, CELL_Y, CELL_Z, GAP_X, GAP_Y) > 0
    assert abs(PLATE_THICKNESS - FLOOR_THICKNESS - CHANNEL_HEIGHT - LID_THICKNESS) < 1e-9
    assert radius > CHANNEL_WIDTH / 2.0, "Turn inner radius must be positive."
    assert CHANNEL_PITCH - CHANNEL_WIDTH >= CHANNEL_WIDTH, "Straight rib is too thin."
    assert x_right > x_left, "No space for straight channel legs."
    assert x_left - outer_radius >= END_WALL - 1e-9
    assert plate_x - x_right - outer_radius >= END_WALL - 1e-9
    assert y_first - CHANNEL_WIDTH / 2.0 >= END_WALL
    assert plate_y - y_first - (CHANNEL_LEGS - 1) * CHANNEL_PITCH - CHANNEL_WIDTH / 2.0 >= END_WALL


def main():
    # A second run in the same document would create 15 coincident bodies.
    part = Window.ActiveWindow.ActiveContext.ActivePart
    if part.Bodies.Count != 0:
        raise RuntimeError("Open a NEW, EMPTY document before running this script; found %d existing bodies." % part.Bodies.Count)

    module_x = CELL_NX * CELL_X + (CELL_NX - 1) * GAP_X
    module_y = CELL_NY * CELL_Y + (CELL_NY - 1) * GAP_Y
    plate_x = module_x + 2.0 * PLATE_MARGIN_X
    plate_y = module_y + 2.0 * PLATE_MARGIN_Y

    fluid_shape, x_left, x_right, y_first = make_channel_shape(plate_x, plate_y)
    validate_dimensions(plate_x, plate_y, x_left, x_right, y_first)
    path_length_mm = (x_right + plate_x - x_left
                      + (CHANNEL_LEGS - 2) * (x_right - x_left)
                      + (CHANNEL_LEGS - 1) * math.pi * CHANNEL_PITCH / 2.0)
    expected_fluid_mm3 = CHANNEL_WIDTH * CHANNEL_HEIGHT * path_length_mm
    assert abs(fluid_shape.Volume * 1e9 - expected_fluid_mm3) < expected_fluid_mm3 * 1e-5, \
        "Sweep volume differs from width x height x centreline length."

    # Build an open, milled groove in a 7 mm base and cover it with a 3 mm lid.
    # The cutter is a COPY; the original fluid shape is retained as one body.
    base_shape = box_shape(0, 0, 0, plate_x, plate_y,
                           FLOOR_THICKNESS + CHANNEL_HEIGHT)
    base_volume_before = base_shape.Volume
    fluid_volume = fluid_shape.Volume
    cutters = List[Modeler.Body]()
    cutters.Add(fluid_shape.Copy())
    base_shape.Subtract(cutters)
    base_volume_after = base_shape.Volume
    tol = max(1e-11, fluid_volume * 1e-5)
    assert abs((base_volume_before - base_volume_after) - fluid_volume) < tol, \
        "Groove cut failed, or the channel extends outside the plate."

    lid_shape = box_shape(0, 0, FLOOR_THICKNESS + CHANNEL_HEIGHT,
                          plate_x, plate_y, LID_THICKNESS)
    DesignBody.Create(part, "ColdPlate_Base_Al", base_shape)
    DesignBody.Create(part, "ColdPlate_Lid_Al", lid_shape)
    DesignBody.Create(part, "Fluid_Water", fluid_shape)

    for row in range(CELL_NY):
        for col in range(CELL_NX):
            x0 = PLATE_MARGIN_X + col * (CELL_X + GAP_X)
            y0 = PLATE_MARGIN_Y + row * (CELL_Y + GAP_Y)
            cell = box_shape(x0, y0, PLATE_THICKNESS,
                             CELL_X, CELL_Y, CELL_Z)
            DesignBody.Create(part, "Cell_R%d_C%d" % (row + 1, col + 1), cell)

    # 12 cells + base + lid + one connected coolant volume = 15 bodies.
    DocumentSave.Execute(OUTPUT_PATH)
    print("Saved: " + OUTPUT_PATH)
    print("Cell footprint: %.1f x %.1f mm; plate: %.1f x %.1f x %.1f mm" %
          (module_x, module_y, plate_x, plate_y, PLATE_THICKNESS))
    print("Channel length: %.1f mm; fluid volume: %.1f mm^3" %
          (path_length_mm, fluid_volume * 1e9))
    print("Expected body count: %d" % (CELL_NX * CELL_NY + 3))


main()
