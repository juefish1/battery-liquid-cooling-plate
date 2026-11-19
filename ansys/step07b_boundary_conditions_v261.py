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

solver.settings.file.read_case(file_name=INPUT_CASE)
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
solver.settings.file.write_case(file_name=OUTPUT_CASE)
print("STEP07 SAVED:", OUTPUT_CASE)
solver.exit()
