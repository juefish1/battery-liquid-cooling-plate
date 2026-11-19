# Model and assumptions

The cell array footprint is 172 × 184 mm. The plate has a 3 mm floor, a 4 mm channel layer and a 3 mm lid. With the origin at the plate bottom corner, the inlet is at x = 0, y = 22 mm and the outlet at x = 192, y = 182 mm, both spanning z = 3–7 mm. The theoretical channel volume is 53,098.48 mm³. The cell orientation and ideal contact are modeling assumptions.

| Material | Density (kg/m³) | Specific heat (J/kg·K) | Conductivity (W/m·K) | Dynamic viscosity (Pa·s) |
| --- | ---: | ---: | ---: | ---: |
| Water at 25 °C | 997.047 | 4181.446 | 0.607198 | 0.000889997 |
| Fluent generic aluminum | 2719 | 871 | 202.4 | — |
| Effective cell solid | 2300 | 1072 | 8.007155 | — |

The surrogate cell conductivity is the geometric mean of source reference directions 18.5, 18.5 and 1.5 W/(m·K). The cell chemistry, conductivity axes and real thermal contact resistance were not verified. The model neglects gravity, radiation and viscous heating. Inlet hydraulic diameter is 2wh/(w+h). Baseline inlet Reynolds number is approximately 11,236.

The nominal coarse/medium/fine water sizing was 1.00/0.80/0.64 mm. Base sizing was 2.50/2.00/1.60 mm, lid sizing 1.875/1.50/1.20 mm and cell sizing 6.25/5.00/4.00 mm. Wet-wall first-layer heights were 0.0125/0.0100/0.0080 mm, with a maximum of 12 layers at growth rate 1.2. The medium mesh's worst cells occurred near a U bend. Removing inflation was a diagnostic and did not supply the reported result.

Tmax and Tmin are extrema across all cell zones. ΔT is their difference. Coolant outlet temperature is mass weighted. Under the adiabatic, constant-property assumptions, the 240 W source implies an outlet rise of 240/(0.06 × 4181.446) = 0.956607 K. This balance checks numerical consistency under those assumptions.

Reference pointers recorded in the source project are the Ansys Fluent 2026 R1 User and Theory Guides (mesh quality and SST near-wall treatment), the NIST water-property document (publication ID 832373), and the UQTR repository document (item 12556) for representative cell properties. The bibliography in the source report is a record of inputs used by the project.

