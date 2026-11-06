from pathlib import Path
import csv
import json
import sys
import time


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

SCENARIO_DIR = (
    ROOT
    / "data"
    / "scenarios"
    / "reduced_scenarios"
)

REPORT_DIR = ROOT / "reports"

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


SCENARIO_FILES = {
    100: SCENARIO_DIR / "scenario_reduced_100.csv",
    50: SCENARIO_DIR / "scenario_reduced_50.csv",
    30: SCENARIO_DIR / "scenario_reduced_30.csv",
}


REQUIRED_COLUMNS = [
    "scenario_id",
    "source_scenario_id",
    "hour",
    "probability",
    "price_error_bc",
    "load_error_bc",
    "wind_on_error_bc",
    "wind_off_error_bc",
    "pv_error_bc",
]


# ============================================================
# HIGHSPY IMPORT
# ============================================================

def import_highspy():

    try:
        import highspy
    except Exception as exc:
        raise RuntimeError(
            "\nCould not import highspy.\n"
            "Install it with:\n\n"
            "python -m pip install highspy\n"
        ) from exc

    return highspy


# ============================================================
# PYTHON ENVIRONMENT
# ============================================================

def print_environment():

    print("\n----------------------------------------------")
    print("PYTHON ENVIRONMENT")
    print("----------------------------------------------")

    print(
        "Python executable:"
    )

    print(
        sys.executable
    )

    print(
        f"\nPython version:"
    )

    print(
        sys.version
    )


# ============================================================
# HIGHSPY VERSION / AVAILABILITY
# ============================================================

def check_highspy(highspy):

    print("\n----------------------------------------------")
    print("HiGHS / HIGHSPY CHECK")
    print("----------------------------------------------")

    h = highspy.Highs()

    # --------------------------------------------------------
    # Version
    # --------------------------------------------------------

    try:
        version = (
            h.versionMajor(),
            h.versionMinor(),
            h.versionPatch(),
        )
    except Exception:

        try:
            version = (
                highspy.HIGHS_VERSION_MAJOR,
                highspy.HIGHS_VERSION_MINOR,
                highspy.HIGHS_VERSION_PATCH,
            )
        except Exception:

            version = "unknown"

    print(
        f"HiGHS version: {version}"
    )

    # --------------------------------------------------------
    # Basic object creation
    # --------------------------------------------------------

    print(
        "[OK] highspy.Highs() initialized."
    )

    return {
        "version": version
    }


# ============================================================
# DIRECT HIGHSPY MILP SMOKE TEST
# ============================================================

def highspy_smoke_test(highspy):

    print("\n----------------------------------------------")
    print("DIRECT HiGHS MILP SMOKE TEST")
    print("----------------------------------------------")

    h = highspy.Highs()

    # --------------------------------------------------------
    # Variables
    #
    # Maximize:
    #
    #     5x + 2z
    #
    # subject to:
    #
    #     x <= 10z
    #
    #     0 <= x <= 10
    #
    #     z binary
    #
    # Optimal:
    #
    #     x = 10
    #     z = 1
    #     objective = 52
    # --------------------------------------------------------

    x = h.addVariable(
        lb=0.0,
        ub=10.0,
        obj=5.0,
        name="x",
    )

    z = h.addVariable(
        lb=0.0,
        ub=1.0,
        obj=2.0,
        type=highspy.HighsVarType.kInteger,
        name="z",
    )

    # Binary/integer variable explicitly limited to {0,1}.
    h.addConstr(
        z <= 1
    )

    h.addConstr(
        z >= 0
    )

    # x <= 10 z
    h.addConstr(
        x - 10.0 * z <= 0.0
    )

    # --------------------------------------------------------
    # Objective
    # --------------------------------------------------------

    h.maximize(
        5.0 * x
        + 2.0 * z
    )

    # --------------------------------------------------------
    # Solve
    # --------------------------------------------------------

    start = time.perf_counter()

    status = h.run()

    elapsed = (
        time.perf_counter()
        - start
    )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status_string = str(status)

    print(
        f"HiGHS run status: "
        f"{status_string}"
    )

    try:
        model_status = h.getModelStatus()

        print(
            f"Model status: "
            f"{model_status}"
        )

    except Exception:
        model_status = "unknown"

    # --------------------------------------------------------
    # Solution
    # --------------------------------------------------------

    try:
        x_value = float(
            h.val(x)
        )

        z_value = float(
            h.val(z)
        )

    except Exception as exc:

        raise RuntimeError(
            "HiGHS solved the model but "
            "solution values could not be read."
        ) from exc

    objective = (
        5.0 * x_value
        + 2.0 * z_value
    )

    print(
        f"x         : {x_value:.6f}"
    )

    print(
        f"z         : {z_value:.6f}"
    )

    print(
        f"objective : {objective:.6f}"
    )

    print(
        f"runtime   : {elapsed:.6f} s"
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    checks = {

        "x_optimal":
            abs(x_value - 10.0) < 1e-6,

        "z_optimal":
            abs(z_value - 1.0) < 1e-6,

        "objective_optimal":
            abs(objective - 52.0) < 1e-6,

        "runtime_valid":
            elapsed >= 0.0,
    }

    for name, passed in checks.items():

        print(
            f"[{'OK' if passed else 'FAIL'}] "
            f"{name}"
        )

    if not all(
        checks.values()
    ):
        raise RuntimeError(
            "Direct HiGHS MILP smoke test failed."
        )

    print(
        "\n[PASS] Direct highspy MILP smoke test."
    )

    return {
        "status": status_string,
        "model_status": str(model_status),
        "x": x_value,
        "z": z_value,
        "objective": objective,
        "runtime_seconds": elapsed,
        "checks": checks,
    }


# ============================================================
# CSV SCENARIO CHECK
# ============================================================

def read_csv_rows(path):

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(
                f"{path.name}: CSV header missing."
            )

        rows = list(reader)

    return reader.fieldnames, rows


# ============================================================
# SCENARIO FILE VALIDATION
# ============================================================

def check_scenario_file(
    k,
    path
):

    print("\n----------------------------------------------")
    print(
        f"SCENARIO CHECK — K={k}"
    )
    print("----------------------------------------------")

    if not path.exists():

        raise FileNotFoundError(
            f"Scenario file not found:\n{path}"
        )

    fieldnames, rows = (
        read_csv_rows(path)
    )

    # --------------------------------------------------------
    # Columns
    # --------------------------------------------------------

    missing_columns = [
        col
        for col in REQUIRED_COLUMNS
        if col not in fieldnames
    ]

    if missing_columns:

        raise ValueError(
            f"K={k}: missing columns:\n"
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Basic row count
    # --------------------------------------------------------

    expected_rows = (
        k * 24
    )

    if len(rows) != expected_rows:

        raise ValueError(
            f"K={k}: expected "
            f"{expected_rows:,} rows, "
            f"got {len(rows):,}."
        )

    # --------------------------------------------------------
    # Parse rows
    # --------------------------------------------------------

    scenario_hours = {}

    probability_by_scenario = {}

    min_probability = None
    max_probability = None

    missing_value_count = 0

    for row_number, row in enumerate(
        rows,
        start=2
    ):

        try:

            scenario_id = int(
                float(
                    row["scenario_id"]
                )
            )

            hour = int(
                float(
                    row["hour"]
                )
            )

            probability = float(
                row["probability"]
            )

        except Exception as exc:

            raise ValueError(
                f"K={k}: invalid ID/hour/"
                f"probability at CSV row "
                f"{row_number}."
            ) from exc

        # ----------------------------------------------------
        # Hour
        # ----------------------------------------------------

        if not (
            0 <= hour <= 23
        ):

            raise ValueError(
                f"K={k}: invalid hour "
                f"{hour} at row "
                f"{row_number}."
            )

        scenario_hours.setdefault(
            scenario_id,
            []
        ).append(hour)

        # ----------------------------------------------------
        # Probability
        # ----------------------------------------------------

        if probability <= 0:

            raise ValueError(
                f"K={k}: non-positive "
                f"probability at row "
                f"{row_number}."
            )

        if (
            scenario_id
            in probability_by_scenario
        ):

            previous = (
                probability_by_scenario[
                    scenario_id
                ]
            )

            if abs(
                previous - probability
            ) > 1e-12:

                raise ValueError(
                    f"K={k}: inconsistent "
                    f"probability for scenario "
                    f"{scenario_id}."
                )

        else:

            probability_by_scenario[
                scenario_id
            ] = probability

        # ----------------------------------------------------
        # Numerical columns
        # ----------------------------------------------------

        value_columns = [
            "price_error_bc",
            "load_error_bc",
            "wind_on_error_bc",
            "wind_off_error_bc",
            "pv_error_bc",
        ]

        for col in value_columns:

            raw = row[col]

            if (
                raw is None
                or
                raw.strip() == ""
            ):

                missing_value_count += 1
                continue

            try:
                float(raw)
            except Exception as exc:

                raise ValueError(
                    f"K={k}: non-numeric "
                    f"{col} at row "
                    f"{row_number}."
                ) from exc

    # --------------------------------------------------------
    # Number of scenarios
    # --------------------------------------------------------

    scenario_ids = sorted(
        scenario_hours.keys()
    )

    if len(scenario_ids) != k:

        raise ValueError(
            f"K={k}: expected "
            f"{k} scenario IDs, "
            f"found {len(scenario_ids)}."
        )

    # --------------------------------------------------------
    # Scenario hour sequence
    # --------------------------------------------------------

    for sid in scenario_ids:

        hours = sorted(
            scenario_hours[sid]
        )

        if hours != list(
            range(24)
        ):

            raise ValueError(
                f"K={k}, scenario "
                f"{sid}: expected hours "
                f"0..23, got {hours}."
            )

    # --------------------------------------------------------
    # Probability sum
    # --------------------------------------------------------

    probability_sum = sum(
        probability_by_scenario.values()
    )

    if not (
        abs(
            probability_sum - 1.0
        )
        <= 1e-10
    ):

        raise ValueError(
            f"K={k}: probability sum "
            f"is {probability_sum:.15f}"
        )

    min_probability = min(
        probability_by_scenario.values()
    )

    max_probability = max(
        probability_by_scenario.values()
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print(
        f"Rows               : "
        f"{len(rows):,}"
    )

    print(
        f"Scenarios          : "
        f"{len(scenario_ids)}"
    )

    print(
        f"Probability sum    : "
        f"{probability_sum:.12f}"
    )

    print(
        f"Min probability    : "
        f"{min_probability:.10f}"
    )

    print(
        f"Max probability    : "
        f"{max_probability:.10f}"
    )

    print(
        f"Missing values     : "
        f"{missing_value_count}"
    )

    print(
        "[PASS] Scenario integrity."
    )

    return {
        "rows": len(rows),
        "scenarios": len(scenario_ids),
        "probability_sum": probability_sum,
        "min_probability": min_probability,
        "max_probability": max_probability,
        "missing_values": missing_value_count,
        "path": str(path),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10F.0 — SOLVER & INPUT INTEGRITY")
    print("==============================================")

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    print_environment()

    # --------------------------------------------------------
    # Highspy
    # --------------------------------------------------------

    highspy = import_highspy()

    highspy_info = check_highspy(
        highspy
    )

    # --------------------------------------------------------
    # Direct solver smoke test
    # --------------------------------------------------------

    smoke = highspy_smoke_test(
        highspy
    )

    # --------------------------------------------------------
    # Scenario checks
    # --------------------------------------------------------

    scenario_results = {}

    for k in [
        100,
        50,
        30,
    ]:

        scenario_results[str(k)] = (
            check_scenario_file(
                k,
                SCENARIO_FILES[k]
            )
        )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    report = {

        "gate": "10F.0",

        "status": "PASS",

        "environment": {
            "python_executable":
                sys.executable,

            "python_version":
                sys.version,
        },

        "solver": {

            "interface":
                "highspy",

            "version":
                highspy_info[
                    "version"
                ],

            "smoke_test":
                smoke,
        },

        "scenario_files":
            scenario_results,

        "reason_for_highspy":
            (
                "Pyomo's current HiGHS interface "
                "uses file-descriptor output capture "
                "internally on Windows; the direct "
                "highspy interface avoids that layer."
            ),

        "next_gate":
            "10F.1 — final stochastic MILP",
    }

    report_file = (
        REPORT_DIR
        / "gate10f0_solver_integrity.json"
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

    print("\n==============================================")
    print(" GATE 10F.0 COMPLETE")
    print("==============================================")

    print(
        f"\nSaved report:\n"
        f"{report_file}"
    )

    print(
        "\nNext:"
    )

    print(
        "GATE 10F.1 — STOCHASTIC MILP"
    )


if __name__ == "__main__":
    main()
