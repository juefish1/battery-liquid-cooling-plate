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

solver.settings.file.read_case(file_name=INPUT_CASE)
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
solver.settings.file.write_case_data(file_name=OUTPUT_CASE)
print("STEP09 SAVED:", OUTPUT_CASE)
solver.exit()
