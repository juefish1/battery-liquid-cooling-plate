"""Test local pseudo-time stepping on a separate Fluent 2026 R1 checkpoint.

This remains a steady pressure-based SIMPLE calculation. The original 450
iteration case/data is left unchanged so the trial can be compared or reverted.
"""
import os
from ansys.units import VariableCatalog

if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    globals().update(pyfluent.setup_for_fluent(
        product_version="26.1.0", mode="solver", dimension=3,
        precision="double", processor_count=1,
        ui_mode="no_gui_or_graphics", graphics_driver="null", gpu=False))

BASE = os.environ["COLDPLATE_RUN_DIR"]
INPUT = "step10_second_order_450_v261"
OUTPUT = "step10_pseudotime_500_v261"
solver.settings.file.read_case_data(file_name=BASE + "/" + INPUT + ".cas.h5")
methods = solver.settings.solution.methods
assert methods.p_v_coupling.flow_scheme.get_state() == "SIMPLE"
assert methods.pseudo_time_method.formulation.segregated_solver.get_state() == "off"
methods.pseudo_time_method.formulation.segregated_solver.set_state("local-time-step")
print("STEP10 PSEUDOTIME STATE", methods.pseudo_time_method.get_state())
solver.settings.solution.run_calculation.iterate(iter_count=50)

inlet = solver.settings.setup.boundary_conditions.mass_flow_inlet["water_inlet"]
outlet = solver.settings.setup.boundary_conditions.pressure_outlet["water_outlet"]
cells = [solver.settings.setup.cell_zone_conditions.solid[
    "cell_r%d_c%d" % (row, col)] for row in (1, 2) for col in range(1, 7)]
r = solver.fields.reduction
p_drop = float(r.area_average(VariableCatalog.STATIC_PRESSURE, locations=[inlet])
               - r.area_average(VariableCatalog.STATIC_PRESSURE, locations=[outlet]))
t_max = float(r.maximum(VariableCatalog.TEMPERATURE, locations=cells))
print("STEP10 PSEUDOTIME METRICS", "pressure_drop_Pa=", p_drop,
      "battery_Tmax_K=", t_max)
solver.settings.file.write_case_data(file_name=BASE + "/" + OUTPUT + ".cas.h5")
print("STEP10 PSEUDOTIME saved", OUTPUT)
solver.exit()
