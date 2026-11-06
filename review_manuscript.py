"""Create a separately reviewed Word copy with verified equations and references."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

root = Path(__file__).resolve().parents[1]
paper_dir = root / "paper"
source = next(p for p in paper_dir.glob("*_revised.docx") if not p.name.startswith("~"))
target = source.with_name(source.stem.replace("_revised", "") + "_reviewed.docx")
document = Document(source)


def replace_paragraph(prefix: str, replacement: str) -> None:
    matches = [p for p in document.paragraphs if p.text.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph starting {prefix!r}; found {len(matches)}")
    paragraph = matches[0]
    if paragraph.runs:
        paragraph.runs[0].text = replacement
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(replacement)


def remove_paragraph(prefix: str) -> None:
    matches = [p for p in document.paragraphs if p.text.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one paragraph starting {prefix!r}; found {len(matches)}")
    paragraph = matches[0]
    paragraph._element.getparent().remove(paragraph._element)


def replace_reference(number: int, segments: list[tuple[str, bool]]) -> None:
    marker = f"[{number}]"
    matches = [p for p in document.paragraphs if p.text.startswith(marker)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one bibliography entry {marker}; found {len(matches)}")
    paragraph = matches[0]
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)
    for text, italic in segments:
        run = paragraph.add_run(text)
        run.italic = italic


def math_run(text: str):
    run = OxmlElement("m:r")
    token = OxmlElement("m:t")
    if text[:1].isspace() or text[-1:].isspace():
        token.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    token.text = text
    run.append(token)
    return run


def math_sub(base: str, subscript: str):
    node = OxmlElement("m:sSub")
    exponent = OxmlElement("m:e")
    exponent.append(math_run(base))
    sub = OxmlElement("m:sub")
    sub.append(math_run(subscript))
    node.extend([exponent, sub])
    return node


def math_subsup(base: str, subscript: str, superscript: str):
    node = OxmlElement("m:sSubSup")
    exponent = OxmlElement("m:e")
    exponent.append(math_run(base))
    sub = OxmlElement("m:sub")
    sub.append(math_run(subscript))
    sup = OxmlElement("m:sup")
    sup.append(math_run(superscript))
    node.extend([exponent, sub, sup])
    return node


replace_paragraph(
    "SoC Occupancy Aging and Energy–Reserve Bidding Under Price Stress:",
    "State-of-Charge Occupancy and Battery Aging in Energy–Reserve Bidding Under Price Stress: A Diagnostic Using German Market Data",
)
replace_paragraph(
    "Abstract—",
    "Abstract—Joint energy and reserve offers can require a battery energy storage system (BESS) to retain energy for upward activation. Throughput and depth-of-discharge (DoD) costs do not directly price this retained energy, whereas calendar aging depends in part on state of charge (SoC). We study when an SoC-occupancy term changes an optimized energy–reserve position in a virtual power plant (VPP). A daily mean–CVaR model represents a 2.5 MW/5 MWh BESS with throughput, daily-depth, and layered calendar–cycle (ReLCCA) aging costs. The input panel contains 262 complete days of German market and system data from December 2025 through August 2026; reserve-capacity and imbalance settlements are modeled using proxies. In the manuscript's reported runs, throughput and Xu formulations select a long energy-only position on 1 May 2026, when the day-ahead price reaches a reported −499 EUR/MWh; ReLCCA remains short. The reported wholesale-profit difference is EUR 1,312, largely associated with a EUR 1,246 difference in day-ahead energy revenue, while direct aging cost differs by EUR 4. A reconstruction using the archived panel and available code does not reproduce this ranking: P1−B2 is negative for all three aging laws in both relaxed-LP and charge/discharge-exclusive MILP runs. The original numerical ranking therefore remains unverified without the original model and parameter set.",
)
replace_paragraph(
    "The objective of this study is not to claim",
    "We ask a narrower question: under what price and residual-portfolio conditions does pricing SoC occupancy change an optimized mean–CVaR energy–reserve position? We compare three aging formulations in a common model and use paired day-level runs, a price intervention, and an event scan. The analysis is a model diagnostic, not a population-wide test or validation of a cell-aging law.",
)
replace_paragraph(
    "The contributions are fourfold.",
    "The contribution is the controlled comparison of three aging costs in a common energy–reserve model, with explicit SoC occupancy, reserve parking, and a decomposition that separates direct aging expenditure from the resulting market position. The negative-price intervention and event scan test whether price depth alone is sufficient to explain the reported reversal.",
)
remove_paragraph("The remainder of the paper is organized as follows.")
replace_paragraph(
    "The literature relevant to this study can be organized into four strands:",
    "Prior work relevant to this question covers VPP bidding under uncertainty, battery-aging costs, and joint energy–reserve scheduling. Stochastic and robust models address uncertain renewable output and prices [5]–[7], [29], while risk-averse VPP scheduling has also considered energy and reserve jointly [8].",
)
replace_paragraph(
    "The second strand concerns battery aging.",
    "Battery-aging studies distinguish calendar and cycle mechanisms and document the dependence of calendar aging on SoC [9]–[14]. Optimization models represent degradation through throughput, cycle-depth, or more detailed formulations [15]–[20].",
)
replace_paragraph(
    "The third strand concerns reserve participation.",
    "Energy–reserve co-optimization has been studied with probabilistic delivery constraints and in German secondary-control-reserve applications [21]–[24]. Wind–battery VPP studies have also combined reserve scheduling and degradation costs [24], [25].",
)
replace_paragraph(
    "The fourth strand is risk-aware bidding.",
    "CVaR is a tractable measure of lower-tail risk [26]–[28] and has been applied to VPP, PV-storage, and energy–frequency-regulation bidding [8], [30], [31]. Distributionally robust VPP models provide a related treatment of uncertainty [32].",
)
replace_paragraph(
    "The gap addressed here is narrower than any of these individual topics.",
    "The gap examined here is the incremental effect of pricing SoC occupancy while retaining cycle costs, an upward-reserve energy requirement, and a common mean–CVaR model. The analysis is diagnostic because the reserve-capacity and imbalance inputs are proxies rather than day-specific settlement records.",
)
replace_paragraph(
    "Table I lists the closest studies.",
    "Among the studies summarized in Table I, [25] combines calendar and cycle aging with day-ahead energy–reserve scheduling, but uses deterministic inputs. The present comparison isolates the additional effect of SoC-dependent aging in a mean–CVaR bid; the literature-scope claim is limited to the studies reviewed here.",
)
replace_paragraph(
    "Table II gives every fixed parameter.",
    "Table II lists the parameters specified for the reported study. The manuscript does not state the reserve-sustainment duration τ, initial SoC, or band-specific cycle coefficients γ used by the available reconstruction; those defaults are not treated as original study values.",
)
replace_paragraph(
    "The public market and physical series were retrieved",
    "The panel covers 1 December 2025 00:00 through 21 August 2026 07:00 Berlin time. It contains 6,319 hourly rows across 264 calendar dates: 262 complete days, the 23-hour daylight-saving day on 29 March, and the first 8 hours of 21 August. Day-ahead prices for DE-LU are sourced through the Energy-Charts API from Bundesnetzagentur | SMARD.de; German load, solar, and wind series are from Fraunhofer ISE Energy-Charts [33], [34]. The API's 15-minute observations are averaged to local-time hourly values. Load is scaled so its study-period 95th percentile maps to 5 MW; the study-window solar maximum maps to 4 MW, and the combined onshore/offshore wind maximum maps to 2 MW. Price forecasts use the mean of 48- and 168-hour lags; load, PV, and wind use 48-hour persistence. Daily forecast-error vectors are block-bootstrapped from complete days no later than D−2, with uniform scenario weights. Raw responses, the processed panel, retrieval timestamp, licenses, URLs, scaling factors, and SHA-256 hashes are archived with the data package. These are national system series, not battery telemetry.",
)
replace_paragraph(
    "The reserve-capacity prices are published German aFRR four-hour block means",
    "The reserve-capacity inputs are six positive- and negative-direction German aFRR four-hour block means reported by Modo Energy and Pexapark [35], [36]: positive values are 4.5, 12.0, 47.1, 18.4, 35.6, and 8.0 EUR/MW/h; negative values are 6.0, 15.0, 36.9, 57.4, 20.0, and 2.4 EUR/MW/h. They are held fixed across operating days and serve as capacity-price proxies, not daily auction results.",
)
replace_paragraph(
    "Here is energy sold day-ahead",
    "A positive p_t^DA denotes a day-ahead sale, and a positive z_t,ω denotes energy purchased in the imbalance market. The balance therefore subtracts the day-ahead sale and adds the imbalance purchase. At a negative price, a positive purchase is a long position. The implementation uses separate nonnegative short and long imbalance variables; z represents their signed net position. Renewable and generator limits are linear, and generator ramping is represented by intertemporal inequalities.",
)
replace_paragraph(
    "No binary charging and discharging variable is put in.",
    "The baseline LP omits binary charge/discharge exclusivity, so simultaneous charging and discharging are feasible. The economic terms do not guarantee that this overlap is zero; we therefore report an overlap diagnostic and a binary-exclusive MILP sensitivity case. LP results apply only to the relaxed formulation.",
)
replace_paragraph(
    "The default eight-band κ map uses three plateaus",
    "The default eight-band κ map uses three plateaus derived from the supplied Keil-based calibration: 0.247, 0.493, and 0.822 EUR/MWh/h for low-, mid-, and high-SoC bands, respectively [12]. These are economic inputs based on published calendar-aging relationships, not a fitted cell-aging model.",
)
replace_paragraph(
    "All terms are affine under the stated assumptions.",
    "Without binary charge/discharge exclusivity, the objective and constraints are affine and the baseline problem is an LP. The exclusive sensitivity case adds binary variables and is a MILP. The daily DoD epigraph and CVaR use auxiliary variables and linear constraints.",
)
replace_paragraph(
    "Two bid types are compared throughout.",
    "B2 is the energy-only bid; P1 jointly offers day-ahead energy and aFRR capacity. P1−B2 is the difference in simulated wholesale profit after settlement. For each day, bids are optimized over the same scenario set, then first-stage positions are fixed while recourse is re-optimized on the observed day. Plant, prices, risk settings, and solver are held constant within each aging-law comparison.",
)
replace_paragraph(
    "The complete panel is scanned for days with minimum day-ahead price",
    "We scan days with a minimum day-ahead price below −20 EUR/MWh. The 20 qualifying days form an in-sample event set, not a random sample; the scan is descriptive and does not estimate a population probability.",
)
replace_paragraph(
    "Table III compares the three aging models on four days.",
    "For the three non-event dates, P1−B2 is positive under all three aging laws. On 1 May, the manuscript-reported sign is negative for throughput and Xu but positive for ReLCCA. These original table values have not been reproduced by the available reconstruction; see the reproducibility note.",
)
remove_paragraph("The isolation results do not show a systematic dominance of ReLCCA.")
replace_paragraph(
    "Fig. 1 pushes the midday price lower and lower",
    "On the 19 August portfolio, P1−B2 remains positive across the injected troughs: throughput declines from +1,145 to +790 EUR and ReLCCA from +1,353 to +1,056 EUR. Deepening the trough alone does not reproduce the 1 May reversal in this one frozen portfolio; this counterfactual is not a forecast or a general causal test.",
)
remove_paragraph("The throughput and ReLCCA differentials remain positive throughout the intervention range.")
replace_paragraph(
    "Table IV splits each result into its parts.",
    "In the manuscript-reported decomposition, B2–Throughput and B2–ReLCCA differ by EUR 1,246 in day-ahead energy revenue (+978 versus −268 EUR) but by only EUR 4 in direct aging cost (−58 versus −54 EUR). Their reported wholesale profits differ by EUR 1,312 (−194 versus −1,506 EUR). This decomposition attributes the difference to the optimized market position, not to an aging-cost saving of EUR 1,246; it does not identify a causal shadow price.",
)
remove_paragraph("The central comparison is between B2–Throughput and B2–ReLCCA.")
replace_paragraph(
    "Table V checks whether 1 May is special.",
    "The manuscript's original scan reports one throughput reversal among 20 days below −20 EUR/MWh: 1 May. ReLCCA is reported positive on all 20 days. These are in-sample counts over days with different portfolio states, not probability estimates. The available reconstruction produces two reversals for each aging law, so the original scan result remains unverified.",
)
remove_paragraph("The full scan contains 20 days below −20 EUR/MWh;")
replace_paragraph(
    "Both the calendar-only and the cycle-only variants keep P1−B2 positive",
    "In the manuscript-reported component checks, P1−B2 is +587 EUR for calendar-only, +512 EUR for cycle-only, and +515 EUR for the combined model. This suggests that SoC dependence, rather than the calendar term alone, drives the reported distinction; the result remains subject to the reconstruction caveat.",
)
replace_paragraph(
    "Table VI changes one setting at a time on 1 May.",
    "In the reported sensitivity runs, the ReLCCA P1−B2 gap ranges from +234 to +800 EUR across the tested reserve caps and remains positive for 4, 6, 8, and 12 SoC bands (+565, +533, +576, and +561 EUR). Throughput remains negative except for the 2 MWh case (+19 EUR). These values describe the manuscript's runs and have not been independently reproduced.",
)
remove_paragraph("The sign of the ReLCCA differential remains positive across the tested band resolutions")
replace_paragraph(
    "Throughput and daily-depth formulations attach aging cost primarily",
    "Throughput and daily-depth costs depend on energy processed or the SoC excursion. ReLCCA also prices energy retained in each SoC band. Under an upward-reserve commitment, that occupancy cost can alter the marginal value of stored energy and the selected day-ahead position. In the reported 1 May decomposition, the market-position difference is much larger than the direct aging-cost difference; the available code does not reproduce that result.",
)
remove_paragraph("The 1 May decomposition shows that the market-position effect")
remove_paragraph("B. Post-optimization CMRI diagnostic")
remove_paragraph("The Capacity Margin and Risk Index (CMRI) is retained only")
remove_paragraph("The first term measures normalized energy headroom")
replace_paragraph(
    "C. Scope of the empirical evidence",
    "B. Scope of the empirical evidence",
)
replace_paragraph(
    "The evidence does not establish universal superiority of ReLCCA",
    "The evidence does not establish universal superiority of ReLCCA, a universal negative-price threshold, a population-level reversal probability, or a validated cell-level degradation law. Reserve and imbalance prices are proxies, so reported euro values are simulated wholesale profits, not realized German settlements.",
)
replace_paragraph(
    "First, the diagnosed condition occurs once within the 262 complete days",
    "The manuscript reports one reversal in 262 complete days, and the panel does not cover September–November. That frequency cannot be generalized to a full year. ReLCCA is an optimization-oriented encoding of published aging relationships, not a cell-level electrochemical model; its coefficients require chemistry-, temperature-, and history-specific calibration. The calendar-cost annualization is linear in time, while the square-root-time case is only a sensitivity test. The EUR 150/kWh replacement value is a cell-cost assumption, not installed EPC cost.",
)
replace_paragraph(
    "Sixth, imbalance prices are generated by a documented two-price proxy",
    "aFRR capacity prices are repeated four-hour block means, and activation trajectories are not simulated. Imbalance prices use a two-price proxy rather than observed reBAP settlements. The Xu benchmark represents daily depth and is not rainflow counting. The VPP is a price taker and omits network constraints and strategic price-making. The event scan is limited to the available panel.",
)
replace_paragraph(
    "The manuscript reports Python/Pyomo with HiGHS and random seed 20260821.",
    "The manuscript reports Python/Pyomo with HiGHS and seed 20260821. The original source and exact run configuration were not supplied. The accompanying reconstruction uses SciPy's MILP interface to HiGHS [37], [38]; it includes assumptions for initial SoC, reserve-sustainment duration, and separate charge/discharge γ coefficients. It uses the archived public panel but does not reproduce the original 1 May ranking or negative-price scan. The reconstruction outputs are archived separately and must not replace Tables III–VI. Exact replication requires the original source, original input snapshot, and complete parameter configuration.",
)
replace_paragraph(
    "This paper developed a controlled diagnostic",
    "This study examines whether SoC-occupancy aging changes a BESS energy–reserve decision under stressed prices. The manuscript's original runs report a 1 May 2026 reversal between the throughput/Xu and ReLCCA formulations, with most of the reported profit difference arising from the day-ahead position rather than direct aging cost. The available reconstruction does not reproduce that ranking, so the original numerical conclusion remains provisional until the original model and parameters are available. The analysis supports a narrower motivation for explicit occupancy costs; it does not establish a universal degradation law or realized German settlement outcome.",
)
remove_paragraph("The controlled trough intervention and historical negative-price scan indicate")
replace_paragraph(
    "The authors acknowledge the public German market and physical data",
    "The authors acknowledge the public German market and physical data made available through Bundesnetzagentur | SMARD and Fraunhofer ISE Energy-Charts. The reported optimization used Pyomo and HiGHS; the accompanying reconstruction uses SciPy's MILP interface to HiGHS.",
)

replace_reference(18, [
    ("[18] Y. Shi, B. Xu, Y. Tan, D. Kirschen, and B. Zhang, “Optimal battery control under cycle aging mechanisms in pay for performance settings,” ", False),
    ("IEEE Trans. Autom. Control", True),
    (", vol. 64, no. 6, pp. 2324–2339, Jun. 2019, doi: 10.1109/TAC.2018.2867507.", False),
])
replace_reference(19, [
    ("[19] G. K. Petrin, S. Arens, P. Schoenfeldt, P. Klement, and S. Schlüters, “Modeling battery aging in linear energy system optimizations by applying convex hulls: accuracy benefits and computational costs,” ", False),
    ("Appl. Energy", True),
    (", vol. 399, Art. no. 126492, Dec. 2025, doi: 10.1016/j.apenergy.2025.126492.", False),
])
replace_reference(30, [
    ("[30] X. Wang, K. Lei, H. Wu, B. Xu, and J. Ding, “A conditional value-at-risk-based bidding strategy for PVSS participation in energy and frequency regulation ancillary markets,” ", False),
    ("Sustainability", True),
    (", vol. 18, no. 2, Art. no. 1122, 2026, doi: 10.3390/su18021122.", False),
])
replace_reference(33, [("[33] Bundesnetzagentur, “SMARD – Strommarktdaten,” SMARD.de. [Online]. Available: https://www.smard.de. Accessed: Oct. 30, 2026.", False)])
replace_reference(34, [("[34] B. Burger, “Energy-Charts,” Fraunhofer Institute for Solar Energy Systems ISE, Freiburg, Germany. [Online]. Available: https://www.energy-charts.info. Accessed: Oct. 30, 2026.", False)])
replace_reference(35, [("[35] Modo Energy, “German aFRR market data explained: How Ko can analyse it.” [Online]. Available: https://modoenergy.com/research/en/germany-afrr-data-explained-ko-analysis. Accessed: Oct. 30, 2026.", False)])
replace_reference(36, [("[36] C. Meili, “High Downward aFRR Prices Can Drive Additional Income for Solar Assets in Germany – Pexapark Analysis,” Pexapark, Jan. 6, 2026. [Online]. Available: https://pexapark.com/blog/high-downward-afrr-prices-can-drive-additional-income-for-solar-assets-in-germany-pexapark-analysis/. Accessed: Oct. 30, 2026.", False)])
replace_reference(37, [
    ("[37] Q. Huangfu and J. A. J. Hall, “Parallelizing the dual revised simplex method,” ", False),
    ("Math. Program. Comput.", True),
    (", vol. 10, no. 1, pp. 119–142, 2018, doi: 10.1007/s12532-017-0130-5.", False),
])
replace_reference(38, [
    ("[38] P. Virtanen ", False),
    ("et al.", True),
    (", “SciPy 1.0: Fundamental algorithms for scientific computing in Python,” ", False),
    ("Nat. Methods", True),
    (", vol. 17, pp. 261–272, 2020, doi: 10.1038/s41592-019-0686-2.", False),
])

math_nodes = document._element.xpath(".//m:oMath")
if len(math_nodes) < 5:
    raise RuntimeError("Expected the manuscript's balance and battery-bound equations")

def tokens(node):
    return list(node.iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}t"))

balance = math_nodes[0]
balance_tokens = tokens(balance)
if "".join(token.text or "" for token in balance_tokens[:4]) != "PtDA-":
    raise RuntimeError("Unexpected equation (1) structure; refusing to alter it")
balance_tokens[3].text = "+"
balance.insert(0, math_run("-"))

bounds = next(
    node for node in math_nodes
    if "".join(token.text or "" for token in tokens(node)).replace(" ", "").startswith("Emin≤Et,ω≤Emax")
)
for child in list(bounds):
    bounds.remove(child)
for item in (
    math_sub("E", "min"), math_run(" ≤ "), math_sub("E", "t,ω"), math_run(" ≤ "),
    math_sub("E", "max"), math_run(", 0 ≤ "), math_subsup("P", "t,ω", "ch"),
    math_run(" ≤ "), math_sub("P", "B"), math_run(", 0 ≤ "),
    math_subsup("P", "t,ω", "dis"), math_run(" ≤ "), math_sub("P", "B"),
):
    bounds.append(item)

cmri_tables = [
    table for table in document.tables
    if "(18)" in " ".join(cell.text for row in table.rows for cell in row.cells)
    and "(19)" in " ".join(cell.text for row in table.rows for cell in row.cells)
]
if len(cmri_tables) != 1:
    raise RuntimeError(f"Expected one CMRI equation table; found {len(cmri_tables)}")
cmri_table = cmri_tables[0]._element
cmri_table.getparent().remove(cmri_table)

document.save(target)

check = Document(target)
text = "\n".join(paragraph.text for paragraph in check.paragraphs)
if any(token in text for token in ("[verify", "[could not verify", "[date]", "Post-optimization CMRI")):
    raise RuntimeError("Unresolved editorial placeholder or unsupported CMRI text remains")
reference_numbers = {
    number
    for paragraph in check.paragraphs
    for number in range(1, 39)
    if paragraph.text.startswith(f"[{number}]")
}
if reference_numbers != set(range(1, 39)):
    raise RuntimeError(f"Bibliography numbering is incomplete: {sorted(reference_numbers)}")
check_math = check._element.xpath(".//m:oMath")
check_balance = "".join(token.text or "" for token in tokens(check_math[0]))
if not check_balance.startswith("-PtDA+zt,ω"):
    raise RuntimeError(f"Equation (1) sign check failed: {check_balance}")
check_bounds = next(node for node in check_math if "".join(token.text or "" for token in tokens(node)).replace(" ", "").startswith("Emin≤Et,ω≤Emax"))
bounds_text = "".join(token.text or "" for token in tokens(check_bounds)).replace(" ", "")
if "0≤Pt,ωch≤PB,0≤Pt,ωdis≤PB" not in bounds_text:
    raise RuntimeError(f"Battery power bounds are incomplete: {bounds_text}")
if len(check.tables) != 19:
    raise RuntimeError(f"Unexpected table count after removing CMRI equations: {len(check.tables)}")
print(f"Reviewed manuscript saved and checked: {target.name}")
