# Battery aging datasets recommended for gamma/kappa (SoC-occupancy) calibration

The manuscript's ReLCCA coefficients (kappa levels, gamma charge/discharge per SoC band)
are code assumptions. The following public datasets provide chemistry- and
temperature-resolved aging data suitable for calibrating them:

1. Sandia National Laboratories — Preger et al. 2020,
   "Degradation of Commercial Lithium-ion Cells as a Function of Chemistry and
   Cycling Conditions", J. Electrochem. Soc. 167, 120532.
   Commercial 18650 NCA, NMC, LFP cells; temperature, DOD, discharge current.
   Data: https://batteryarchive.org (study "Sandia National Laboratories (SNL)").
   DOI: 10.1149/1945-7111/abae37

2. Keil et al. 2016, "Calendar Aging of Lithium-Ion Batteries",
   J. Electrochem. Soc. 163(9), A1872 — calendar aging vs SoC and temperature
   for NMC/LFP. (Manuscript ref [13].)

3. Schimpe et al. 2018, "Comprehensive modeling of temperature-dependent
   degradation mechanisms in lithium iron phosphate batteries",
   J. Electrochem. Soc. 165(10), A181 — temperature-dependent calendar + cycle
   for LFP. (Manuscript ref [14].)

4. CALCE (University of Maryland) battery aging datasets:
   https://web.calce.umd.edu/batteries/data.htm

5. Oxford Battery Degradation Dataset 1 — LCO pouch, 40 C, drive cycles:
   https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac

None of these was used in the present reconstruction; they are listed so that
a follow-up study can replace the assumed gamma/kappa values with
chemistry- and temperature-specific fits.
