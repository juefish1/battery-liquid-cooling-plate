# Ansys workflow reference

The exported numerical summaries can be analyzed in ordinary Python. The journals below are version-specific research scripts for a separately licensed Ansys 2026 R1 installation. CAD and mesh databases, solver fields and the private Workbench project are excluded, so the full solve requires rebuilding the inputs.

1. Create a fresh scratch directory outside the original project. Copy the files from `ansys/` there. Set `COLDPLATE_RUN_DIR` to its absolute path before launching the relevant Windows Ansys application. Child applications must inherit the setting. Use that directory as Fluent's working directory for the relative paths in the TUI journal.
2. In an empty SpaceClaim/Discovery V261 document, run Step 01 in its scripting environment, followed by the saved project's fluid audit, named selections and shared topology scripts (Steps 02, 03, 04a). Check one connected fluid and 14 solids, and verify interface contact and fluid volume before meshing.
3. Import the shared-topology model into Workbench, build the mesh controls described in [model notes](model.md) and use Step 05w as a reference for export zone types. The Step 12 WBJN expects locally prepared coarse and fine Workbench copies (including their support directories), and calls Step 12a. Inspect versions, zone names, units, quality and interface pairing on each newly built mesh. Use the expected original input names if running a journal verbatim.
4. In Fluent, run Step 05ag on the correctly typed baseline mesh, then use Steps 06b, 07b, 08b and 09c to configure materials, boundaries, cell sources and initialization. Step 10k is a subsequent pseudo-time stage and expects a saved second-order checkpoint. The journals are not a complete batch driver. Use the initialization and discretization settings in the README and check each stage's inputs before proceeding.
5. Steps 12d/12e illustrate preparation and independent solution of the locally rebuilt grids. Step 13b is invoked with the case identifier in `CODEX_STUDY_CASE` and the historical study manifest in the run directory. Inspect the environment controls and required filenames at the top of each script before running. Steps 11a and 11f show how the baseline reports and contours were extracted from the saved medium-mesh fields.

The selected journals document the model setup and retain the core project logic. They were syntax-checked here where applicable. The reviewed numerical summaries were recomputed from exported tables without an Ansys rerun. See [provenance](provenance.md).


