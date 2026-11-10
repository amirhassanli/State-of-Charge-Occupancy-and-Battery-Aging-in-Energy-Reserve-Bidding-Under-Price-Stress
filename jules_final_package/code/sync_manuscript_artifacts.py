"""Update the revised manuscript's data and reproducibility disclosures."""
from pathlib import Path

from docx import Document

paper_dir = Path(__file__).resolve().parents[1] / "paper"
path = next(paper_dir.glob("*_revised.docx"))
document = Document(path)

old_data_marker = "The retrieval date and archived panel CSV are not included"
new_data = (
    "The public market and physical series were retrieved from the Energy-Charts API on 30 October 2026. "
    "The unchanged API responses, derived hourly panel, scaling factors, endpoint URLs, licenses, and SHA-256 "
    "hashes are archived in the accompanying data package. These are national market and power-system series, "
    "not battery telemetry; battery ratings and aging coefficients remain model inputs."
)
old_repro_marker = "The manuscript reports Python/Pyomo with HiGHS and random seed 20260821."
new_repro = (
    "The manuscript reports Python/Pyomo with HiGHS and random seed 20260821. The original model source is not "
    "present in the supplied artifact; the accompanying Python implementation is a reviewer-oriented "
    "reconstruction and uses SciPy's MILP interface rather than the reported Pyomo/HiGHS pipeline. The public "
    "market and system time series retrieved on 30 October 2026, their raw API responses, the derived hourly "
    "panel, and new reconstructed diagnostics are now included in the data package. The reconstruction uses "
    "code defaults for initial SoC, reserve sustainment, and separate charge/discharge gamma values because the "
    "manuscript does not specify these parameters. Accordingly, the new runs do not reproduce the original "
    "numerical tables and are archived separately; they must not be substituted for Tables III-VI. Exact "
    "replication still requires the original source, the exact data snapshot used in the reported runs, and the "
    "complete original parameter configuration."
)


def replace_paragraph(marker: str, replacement: str) -> None:
    matches = [p for p in document.paragraphs if marker in p.text]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph containing {marker!r}, found {len(matches)}")
    paragraph = matches[0]
    if not paragraph.runs:
        paragraph.add_run(replacement)
        return
    paragraph.runs[0].text = replacement
    for run in paragraph.runs[1:]:
        run.text = ""


replace_paragraph(old_data_marker, new_data)
replace_paragraph(old_repro_marker, new_repro)
document.save(path)

check = Document(path)
text = "\n".join(paragraph.text for paragraph in check.paragraphs)
for required in (
    "retrieved from the Energy-Charts API on 30 October 2026",
    "not battery telemetry",
    "new runs do not reproduce the original numerical tables",
    "must not be substituted for Tables III-VI",
):
    if required not in text:
        raise RuntimeError(f"Saved manuscript is missing required disclosure: {required}")
print(f"Updated and verified data/reproducibility disclosures in {path.name}")
