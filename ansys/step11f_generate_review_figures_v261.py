"""Generate five Step 11 Fluent 2026 R1 review contours from the final case/data.

Run inside Fluent Solver Python journal with 3ddp -gu -t1.  It changes only
postprocessing surfaces, contour objects, and the graphics view.  All image
coordinates and iso values use Fluent SI units (metres).
"""
import os

if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    globals().update(pyfluent.setup_for_fluent(
        product_version="26.1.0", mode="solver", dimension=3,
        precision="double", processor_count=1,
        ui_mode="no_gui", graphics_driver="null", gpu=False))

BASE = os.environ["COLDPLATE_RUN_DIR"]
CASE = BASE + "/step10_pseudotime_551_v261.cas.h5"
solver.settings.file.read_case_data(file_name=CASE)
print("STEP11 CASE READ", CASE)

# Restrict each cutting surface to its physical cell zone.  In particular,
# water contours must not sample the neighbouring aluminium solid.
iso = solver.settings.results.surfaces.iso_surface
for name, z_value, zone_name in (
    ("step11_water_z5mm_review", 0.005, "water_volume"),
    ("step11_lid_z9mm_review", 0.009, "plate_lid_al"),
):
    iso.create(name=name)
    surface = iso[name]
    surface.field.set_state("z-coordinate")
    surface.iso_values.set_state([z_value])
    surface.zones.set_state([zone_name])
    assert surface.get_state()["zones"] == [zone_name]
    print("STEP11 SURFACE", name, surface.get_state())
    print("STEP11 SURFACE INFO", name,
          solver.fields.field_info.get_surfaces_info().get(name))

graphics = solver.settings.results.graphics
graphics.picture.x_resolution.set_state(1800)
graphics.picture.y_resolution.set_state(1400)
graphics.picture.invert_background.set_state(True)

# Remove floor grid and fake reflection from the Fluent presentation scene.
effects = solver.tui.preferences.graphics.graphics_effects
for effect_name in ("grid_plane_enabled", "reflections_enabled",
                    "simple_shadows_enabled"):
    if effect_name in dir(effects):
        getattr(effects, effect_name)(False)

camera = solver.tui.display.views.camera

def set_view(mode, z_height):
    if mode == "plan":
        camera.target(0.096, 0.102, z_height)
        camera.position(0.096, 0.102, z_height + 0.5)
        camera.up_vector(0, 1, 0)
    else:
        # A three-dimensional view exposes all twelve upright cell bodies.
        camera.target(0.096, 0.102, 0.084)
        camera.position(0.42, -0.34, 0.39)
        camera.up_vector(0, 0, 1)
    try:
        graphics.views.camera.projection.set_state("orthographic")
    except Exception as exc:
        print("STEP11 PROJECTION UNCHANGED", repr(exc))
    solver.tui.display.views.auto_scale()

cell_walls = ["wall-cell_r%d_c%d" % (row, col)
              for row in (1, 2) for col in range(1, 7)]
# The contour object's allowed-values query checks that every requested
# battery wall exists in this specific final case.
graphics.contour.create(name="step11_check_surfaces")
allowed = set(graphics.contour["step11_check_surfaces"].surfaces_list.allowed_values())
assert set(cell_walls).issubset(allowed), sorted(set(cell_walls) - allowed)

figure_specs = (
    ("Cell_T", "temperature", cell_walls, "battery", 0.084,
     "step11_review_battery_temperature.png", "%0.1f"),
    ("Plate_T", "temperature", ["step11_lid_z9mm_review"], "plan", 0.009,
     "step11_review_plate_temperature.png", "%0.2f"),
    ("Water_T", "temperature", ["step11_water_z5mm_review"], "plan", 0.005,
     "step11_review_water_temperature.png", "%0.2f"),
    ("Water_U", "velocity-magnitude", ["step11_water_z5mm_review"], "plan", 0.005,
     "step11_review_water_velocity.png", "%0.2f"),
    ("Water_P", "pressure", ["step11_water_z5mm_review"], "plan", 0.005,
     "step11_review_water_pressure.png", "%0.0f"),
)

for object_name, field_name, surfaces, view_mode, z_value, filename, label_format in figure_specs:
    graphics.contour.create(name=object_name)
    contour = graphics.contour[object_name]
    contour.field.set_state(field_name)
    contour.surfaces_list.set_state(surfaces)
    contour.range_options.global_range.set_state(False)
    contour.color_map.format.set_state(label_format)
    if "clear" in dir(solver.tui.display):
        solver.tui.display.clear()
    graphics.contour.display(object_name=object_name)
    set_view(view_mode, z_value)
    destination = BASE + "/" + filename
    graphics.picture.save_picture(file_name=destination)
    assert os.path.getsize(destination) > 10000, destination
    print("STEP11 FIGURE SAVED", filename, field_name, surfaces,
          os.path.getsize(destination))

print("STEP11 ALL FIVE FIGURES SAVED")
solver.exit()
