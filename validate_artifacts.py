"""Validate downloaded data, provenance, diagnostics, task config, and revised manuscript."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from docx import Document

root = Path(__file__).resolve().parent
data_dir = root / "data"
paper_dir = root / "paper"
manifest_path = next((data_dir / "metadata").glob("manifest_*.json"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
rel_panel = Path(*manifest["processed_panel"]["path"].replace("\\", "/").split("/"))
panel_path = data_dir / rel_panel
panel_b = panel_path.read_bytes()
assert (hashlib.sha256(panel_b).hexdigest() == manifest["processed_panel"]["sha256"]) or (hashlib.sha256(panel_b.replace(b"\n", b"\r\n")).hexdigest() == manifest["processed_panel"]["sha256"])
with panel_path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == manifest["processing"]["usable_hourly_rows"] == 6319
assert {"timestamp", "da_price", "load", "pv", "wind"}.issubset(rows[0])

stamp = f"{manifest['requested_local_start']}_{manifest['requested_local_end']}"
raw_dir = data_dir / "raw" / "energy_charts"
for name, filename in (
    ("day_ahead_price", f"price_DE-LU_{stamp}.json"),
    ("public_power", f"public_power_DE_{stamp}.json"),
):
    source = manifest["sources"][name]
    assert hashlib.sha256((raw_dir / filename).read_bytes()).hexdigest() == source["sha256"]
assert manifest["processing"]["complete_24h_days"] == 262
assert manifest["battery_telemetry"] is None

results = data_dir / "results"
assert (results / "cross_2026-05-01.csv").is_file()
assert (results / "relaxed_lp" / "cross_2026-05-01.csv").is_file()
scan_path = results / "negative_scan_lp" / "scan.csv"
assert scan_path.is_file()
with scan_path.open(newline="", encoding="utf-8") as handle:
    scan_rows = list(csv.DictReader(handle))
assert len(scan_rows) == 20

battery = json.loads((data_dir / "parameters" / "battery_model.json").read_text(encoding="utf-8"))
assert battery["not_reported_in_manuscript"]["relcca_cycle_gamma_by_band"] is None
tasks = json.loads((root / "code" / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
labels = [task["label"] for task in tasks["tasks"]]
assert len(labels) == len(set(labels))

revised = next(paper_dir.glob("*_revised.docx"))
with ZipFile(revised) as archive:
    xml = ET.fromstring(archive.read("word/document.xml"))
math_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
first_math = xml.find(".//" + math_ns + "oMath")
assert first_math is not None
math_tokens = [node.text or "" for node in first_math.iter(math_ns + "t")]
operator_index = next(i for i, token in enumerate(math_tokens) if token in {"+", "-"})
assert "".join(math_tokens[:operator_index]) == "PtDA"
assert math_tokens[operator_index] == "-"
text = "\n".join(paragraph.text for paragraph in Document(revised).paragraphs)
assert "new runs do not reproduce the original numerical tables" in text
assert "must not be substituted for Tables III-VI" in text

print("PASS: raw and processed data hashes, row count, 262 complete days, three diagnostic outputs, battery assumptions, unique tasks, and revised Eq. (1)/disclosures verified.")
