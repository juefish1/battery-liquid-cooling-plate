"""Fluent 2026 R1 Python journal: converge a flow/heat study case.

CODEX_STUDY_CASE selects the manifest entry. SST uses the solved fine mesh
as a warm start; the Laminar sensitivity case is independently initialized.
Check residuals, source integration, conservation and checkpoint stability.
Write results after each 100 second-order iterations for recoverability.
"""
import os
import json
import re
from pathlib import Path
from ansys.units import VariableCatalog
if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    globals().update(pyfluent.setup_for_fluent(product_version="26.1.0", mode="solver",
        dimension=3, precision="double", processor_count=4,
        ui_mode="no_gui_or_graphics", graphics_driver="null", gpu=False))
ROOT = os.environ["COLDPLATE_RUN_DIR"]
LEVEL = os.environ["CODEX_STUDY_CASE"]
with open(ROOT + "/step13_study_manifest.json", encoding="utf-8") as stream:
    manifest = json.load(stream)
SPEC = next(item for item in manifest["cases"] if item["id"] == LEVEL)
resume_case = ROOT + "/step13_" + LEVEL + "_checkpoint.cas.h5"
RESUMED = Path(resume_case).exists() and Path(resume_case.replace(".cas.h5", ".dat.h5")).exists()
BASE_ADDED = 0
saved_history = []
if RESUMED:
    with open(ROOT + "/step13_" + LEVEL + "_convergence_history.json", encoding="utf-8") as stream:
        saved_history = json.load(stream)
    BASE_ADDED = saved_history[-1]["added_iterations"]
solver.settings.file.read_case_data(file_name=resume_case if RESUMED else ROOT + "/step12_fine_final.cas.h5")
print("STEP13 RESUME", RESUMED, "added iterations", BASE_ADDED)
setup = solver.settings.setup
setup.boundary_conditions.mass_flow_inlet["water_inlet"].momentum.mass_flow_rate.value.set_state(SPEC["mass_flow_kg_s"])
for row in (1,2):
    for col in range(1,7):
        zone = setup.cell_zone_conditions.solid["cell_r%d_c%d" % (row,col)]
        zone.sources.terms["energy"][0].value.set_state(SPEC["power_per_cell_W"]/0.000363636)
if SPEC["model"] == "laminar":
    setup.models.viscous.model.set_state("laminar")
sol = solver.settings.solution
if SPEC["model"] == "laminar" and not RESUMED:
    sol.initialization.hybrid_initialize()
print("STEP13 CONFIGURED", SPEC)
assert setup.boundary_conditions.mass_flow_inlet["water_inlet"].thermal.total_temperature.value.get_state() == 298.15
assert setup.boundary_conditions.pressure_outlet["water_outlet"].momentum.gauge_pressure.value.get_state() == 0.0
assert len(setup.cell_zone_conditions.solid.get_object_names()) == 14
assert setup.cell_zone_conditions.fluid.get_object_names() == ["water_volume"]
criteria = {"continuity": 1e-4, "x-velocity": 1e-4, "y-velocity": 1e-4,
            "z-velocity": 1e-4, "energy": 1e-7, "k": 1e-4, "omega": 1e-4}
if SPEC["model"] == "laminar":
    criteria.pop("k")
    criteria.pop("omega")
# Fixed checkpoint lengths let us check stability even after residual stopping.
for equation in criteria:
    sol.monitor.residual.equations[equation].check_convergence.set_state(False)
print("STEP13 START", LEVEL)
if not RESUMED:
    sol.methods.pseudo_time_method.formulation.segregated_solver.set_state("off")
    startup_disc = sol.methods.spatial_discretization.discretization_scheme
    startup_disc["pressure"].set_state("standard")
    for field in (("mom", "k", "omega", "temperature") if SPEC["model"] == "sst" else ("mom", "temperature")):
        startup_disc[field].set_state("first-order-upwind")
    sol.run_calculation.iterate(iter_count=50)
    BASE_ADDED = 50
disc = sol.methods.spatial_discretization.discretization_scheme
disc["pressure"].set_state("second-order")
for field in (("mom", "k", "omega", "temperature") if SPEC["model"] == "sst" else ("mom", "temperature")):
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
    path = ROOT + "/step13_" + LEVEL + "_solve_stdout.txt"
    raw = Path(path).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    lines = raw.decode(encoding, errors="replace").splitlines()
    last = None
    for line in lines:
        parts = line.split()
        if len(parts) < len(criteria)+1 or not parts[0].isdigit():
            continue
        try:
            values = [float(v) for v in parts[1:len(criteria)+1]]
        except ValueError:
            continue
        last = dict(zip(criteria, values))
        last["iteration"] = int(parts[0])
    return last

def metrics(iteration):
    temperature = VariableCatalog.TEMPERATURE
    pressure = VariableCatalog.STATIC_PRESSURE
    data = {"level": LEVEL, "iteration": iteration, "spec": SPEC,
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
    data["energy_imbalance_fraction"] = abs(data["Q_water_W"]-data["Q_source_total_W"])/data["Q_source_total_W"]
    data["residuals"] = residuals_from_log()
    data["hydraulic_power_W"] = data["pressure_drop_Pa"] * SPEC["mass_flow_kg_s"] / 997.047013
    assert abs(data["Q_source_total_W"]-12*SPEC["power_per_cell_W"]) < 1e-5
    assert abs(abs(data["inlet_mass_flow_kg_s"])-SPEC["mass_flow_kg_s"]) < 1e-6
    return data

history = saved_history
accepted = False
for checkpoint in range(BASE_ADDED + 100, BASE_ADDED + 1601, 100):
    sol.run_calculation.iterate(iter_count=100)
    current = metrics(checkpoint)
    if current["residuals"]:
        current["iteration"] = current["residuals"]["iteration"]
    current["added_iterations"] = checkpoint
    if history:
        previous = history[-1]
        current["change_Tmax_K"] = abs(current["battery_Tmax_K"]-previous["battery_Tmax_K"])
        current["change_pressure_fraction"] = abs(current["pressure_drop_Pa"]-previous["pressure_drop_Pa"])/abs(current["pressure_drop_Pa"])
        current["all_checks_met"] = bool(current["residuals"] and
            all(current["residuals"][n] <= limit for n,limit in criteria.items()) and
            current["mass_imbalance_fraction"] <= 0.002 and
            current["energy_imbalance_fraction"] <= 0.01 and
            current["change_Tmax_K"] <= 0.1 and current["change_pressure_fraction"] <= 0.01)
    history.append(current)
    with open(ROOT + "/step13_" + LEVEL + "_convergence_history.json", "w", encoding="utf-8") as stream:
        json.dump(history, stream, indent=2)
    solver.settings.file.write_case_data(file_name=ROOT + "/step13_" + LEVEL + "_checkpoint.cas.h5")
    print("STEP13 CHECKPOINT", current, flush=True)
    if current.get("all_checks_met"):
        accepted = True
        break

for equation in criteria:
    sol.monitor.residual.equations[equation].check_convergence.set_state(True)
solver.settings.file.write_case_data(file_name=ROOT + "/step13_" + LEVEL + "_final.cas.h5")
with open(ROOT + "/step13_" + LEVEL + "_metrics.json", "w", encoding="utf-8") as stream:
    json.dump(history[-1], stream, indent=2)
print("STEP13 SOLVE COMPLETE", LEVEL, "accepted=", accepted)
# Print area-average/minimum/maximum y+ using actual local command signatures.
reports = solver.settings.results.report.surface_integrals
print("STEP13 YPLUS REPORT API", [n for n in dir(reports) if "average" in n or "minimum" in n or "maximum" in n])
for command in ("area_weighted_avg", "minimum", "maximum"):
    if command in dir(reports):
        try:
            getattr(reports, command)(report_of="y-plus", surface_names=["water_wall_base", "water_wall_lid"])
        except Exception as exc:
            print("STEP13 YPLUS REPORT ISSUE", command, repr(exc))
solver.exit()
