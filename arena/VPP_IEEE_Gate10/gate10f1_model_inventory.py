from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parent

REPORTS = ROOT / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

OUTPUT = REPORTS / "gate10f1_model_inventory.json"


# ============================================================
# FILE PATTERNS
# ============================================================

KEYWORDS = [
    "pyomo",
    "highspy",
    "ConcreteModel",
    "AbstractModel",
    "Objective",
    "Constraint",
    "Var(",
    "Binary",
    "Integers",
    "SolverFactory",
    "highs",
    "milp",
    "N-1",
    "n-1",
    "BESS",
    "battery",
    "dispatch",
    "reserve",
    "demand response",
    "DR",
    "rolling",
    "scenario",
]


EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "data",
    "reports",
    "figures",
}


# ============================================================
# SCAN PYTHON FILE
# ============================================================

def scan_python_file(path):

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception:
        return None

    lowered = text.lower()

    matches = []

    for keyword in KEYWORDS:

        if keyword.lower() in lowered:

            matches.append(keyword)

    # --------------------------------------------------------
    # Count important constructs
    # --------------------------------------------------------

    counts = {
        "pyomo_imports":
            len(re.findall(
                r"from\s+pyomo|import\s+pyomo",
                text,
                re.IGNORECASE
            )),

        "highspy":
            len(re.findall(
                r"highspy",
                text,
                re.IGNORECASE
            )),

        "objectives":
            len(re.findall(
                r"\bObjective\s*\(",
                text
            )),

        "constraints":
            len(re.findall(
                r"\bConstraint\s*\(",
                text
            )),

        "variables":
            len(re.findall(
                r"\bVar\s*\(",
                text
            )),

        "binary":
            len(re.findall(
                r"\bBinary\b",
                text
            )),

        "solver_calls":
            len(re.findall(
                r"\.solve\s*\(",
                text
            )),
    }

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    score = (
        4 * counts["objectives"]
        + 2 * counts["constraints"]
        + 2 * counts["variables"]
        + 3 * counts["solver_calls"]
        + 3 * counts["pyomo_imports"]
        + 3 * counts["highspy"]
        + len(matches)
    )

    return {
        "file": str(path),
        "relative_path": str(
            path.relative_to(ROOT)
        ),
        "size_bytes": path.stat().st_size,
        "score": score,
        "keywords": matches,
        "counts": counts,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10F.1 — MODEL INVENTORY")
    print("==============================================\n")

    results = []

    for path in ROOT.rglob("*.py"):

        relative_parts = set(
            path.relative_to(ROOT).parts
        )

        if relative_parts & EXCLUDE_DIRS:
            continue

        result = scan_python_file(
            path
        )

        if result is not None:
            results.append(result)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # Print candidates
    # --------------------------------------------------------

    print("----------------------------------------------")
    print("TOP MODEL CANDIDATES")
    print("----------------------------------------------")

    if not results:

        print(
            "No Python files found."
        )

    else:

        for i, item in enumerate(
            results[:20],
            start=1
        ):

            print(
                f"\n{i}. "
                f"{item['relative_path']}"
            )

            print(
                f"   score = {item['score']}"
            )

            print(
                f"   Objective = "
                f"{item['counts']['objectives']}"
            )

            print(
                f"   Constraint = "
                f"{item['counts']['constraints']}"
            )

            print(
                f"   Var = "
                f"{item['counts']['variables']}"
            )

            print(
                f"   solve() = "
                f"{item['counts']['solver_calls']}"
            )

            print(
                f"   keywords = "
                f"{', '.join(item['keywords'][:10])}"
            )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {
        "gate": "10F.1",
        "status": "INVENTORY_COMPLETE",
        "project_root": str(ROOT),
        "python_file_count": len(results),
        "top_candidates": results[:20],
    }

    with open(
        OUTPUT,
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
    print(" MODEL INVENTORY COMPLETE")
    print("==============================================")

    print(
        f"\nReport:\n{OUTPUT}"
    )


if __name__ == "__main__":
    main()