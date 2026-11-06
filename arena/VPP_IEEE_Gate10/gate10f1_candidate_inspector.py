from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


FILES = [
    ROOT / "1.py",
]


KEY_PATTERNS = {
    "pyomo": r"\bpyomo\b",
    "highspy": r"\bhighspy\b",
    "objective": r"\bObjective\s*\(",
    "constraint": r"\bConstraint\s*\(",
    "variable": r"\bVar\s*\(",
    "binary": r"\bBinary\b",
    "solver": r"\.solve\s*\(",
    "milp": r"\bMILP\b",
    "bess": r"\bBESS\b|\bbattery\b",
    "dispatch_group": r"dispatch[_ ]group",
    "n_minus_1": r"N[\-\u2212]1|N[\-\u2212]1",
    "reserve": r"\breserve\b",
    "intraday": r"\bintraday\b",
    "day_ahead": r"day[\-\ ]ahead",
    "demand_response": r"demand response|\bDR\b",
    "rolling_horizon": r"rolling[\-\ ]horizon",
}


def inspect(path):

    if not path.exists():
        return {
            "file": str(path),
            "exists": False,
        }

    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    results = {}

    for name, pattern in KEY_PATTERNS.items():

        results[name] = len(
            re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

    return {
        "file": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "patterns": results,
        "first_120_lines": (
            text.splitlines()[:120]
        ),
    }


def main():

    print("\n==============================================")
    print(" GATE 10F.1 — CANDIDATE INSPECTION")
    print("==============================================")

    report = []

    for path in FILES:

        result = inspect(path)

        report.append(result)

        print(
            f"\nFILE: {path.name}"
        )

        if not result["exists"]:
            print("NOT FOUND")
            continue

        print(
            f"Size: "
            f"{result['size_bytes']:,} bytes"
        )

        print("\nPattern counts:")

        for k, v in result[
            "patterns"
        ].items():

            print(
                f"  {k:20s}: {v}"
            )

        print(
            "\nFirst 120 lines:"
        )

        for i, line in enumerate(
            result["first_120_lines"],
            start=1,
        ):

            print(
                f"{i:4d}: {line}"
            )

    output = (
        REPORTS /
        "gate10f1_candidate_inspection.json"
    )

    with open(
        output,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"\nReport saved:\n{output}"
    )


if __name__ == "__main__":
    main()