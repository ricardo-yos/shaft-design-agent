# Problem statement

A shaft is loaded in bending and torsion such that Ma = 70 N.m, Ta = 45 N.m, Mm = 55 N.m, and Tm = 35 N.m. For the shaft, Su = 700 MPa and Sy = 560 MPa, and a fully corrected endurance limit of Se = 210 MPa is assumed. Let Kf = 2.2 and Kfs = 1.8. With a design factor of 2.0 determine the minimum acceptable diameter of the shaft using the (a) DE-Gerber criterion. (b) DE-ASME Elliptic criterion. (c) DE-Soderberg criterion. (d) DE-Goodman criterion. Discuss and compare the results.

# Agent response

### 1. Parameters Extracted from the Statement
* **Fatigue stress-concentration factor for bending (Kf):** 2.2
* **Fatigue stress-concentration factor for torsion (Kfs):** 1.8
* **Alternating bending moment (Ma):** 70 N·m
* **Mean bending moment (Mm):** 55 N·m
* **Corrected endurance limit (Se):** 210 MPa
* **Ultimate tensile strength (Sut):** 700 MPa
* **Alternating torque (Ta):** 45 N·m
* **Mean torque (Tm):** 35 N·m
* **Design factor (n):** 2
* **Yield strength (Sy):** 560 MPa

### 2. Criteria Applied
In the order requested by the problem statement:
(a) DE-Gerber criterion
(b) DE-ASME Elliptic criterion
(c) DE-Soderberg criterion
(d) DE-Goodman criterion

### 3. Tool Results (Minimum Diameter per Criterion)
* **DE-Gerber:** 25.853 mm
* **DE-ASME Elliptic:** 25.769 mm
* **DE-Soderberg:** 27.696 mm
* **DE-Goodman:** 27.27 mm

### 4. Comparison Table (Largest to Smallest Diameter)
| Rank | Criterion | Minimum Diameter (mm) |
|:----:|:----------|:----------------------:|
| 1 | DE-Soderberg | 27.696 |
| 2 | DE-Goodman | 27.27 |
| 3 | DE-Gerber | 25.853 |
| 4 | DE-ASME Elliptic | 25.769 |

### 5. Discussion

The four fatigue criteria produce different minimum shaft diameters because they use different failure loci to model the interaction between mean and alternating stresses. The results range from **25.769 mm** (DE-ASME Elliptic) to **27.696 mm** (DE-Soderberg).

*   **DE-ASME Elliptic (25.769 mm)** and **DE-Gerber (25.853 mm)** yield the smallest diameters. These criteria are considered the least conservative (and most accurate for many ductile materials) because they utilize curved failure loci that allow for a greater combination of mean and alternating stresses before failure is predicted. The Gerber parabola is generally slightly less conservative than the elliptic criterion near the endurance limit but approaches the ultimate strength, leading to very close results in this case.
*   **DE-Goodman (27.27 mm)** produces a larger diameter than Gerber and Elliptic. The Goodman criterion uses a straight-line failure locus connecting the endurance limit ($S_e$) and the ultimate tensile strength ($S_{ut}$). This linear approximation is inherently more conservative than the curved Gerber and Elliptic loci, as it assumes a strictly linear trade-off between mean and alternating stress capacities.
*   **DE-Soderberg (27.696 mm)** yields the largest diameter, making it the most conservative criterion. It uses a straight-line locus connecting the endurance limit ($S_e$) and the yield strength ($S_y$). Since $S_y$ (560 MPa) is significantly lower than $S_{ut}$ (700 MPa), the allowable mean stress range is reduced, requiring a larger shaft diameter to satisfy the design factor. This criterion is often used when preventing yield is a critical design constraint alongside fatigue.

**Engineering Interpretation:**
The spread in results (approximately 25.8 mm to 27.7 mm) indicates that the choice of criterion has a tangible impact on material usage and shaft sizing. If the design requires adherence to all criteria (to ensure no fatigue failure by any standard and no yielding), the **DE-Soderberg** result of **27.696 mm** would be the controlling minimum diameter. In many standard design practices, the DE-Gerber or DE-ASME Elliptic criteria are preferred for their accuracy with ductile materials, while Goodman is often used for hand calculations due to its simplicity and safety margin. Soderberg is reserved for cases where yield prevention is paramount.

### 6. Assumptions & Missing Data

None. All necessary parameters (Ma, Ta, Mm, Tm, Kf, Kfs, Se, Sut, Sy, n) were provided in the problem statement.
