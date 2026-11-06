from pathlib import Path
import json
import zipfile
import re


# ============================================================
# ROOT SEARCH LOCATION
# ============================================================

GATE_ROOT = Path(__file__).resolve().parent

# Search the whole "مقاله 4" directory
SEARCH_ROOT = GATE_ROOT.parent


# ============================================================
# EXCLUSIONS
# ============================================================

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
    "results",
    "scenarios",
}


# ============================================================
# FILE TYPES
# ============================================================

TEXT_EXTENSIONS = {
    ".py",
    ".ipynb",
    ".mps",
    ".lp",
    ".mod",
    ".nl",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
}

DOCUMENT_EXTENSIONS = {
    ".docx",
}


# ============================================================
# MODEL KEYWORDS
# ============================================================

KEYWORDS = [
    "ConcreteModel",
    "AbstractModel",
    "Pyomo",
    "highspy",
    "SolverFactory",
    "Objective(",
    "Constraint(",
    "Var(",
    "Binary",
    "Integers",
    "MILP",
    "Mixed-Integer",
    "stochastic",
    "rolling horizon",
    "N-1",
    "N−1",
    "BESS",
    "battery",
    "dispatch group",
    "dispatch_group",
    "reserve",
    "secondary reserve",
    "intraday",
    "day-ahead",
    "demand response",
    "DR",
    "virtual power plant",
    "VPP",
    "profit",
    "CVaR",
    "scenario",
]


# ============================================================
# SCORE FILE
# ============================================================

def score_text(text):

    lowered = text.lower()

    matches = []

    for kw in KEYWORDS:

        if kw.lower() in lowered:
            matches.append(kw)

    score = 0

    # Strong indicators
    score += 10 * len(
        re.findall(
            r"ConcreteModel|AbstractModel",
            text,
            re.IGNORECASE,
        )
    )

    score += 8 * len(
        re.findall(
            r"Objective\s*\(",
            text,
        )
    )

    score += 5 * len(
        re.findall(
            r"Constraint\s*\(",
            text,
        )
    )

    score += 5 * len(
        re.findall(
            r"Var\s*\(",
            text,
        )
    )

    score += 6 * len(
        re.findall(
            r"SolverFactory|highspy",
            text,
            re.IGNORECASE,
        )
    )

    score += 3 * len(matches)

    return score, matches


# ============================================================
# READ TEXT FILE
# ============================================================

def inspect_text_file(path):

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return None

    score, matches = score_text(text)

    if score <= 0:
        return None

    return {
        "file": str(path),
        "relative_path": str(
            path.relative_to(SEARCH_ROOT)
        ),
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "score": score,
        "keywords": matches,
    }


# ============================================================
# READ DOCX
# ============================================================

def inspect_docx(path):

    try:

        with zipfile.ZipFile(
            path,
            "r",
        ) as z:

            names = [
                n
                for n in z.namelist()
                if n.endswith(".xml")
            ]

            pieces = []

            for name in names:

                try:
                    data = z.read(
                        name
                    ).decode(
                        "utf-8",
                        errors="ignore",
                    )

                    pieces.append(data)

                except Exception:
                    pass

            text = "\n".join(
                pieces
            )

    except Exception:
        return None

    score, matches = score_text(
        text
    )

    if score <= 0:
        return None

    return {
        "file": str(path),
        "relative_path": str(
            path.relative_to(SEARCH_ROOT)
        ),
        "extension": ".docx",
        "size_bytes": path.stat().st_size,
        "score": score,
        "keywords": matches,
    }


# ============================================================
# SCAN
# ============================================================

def main():

    print("\n==============================================")
    print(" GATE 10F.1 — GLOBAL MODEL DISCOVERY")
    print("==============================================\n")

    print(
        f"Search root:\n{SEARCH_ROOT}"
    )

    results = []

    # --------------------------------------------------------
    # Scan all relevant files
    # --------------------------------------------------------

    for path in SEARCH_ROOT.rglob("*"):

        if not path.is_file():
            continue

        relative_parts = set(
            path.relative_to(
                SEARCH_ROOT
            ).parts
        )

        if relative_parts & EXCLUDE_DIRS:
            continue

        ext = path.suffix.lower()

        result = None

        if ext in TEXT_EXTENSIONS:

            result = inspect_text_file(
                path
            )

        elif ext in DOCUMENT_EXTENSIONS:

            result = inspect_docx(
                path
            )

        if result:
            results.append(
                result
            )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    results.sort(
        key=lambda x: (
            x["score"],
            x["size_bytes"],
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Console
    # --------------------------------------------------------

    print("\n----------------------------------------------")
    print("TOP MODEL CANDIDATES")
    print("----------------------------------------------")

    if not results:

        print(
            "NO MODEL CANDIDATES FOUND."
        )

    else:

        for i, item in enumerate(
            results[:50],
            start=1,
        ):

            print(
                f"\n{i}. "
                f"{item['relative_path']}"
            )

            print(
                f"   score    : "
                f"{item['score']}"
            )

            print(
                f"   type     : "
                f"{item['extension']}"
            )

            print(
                f"   keywords : "
                f"{', '.join(item['keywords'][:20])}"
            )

    # --------------------------------------------------------
    # Separate likely executable models
    # --------------------------------------------------------

    executable = []

    for item in results:

        ext = item["extension"]

        keywords = {
            k.lower()
            for k in item["keywords"]
        }

        has_model_construct = (
            "concretemodel" in keywords
            or
            "abstractmodel" in keywords
            or
            "objective(" in keywords
            or
            "constraint(" in keywords
            or
            "var(" in keywords
            or
            "highspy" in keywords
            or
            "pyomo" in keywords
        )

        if (
            ext in {".py", ".ipynb", ".mps", ".lp"}
            and has_model_construct
        ):
            executable.append(item)

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {
        "gate": "10F.1",
        "status": "MODEL_DISCOVERY_COMPLETE",
        "search_root": str(
            SEARCH_ROOT
        ),
        "candidate_count": len(results),
        "executable_model_count": len(
            executable
        ),
        "top_candidates": results[:50],
        "executable_candidates": executable[:30],
        "next_action": (
            "Select the actual final MILP source "
            "before connecting K=100/50/30 scenarios."
        ),
    }

    output = (
        GATE_ROOT
        / "reports"
        / "gate10f1_global_model_search.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
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

    print("\n==============================================")
    print(" GLOBAL MODEL SEARCH COMPLETE")
    print("==============================================")

    print(
        f"\nCandidates found: "
        f"{len(results)}"
    )

    print(
        f"Executable model candidates: "
        f"{len(executable)}"
    )

    print(
        f"\nReport:\n{output}"
    )


if __name__ == "__main__":
    main()