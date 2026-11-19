"""Fluent 2026 R1 Python journal: converge one mesh-study case.

CODEX_MESH_LEVEL is coarse/fine. Start from independently initialized data.
Check residuals, source integration, conservation and checkpoint stability.
Write results after each 100 second-order iterations for recoverability.
"""
import os
import json
import re
from ansys.units import VariableCatalog
if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    globals().update(pyfluent.setup_for_fluent(product_version="26.1.0", mode="solver",
        dimension=3, precision="double", processor_count=4,
        ui_mode="no_gui_or_graphics", graphics_driver="null", gpu=False))
ROOT = os.environ["COLDPLATE_RUN_DIR"]
LEVEL = os.environ["CODEX_MESH_LEVEL"]
assert LEVEL in ("coarse", "fine")
solver.settings.file.read_case_data(file_name=ROOT + "/step12_" + LEVEL + "_initialized.cas.h5")
sol = solver.settings.solution
criteria = {"continuity": 1e-4, "x-velocity": 1e-4, "y-velocity": 1e-4,
            "z-velocity": 1e-4, "energy": 1e-7, "k": 1e-4, "omega": 1e-4}
# Fixed checkpoint lengths let us check stability even after residual stopping.
for equation in criteria:
    sol.monitor.residual.equations[equation].check_convergence.set_state(False)
print("STEP12 WARMUP START", LEVEL)
sol.run_calculation.iterate(iter_count=50)
disc = sol.methods.spatial_discretization.discretization_scheme
disc["pressure"].set_state("second-order")
for field in ("mom", "k", "omega", "temperature"):
    disc[field].set_state("second-order-upwind")
sol.methods.pseudo_time_method.formulation.segregated_solver.set_state("local-time-step")

setup = solver.settings.setup
reduction = solver.fields.reduction
cells = [setup.cell_zone_conditions.solid["cell_r%d_c%d" % (row,col)]
         for row in (1,2) for col in range(1,7)]
inlet = setup.boundary_conditions.mass_flow_inlet["water_inlet"]
outlet = setup.boundary_conditions.pressure_outlet["water_outlet"]
wet_walls = [setup.boundary_conditions.wall[n] for n in ("water_wall_base", "water_wall_lid")]

def residuals_from_log():
    # The launcher's stdout file contains Fluent's native iteration table.
    path = ROOT + "/step12_" + LEVEL + "_solve_stdout.txt"
    with open(path, encoding="utf-8", errors="replace") as stream:
        lines = stream.readlines()
    last = None
    for line in lines:
        parts = line.split()
        if len(parts) < 8 or not parts[0].isdigit():
            continue
        try:
            values = [float(v) for v in parts[1:8]]
        except ValueError:
            continue
        last = dict(zip(criteria, values))
        last["iteration"] = int(parts[0])
    return last

def metrics(iteration):
    temperature = VariableCatalog.TEMPERATURE
    pressure = VariableCatalog.STATIC_PRESSURE
    data = {"level": LEVEL, "iteration": iteration,
        "battery_Tmax_K": float(reduction.maximum(temperature, locations=cells)),
        "battery_Tmin_K": float(reduction.minimum(temperature, locations=cells)),
        "outlet_T_massavg_K": float(reduction.mass_flow_average(temperature, locations=[outlet])),
        "inlet_P_areaavg_Pa": float(reduction.area_average(pressure, locations=[inlet])),
        "outlet_P_areaavg_Pa": float(reduction.area_average(pressure, locations=[outlet])),
        "inlet_mass_flow_kg_s": float(reduction.mass_flow_integral(expression="1", locations=[inlet])),
        "outlet_mass_flow_kg_s": float(reduction.mass_flow_integral(expression="1", locations=[outlet]))}
    data["battery_dT_K"] = data["battery_Tmax_K"] - data["battery_Tmin_K"]
    data["pressure_drop_Pa"] = data["inlet_P_areaavg_Pa"] - data["outlet_P_areaavg_Pa"]
    m_in = abs(data["inlet_mass_flow_kg_s"])
    m_out = abs(data["outlet_mass_flow_kg_s"])
    data["mass_imbalance_fraction"] = abs(m_in-m_out)/m_in
    data["Q_source_total_W"] = sum(float(reduction.volume(locations=[zone])) *
        zone.sources.terms["energy"][0].value.get_state() for zone in cells)
    data["Q_water_W"] = m_out * 4181.44618 * (data["outlet_T_massavg_K"]-298.15)
    data["energy_imbalance_fraction"] = abs(data["Q_water_W"]-data["Q_source_total_W"])/240.0
    data["residuals"] = residuals_from_log()
    return data

history = []
accepted = False
for checkpoint in range(150, 1151, 100):
    sol.run_calculation.iterate(iter_count=100)
    current = metrics(checkpoint)
    if history:
        previous = history[-1]
        current["change_Tmax_K"] = abs(current["battery_Tmax_K"]-previous["battery_Tmax_K"])
        current["change_pressure_fraction"] = abs(current["pressure_drop_Pa"]-previous["pressure_drop_Pa"])/abs(current["pressure_drop_Pa"])
        current["all_checks_met"] = bool(current["residuals"] and
            current["residuals"]["iteration"] == checkpoint and
            all(current["residuals"][n] <= limit for n,limit in criteria.items()) and
            current["mass_imbalance_fraction"] <= 0.002 and
            current["energy_imbalance_fraction"] <= 0.01 and
            current["change_Tmax_K"] <= 0.1 and current["change_pressure_fraction"] <= 0.01)
    history.append(current)
    with open(ROOT + "/step12_" + LEVEL + "_convergence_history.json", "w", encoding="utf-8") as stream:
        json.dump(history, stream, indent=2)
    solver.settings.file.write_case_data(file_name=ROOT + "/step12_" + LEVEL + "_checkpoint.cas.h5")
    print("STEP12 CHECKPOINT", current, flush=True)
    if current.get("all_checks_met"):
        accepted = True
        break

for equation in criteria:
    sol.monitor.residual.equations[equation].check_convergence.set_state(True)
solver.settings.file.write_case_data(file_name=ROOT + "/step12_" + LEVEL + "_final.cas.h5")
with open(ROOT + "/step12_" + LEVEL + "_metrics.json", "w", encoding="utf-8") as stream:
    json.dump(history[-1], stream, indent=2)
print("STEP12 SOLVE COMPLETE", LEVEL, "accepted=", accepted)
# Print area-average/minimum/maximum y+ using actual local command signatures.
reports = solver.settings.results.report.surface_integrals
print("STEP12 YPLUS REPORT API", [n for n in dir(reports) if "average" in n or "minimum" in n or "maximum" in n])
for command in ("area_weighted_avg", "minimum", "maximum"):
    if command in dir(reports):
        try:
            getattr(reports, command)(report_of="y-plus", surface_names=["water_wall_base", "water_wall_lid"])
        except Exception as exc:
            print("STEP12 YPLUS REPORT ISSUE", command, repr(exc))
solver.exit()
