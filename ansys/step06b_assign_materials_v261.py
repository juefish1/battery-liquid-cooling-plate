"""Step 6 materials for the 12-cell CHT case, Fluent 2026 R1 Python journal.

Run in Fluent 3D double precision SOLUTION mode via -i. Inputs/outputs are
independent case files, so re-running this journal starts from the Step 5 case.
All values below use SI units. This does not apply heat sources or boundaries.
"""
import os

if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    flglobals = pyfluent.setup_for_fluent(
        product_version="26.1.0", mode="solver", dimension=3,
        precision="double", processor_count=1, ui_mode="no_gui_or_graphics",
        graphics_driver="null", gpu=False)
    globals().update(flglobals)

BASE = os.environ["COLDPLATE_RUN_DIR"]
INPUT_CASE = BASE + "/step05_physics_base_v261.cas.h5"
OUTPUT_CASE = BASE + "/step06_materials_coupled_v261.cas.h5"

# Water at 25 C, 0.1 MPa (NIST). Constant properties for the first pass.
WATER = {
    "density": 997.047013,            # kg/m3
    "specific_heat": 4181.44618,      # J/(kg K)
    "thermal_conductivity": 0.607198237,  # W/(m K)
    "viscosity": 0.000889996774,     # Pa s
}

# Working equivalent battery values; chemistry and vendor properties unknown.
# rho and cp: published 148 x 92 x 27 mm prismatic NCM cell analogue.
# k_iso = geometric mean of published principal values 18.5, 18.5, 1.5 W/(m K).
BATTERY = {
    "density": 2300.0,
    "specific_heat": 1072.0,
    "thermal_conductivity": (18.5 * 18.5 * 1.5) ** (1.0 / 3.0),
}

solver.settings.file.read_case(file_name=INPUT_CASE)
setup = solver.settings.setup
fluid_zones = setup.cell_zone_conditions.fluid.get_object_names()
solid_zones = setup.cell_zone_conditions.solid.get_object_names()
cell_zones = ["cell_r%d_c%d" % (row, col)
              for row in (1, 2) for col in range(1, 7)]
assert fluid_zones == ["water_volume"], fluid_zones
assert len(solid_zones) == 14 and set(cell_zones).issubset(solid_zones), solid_zones
assert {"plate_base_al", "plate_lid_al"}.issubset(solid_zones), solid_zones

water = setup.materials.fluid.create("water_liquid_25c_v1")
for property_name, si_value in WATER.items():
    getattr(water, property_name).value.set_state(si_value)

battery = setup.materials.solid.create("battery_equiv_iso_v1")
battery.chemical_formula.set_state("")  # Do not inherit aluminum's chemical label.
for property_name, si_value in BATTERY.items():
    getattr(battery, property_name).value.set_state(si_value)

setup.cell_zone_conditions.fluid["water_volume"].general.material.set_state(
    "water_liquid_25c_v1")
for zone_name in cell_zones:
    setup.cell_zone_conditions.solid[zone_name].general.material.set_state(
        "battery_equiv_iso_v1")

# Different solid materials may still share interior faces after reassignment.
# Fluent 2026 R1 converts every such face zone into a coupled wall/shadow pair.
setup.boundary_conditions.slit_interior_between_diff_materials()
wall_names = setup.boundary_conditions.wall.get_object_names()
print("STEP06 CHECK wall zone count after slit:", len(wall_names))
print("STEP06 CHECK bottom contact walls:", [n for n in wall_names if "cell_bottom" in n])

# Retain Fluent's generic aluminum (2719, 871, 202.4 SI), verify both plates.
for zone_name in ("plate_base_al", "plate_lid_al"):
    assert setup.cell_zone_conditions.solid[zone_name].general.material.get_state() == "aluminum"

assert setup.cell_zone_conditions.fluid["water_volume"].general.material.get_state() == "water_liquid_25c_v1"
assert all(setup.cell_zone_conditions.solid[n].general.material.get_state() == "battery_equiv_iso_v1"
           for n in cell_zones)
print("STEP06 CHECK: fluid =", fluid_zones, "water_liquid_25c_v1")
print("STEP06 CHECK: batteries =", len(cell_zones), "battery_equiv_iso_v1")
print("STEP06 CHECK: plates = aluminum")
print("STEP06 CHECK water properties:", water.get_state())
print("STEP06 CHECK battery properties:", battery.get_state())
print("STEP06 CHECK aluminum properties:", setup.materials.solid["aluminum"].get_state())

solver.settings.file.write_case(file_name=OUTPUT_CASE)
print("STEP06 SAVED:", OUTPUT_CASE)
solver.exit()
