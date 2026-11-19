"""Fluent Solver Python 2026 R1: initialize a new mesh with baseline physics.

CODEX_MESH_LEVEL selects coarse/fine. Reuse the already verified Step 6-9
setup scripts, removing only case read/write and exit calls. New mesh is
initialized from scratch; no old solution data is transferred.
"""
import os
import json
if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    globals().update(pyfluent.setup_for_fluent(product_version="26.1.0", mode="solver",
        dimension=3, precision="double", processor_count=4,
        ui_mode="no_gui_or_graphics", graphics_driver="null", gpu=False))
ROOT = os.environ["COLDPLATE_RUN_DIR"]
LEVEL = os.environ["CODEX_MESH_LEVEL"]
assert LEVEL in ("coarse", "fine")
solver.settings.file.read_case(file_name=ROOT + "/step10_pseudotime_551_v261.cas.h5")
reference_models = solver.settings.setup.models.get_state()
reference_materials = solver.settings.setup.materials.get_state()
reference_general = solver.settings.setup.general.get_state()
solver.settings.file.read_case(file_name=ROOT + "/step12_" + LEVEL + ".msh")
print("STEP12 QUALITY BEGIN", LEVEL)
solver.tui.mesh.check()
solver.tui.mesh.quality()
print("STEP12 QUALITY END", LEVEL)
solver.settings.setup.models.energy.enabled.set_state(True)
solver.settings.setup.models.viscous.model.set_state("k-omega")
solver.settings.setup.models.viscous.k_omega_model.set_state("sst")


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

"""Step 7 boundary conditions, Fluent 2026 R1 Python journal (SI units).

Starts from the verified Step 6 case each run and writes a separate Step 7
case. No battery heat source, solver initialization, or iterations are applied.
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
INPUT_CASE = BASE + "/step06_materials_coupled_v261.cas.h5"
OUTPUT_CASE = BASE + "/step07_boundaries_v261.cas.h5"

# Geometry was designed in mm; convert to SI before using Fluent and formulas.
CHANNEL_WIDTH_MM = 8.0
CHANNEL_HEIGHT_MM = 4.0
MASS_FLOW_KG_S = 0.06
INLET_TEMPERATURE_K = 25.0 + 273.15
OUTLET_GAUGE_PRESSURE_PA = 0.0
TURBULENCE_INTENSITY = 0.05  # Fraction in PyFluent, equivalent to 5% in GUI.

width_m = CHANNEL_WIDTH_MM / 1000.0
height_m = CHANNEL_HEIGHT_MM / 1000.0
area_m2 = width_m * height_m
hydraulic_diameter_m = 2.0 * width_m * height_m / (width_m + height_m)
rho_kg_m3 = 997.047013  # Step 6 water at 25 C.
mu_pa_s = 0.000889996774
mean_velocity_m_s = MASS_FLOW_KG_S / (rho_kg_m3 * area_m2)
reynolds = rho_kg_m3 * mean_velocity_m_s * hydraulic_diameter_m / mu_pa_s
print("STEP07 PRECHECK A_m2=%.9g Dh_m=%.9g U_m_s=%.6g Re=%.6g" %
      (area_m2, hydraulic_diameter_m, mean_velocity_m_s, reynolds))

setup = solver.settings.setup
bc = setup.boundary_conditions
assert bc.velocity_inlet.get_object_names() == ["water_inlet"]
assert bc.pressure_outlet.get_object_names() == ["water_outlet"]
assert setup.cell_zone_conditions.fluid["water_volume"].general.material.get_state() == "water_liquid_25c_v1"
assert setup.general.operating_conditions.operating_pressure.get_state() == 101325

# The geometry's inlet was imported as zero-speed velocity-inlet. Change type.
bc.set_zone_type(zone_list=["water_inlet"], new_type="mass-flow-inlet")
inlet = bc.mass_flow_inlet["water_inlet"]
inlet.momentum.mass_flow_rate.value.set_state(MASS_FLOW_KG_S)
inlet.momentum.direction_specification.set_state("Normal to Boundary")
inlet.thermal.total_temperature.value.set_state(INLET_TEMPERATURE_K)
inlet.turbulence.turbulence_specification.set_state("Intensity and Hydraulic Diameter")
inlet.turbulence.turbulent_intensity.set_state(TURBULENCE_INTENSITY)
inlet.turbulence.hydraulic_diameter.set_state(hydraulic_diameter_m)

outlet = bc.pressure_outlet["water_outlet"]
outlet.momentum.gauge_pressure.value.set_state(OUTLET_GAUGE_PRESSURE_PA)
outlet.thermal.backflow_total_temperature.value.set_state(INLET_TEMPERATURE_K)
outlet.turbulence.turbulence_specification.set_state("Intensity and Hydraulic Diameter")
outlet.turbulence.backflow_turbulent_intensity.set_state(TURBULENCE_INTENSITY)
outlet.turbulence.backflow_hydraulic_diameter.set_state(hydraulic_diameter_m)

# Benchmark assumption: exterior cell and plate faces are insulated.
external_walls = ["wall-plate_base_al", "wall-plate_lid_al"] + [
    "wall-cell_r%d_c%d" % (row, col)
    for row in (1, 2) for col in range(1, 7)]
assert set(external_walls).issubset(bc.wall.get_object_names())
for name in external_walls:
    thermal = bc.wall[name].thermal
    thermal.thermal_condition.set_state("Heat Flux")
    thermal.heat_flux.value.set_state(0.0)  # W/m2, adiabatic outer boundary.

# Keep the conjugate walls thermally coupled and water walls stationary/no slip.
coupled_names = [n for n in bc.wall.get_object_names()
                 if n.startswith("cell_bottoms") or n.startswith("water_wall_")]
assert len(coupled_names) == 28, coupled_names
assert all(bc.wall[n].thermal.thermal_condition.get_state() == "Coupled"
           for n in coupled_names)
for name in ("water_wall_base", "water_wall_lid"):
    assert bc.wall[name].momentum.shear_condition.get_state() == "No Slip"
    assert bc.wall[name].momentum.wall_motion.get_state() == "Stationary Wall"

assert inlet.momentum.mass_flow_rate.value.get_state() == MASS_FLOW_KG_S
assert inlet.thermal.total_temperature.value.get_state() == INLET_TEMPERATURE_K
assert outlet.momentum.gauge_pressure.value.get_state() == OUTLET_GAUGE_PRESSURE_PA
assert outlet.thermal.backflow_total_temperature.value.get_state() == INLET_TEMPERATURE_K
assert all(bc.wall[n].thermal.heat_flux.value.get_state() == 0.0
           for n in external_walls)
print("STEP07 CHECK inlet:", inlet.get_state())
print("STEP07 CHECK outlet:", outlet.get_state())
print("STEP07 CHECK exterior adiabatic walls:", len(external_walls))
print("STEP07 CHECK coupled wall zones:", len(coupled_names))
"""Step 8: 20 W uniform heat generation in each of 12 solid cells.

Fluent 2026 R1 Solver Python journal; all source units are W/m3.
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
INPUT_CASE = BASE + "/step07_boundaries_v261.cas.h5"
OUTPUT_CASE = BASE + "/step08_heat_sources_v261.cas.h5"
CELL_HEIGHT_MM = 148.0
CELL_WIDTH_MM = 91.0
CELL_THICKNESS_MM = 27.0
POWER_PER_CELL_W = 20.0

volume_m3 = (CELL_HEIGHT_MM / 1000.0 * CELL_WIDTH_MM / 1000.0
             * CELL_THICKNESS_MM / 1000.0)
source_w_m3 = POWER_PER_CELL_W / volume_m3
zone_names = ["cell_r%d_c%d" % (row, col)
              for row in (1, 2) for col in range(1, 7)]
print("STEP08 PRECHECK Vcell_m3=%.12g q_W_m3=%.12g Qtotal_W=%.6g" %
      (volume_m3, source_w_m3, len(zone_names) * POWER_PER_CELL_W))

setup = solver.settings.setup
solid = setup.cell_zone_conditions.solid
assert set(zone_names).issubset(solid.get_object_names())
assert setup.models.energy.enabled.get_state() is True
for name in zone_names:
    zone = solid[name]
    assert zone.general.material.get_state() == "battery_equiv_iso_v1", name
    zone.sources.enable.set_state(True)
    terms = zone.sources.terms["energy"]
    terms.resize(1)
    terms[0].option.set_state("value")
    terms[0].value.set_state(source_w_m3)

for name in zone_names:
    source = solid[name].sources
    assert source.enable.get_state() is True, name
    assert source.terms["energy"].get_size() == 1, name
    state = source.terms["energy"][0].get_state()
    assert state["option"] == "value" and abs(state["value"] - source_w_m3) < 1e-6, (name, state)
assert all(solid[n].sources.enable.get_state() is False
           for n in ("plate_base_al", "plate_lid_al"))
assert setup.cell_zone_conditions.fluid["water_volume"].sources.enable.get_state() is False
print("STEP08 CHECK assigned cells:", len(zone_names))
print("STEP08 CHECK first source:", solid["cell_r1_c1"].sources.get_state())
print("STEP08 CHECK plates and fluid have no heat source")
"""Step 9: stable startup numerics and hybrid initialization for CHT.

Fluent 2026 R1 Solver Python journal. Produces case and initialized data only;
iteration and convergence assessment belong to Step 10.
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
INPUT_CASE = BASE + "/step08_heat_sources_v261.cas.h5"
OUTPUT_CASE = BASE + "/step09_initialized_v261.cas.h5"
CELL_NAMES = ["cell_r%d_c%d" % (r, c) for r in (1, 2) for c in range(1, 7)]

setup = solver.settings.setup
sol = solver.settings.solution
assert setup.general.solver.time.get_state() == "steady"
assert setup.general.solver.type.get_state() == "pressure-based"
assert setup.models.energy.enabled.get_state() is True
assert setup.models.viscous.k_omega_model.get_state() == "sst"
assert all(setup.cell_zone_conditions.solid[n].sources.enable.get_state()
           for n in CELL_NAMES)

# A robust startup stage for the bent passage and its local low-quality cells.
sol.methods.p_v_coupling.flow_scheme.set_state("SIMPLE")
disc = sol.methods.spatial_discretization.discretization_scheme
disc["pressure"].set_state("standard")
for equation in ("mom", "k", "omega", "temperature"):
    disc[equation].set_state("first-order-upwind")

criteria = {"continuity": 1e-4, "x-velocity": 1e-4,
            "y-velocity": 1e-4, "z-velocity": 1e-4,
            "k": 1e-4, "omega": 1e-4, "energy": 1e-7}
for equation, threshold in criteria.items():
    residual = sol.monitor.residual.equations[equation]
    residual.absolute_criteria.set_state(threshold)
    residual.check_convergence.set_state(True)
sol.monitor.residual.options.print.set_state(True)
sol.monitor.residual.options.plot.set_state(False)
print("STEP09 CHECK method:", sol.methods.get_state()["p_v_coupling"])
print("STEP09 CHECK discretization:", disc.get_state())
print("STEP09 CHECK residual thresholds:",
      {n: sol.monitor.residual.equations[n].absolute_criteria.get_state()
       for n in criteria})

sol.initialization.initialization_type.set_state("hybrid")
print("STEP09 starting hybrid initialization")
sol.initialization.hybrid_initialize()
print("STEP09 hybrid initialization completed")
print("STEP09 actual cell volume report follows:")
solver.settings.results.report.volume_integrals.volume(cell_zones=CELL_NAMES)
setup = solver.settings.setup
sol = solver.settings.solution
# Compare active physical model states and every material with original case.
assert setup.models.get_state() == reference_models, "Physical model state changed"
assert setup.materials.get_state() == reference_materials, "Material state changed"
assert setup.general.get_state() == reference_general, "General solver state changed"
solid = setup.cell_zone_conditions.solid
from ansys.units import VariableCatalog
volumes = {name: float(solver.fields.reduction.volume(locations=[solid[name]]))
           for name in CELL_NAMES}
assert all(abs(v - 0.000363636) < 1e-10 for v in volumes.values())
total_heat = sum(volumes[name] * solid[name].sources.terms["energy"][0].value.get_state()
                 for name in CELL_NAMES)
assert abs(total_heat - 240.0) < 1e-5
verification = {"level": LEVEL, "same_models": True, "same_materials": True,
    "same_general": True, "total_heat_W": total_heat, "cell_volumes_m3": volumes,
    "inlet": setup.boundary_conditions.mass_flow_inlet["water_inlet"].get_state(),
    "outlet": setup.boundary_conditions.pressure_outlet["water_outlet"].get_state()}
with open(ROOT + "/step12_" + LEVEL + "_setup_verification.json", "w", encoding="utf-8") as stream:
    json.dump(verification, stream, indent=2)
solver.settings.file.write_case_data(file_name=ROOT + "/step12_" + LEVEL + "_initialized.cas.h5")
print("STEP12 PREPARED", LEVEL)
solver.exit()
