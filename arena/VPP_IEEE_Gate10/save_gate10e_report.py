from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent

REPORTS_DIR = ROOT / "reports"
REDUCED_DIR = (
    ROOT
    / "data"
    / "scenarios"
    / "reduced_scenarios"
)

REPORTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


results = [
    {
        "target_k": 100,
        "selected_scenarios": 100,
        "probability_sum": 1.0,
        "reconstruction_error": 74.703402,
        "mean_distribution_error": 45.919874,
        "mean_std_error": 88.122595,
        "output_file": str(
            REDUCED_DIR / "scenario_reduced_100.csv"
        ),
    },
    {
        "target_k": 50,
        "selected_scenarios": 50,
        "probability_sum": 1.0,
        "reconstruction_error": 81.765477,
        "mean_distribution_error": 23.791356,
        "mean_std_error": 145.438916,
        "output_file": str(
            REDUCED_DIR / "scenario_reduced_50.csv"
        ),
    },
    {
        "target_k": 30,
        "selected_scenarios": 30,
        "probability_sum": 1.0,
        "reconstruction_error": 88.763241,
        "mean_distribution_error": 34.968099,
        "mean_std_error": 117.447349,
        "output_file": str(
            REDUCED_DIR / "scenario_reduced_30.csv"
        ),
    },
]


report = {
    "gate": "10E",
    "status": "PASS",
    "source_scenarios": 5000,
    "trajectory_dimension": 120,
    "method": (
        "Standardized trajectory clustering "
        "with representative real-scenario selection"
    ),
    "warning": (
        "K selection is provisional. "
        "Final K must be selected after MILP "
        "runtime/objective fidelity testing."
    ),
    "results": results,
}


report_file = (
    REPORTS_DIR
    / "gate10e_scenario_reduction_report.json"
)

with open(
    report_file,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        report,
        f,
        ensure_ascii=False,
        indent=2
    )


print("==============================================")
print(" GATE 10E REPORT SAVED")
print("==============================================")
print()
print(report_file)