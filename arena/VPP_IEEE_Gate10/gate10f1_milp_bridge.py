from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
import highspy


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

CONFIG_FILE = ROOT / "gate10f1_milp_config.json"

PROCESSED_DIR = ROOT / "data" / "processed"

CALIBRATION_DIR = ROOT / "data" / "calibration"

SCENARIO_DIR = (
    ROOT
    / "data"
    / "scenarios"
    / "reduced_scenarios"
)

RESULTS_DIR = ROOT / "results" / "gate10f1"

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SCENARIO FILES
# ============================================================

SCENARIO_FILES = {
    100: SCENARIO_DIR / "scenario_reduced_100.csv",
    50: SCENARIO_DIR / "scenario_reduced_50.csv",
    30: SCENARIO_DIR / "scenario_reduced_30.csv",
}


# ============================================================
# INPUT FILES
# ============================================================

LOAD_FORECAST_FILE = (
    PROCESSED_DIR
    / "load_forecast_derived_from_smard.csv"
)

PHYSICAL_MASTER_FILE = (
    PROCESSED_DIR
    / "master_physical_15min.csv"
)

DA_PRICE_FILE = (
    CALIBRATION_DIR
    / "da_price_calibrated_forecast.csv"
)


# ============================================================
# MODEL DIMENSION
# ============================================================

HOURS = 24


# ============================================================
# CONFIGURATION
# ============================================================

def load_config():
    """
    Load Gate 10F.1 configuration.
    """

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Missing configuration file:\n{CONFIG_FILE}"
        )

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        config = json.load(f)

    return config


# ============================================================
# PARAMETER VALIDATION
# ============================================================

def validate_model_parameters(config):
    """
    Do not allow undefined physical parameters
    to enter the research MILP.
    """

    assets = config["assets"]

    required_parameters = [
        "wind_onshore_mw",
        "wind_offshore_mw",
        "pv_mw",
        "dg_mw",
        "dg_cost_eur_mwh",
        "dr_mw",
    ]

    missing_parameters = [
        parameter
        for parameter in required_parameters
        if assets.get(parameter) is None
    ]

    if missing_parameters:

        message = (
            "\nGate 10F.1 cannot run the research MILP yet.\n\n"
            "The following physical parameters are undefined:\n"
        )

        message += "\n".join(
            f"  - {parameter}"
            for parameter in missing_parameters
        )

        message += (
            "\n\nEnter the actual values from the final "
            "VPP formulation in:\n"
            f"{CONFIG_FILE}\n"
        )

        raise RuntimeError(message)


# ============================================================
# LOAD BASE DATA
# ============================================================

def load_base_data(config):
    """
    Load the 24-hour base information set.

    The current bridge uses:
        - load forecast
        - renewable forecasts
        - DA price forecast
    """

    study_date = pd.Timestamp(
        config["study_date"],
        tz="Europe/Berlin"
    )

    study_end = (
        study_date
        + pd.Timedelta(hours=23)
    )

    # --------------------------------------------------------
    # LOAD FORECAST
    # --------------------------------------------------------

    if not LOAD_FORECAST_FILE.exists():
        raise FileNotFoundError(
            f"Missing load forecast file:\n"
            f"{LOAD_FORECAST_FILE}"
        )

    load_df = pd.read_csv(
        LOAD_FORECAST_FILE
    )

    if "timestamp" not in load_df.columns:
        raise ValueError(
            "load_forecast_derived_from_smard.csv "
            "does not contain 'timestamp'."
        )

    if "load_forecast" not in load_df.columns:
        raise ValueError(
            "load_forecast_derived_from_smard.csv "
            "does not contain 'load_forecast'."
        )

    load_df["timestamp"] = (
        pd.to_datetime(
            load_df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    load_df = load_df[
        (
            load_df["timestamp"] >= study_date
        )
        &
        (
            load_df["timestamp"] <= study_end
        )
    ].copy()

    # Convert 15-min forecast to hourly average.
    load_hourly = (
        load_df
        .set_index("timestamp")["load_forecast"]
        .resample("1h")
        .mean()
        .reset_index()
    )

    # --------------------------------------------------------
    # RENEWABLE FORECASTS
    # --------------------------------------------------------

    if not PHYSICAL_MASTER_FILE.exists():
        raise FileNotFoundError(
            f"Missing physical master:\n"
            f"{PHYSICAL_MASTER_FILE}"
        )

    physical_df = pd.read_csv(
        PHYSICAL_MASTER_FILE
    )

    required_physical_columns = [
        "timestamp",
        "wind_on_forecast",
        "wind_off_forecast",
        "pv_forecast",
    ]

    missing_physical_columns = [
        column
        for column in required_physical_columns
        if column not in physical_df.columns
    ]

    if missing_physical_columns:
        raise ValueError(
            "Physical master is missing:\n"
            + "\n".join(
                missing_physical_columns
            )
        )

    physical_df["timestamp"] = (
        pd.to_datetime(
            physical_df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    physical_df = physical_df[
        (
            physical_df["timestamp"] >= study_date
        )
        &
        (
            physical_df["timestamp"] <= study_end
        )
    ].copy()

    renewable_hourly = (
        physical_df
        .set_index("timestamp")[
            [
                "wind_on_forecast",
                "wind_off_forecast",
                "pv_forecast",
            ]
        ]
        .resample("1h")
        .mean()
        .reset_index()
    )

    # --------------------------------------------------------
    # DA PRICE FORECAST
    # --------------------------------------------------------

    if not DA_PRICE_FILE.exists():
        raise FileNotFoundError(
            f"Missing DA price calibration file:\n"
            f"{DA_PRICE_FILE}"
        )

    price_df = pd.read_csv(
        DA_PRICE_FILE
    )

    required_price_columns = [
        "timestamp",
        "forecast_hybrid",
    ]

    missing_price_columns = [
        column
        for column in required_price_columns
        if column not in price_df.columns
    ]

    if missing_price_columns:
        raise ValueError(
            "DA price file is missing:\n"
            + "\n".join(
                missing_price_columns
            )
        )

    price_df["timestamp"] = (
        pd.to_datetime(
            price_df["timestamp"],
            utc=True,
            errors="coerce"
        )
        .dt.tz_convert("Europe/Berlin")
    )

    price_df = price_df[
        (
            price_df["timestamp"] >= study_date
        )
        &
        (
            price_df["timestamp"] <= study_end
        )
    ].copy()

    # --------------------------------------------------------
    # MERGE
    # --------------------------------------------------------

    base = (
        load_hourly
        .merge(
            renewable_hourly,
            on="timestamp",
            how="inner",
            validate="one_to_one"
        )
        .merge(
            price_df[
                [
                    "timestamp",
                    "forecast_hybrid",
                ]
            ],
            on="timestamp",
            how="inner",
            validate="one_to_one"
        )
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if len(base) != HOURS:
        raise RuntimeError(
            f"Expected {HOURS} hourly records, "
            f"but obtained {len(base)}."
        )

    # --------------------------------------------------------
    # MISSING CHECK
    # --------------------------------------------------------

    required_columns = [
        "timestamp",
        "load_forecast",
        "wind_on_forecast",
        "wind_off_forecast",
        "pv_forecast",
        "forecast_hybrid",
    ]

    if (
        base[required_columns]
        .isna()
        .any()
        .any()
    ):
        raise RuntimeError(
            "Base information set contains missing values."
        )

    return base


# ============================================================
# LOAD REDUCED SCENARIOS
# ============================================================

def load_reduced_scenarios(k):
    """
    Load one reduced scenario set.
    """

    scenario_file = SCENARIO_FILES[k]

    if not scenario_file.exists():
        raise FileNotFoundError(
            f"Missing reduced scenario file:\n"
            f"{scenario_file}"
        )

    scenarios = pd.read_csv(
        scenario_file
    )

    required_columns = [
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

    missing_columns = [
        column
        for column in required_columns
        if column not in scenarios.columns
    ]

    if missing_columns:
        raise ValueError(
            f"K={k}: missing columns:\n"
            + "\n".join(
                missing_columns
            )
        )

    scenarios = (
        scenarios
        .sort_values(
            [
                "scenario_id",
                "hour",
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Integrity
    # --------------------------------------------------------

    number_of_scenarios = (
        scenarios["scenario_id"]
        .nunique()
    )

    if number_of_scenarios != k:
        raise ValueError(
            f"K={k}: expected {k} scenarios, "
            f"found {number_of_scenarios}."
        )

    probability_sum = float(
        scenarios[
            [
                "scenario_id",
                "probability",
            ]
        ]
        .drop_duplicates("scenario_id")
        ["probability"]
        .sum()
    )

    if abs(
        probability_sum - 1.0
    ) > 1e-10:
        raise ValueError(
            f"K={k}: scenario probabilities "
            f"sum to {probability_sum:.12f}."
        )

    return scenarios


# ============================================================
# BUILD MILP
# ============================================================

def build_model(
    base,
    scenarios,
    config
):
    """
    Build the current parameterized stochastic MILP bridge.

    IMPORTANT:
    This is an execution bridge for Gate 10F.1.
    It is NOT yet claimed to be the final manuscript
    formulation.
    """

    # --------------------------------------------------------
    # CREATE HiGHS MODEL
    # --------------------------------------------------------

    model = highspy.Highs()

    solver_config = config["solver"]

    model.setOptionValue(
        "time_limit",
        float(
            solver_config["time_limit_seconds"]
        )
    )

    model.setOptionValue(
        "mip_rel_gap",
        float(
            solver_config["mip_gap"]
        )
    )

    # --------------------------------------------------------
    # MODEL PARAMETERS
    # --------------------------------------------------------

    assets = config["assets"]

    market = config["market"]

    reliability = config["reliability"]

    wind_onshore_mw = float(
        assets["wind_onshore_mw"]
    )

    wind_offshore_mw = float(
        assets["wind_offshore_mw"]
    )

    pv_mw = float(
        assets["pv_mw"]
    )

    dg_mw = float(
        assets["dg_mw"]
    )

    dg_cost = float(
        assets["dg_cost_eur_mwh"]
    )

    dr_mw = float(
        assets["dr_mw"]
    )

    bess_energy_mwh = float(
        assets["bess_energy_mwh"]
    )

    bess_charge_mw = float(
        assets["bess_charge_mw"]
    )

    bess_discharge_mw = float(
        assets["bess_discharge_mw"]
    )

    bess_initial_soc_mwh = float(
        assets["bess_initial_soc_mwh"]
    )

    bess_min_soc = (
        bess_energy_mwh
        * float(
            assets["bess_min_soc_fraction"]
        )
    )

    bess_max_soc = (
        bess_energy_mwh
        * float(
            assets["bess_max_soc_fraction"]
        )
    )

    eta_charge = float(
        assets["bess_eta_charge"]
    )

    eta_discharge = float(
        assets["bess_eta_discharge"]
    )

    degradation_cost = float(
        assets[
            "bess_degradation_cost_eur_mwh"
        ]
    )

    reserve_margin = float(
        market["reserve_margin"]
    )

    dr_price_fraction = float(
        market["dr_price_fraction"]
    )

    n_minus_1_required = bool(
        reliability["n_minus_1_required"]
    )

    dispatch_groups = int(
        reliability["dispatch_groups"]
    )

    if dispatch_groups <= 0:
        raise ValueError(
            "dispatch_groups must be positive."
        )

    # --------------------------------------------------------
    # SCENARIO INDEX
    # --------------------------------------------------------

    scenario_ids = sorted(
        scenarios["scenario_id"]
        .unique()
    )

    scenario_probabilities = (
        scenarios[
            [
                "scenario_id",
                "probability",
            ]
        ]
        .drop_duplicates("scenario_id")
        .set_index("scenario_id")
        ["probability"]
        .to_dict()
    )

    # --------------------------------------------------------
    # VARIABLE DICTIONARY
    # --------------------------------------------------------

    variables = {}

    # ========================================================
    # FIRST-STAGE / DA VARIABLES
    # ========================================================

    for t in range(HOURS):

        variables[
            ("p_da", t)
        ] = model.addVariable(
            lb=0.0,
            ub=1.0e6,
            obj=0.0,
            name=f"P_DA_{t}",
        )

        variables[
            ("p_dg", t)
        ] = model.addVariable(
            lb=0.0,
            ub=dg_mw,
            obj=0.0,
            name=f"P_DG_{t}",
        )

        variables[
            ("p_dr", t)
        ] = model.addVariable(
            lb=0.0,
            ub=dr_mw,
            obj=0.0,
            name=f"P_DR_{t}",
        )

        variables[
            ("p_ch", t)
        ] = model.addVariable(
            lb=0.0,
            ub=bess_charge_mw,
            obj=0.0,
            name=f"P_CH_{t}",
        )

        variables[
            ("p_dch", t)
        ] = model.addVariable(
            lb=0.0,
            ub=bess_discharge_mw,
            obj=0.0,
            name=f"P_DCH_{t}",
        )

        variables[
            ("soc", t)
        ] = model.addVariable(
            lb=bess_min_soc,
            ub=bess_max_soc,
            obj=0.0,
            name=f"SOC_{t}",
        )

        variables[
            ("u_ch", t)
        ] = model.addVariable(
            lb=0.0,
            ub=1.0,
            type=highspy.HighsVarType.kInteger,
            obj=0.0,
            name=f"U_CH_{t}",
        )

    # ========================================================
    # SCENARIO RECOURSE VARIABLES
    # ========================================================

    for scenario_id in scenario_ids:

        for t in range(HOURS):

            variables[
                ("p_rt", scenario_id, t)
            ] = model.addVariable(
                lb=-1.0e6,
                ub=1.0e6,
                obj=0.0,
                name=(
                    f"P_RT_{scenario_id}_{t}"
                ),
            )

            variables[
                ("reserve", scenario_id, t)
            ] = model.addVariable(
                lb=0.0,
                ub=1.0e6,
                obj=0.0,
                name=(
                    f"RES_{scenario_id}_{t}"
                ),
            )

    # ========================================================
    # OBJECTIVE
    # ========================================================

    objective_terms = []

    for t in range(HOURS):

        da_price = float(
            base.loc[
                t,
                "forecast_hybrid",
            ]
        )

        objective_terms.append(
            da_price
            * variables[
                ("p_da", t)
            ]
        )

        objective_terms.append(
            -dg_cost
            * variables[
                ("p_dg", t)
            ]
        )

        objective_terms.append(
            dr_price_fraction
            * da_price
            * variables[
                ("p_dr", t)
            ]
        )

        objective_terms.append(
            -degradation_cost
            * (
                variables[
                    ("p_ch", t)
                ]
                + variables[
                    ("p_dch", t)
                ]
            )
        )

    for scenario_id in scenario_ids:

        probability = float(
            scenario_probabilities[
                scenario_id
            ]
        )

        for t in range(HOURS):

            da_price = float(
                base.loc[
                    t,
                    "forecast_hybrid",
                ]
            )

            objective_terms.append(
                probability
                * da_price
                * variables[
                    (
                        "p_rt",
                        scenario_id,
                        t,
                    )
                ]
            )

            objective_terms.append(
                probability
                * da_price
                * reserve_margin
                * variables[
                    (
                        "reserve",
                        scenario_id,
                        t,
                    )
                ]
            )

    model.maximize(
        sum(
            objective_terms
        )
    )

    # ========================================================
    # BASE ENERGY / ASSET CONSTRAINTS
    # ========================================================

    for t in range(HOURS):

        load_forecast = float(
            base.loc[
                t,
                "load_forecast",
            ]
        )

        wind_on_forecast = float(
            base.loc[
                t,
                "wind_on_forecast",
            ]
        )

        wind_off_forecast = float(
            base.loc[
                t,
                "wind_off_forecast",
            ]
        )

        pv_forecast = float(
            base.loc[
                t,
                "pv_forecast",
            ]
        )

        wind_on_available = (
            wind_onshore_mw
            * wind_on_forecast
        )

        wind_off_available = (
            wind_offshore_mw
            * wind_off_forecast
        )

        pv_available = (
            pv_mw
            * pv_forecast
        )

        renewable_available = (
            wind_on_available
            + wind_off_available
            + pv_available
        )

        # ----------------------------------------------------
        # Base balance
        # ----------------------------------------------------

        model.addConstr(
            variables[
                ("p_da", t)
            ]
            + variables[
                ("p_dg", t)
            ]
            + variables[
                ("p_dch", t)
            ]
            - variables[
                ("p_ch", t)
            ]
            + variables[
                ("p_dr", t)
            ]
            <= load_forecast
        )

        # ----------------------------------------------------
        # DA capacity upper bound
        # ----------------------------------------------------

        model.addConstr(
            variables[
                ("p_da", t)
            ]
            <= (
                renewable_available
                + dg_mw
                + bess_discharge_mw
                + dr_mw
            )
        )

        # ----------------------------------------------------
        # BESS charge/discharge exclusivity
        # ----------------------------------------------------

        model.addConstr(
            variables[
                ("p_ch", t)
            ]
            <= (
                bess_charge_mw
                * variables[
                    ("u_ch", t)
                ]
            )
        )

        model.addConstr(
            variables[
                ("p_dch", t)
            ]
            <= (
                bess_discharge_mw
                * (
                    1.0
                    - variables[
                        ("u_ch", t)
                    ]
                )
            )
        )

        # ----------------------------------------------------
        # SOC transition
        # ----------------------------------------------------

        if t == 0:

            model.addConstr(
                variables[
                    ("soc", t)
                ]
                ==
                (
                    bess_initial_soc_mwh
                    + eta_charge
                    * variables[
                        ("p_ch", t)
                    ]
                    - (
                        1.0
                        / eta_discharge
                    )
                    * variables[
                        ("p_dch", t)
                    ]
                )
            )

        else:

            model.addConstr(
                variables[
                    ("soc", t)
                ]
                ==
                (
                    variables[
                        ("soc", t - 1)
                    ]
                    + eta_charge
                    * variables[
                        ("p_ch", t)
                    ]
                    - (
                        1.0
                        / eta_discharge
                    )
                    * variables[
                        ("p_dch", t)
                    ]
                )
            )

    # --------------------------------------------------------
    # Terminal SOC
    # --------------------------------------------------------

    model.addConstr(
        variables[
            ("soc", HOURS - 1)
        ]
        ==
        bess_initial_soc_mwh
    )

    # ========================================================
    # SCENARIO RECOURSE / RESERVE
    # ========================================================

    for scenario_id in scenario_ids:

        scenario_data = (
            scenarios[
                scenarios["scenario_id"]
                == scenario_id
            ]
            .sort_values("hour")
            .reset_index(drop=True)
        )

        if len(scenario_data) != HOURS:
            raise RuntimeError(
                f"Scenario {scenario_id} does not "
                f"contain exactly {HOURS} hours."
            )

        for t in range(HOURS):

            scenario_row = (
                scenario_data.iloc[t]
            )

            load_error = float(
                scenario_row[
                    "load_error_bc"
                ]
            )

            price_error = float(
                scenario_row[
                    "price_error_bc"
                ]
            )

            del price_error

            # ------------------------------------------------
            # Available flexible capability
            # ------------------------------------------------

            flexible_capacity = (
                dg_mw
                + dr_mw
                + bess_discharge_mw
            )

            # ------------------------------------------------
            # Reserve limit
            # ------------------------------------------------

            model.addConstr(
                variables[
                    (
                        "reserve",
                        scenario_id,
                        t,
                    )
                ]
                <= flexible_capacity
            )

            # ------------------------------------------------
            # Recourse energy
            # ------------------------------------------------

            model.addConstr(
                variables[
                    (
                        "p_rt",
                        scenario_id,
                        t,
                    )
                ]
                <= (
                    flexible_capacity
                    + max(
                        0.0,
                        load_error
                    )
                    + 1.0e6
                )
            )

            model.addConstr(
                variables[
                    (
                        "p_rt",
                        scenario_id,
                        t,
                    )
                ]
                >= -(
                    flexible_capacity
                    + max(
                        0.0,
                        -load_error
                    )
                    + 1.0e6
                )
            )

    # ========================================================
    # N-1 RELIABILITY BRIDGE
    # ========================================================

    if n_minus_1_required:

        # ----------------------------------------------------
        # Current bridge:
        # aggregate deliverable flexibility cannot exceed
        # physical flexible capacity.
        #
        # The exact group-specific N-1 equations from the
        # final manuscript must replace this bridge.
        # ----------------------------------------------------

        for scenario_id in scenario_ids:

            for t in range(HOURS):

                model.addConstr(
                    variables[
                        (
                            "reserve",
                            scenario_id,
                            t,
                        )
                    ]
                    <= (
                        dg_mw
                        + dr_mw
                        + bess_discharge_mw
                    )
                )

    return model


# ============================================================
# SOLVE ONE SCENARIO COUNT
# ============================================================

def solve_one_k(
    base,
    scenarios,
    config,
    k
):
    """
    Solve the current MILP bridge for one reduced
    scenario count.
    """

    print("\n----------------------------------------------")
    print(
        f"RUNNING MILP BRIDGE — K={k}"
    )
    print("----------------------------------------------")

    start_time = time.perf_counter()

    model = build_model(
        base=base,
        scenarios=scenarios,
        config=config,
    )

    model.run()

    runtime = (
        time.perf_counter()
        - start_time
    )

    model_status = str(
        model.getModelStatus()
    )

    try:
        objective = float(
            model.getObjectiveValue()
        )
    except Exception:
        objective = None

    print(
        f"Model status : {model_status}"
    )

    print(
        f"Objective    : {objective}"
    )

    print(
        f"Runtime      : {runtime:.3f} s"
    )

    return {
        "K": int(k),
        "status": model_status,
        "objective": objective,
        "runtime_seconds": float(runtime),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10F.1 — STOCHASTIC MILP BRIDGE")
    print("==============================================\n")

    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------

    config = load_config()

    validate_model_parameters(
        config
    )

    # --------------------------------------------------------
    # Base information set
    # --------------------------------------------------------

    base = load_base_data(
        config
    )

    print(
        f"Study date     : "
        f"{config['study_date']}"
    )

    print(
        f"Hourly records : "
        f"{len(base)}"
    )

    # --------------------------------------------------------
    # Solve K = 100 / 50 / 30
    # --------------------------------------------------------

    results = []

    for k in [
        100,
        50,
        30,
    ]:

        scenarios = load_reduced_scenarios(
            k
        )

        result = solve_one_k(
            base=base,
            scenarios=scenarios,
            config=config,
            k=k,
        )

        results.append(
            result
        )

    # --------------------------------------------------------
    # Save comparison
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        results
    )

    comparison_file = (
        RESULTS_DIR
        / "gate10f1_k_comparison.csv"
    )

    result_df.to_csv(
        comparison_file,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Save report
    # --------------------------------------------------------

    report = {
        "gate": "10F.1",

        "status": "COMPLETE",

        "model_type":
            "Parameterized stochastic MILP bridge",

        "study_date":
            config["study_date"],

        "results":
            results,

        "important_note":
            (
                "This bridge is not yet the final "
                "manuscript MILP formulation. "
                "The exact dispatch-group N-1 formulation, "
                "market coupling, intraday decision equations, "
                "and final asset parameters must be "
                "provided from the final model before "
                "results are reported as manuscript results."
            ),
    }

    report_file = (
        RESULTS_DIR
        / "gate10f1_report.json"
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
    print(" GATE 10F.1 COMPLETE")
    print("==============================================")

    print(
        f"\nComparison file:\n"
        f"{comparison_file}"
    )

    print(
        f"\nReport:\n"
        f"{report_file}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
