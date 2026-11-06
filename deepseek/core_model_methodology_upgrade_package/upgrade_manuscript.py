from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
import pandas as pd, numpy as np, matplotlib.pyplot as plt, json, shutil, zipfile

ROOT=Path('/mnt/data')
RES=ROOT/'core_model_audit_results'
source=ROOT/'4-1_literature_expanded.docx'
out=ROOT/'4-1_methodology_upgraded_full_history.docx'

# Build publication figures from computed outputs.
d=pd.read_csv(RES/'daily_paired_dispatch_results.csv')
d=d[d.solve_ok==True].copy(); d['date']=pd.to_datetime(d.date); d['year']=d.date.dt.year
sweep=pd.read_csv(RES/'relcca_kappa_stress_sweep.csv')
base=d[['date','Throughput_profit_eur']].copy(); base['date']=base.date.dt.strftime('%Y-%m-%d')
sweep=sweep.merge(base,on='date'); sweep['delta_vs_throughput']=sweep.profit_eur-sweep.Throughput_profit_eur
ks=sweep.groupby('kappa_scale').agg(mean_delta=('delta_vs_throughput','mean'),lo=('delta_vs_throughput',lambda x:x.quantile(.25)),hi=('delta_vs_throughput',lambda x:x.quantile(.75))).reset_index()
plt.figure(figsize=(6.5,4.0)); plt.plot(ks.kappa_scale,ks.mean_delta,marker='o'); plt.fill_between(ks.kappa_scale,ks.lo,ks.hi,alpha=.18); plt.xscale('log'); plt.axhline(0,linewidth=1); plt.xlabel('ReLCCA occupancy-cost multiplier'); plt.ylabel('ReLCCA − throughput profit (EUR/day)'); plt.title('Deep-negative-price days (min DA ≤ −50 EUR/MWh)'); plt.tight_layout(); plt.savefig(RES/'fig_kappa_sensitivity.png',dpi=300); plt.close()
plt.figure(figsize=(6.5,4.0)); vals=[d['ReLCCA_minus_Throughput_EUR'].to_numpy(),d['ReLCCA_minus_Xu_EUR'].to_numpy(),d['Xu_minus_Throughput_EUR'].to_numpy()]; plt.boxplot(vals,labels=['ReLCCA − throughput','ReLCCA − Xu','Xu − throughput'],showfliers=False); plt.axhline(0,linewidth=1); plt.ylabel('Paired daily profit difference (EUR/day)'); plt.title('Ex-post battery-only audit, 2,069 local days'); plt.xticks(rotation=10); plt.tight_layout(); plt.savefig(RES/'fig_paired_differences.png',dpi=300); plt.close()

D=Document(source)
# Helpers to insert text/tables at a target paragraph without flattening the rest of the manuscript.
def insert_p_before(target, text, style=None, bold_prefix=None):
    p=target.insert_paragraph_before(text, style=style)
    if bold_prefix and text.startswith(bold_prefix):
        p.clear(); r=p.add_run(bold_prefix); r.bold=True; p.add_run(text[len(bold_prefix):])
    return p

def insert_table_before(target, headers, rows, caption=None):
    if caption:
        insert_p_before(target, caption, style='Normal')
    table=D.add_table(rows=1, cols=len(headers))
    table.alignment=WD_TABLE_ALIGNMENT.CENTER
    try:
        table.style='Table Grid'
    except KeyError:
        pass
    for j,h in enumerate(headers):
        cell=table.rows[0].cells[j]; cell.text=str(h)
        for r in cell.paragraphs[0].runs: r.bold=True
    for row in rows:
        cells=table.add_row().cells
        for j,val in enumerate(row):
            cells[j].text=str(val)
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                for r in p.runs: r.font.size=Pt(8)
    target._p.addprevious(table._tbl)
    return table

# Abstract: append carefully, preserving original abstract text.
abstract=D.paragraphs[2]
extra=(' A separate full-history, ex-post battery-only audit over 2,069 German local days (2021–August 2026) is added as a falsification test, not as a bid backtest. In that oracle-dispatch experiment, ReLCCA earns EUR 20.51/day less than the throughput model on average (30-day moving-block 95% interval: −20.90 to −20.16), showing that occupancy pricing is not intrinsically profit-enhancing and that the paper’s main energy–reserve result must remain conditional on portfolio and reserve interactions.')
if '2,069 German local days' not in abstract.text: abstract.add_run(extra)

# Methods subsection before Results heading.
results_heading=next(p for p in D.paragraphs if p.text.strip()=='VI. RESULTS AND DISCUSSION')
insert_p_before(results_heading,'F. Full-history battery-only falsification audit','Heading 2')
insert_p_before(results_heading,
 'To test whether the proposed occupancy term creates a general arbitrage advantage independently of the VPP and reserve mechanism, a second, deliberately narrower experiment is run on the complete SMARD hourly price panel from 1 January 2021 through 31 August 2026. All 2,069 German local days are retained, including 23- and 25-hour daylight-saving days. For each day, the realized hourly day-ahead price path is supplied to a battery-only dispatch problem. This is a perfect-foresight, ex-post mechanism test; it is not an implementable day-ahead bidding policy, an out-of-sample forecast, or a realized VPP profit estimate.')
insert_p_before(results_heading,
 'The 5 MWh battery is constrained to 2.5 MW charge/discharge, 10–90% SoC, 95% charge and discharge efficiencies, and a cyclic daily energy boundary. The objective maximizes realized-price arbitrage revenue less a EUR 1.5/MWh charge-and-discharge throughput cost and the selected aging cost. The throughput model applies only the throughput term. The Xu benchmark adds a convex daily depth-of-discharge cost with segment widths (0.20, 0.30, 0.30, 0.20) and slopes (10, 40, 80, 120) EUR per unit normalized depth. ReLCCA adds hourly SoC occupancy cost using the paper’s eight-band coefficients (0.247, 0.247, 0.493, 0.493, 0.493, 0.822, 0.822, 0.822 EUR/MWh/h), with the same throughput term. A binary charge-mode variable enforces charge/discharge exclusivity; therefore, the experiment does not rely on the assumption that an LP objective alone prevents simultaneous operation. Each aging formulation is solved on the same price path for each day using a mixed-integer linear program.')
insert_p_before(results_heading,
 'The purpose is falsification and boundary identification, not to replace the main two-stage mean–CVaR energy–reserve model. Because this diagnostic omits generator dispatch, portfolio residuals, reserve-capacity revenue, activation, and imbalance settlement, its absolute profits are not comparable with the main VPP results. It isolates whether the battery aging term by itself improves ex-post arbitrage value under the same realized price path.')

# Results subsection and tables before limitations.
limitations_heading=next(p for p in D.paragraphs if p.text.strip()=='VII. LIMITATIONS AND REPRODUCIBILITY')
insert_p_before(limitations_heading,'I. Full-history battery-only audit','Heading 2')
insert_p_before(limitations_heading,
 'The input file contains 49,655 hourly observations and covers 2,069 local market days. The full panel includes 1,963 hours with DA prices below zero and 118 hours at or below −50 EUR/MWh. At the day level, 351 days have a minimum price below zero, 37 days have a minimum at or below −50 EUR/MWh, and four days reach −200 EUR/MWh or lower. Negative-price days are not treated as data errors. The 2026 count is partial through August and must not be compared with full calendar years without that qualification.')
insert_p_before(limitations_heading,
 'Across the 2,069 paired daily optimizations, mean ReLCCA profit is EUR 20.51/day below the throughput benchmark (median −20.68 EUR/day). A moving-block bootstrap with 30-day blocks and 10,000 replicates gives a 95% interval of [−20.90, −20.16] EUR/day for the mean paired difference. ReLCCA exceeds the Xu model by EUR 17.34/day on average, while Xu is EUR 37.85/day below throughput. These are finite-panel ex-post model comparisons, not estimates of real market profit or a population-level causal effect.')
insert_p_before(limitations_heading,
 'The sign is not reversed on the 37 deep-negative-price days: the mean ReLCCA-minus-throughput difference is −17.10 EUR/day. A multiplier sweep of the ReLCCA occupancy coefficients from 0.1× to 10× yields mean paired differences of −1.76, −4.37, −8.66, −17.10, −33.38, −78.77, and −148.55 EUR/day, respectively; none of the 37 daily differences is positive at any tested multiplier. This result is an important boundary condition: occupancy cost is a cost representation, not a standalone source of arbitrage revenue. Any favorable ReLCCA result in the main model must arise from changed first-stage positions and their interaction with portfolio residuals, reserve constraints, and settlement assumptions, rather than from the occupancy term directly increasing battery-only arbitrage profit.')
insert_p_before(limitations_heading,
 'The full-history audit also resolves one implementation concern: the MILP enforces mutually exclusive charge and discharge, and no simultaneous charging/discharging is observed in any of the 2,069 daily solutions for any of the three aging laws. This is a model-feasibility check, not proof that a continuous relaxation would always avoid simultaneous operation.')

# Add tables in order before the same limitations heading.
insert_table_before(limitations_heading,
 ['Year','Days in panel','Days with min DA < 0','Days with min DA ≤ −50'],
 [['2021','365','24','4'],['2022','365','12','0'],['2023','365','46','4'],['2024','366','88','9'],['2025','365','101','11'],['2026*','243','80','9']],
 'TABLE VII. FULL-HISTORY NEGATIVE-PRICE REGIME COUNTS (*2026 ends on 31 August).')
insert_table_before(limitations_heading,
 ['Paired comparison','Mean (EUR/day)','Median (EUR/day)','30-day moving-block 95% interval'],
 [['ReLCCA − throughput','−20.51','−20.68','[−20.90, −20.16]'],['ReLCCA − Xu','+17.34','+17.24','[+16.94, +17.73]'],['Xu − throughput','−37.85','−38.00','[−37.93, −37.79]']],
 'TABLE VIII. PAIRED EX-POST BATTERY-ONLY PROFIT DIFFERENCES ACROSS 2,069 LOCAL DAYS.')
insert_table_before(limitations_heading,
 ['κ multiplier','Mean ReLCCA − throughput (EUR/day)','Positive days / 37'],
 [['0.10×','−1.76','0 / 37'],['0.25×','−4.37','0 / 37'],['0.50×','−8.66','0 / 37'],['1.00×','−17.10','0 / 37'],['2.00×','−33.38','0 / 37'],['5.00×','−78.77','0 / 37'],['10.00×','−148.55','0 / 37']],
 'TABLE IX. RE LCCA OCCUPANCY-COEFFICIENT SENSITIVITY ON DAYS WITH MINIMUM DA PRICE ≤ −50 EUR/MWh.')

# Add figures as inline visuals before limitations.
for path, caption in [(RES/'fig_paired_differences.png','Fig. 5. Paired daily ex-post profit differences across the full historical panel. The battery-only oracle experiment is separate from the main VPP energy–reserve model.'),(RES/'fig_kappa_sensitivity.png','Fig. 6. ReLCCA occupancy-coefficient sensitivity on 37 deep-negative-price days; the shaded band shows the interquartile range across daily paired differences.')]:
    imgp=limitations_heading.insert_paragraph_before('')
    imgp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    imgp.add_run().add_picture(str(path),width=Inches(5.8))
    p=limitations_heading.insert_paragraph_before(caption)
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER

# Strengthen limitations: explicitly distinguish new ex-post audit from market-bidding evidence.
for p in D.paragraphs:
    if p.text.startswith('First, the diagnosed condition appears once within the 262 complete days'):
        p.add_run(' The supplementary 2021–August 2026 battery-only audit uses realized prices with perfect foresight and deliberately excludes reserve and imbalance revenue; it is therefore a falsification test of the aging-cost component, not out-of-sample validation of the two-stage bidding policy.')
        break
# Conclusion: add boundary statement.
for p in D.paragraphs:
    if p.text.strip()=='VIII. CONCLUSION':
        p.text='IX. CONCLUSION'
    if p.text.startswith('This paper developed a controlled diagnostic framework'):
        p.add_run(' The supplementary full-history oracle audit provides a necessary boundary check: in battery-only dispatch, ReLCCA reduces rather than increases ex-post arbitrage profit relative to throughput across the tested sample, including all deep-negative-price days. This does not contradict the main coupled-model mechanism, but it rules out interpreting the occupancy penalty as an intrinsic profit enhancer. The defensible contribution is therefore conditional: explicit occupancy costs can alter the optimizer’s chosen market position in a coupled VPP/reserve setting, and the value of that change must be evaluated against realistic reserve, imbalance, and out-of-sample information structures.')
    if p.text.strip()=='VII. LIMITATIONS AND REPRODUCIBILITY': p.text='VIII. LIMITATIONS AND REPRODUCIBILITY'
# References section should remain after IX conclusion.
D.save(out)
print('saved',out)
