"""Extract Step 11 cell-by-cell temperatures from converged Fluent 2026 R1 data.

Fluent Solver Python journal, run with 3ddp -g -t1. All Fluent temperatures are
read in kelvin; Celsius columns are derived only when writing the report.
"""
import csv
import json
import os
from ansys.units import VariableCatalog

if not os.getenv("FLUENT_PROD_DIR"):
    import ansys.fluent.core as pyfluent
    globals().update(pyfluent.setup_for_fluent(
        product_version="26.1.0", mode="solver", dimension=3,
        precision="double", processor_count=1,
        ui_mode="no_gui_or_graphics", graphics_driver="null", gpu=False))

BASE = os.environ["COLDPLATE_RUN_DIR"]
STEM = "step10_pseudotime_551_v261"
solver.settings.file.read_case_data(file_name=BASE + "/" + STEM + ".cas.h5")
r = solver.fields.reduction
solids = solver.settings.setup.cell_zone_conditions.solid
cell_names = ["cell_r%d_c%d" % (row, col)
              for row in (1, 2) for col in range(1, 7)]
rows = []
for name in cell_names:
    zone = solids[name]
    t_min = float(r.minimum(VariableCatalog.TEMPERATURE, locations=[zone]))
    t_max = float(r.maximum(VariableCatalog.TEMPERATURE, locations=[zone]))
    row = {
        "cell_zone": name,
        "Tmin_K": t_min,
        "Tmax_K": t_max,
        "Tmin_C": t_min - 273.15,
        "Tmax_C": t_max - 273.15,
        "intra_cell_dT_K": t_max - t_min,
    }
    if "volume_average" in dir(r):
        t_mean = float(r.volume_average(
            VariableCatalog.TEMPERATURE, locations=[zone]))
        row["Tmean_K"] = t_mean
        row["Tmean_C"] = t_mean - 273.15
    rows.append(row)

reference = json.load(open(BASE + "/" + STEM + "_metrics.json", encoding="utf-8"))
assert len(rows) == 12
assert abs(max(row["Tmax_K"] for row in rows)
           - reference["battery_Tmax_K"]) < 1e-5
assert abs(min(row["Tmin_K"] for row in rows)
           - reference["battery_Tmin_K"]) < 1e-5
assert all(row["Tmax_K"] >= row["Tmin_K"] >= 298.15 for row in rows)

summary = {
    "case_stem": STEM,
    "temperature_unit_raw": "K",
    "temperature_unit_report": "degC",
    "global_Tmax_C": reference["battery_Tmax_K"] - 273.15,
    "global_Tmin_C": reference["battery_Tmin_K"] - 273.15,
    "global_dT_K": reference["battery_dT_K"],
    "outlet_T_massavg_C": reference["outlet_T_massavg_K"] - 273.15,
    "pressure_drop_kPa": reference["pressure_drop_Pa"] / 1000.0,
    "water_heat_removed_W": reference["Q_water_W"],
    "total_heat_source_W": reference["Q_source_total_W"],
    "cell_Tmax_spread_K": max(row["Tmax_K"] for row in rows)
                           - min(row["Tmax_K"] for row in rows),
    "cells": rows,
}
if "Tmean_K" in rows[0]:
    summary["cell_Tmean_spread_K"] = (max(row["Tmean_K"] for row in rows)
                                     - min(row["Tmean_K"] for row in rows))

csv_path = BASE + "/step11_cell_temperatures.csv"
with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
json_path = BASE + "/step11_scalar_results.json"
with open(json_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, ensure_ascii=False)
print("STEP11 SCALAR SUMMARY", {key: value for key, value in summary.items()
                                if key != "cells"})
print("STEP11 SAVED", csv_path, json_path)
solver.exit()
