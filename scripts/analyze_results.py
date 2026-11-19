"""Recompute study summaries from exported Fluent results using standard Python."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def load_rows(name):
    with (ROOT / "data" / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    config = load_json("config/baseline.json")
    meshes = {row["mesh"]: row for row in load_rows("step12_mesh_comparison.csv")}
    medium, fine = meshes["medium"], meshes["fine"]
    print("Medium-to-fine mesh differences")
    for field, limit in config["mesh_pair_limits"].items():
        if field == "deltaP_relative_percent":
            pressure = float(fine["deltaP_kPa"])
            difference = 100 * abs(pressure - float(medium["deltaP_kPa"])) / abs(pressure)
            label, unit = "Pressure drop (relative to fine mesh)", "%"
        else:
            difference = abs(float(fine[field]) - float(medium[field]))
            label, unit = field, "K"
        result = "PASS" if difference <= limit else "FAIL"
        print(f"  {label}: {difference:.6g} {unit} (limit {limit:g} {unit}) {result}")

    manifest = load_json("config/step13_study_manifest.json")
    planned = {case["id"]: case for case in manifest["cases"]}
    dispositions = {row["case"]: row["state"] for row in load_rows("step14_case_status.csv")}
    accepted = {row["case"]: row for row in load_rows("step14_study_results.csv")}
    if planned.keys() != dispositions.keys() or accepted.keys() != {
        case for case, state in dispositions.items() if state == "accepted"
    }:
        raise ValueError("The study manifest, dispositions and results disagree")
    for case, row in accepted.items():
        for field in ("mass_flow_kg_s", "power_per_cell_W"):
            if float(row[field]) != planned[case][field]:
                raise ValueError(f"{case} does not match the manifest for {field}")
        if row["model"] != planned[case]["model"] or row["mesh"] != planned[case]["mesh"]:
            raise ValueError(f"{case} does not match the manifest model or mesh")

    print(f"\nAccepted study cases: {len(accepted)}/{len(planned)}")
    for case, state in dispositions.items():
        if state == "excluded":
            print(f"  Excluded: {case}")

    baseline = accepted["flow_060_sst"]
    boundary = config["boundary"]
    cp = config["materials"]["water"]["cp_J_kg_K"]
    predicted_rise = boundary["heat_total_W"] / (boundary["inlet_mass_flow_kg_s"] * cp)
    exported_rise = float(baseline["Tout_C"]) + 273.15 - boundary["inlet_temperature_K"]
    print(f"\nFine-mesh baseline Tmax: {float(baseline['Tmax_C']):.3f} deg C")
    print(f"Outlet temperature rise: {exported_rise:.6f} K (adiabatic balance: {predicted_rise:.6f} K)")
    baseline_dp = float(baseline["deltaP_kPa"])
    heat_dp_difference = max(
        100 * abs(float(row["deltaP_kPa"]) - baseline_dp) / abs(baseline_dp)
        for row in accepted.values()
        if row["study"] == "heat"
    )
    print(f"Maximum fixed-flow pressure difference across heat loads: {heat_dp_difference:.2f}%")


if __name__ == "__main__":
    main()

