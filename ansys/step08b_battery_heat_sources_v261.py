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

solver.settings.file.read_case(file_name=INPUT_CASE)
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
solver.settings.file.write_case(file_name=OUTPUT_CASE)
print("STEP08 SAVED:", OUTPUT_CASE)
solver.exit()
