from pathlib import Path
import json

import numpy as np
import pandas as pd

from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

SCENARIOS_DIR = ROOT / "data" / "scenarios"
REDUCED_DIR = SCENARIOS_DIR / "reduced_scenarios"
REPORTS_DIR = ROOT / "reports"

SCENARIOS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

REDUCED_DIR.mkdir(
    parents=True,
    exist_ok=True
)

REPORTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# INPUT
# ============================================================

INPUT_FILE = (
    SCENARIOS_DIR
    / "empirical_block_bootstrap_5000_scenarios.csv.gz"
)


# ============================================================
# SETTINGS
# ============================================================

TARGETS = [100, 50, 30]

N_SOURCE_SCENARIOS = 5000
HOURS = 24

VARIABLES = [
    "price_error_bc",
    "load_error_bc",
    "wind_on_error_bc",
    "wind_off_error_bc",
    "pv_error_bc",
]

RANDOM_STATE = 20260817


# ============================================================
# LOAD
# ============================================================

def load_scenarios():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing scenario file:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required = [
        "scenario_id",
        "hour",
        "probability",
        *VARIABLES,
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    for col in VARIABLES:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = (
        df
        .sort_values(
            ["scenario_id", "hour"]
        )
        .reset_index(drop=True)
    )

    return df


# ============================================================
# BUILD TRAJECTORY MATRIX
# ============================================================

def build_trajectory_matrix(df):

    scenario_ids = np.sort(
        df["scenario_id"]
        .drop_duplicates()
        .to_numpy()
    )

    matrix = []

    for sid in scenario_ids:

        group = (
            df[
                df["scenario_id"] == sid
            ]
            .sort_values("hour")
        )

        if len(group) != HOURS:
            raise ValueError(
                f"Scenario {sid} has "
                f"{len(group)} rows; "
                f"expected {HOURS}."
            )

        row = []

        # Fixed order:
        # price → load → wind_on → wind_off → PV
        for col in VARIABLES:

            values = (
                group[col]
                .to_numpy(dtype=float)
            )

            row.extend(values)

        matrix.append(row)

    matrix = np.asarray(
        matrix,
        dtype=float
    )

    expected_dimension = (
        HOURS * len(VARIABLES)
    )

    if matrix.shape != (
        len(scenario_ids),
        expected_dimension
    ):
        raise ValueError(
            f"Unexpected trajectory matrix shape: "
            f"{matrix.shape}"
        )

    return scenario_ids, matrix


# ============================================================
# REDUCE
# ============================================================

def reduce_scenarios(
    matrix,
    target_k
):

    # --------------------------------------------------------
    # Standardize every trajectory dimension
    # --------------------------------------------------------

    scaler = StandardScaler()

    X = scaler.fit_transform(
        matrix
    )

    # --------------------------------------------------------
    # MiniBatch K-Means
    # --------------------------------------------------------

    model = MiniBatchKMeans(
        n_clusters=target_k,
        random_state=RANDOM_STATE,
        batch_size=256,
        n_init=10,
        max_iter=300,
        reassignment_ratio=0.01,
    )

    labels = model.fit_predict(X)

    centers = model.cluster_centers_

    # --------------------------------------------------------
    # Select one real scenario closest to each center
    # --------------------------------------------------------

    selected_indices = []

    cluster_sizes = []

    for cluster_id in range(target_k):

        idx = np.where(
            labels == cluster_id
        )[0]

        if len(idx) == 0:
            raise RuntimeError(
                f"Empty cluster detected: "
                f"{cluster_id}"
            )

        cluster_points = X[idx]

        center = centers[
            cluster_id
        ]

        distances = np.sum(
            (
                cluster_points
                - center
            ) ** 2,
            axis=1
        )

        local_best = int(
            np.argmin(distances)
        )

        selected_indices.append(
            idx[local_best]
        )

        cluster_sizes.append(
            len(idx)
        )

    selected_indices = np.asarray(
        selected_indices,
        dtype=int
    )

    cluster_sizes = np.asarray(
        cluster_sizes,
        dtype=int
    )

    probabilities = (
        cluster_sizes
        / len(matrix)
    )

    # --------------------------------------------------------
    # Reconstruction error
    # --------------------------------------------------------

    selected_centers = centers[
        labels[
            selected_indices
        ]
    ]

    # Actual nearest representative
    selected_scaled = X[
        selected_indices
    ]

    distances = np.sum(
        (
            X[:, None, :]
            - selected_scaled[None, :, :]
        ) ** 2,
        axis=2
    )

    nearest = np.min(
        distances,
        axis=1
    )

    reconstruction_error = float(
        np.mean(nearest)
    )

    return (
        selected_indices,
        probabilities,
        cluster_sizes,
        reconstruction_error,
        scaler,
    )


# ============================================================
# WEIGHTED DISTRIBUTION ERROR
# ============================================================

def calculate_distribution_error(
    original_matrix,
    reduced_matrix,
    probabilities,
):

    errors = []

    for j, variable in enumerate(
        VARIABLES
    ):

        start = j * HOURS
        end = (j + 1) * HOURS

        original = (
            original_matrix[
                :,
                start:end
            ]
            .mean(axis=1)
        )

        reduced = (
            reduced_matrix[
                :,
                start:end
            ]
            .mean(axis=1)
        )

        original_mean = (
            np.mean(original)
        )

        reduced_mean = (
            np.sum(
                reduced
                * probabilities
            )
        )

        original_std = (
            np.std(
                original,
                ddof=1
            )
        )

        reduced_std = np.sqrt(
            np.sum(
                probabilities
                * (
                    reduced
                    - reduced_mean
                ) ** 2
            )
        )

        mean_error = abs(
            reduced_mean
            - original_mean
        )

        std_error = abs(
            reduced_std
            - original_std
        )

        errors.append({
            "variable": variable,
            "mean_error": float(
                mean_error
            ),
            "std_error": float(
                std_error
            ),
        })

    result = pd.DataFrame(
        errors
    )

    return result


# ============================================================
# BUILD REDUCED FILE
# ============================================================

def build_reduced_dataset(
    source_df,
    selected_source_ids,
    probabilities
):

    rows = []

    for new_id, (
        source_id,
        probability
    ) in enumerate(
        zip(
            selected_source_ids,
            probabilities
        ),
        start=1
    ):

        group = (
            source_df[
                source_df["scenario_id"]
                == source_id
            ]
            .sort_values("hour")
        )

        if len(group) != HOURS:
            raise RuntimeError(
                f"Selected source scenario "
                f"{source_id} is incomplete."
            )

        for _, row in group.iterrows():

            rows.append({
                "scenario_id":
                    new_id,

                "source_scenario_id":
                    int(source_id),

                "hour":
                    int(row["hour"]),

                "probability":
                    float(probability),

                "price_error_bc":
                    float(
                        row["price_error_bc"]
                    ),

                "load_error_bc":
                    float(
                        row["load_error_bc"]
                    ),

                "wind_on_error_bc":
                    float(
                        row["wind_on_error_bc"]
                    ),

                "wind_off_error_bc":
                    float(
                        row["wind_off_error_bc"]
                    ),

                "pv_error_bc":
                    float(
                        row["pv_error_bc"]
                    ),
            })

    return pd.DataFrame(rows)


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10E — SCENARIO REDUCTION")
    print("==============================================\n")

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = load_scenarios()

    print(
        f"Loaded rows: "
        f"{len(df):,}"
    )

    n_unique = (
        df["scenario_id"]
        .nunique()
    )

    print(
        f"Source scenarios: "
        f"{n_unique:,}"
    )

    if n_unique != N_SOURCE_SCENARIOS:
        raise ValueError(
            f"Expected {N_SOURCE_SCENARIOS} "
            f"source scenarios, got {n_unique}."
        )

    # --------------------------------------------------------
    # Check probability
    # --------------------------------------------------------

    scenario_probabilities = (
        df[
            [
                "scenario_id",
                "probability"
            ]
        ]
        .drop_duplicates(
            "scenario_id"
        )
    )

    source_probability_sum = float(
        scenario_probabilities[
            "probability"
        ].sum()
    )

    if not np.isclose(
        source_probability_sum,
        1.0,
        atol=1e-12
    ):
        raise ValueError(
            "Source scenario probabilities "
            "do not sum to 1."
        )

    print(
        f"Source probability sum: "
        f"{source_probability_sum:.12f}"
    )

    # --------------------------------------------------------
    # Matrix
    # --------------------------------------------------------

    scenario_ids, matrix = (
        build_trajectory_matrix(df)
    )

    print(
        f"Trajectory matrix: "
        f"{matrix.shape}"
    )

    results = []

    # --------------------------------------------------------
    # Run K values
    # --------------------------------------------------------

    for k in TARGETS:

        print("\n----------------------------------------------")
        print(
            f"REDUCTION: K = {k}"
        )
        print("----------------------------------------------")

        (
            selected_indices,
            probabilities,
            cluster_sizes,
            reconstruction_error,
            _,
        ) = reduce_scenarios(
            matrix,
            k
        )

        selected_source_ids = (
            scenario_ids[
                selected_indices
            ]
        )

        selected_matrix = (
            matrix[
                selected_indices
            ]
        )

        # ----------------------------------------------------
        # Distribution diagnostics
        # ----------------------------------------------------

        distribution = (
            calculate_distribution_error(
                matrix,
                selected_matrix,
                probabilities
            )
        )

        mean_error = float(
            distribution[
                "mean_error"
            ].mean()
        )

        std_error = float(
            distribution[
                "std_error"
            ].mean()
        )

        # ----------------------------------------------------
        # Save diagnostics
        # ----------------------------------------------------

        diagnostic_file = (
            REDUCED_DIR
            / f"reduction_diagnostics_{k}.csv"
        )

        distribution.to_csv(
            diagnostic_file,
            index=False,
            encoding="utf-8-sig"
        )

        # ----------------------------------------------------
        # Save reduced dataset
        # ----------------------------------------------------

        reduced_df = (
            build_reduced_dataset(
                df,
                selected_source_ids,
                probabilities
            )
        )

        output_file = (
            REDUCED_DIR
            / f"scenario_reduced_{k}.csv"
        )

        reduced_df.to_csv(
            output_file,
            index=False,
            encoding="utf-8-sig"
        )

        # ----------------------------------------------------
        # Integrity checks
        # ----------------------------------------------------

        reduced_probability_sum = float(
            reduced_df[
                [
                    "scenario_id",
                    "probability"
                ]
            ]
            .drop_duplicates(
                "scenario_id"
            )[
                "probability"
            ]
            .sum()
        )

        if not np.isclose(
            reduced_probability_sum,
            1.0,
            atol=1e-12
        ):
            raise RuntimeError(
                f"K={k}: reduced probabilities "
                f"do not sum to 1."
            )

        row_count = len(
            reduced_df
        )

        expected_rows = (
            k * HOURS
        )

        if row_count != expected_rows:
            raise RuntimeError(
                f"K={k}: expected "
                f"{expected_rows} rows, "
                f"got {row_count}."
            )

        # ----------------------------------------------------
        # Save result
        # ----------------------------------------------------

        result = {
            "target_k":
                int(k),

            "selected_scenarios":
                int(k),

            "source_scenarios":
                int(N_SOURCE_SCENARIOS),

            "rows":
                int(row_count),

            "probability_sum":
                reduced_probability_sum,

            "min_probability":
                float(
                    probabilities.min()
                ),

            "max_probability":
                float(
                    probabilities.max()
                ),

            "reconstruction_error":
                reconstruction_error,

            "mean_distribution_error":
                mean_error,

            "mean_std_error":
                std_error,

            "output_file":
                str(output_file),

            "diagnostic_file":
                str(diagnostic_file),
        }

        results.append(result)

        print(
            f"Selected scenarios : {k}"
        )

        print(
            f"Probability sum    : "
            f"{reduced_probability_sum:.12f}"
        )

        print(
            f"Reconstruction err : "
            f"{reconstruction_error:.6f}"
        )

        print(
            f"Mean dist. error   : "
            f"{mean_error:.6f}"
        )

        print(
            f"Mean std. error    : "
            f"{std_error:.6f}"
        )

        print(
            f"Saved:\n{output_file}"
        )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    report = {
        "gate": "10E",
        "status": "PASS",
        "method":
            "Standardized trajectory clustering "
            "with representative real-scenario selection",
        "source":
            str(INPUT_FILE),
        "source_scenarios":
            N_SOURCE_SCENARIOS,
        "hours_per_scenario":
            HOURS,
        "trajectory_dimension":
            HOURS * len(VARIABLES),
        "targets":
            TARGETS,
        "results":
            results,
    }

    report_file = (
        REPORTS /
        "gate10e_scenario_reduction_report.json"
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
    print(" GATE 10E COMPLETE")
    print("==============================================")

    print(
        f"\nReport:\n{report_file}"
    )

    print(
        "\nNext checkpoint:"
    )

    print(
        "GATE 10F — STOCHASTIC MILP"
    )


if __name__ == "__main__":
    main()
