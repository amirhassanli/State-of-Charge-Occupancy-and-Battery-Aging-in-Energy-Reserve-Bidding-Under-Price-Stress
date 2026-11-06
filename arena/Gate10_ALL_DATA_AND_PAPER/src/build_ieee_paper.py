#!/usr/bin/env python3
"""Build IEEE-style HTML + DOCX paper with real Gate-10 figures and tables."""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy
import shutil

ROOT = Path("/home/user")
FIG = ROOT / "FINAL_IEEE_PAPER" / "figures"
OUT = ROOT / "FINAL_IEEE_PAPER"
HTML = OUT / "Hassanli_Abbasi_VPP_Bidding_IEEE.html"
DOCX = OUT / "Hassanli_Abbasi_VPP_Bidding_IEEE.docx"

# Paper figure order (IEEE captions live BELOW the graphic; no internal titles)
FIGS = [
    ("Fig01_Forecast_vs_Actual.png", "1",
     "Day-ahead forecast versus realized SMARD series on the operating day 19 August 2026 (DE-LU): electricity price, VPP load, on-site PV, and on-site wind."),
    ("Fig06_Scenario_Fan.png", "2",
     "Block-bootstrap scenario fans (K = 50) for price, load, PV, and wind, with the P10–P90 band, the point forecast, and the realized trajectory."),
    ("Fig08_Error_KDE.png", "3",
     "Kernel density estimates of day-ahead forecast errors for price, load, PV, and wind over 58 historical error days."),
    ("Fig07_Correlation_Matrix.png", "4",
     "Sample correlation of selected-hour forecast errors (price π, load L, PV, wind W at hours 06, 12, and 18)."),
    ("Fig22_DA_Energy_Bids.png", "5",
     "First-stage day-ahead energy position (sell positive) of B0, B2, and P1 against the realized DE-LU day-ahead price."),
    ("Fig03_Profit_Comparison.png", "6",
     "Daily profit on 19 August 2026: in-sample expectation (error bar = scenario standard deviation) versus realized out-of-sample settlement."),
    ("Fig04_CVaR_Comparison.png", "7",
     "In-sample expected profit versus empirical CVaR at α = 0.95 for B0, B2, and P1."),
    ("Fig11_ECDF_Profit.png", "8",
     "Empirical CDF of in-sample scenario profit. P1 first-order stochastically dominates B0 and B2 over the body of the distribution."),
    ("Fig09_Boxplot_Profit.png", "9",
     "Box plot of in-sample scenario profits (K = 50)."),
    ("Fig10_Violin_Profit.png", "10",
     "Violin plot of in-sample scenario profits."),
    ("Fig02_Hourly_Profit.png", "11",
     "Hourly profit trajectories (in-sample mean and P10–P90 band)."),
    ("Fig13_Battery_SoC.png", "12",
     "Battery state of charge. Shaded bands are the in-sample P10–P90 range; dashed lines are the realized recourse SoC. P1 holds a mid-range SoC overnight to keep upward reserve deliverable."),
    ("Fig14_DG_Dispatch.png", "13",
     "Distributed-generation dispatch (in-sample mean and realized recourse)."),
    ("Fig15_Reserve_Schedule.png", "14",
     "Day-ahead reserve allocation of P1 (upward positive, downward negative). B0 and B2 do not offer reserve."),
    ("Fig16_Imbalance.png", "15",
     "Net energy imbalance (long positive, short negative): in-sample mean (solid) and realized (dashed)."),
    ("Fig17_Heatmap_Decisions.png", "16",
     "Row-normalised heatmap of P1 24-hour first-stage bids and mean second-stage recourse."),
    ("Fig18_Sensitivity_lambda.png", "17",
     "P1 sensitivity to the mean–CVaR weight λ (α = 0.95, K = 50)."),
    ("Fig19_Sensitivity_alpha.png", "18",
     "P1 sensitivity to the CVaR confidence α (λ = 0.05, K = 50)."),
    ("Fig20_Rolling_OOS.png", "19",
     "Rolling-origin out-of-sample realized daily profit, 6–19 August 2026. P1 strictly dominates B0 and B2 on every day."),
    ("Fig21_Pareto_Profit_Risk.png", "20",
     "Profit–risk view: expected profit (circles) and CVaR (diamonds) versus scenario standard deviation."),
    ("Fig05_Runtime_Scaling.png", "21",
     "HiGHS wall-clock runtime versus the retained scenario count K."),
    ("Fig12_Radar.png", "22",
     "Min–max-normalised multi-criteria profile of B0, B2, and P1."),
]


def fig_html(fname, num, cap):
    return f'''<figure id="fig{num}">
<img src="figures/{fname}" alt="Fig. {num}"/>
<figcaption><b>Fig. {num}.</b> {cap}</figcaption>
</figure>'''


F = {num: fig_html(fn, num, cap) for fn, num, cap in FIGS}

css = r"""
@page { size: letter; margin: 18mm 16mm; }
html,body { margin:0; padding:0; background:#fff; }
body {
  font-family: "Times New Roman", Times, "DejaVu Serif", serif;
  font-size: 10pt; line-height: 1.22; color: #111;
  max-width: 210mm; margin: 0 auto; padding: 14mm 16mm 20mm;
}
h1.title { font-size: 16.5pt; font-weight: 700; text-align: center; margin: 0 0 8pt; line-height: 1.25; }
.authors { text-align:center; font-size: 11pt; margin: 6pt 0 2pt; }
.affil { text-align:center; font-size: 9pt; font-style: italic; color:#333; margin-bottom: 10pt; }
.abstract, .idx {
  font-size: 9pt; text-align: justify; margin: 8pt 0;
}
.abstract p { margin: 0; }
.idx { margin-bottom: 12pt; }
h2 { font-size: 11pt; font-weight: 700; text-align: center; margin: 13pt 0 7pt;
     text-transform: uppercase; letter-spacing: 0.3pt; }
h3 { font-size: 10.5pt; font-weight: 700; font-style: italic; margin: 9pt 0 4pt; text-align:left; }
p { text-align: justify; margin: 0 0 6pt; hyphens: auto; }
.cols { column-count: 2; column-gap: 7mm; column-rule: 0; }
figure { margin: 8pt 0 10pt; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; height: auto; }
figcaption { font-size: 8.5pt; text-align: justify; margin-top: 3pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8pt; break-inside: avoid; }
th, td { border: 1px solid #444; padding: 2.5pt 4pt; text-align: center; }
th { background: #f3f3f3; font-weight: 700; }
caption { caption-side: top; font-size: 9pt; font-weight: 700; text-align: center; margin: 6pt 0 3pt; }
.eq { text-align:center; margin: 6pt 0; font-style: italic; }
.eqno { float:right; font-style: normal; }
ol.refs { font-size: 8.5pt; padding-left: 18pt; text-align: justify; }
ol.refs li { margin-bottom: 4pt; }
.note { font-size: 8.5pt; font-style: italic; }
hr.sep { border:0; border-top: 1px solid #000; margin: 10pt 0; }
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Calibrated Dependence-Aware Day-Ahead Bidding of Virtual Power Plants</title>
<style>{css}</style>
</head>
<body>

<h1 class="title">Calibrated Dependence-Aware Day-Ahead Bidding of Virtual Power Plants Under Joint Renewable, Load, and Price Uncertainty</h1>
<p class="authors">Amir Hassanli and Ali Reza Abbasi</p>
<p class="affil">Manuscript prepared in IEEE Transactions style. Empirical results: Gate&nbsp;10 real-data settlement on SMARD DE-LU, operating day 19&nbsp;August&nbsp;2026.</p>

<div class="abstract">
<p><b>Abstract—</b>
Virtual power plants (VPPs) that aggregate photovoltaic and wind generation, battery storage, dispatchable distributed generation, and flexible demand are exposed to jointly occurring forecast errors in renewable output, load, and market prices. Stochastic bidding formulations that treat these errors as independent, or that rely on a Gaussian copula, systematically under-represent compound tail events and can therefore produce day-ahead positions that are statistically well-posed yet economically fragile. This paper develops a calibrated, dependence-aware bidding framework that combines pre-decision forecast calibration, a joint error model, tail-aware scenario reduction, and a risk-averse two-stage linear program with a Rockafellar–Uryasev CVaR objective. Three models are compared on identical German SMARD (DE-LU) information sets: a deterministic expected-value scheduler (B0), a two-stage mean–CVaR energy-only program (B2), and the proposed joint energy–reserve mean–CVaR program (P1). Using a 24-hour horizon, K&nbsp;=&nbsp;50 equiprobable scenarios, λ&nbsp;=&nbsp;0.05 and α&nbsp;=&nbsp;0.95, all three programs are solved to proven optimality by the open-source HiGHS solver. On the operating day 19&nbsp;August&nbsp;2026, P1 attains an in-sample expected profit of 11&nbsp;992&nbsp;EUR and a realized out-of-sample profit of 11&nbsp;487&nbsp;EUR, exceeding B0 by 494&nbsp;EUR/day in sample (paired t-test p&nbsp;=&nbsp;2.88×10<sup>−41</sup>, Wilcoxon p&nbsp;=&nbsp;7.50×10<sup>−10</sup>, Cohen’s d&nbsp;=&nbsp;6.29) and by 563&nbsp;EUR/day on a 14-day rolling-origin out-of-sample window in which P1 is strictly better on every day. The economic gain is attributable to deliverable reserve that P1 sells from battery and DG headroom while respecting state-of-charge limits in every scenario; the energy-only CVaR model B2 improves the left tail only modestly relative to B0, and the difference is not significant out of sample. The study therefore supplies the previously missing decision-level evidence that a calibrated, reserve-feasible, CVaR-aware bid improves realized VPP settlement on real SMARD data, without look-ahead leakage.
</p>
</div>
<p class="idx"><b>Index Terms—</b> Virtual power plant, stochastic programming, day-ahead bidding, CVaR, scenario generation, demand response, battery energy storage, reserve deliverability, out-of-sample validation, SMARD.</p>

<hr class="sep"/>
<div class="cols">

<h2>I. Introduction</h2>
<p>The increasing penetration of renewable distributed energy resources has transformed the operational role of virtual power plants (VPPs). By aggregating photovoltaic (PV) generation, wind generation, battery energy storage systems (BESSs), flexible demand, and other distributed resources, a VPP can participate in electricity markets as a single aggregated, market-facing entity. This aggregation creates economic opportunities but simultaneously exposes the VPP to forecast uncertainty, price volatility, imbalance costs, intertemporal resource constraints, and uncertainty in the availability of flexible capacity.</p>
<p>The resulting bidding problem differs fundamentally from deterministic scheduling. A day-ahead energy position that is profitable under a point forecast may become economically inferior once renewable forecast errors, load deviations, and market-price shocks occur jointly. Likewise, allocating excessive flexibility to the energy market can reduce a VPP’s ability to satisfy later reserve or balancing obligations. Recent literature has therefore investigated stochastic programming, robust optimization, CVaR-based bidding, chance constraints, and distributionally robust optimization for VPP participation in energy and ancillary-service markets [1]–[8].</p>
<p>A critical methodological issue remains. The quality of a stochastic bidding model depends not only on the optimization formulation but also on how the underlying uncertainty distribution is constructed. Forecast errors in renewable generation, load, and electricity price are neither necessarily independent nor adequately characterized by light-tailed Gaussian dependence. A VPP may simultaneously experience high renewable underproduction, elevated load, and unfavorable market prices; such compound events are particularly relevant for tail-risk-aware bidding. The uncertainty architecture developed in this paper therefore models the joint forecast-error vector rather than perturbing each variable independently.</p>
<p>A second limitation concerns validation. Conventional scenario-reduction procedures often evaluate statistical distance without asking whether the retained scenarios preserve the resulting bidding decision. The present framework treats scenario reduction as a decision-quality problem: a joint scenario pool is generated from historical SMARD forecast errors, reduced to several cardinalities, and evaluated both statistically and through downstream optimization and out-of-sample (OOS) settlement.</p>
<p>A third limitation, which earlier drafts of this manuscript explicitly recorded, is empirical: formulation smoke-tests and copula diagnostics do not by themselves establish economic superiority. Gate&nbsp;10 of this study therefore executes a common OOS settlement experiment on real SMARD DE-LU data, with frozen first-stage bids, identical physical limits, and an open-source solver, so that only the bidding architecture differs across B0, B2, and P1.</p>

<h3>A. Contributions</h3>
<p>The main contributions are as follows.</p>
<p>1) <i>Calibrated joint uncertainty representation.</i> Day-ahead forecast errors of price, load, PV, and wind are estimated on a rolling historical window and resampled as daily blocks, thereby preserving intra-day temporal dependence and cross-variable correlation.</p>
<p>2) <i>Tail-aware scenario use in a CVaR program.</i> A linear Rockafellar–Uryasev CVaR is optimized over the retained scenarios so that lower-tail profit, not only the mean, enters the first-stage bid.</p>
<p>3) <i>Deliverable reserve co-optimization (P1).</i> Upward and downward reserve is offered only if it remains feasible for the battery SoC and DG headroom in every retained scenario, i.e., a robust, dispatch-group style deliverability restriction.</p>
<p>4) <i>Strict empirical validation.</i> Real German SMARD data (CC&nbsp;BY&nbsp;4.0), chronological information sets, independent OOS settlement, multiple scenario cardinalities, sensitivity in λ and α, and paired statistical tests (t, Wilcoxon, bootstrap CI, Cohen’s d).</p>
<p>5) <i>Reproducible open-source solve.</i> All programs are LPs solved by HiGHS through SciPy to status <i>kOptimal</i>, with recorded runtimes, variable counts, and settlement accounts.</p>
<p>The remainder of the paper is organized as follows. Section&nbsp;II reviews the literature. Section&nbsp;III states the system and assumptions. Section&nbsp;IV describes the SMARD data and the scenario engine. Section&nbsp;V formulates the stochastic program. Section&nbsp;VI presents the experimental design. Section&nbsp;VII reports the Gate-10 results. Section&nbsp;VIII discusses implications, Section&nbsp;IX states limitations, and Section&nbsp;X concludes.</p>

<h2>II. Related Work and Research Gap</h2>
<h3>A. VPP Bidding under Uncertainty</h3>
<p>Much of the recent literature formulates VPP day-ahead bidding as a two-stage stochastic program, in which the first-stage DA bid is fixed before uncertainty is revealed and a second-stage recourse action absorbs the resulting imbalance [8]–[12]. Learning-based and game-theoretic alternatives have also been explored [11], [12]. Across this body of work, the two-stage MILP/LP remains the dominant and most tractable structure and is retained as the backbone of the model proposed here.</p>
<h3>B. Risk Measures</h3>
<p>Because a risk-neutral expected-profit objective can expose a VPP operator to large losses in adverse scenarios, CVaR has become the standard risk measure, valued for its convexity and its exact linear reformulation [3], [6], [9], [14]. Distributionally robust optimization (DRO) addresses ambiguity in the distribution itself [13], [32], whereas CVaR addresses the shape of the loss tail once a distribution has been fixed. This paper retains CVaR for MILP/LP tractability and addresses distributional risk through calibrated, dependence-preserving scenarios rather than an explicit ambiguity set.</p>
<h3>C. Dependence, Calibration, and Deliverable Reserve</h3>
<p>Copula-based scenario generation for wind and price errors exists but defaults overwhelmingly to the Gaussian copula, which under-represents joint tail events [18]. Conformal prediction has recently been applied to electricity-price intervals [19], [20], yet has not been linked, in the studies reviewed here, to a CVaR-constrained VPP bid. Reserve offers are frequently sized from nominal aggregate capacity rather than from the capacity that remains deliverable after the loss of a single asset. No identified study combines calibrated joint errors, CVaR, degradation-aware battery cost, dispatch-group deliverability, and a rolling-origin SMARD OOS protocol. That combination is the gap addressed below.</p>

<table>
<caption>TABLE I<br/>POSITIONING OF THE PROPOSED MODEL AGAINST REPRESENTATIVE STUDIES</caption>
<thead>
<tr><th>Study</th><th>Uncertainty</th><th>Dependence</th><th>Risk</th><th>BESS deg.</th><th>Real data</th><th>Deliverable reserve</th></tr>
</thead>
<tbody>
<tr><td>Mujeeb et al. [8]</td><td>Two-stage SP</td><td>Independent</td><td>CVaR</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Fan and Liu [13]</td><td>Wasserstein DRO</td><td>—</td><td>Chance/DRO</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Wang et al. [18]</td><td>Conditional scenarios</td><td>Gaussian mixture</td><td>Forecast only</td><td>—</td><td>Wind</td><td>—</td></tr>
<tr><td>O’Connor et al. [19]</td><td>Conformal intervals</td><td>—</td><td>Forecast only</td><td>—</td><td>DA/BM prices</td><td>—</td></tr>
<tr><td>Vahedipour-Dahraie et al. [3]</td><td>SP</td><td>—</td><td>CVaR</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Nemati et al. [1]</td><td>Flexible robust</td><td>Asymmetric sets</td><td>Robust</td><td>—</td><td>Sequential markets</td><td>—</td></tr>
<tr><td><b>This paper (P1)</b></td><td>Calibrated joint scenarios</td><td>Block-bootstrap / heavy-tail-aware</td><td>Linear CVaR</td><td>Yes (throughput)</td><td>SMARD DE-LU, rolling OOS</td><td>Yes (SoC-feasible in all scenarios)</td></tr>
</tbody>
</table>

<h2>III. System Description and Assumptions</h2>
<p>The VPP aggregates PV, wind, a BESS, a dispatchable DG unit, and an industrial load, and participates in the day-ahead energy market as a price-taker, with an optional reserve product in P1. Explicit assumptions are:</p>
<p>1) Forecast errors are treated as stationary within each rolling estimation window.</p>
<p>2) Battery degradation is a linear throughput cost [15], [16]; this is a modeling choice, not a claim of electrochemical accuracy.</p>
<p>3) The VPP is a price-taker.</p>
<p>4) Imbalance settlement uses a two-price structure (short at a premium to DA, long at a discount), consistent with a dual-imbalance mechanism.</p>
<p>5) Reserve, where offered, must be deliverable given SoC and DG headroom in every retained scenario.</p>
<p>6) Load is served under an energy-only industrial contract of 180&nbsp;EUR/MWh used only in reporting (the load trajectory is exogenous and does not change first-stage optimality up to a scenario-wise constant).</p>

<table>
<caption>TABLE II<br/>VPP RATINGS AND MARKET PARAMETERS USED IN GATE 10</caption>
<thead><tr><th>Parameter</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Load reference (p95, scaled)</td><td>5.00 MW</td></tr>
<tr><td>PV / wind ratings</td><td>4.00 / 2.00 MW</td></tr>
<tr><td>BESS power / energy</td><td>2.50 MW / 5.00 MWh</td></tr>
<tr><td>Charge / discharge efficiency</td><td>0.95 / 0.95</td></tr>
<tr><td>SoC bounds / initial (cyclic)</td><td>10%–90% / 50%</td></tr>
<tr><td>Throughput degradation</td><td>1.50 EUR/MWh</td></tr>
<tr><td>DG rating / variable cost / ramp</td><td>1.80 MW / 68 EUR/MWh / 1.20 MW/h</td></tr>
<tr><td>Max |DA position| / max reserve</td><td>12 MW / 1.50 MW</td></tr>
<tr><td>Default λ / α / K</td><td>0.05 / 0.95 / 50</td></tr>
<tr><td>Reserve price (up / down base)</td><td>9.0 / 6.5 EUR/MW/h (shaped by DA price)</td></tr>
<tr><td>Imbalance short add / coef.</td><td>18 EUR/MWh / 0.12</td></tr>
<tr><td>Imbalance long add / coef.</td><td>10 EUR/MWh / 0.08</td></tr>
<tr><td>Solver</td><td>HiGHS (SciPy linprog, method=highs)</td></tr>
</tbody>
</table>

<h2>IV. Data and Uncertainty Modeling</h2>
<h3>A. Data Source</h3>
<p>The empirical analysis uses publicly available German electricity-market data published by the Bundesnetzagentur on SMARD.de and accessed via the Energy-Charts API under a CC&nbsp;BY&nbsp;4.0 licence, bidding zone DE-LU. Day-ahead prices, public net generation by technology, load, and day-ahead forecasts of solar, onshore wind, offshore wind, and load are obtained at 15-min resolution and resampled to hourly means. The processed panel covers 1&nbsp;June 2026 00:00 to 21&nbsp;August 2026 07:00 Europe/Berlin (1&nbsp;952 hourly stamps, 81 complete calendar days). National series are scaled to the VPP ratings of Table&nbsp;II using study-window peaks (load p95 60.4&nbsp;GW, solar max 58.1&nbsp;GW, wind max 41.6&nbsp;GW). A day-ahead price forecast is formed as a 0.55/0.45 mix of yesterday’s and last-week’s same-hour prices. The Gate-10 operating day is Wednesday 19&nbsp;August 2026; the rolling OOS window is 6–19&nbsp;August 2026.</p>
{F['1']}
<table>
<caption>TABLE III<br/>DATASET SUMMARY (SMARD DE-LU)</caption>
<thead><tr><th>Item</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Bidding zone / licence</td><td>DE-LU / CC BY 4.0, Bundesnetzagentur | SMARD.de</td></tr>
<tr><td>Raw resolution</td><td>15 min, resampled to 1 h</td></tr>
<tr><td>Study window</td><td>2026-06-01 to 2026-08-21</td></tr>
<tr><td>Complete days / hourly stamps</td><td>81 / 1 952</td></tr>
<tr><td>DA price mean / std</td><td>109.23 / 71.58 EUR/MWh (15-min native)</td></tr>
<tr><td>DA price min / max</td><td>−499.99 / 747.10 EUR/MWh</td></tr>
<tr><td>Operating day</td><td>2026-08-19 (complete actuals and forecasts)</td></tr>
<tr><td>Scenario history</td><td>58 error days, K = 50 daily block bootstrap</td></tr>
</tbody>
</table>
<p>Forecast errors on the historical window are</p>
<p class="eq">e<sub>t</sub><sup>x</sup> = x<sub>t</sub><sup>act</sup> − x<sub>t</sub><sup>fc</sup>, &nbsp; x ∈ {{P, L, PV, W}}. <span class="eqno">(1)</span></p>
<p>Table&nbsp;IV reports the error statistics used by the scenario engine. Price errors are heavy-tailed (excess kurtosis 15.8); load errors are nearly symmetric; PV and wind errors are concentrated around zero with moderate tails.</p>
<table>
<caption>TABLE IV<br/>DAY-AHEAD FORECAST-ERROR STATISTICS (58 DAYS, HOURLY)</caption>
<thead><tr><th>Variable</th><th>Mean</th><th>Std</th><th>MAE</th><th>RMSE</th><th>P5</th><th>P95</th><th>Skew</th><th>Kurtosis</th></tr></thead>
<tbody>
<tr><td>DA price (EUR/MWh)</td><td>3.10</td><td>43.42</td><td>26.30</td><td>43.51</td><td>−59.51</td><td>61.76</td><td>−0.26</td><td>15.81</td></tr>
<tr><td>Load (MW)</td><td>−0.006</td><td>0.194</td><td>0.157</td><td>0.194</td><td>−0.326</td><td>0.321</td><td>0.03</td><td>−0.30</td></tr>
<tr><td>PV (MW)</td><td>−0.006</td><td>0.093</td><td>0.052</td><td>0.093</td><td>−0.184</td><td>0.126</td><td>−0.06</td><td>5.51</td></tr>
<tr><td>Wind (MW)</td><td>−0.002</td><td>0.090</td><td>0.062</td><td>0.090</td><td>−0.160</td><td>0.127</td><td>0.03</td><td>3.59</td></tr>
</tbody>
</table>
{F['3']}
{F['4']}
<h3>B. Scenario Generation</h3>
<p>For an operating day D, K historical error days are drawn with replacement from the 50-day look-back window that ends on D−1. Each drawn day contributes a 24-hour error vector that is added to the point forecast of D, with physical clipping of load, PV, and wind. Scenarios are equiprobable, π<sub>ω</sub>&nbsp;=&nbsp;1/K. This daily block bootstrap preserves the intra-day autocorrelation that a purely i.i.d. copula draw would have to reconstruct explicitly. Earlier gates of the project fitted a Student-t copula with ν&nbsp;=&nbsp;18.55, validation AIC −670.74 versus −429.90 for a Gaussian copula, and OOS log-likelihood +12.99 versus −30.71, together with a pooled mean absolute ACF error of 0.00395. Gate&nbsp;10 uses the block bootstrap on the same SMARD error processes so that the bidding experiment remains fully auditable from the public series.</p>
{F['2']}
<p>Two-price imbalance paths are obtained from the scenario DA price by a short premium and a long discount, enforcing λ<sup>long</sup> ≤ λ<sup>DA</sup> ≤ λ<sup>short</sup>. Reserve capacity prices are shaped by the DA price forecast (base 9.0/6.5&nbsp;EUR/MW/h).</p>

<h2>V. Stochastic Formulation</h2>
<p>Let T&nbsp;=&nbsp;24 hours and Ω the retained scenario set. First-stage decisions (here-and-now) are the DA energy position p<sub>t</sub><sup>DA</sup> and, in P1, upward/downward reserve r<sub>t</sub><sup>↑</sup>, r<sub>t</sub><sup>↓</sup>. Second-stage recourse in scenario ω comprises charge/discharge, SoC, DG, and short/long imbalance. The mean–CVaR objective is</p>
<p class="eq">max &nbsp; (1−λ) E[Π<sub>ω</sub>] + λ CVaR<sub>α</sub>(Π<sub>ω</sub>), <span class="eqno">(2)</span></p>
<p>with the Rockafellar–Uryasev representation [6], [14]</p>
<p class="eq">CVaR<sub>α</sub>(Π) = η − (1−α)<sup>−1</sup> E[ξ<sub>ω</sub>], &nbsp; ξ<sub>ω</sub> ≥ η − Π<sub>ω</sub>, &nbsp; ξ<sub>ω</sub> ≥ 0. <span class="eqno">(3)</span></p>
<p>Scenario profit is DA energy revenue plus reserve capacity revenue minus DG fuel, battery degradation, and two-price imbalance settlement. Power balance, SoC dynamics with cyclic terminal SoC, DG ramp, and (in P1) reserve–SoC coupling</p>
<p class="eq">p<sub>t,ω</sub><sup>dis</sup> + p<sub>t,ω</sub><sup>DG</sup> + r<sub>t</sub><sup>↑</sup> ≤ P<sup>batt</sup> + P<sup>DG</sup>, &nbsp; E<sub>t,ω</sub> − r<sub>t</sub><sup>↑</sup>/η<sup>dis</sup> ≥ E<sup>min</sup> <span class="eqno">(4)</span></p>
<p>are imposed for all ω, t. Simultaneous charge and discharge is never optimal under η&nbsp;&lt;&nbsp;1 and a positive degradation cost, so the formulation is an LP. B0 is the expected-value restriction (K&nbsp;=&nbsp;1, λ&nbsp;=&nbsp;0, no reserve). B2 is (2)–(3) without reserve. P1 is the full joint energy–reserve program.</p>

<h2>VI. Solution Method and Experimental Design</h2>
<p>The workflow is: SMARD → hourly VPP panel → error-day bootstrap → LP (B0/B2/P1) → freeze first-stage bids → recourse on each in-sample scenario and on the realized day. HiGHS is used throughout. No MIP gap arises because the implemented Gate-10 programs are LPs.</p>
<p><b>B0</b> — deterministic expected-value energy-only. <b>B2</b> — two-stage mean–CVaR energy-only. <b>P1</b> — proposed two-stage mean–CVaR joint energy–reserve. (The Gaussian-copula stochastic program B1 of the methodological taxonomy is retained as a statistical benchmark in the copula AIC comparison; it is not a separate Gate-10 economic column, because the executed decision experiment contrasts B0, B2, and P1 on a common scenario set.)</p>
<p>Sensitivity: λ ∈ {{0, 0.01, 0.02, 0.05, 0.1, 0.2}}, α ∈ {{0.90, 0.95, 0.99}}, K ∈ {{30, 50, 100}} (full factorial on P1, 54 solves, all kOptimal). Rolling OOS: 14 consecutive complete days ending 19&nbsp;August&nbsp;2026, each with its own look-back scenarios. Paired tests use scenario-level profits (n&nbsp;=&nbsp;50) and day-level OOS profits (n&nbsp;=&nbsp;14), with 8&nbsp;000 bootstrap resamples of the mean difference.</p>

<h2>VII. Results</h2>
<h3>A. Forecast Diagnostics</h3>
<p>Fig.&nbsp;1 shows that 19&nbsp;August&nbsp;2026 is a high-price weekday (realized DA around 130–210&nbsp;EUR/MWh) with a pronounced solar peak and a wind forecast that over-states afternoon output. Fig.&nbsp;2 confirms that the bootstrap fans cover the realized paths. Figs.&nbsp;3–4 document heavy-tailed price errors and the hour-specific correlation structure that a diagonal-covariance model would miss.</p>

<h3>B. Computational Validation</h3>
<p>All Gate-10 programs returned HiGHS status kOptimal. Table&nbsp;V reports sizes and runtimes on the operating day. P1 with K&nbsp;=&nbsp;50 has 7&nbsp;323 variables and 7&nbsp;150 inequalities and solves in 0.30&nbsp;s; at K&nbsp;=&nbsp;100 the runtime remains 1.61&nbsp;s (Fig.&nbsp;21).</p>
<table>
<caption>TABLE V<br/>COMPUTATIONAL PERFORMANCE (OPERATING DAY 19 AUG 2026)</caption>
<thead><tr><th>Model</th><th>K</th><th>Variables</th><th>Equalities</th><th>Inequalities</th><th>HiGHS status</th><th>Iterations</th><th>Runtime (s)</th></tr></thead>
<tbody>
<tr><td>B0</td><td>1</td><td>216</td><td>49</td><td>46</td><td>kOptimal</td><td>62</td><td>0.011</td></tr>
<tr><td>B2</td><td>50</td><td>7 323</td><td>2 450</td><td>2 350</td><td>kOptimal</td><td>6 568</td><td>0.173</td></tr>
<tr><td>P1</td><td>50</td><td>7 323</td><td>2 450</td><td>7 150</td><td>kOptimal</td><td>5 226</td><td>0.303</td></tr>
</tbody>
</table>
{F['21']}

<h3>C. Day-Ahead Positions and Recourse</h3>
<p>Fig.&nbsp;5 shows that all three models are net buyers over the day (DA energy −23.7 to −25.8&nbsp;MWh), as expected for a 5&nbsp;MW industrial load with limited on-site RES. P1 additionally sells 26.62&nbsp;MW·h of upward and 28.25&nbsp;MW·h of downward reserve, earning 589&nbsp;EUR of capacity revenue. Fig.&nbsp;12 is the operational signature of that offer: unlike B0/B2, which empty the battery to the 10% floor overnight, P1 holds approximately 2.2&nbsp;MWh of SoC through the first hours so that upward reserve remains energy-feasible. DG is dispatched at its 1.8&nbsp;MW cap in high-price hours (Fig.&nbsp;13). Realized short imbalance falls from 2.05&nbsp;MWh (B0) to 0.65&nbsp;MWh (B2 and P1).</p>
{F['5']}
{F['12']}
{F['13']}
{F['14']}
{F['15']}
{F['16']}

<h3>D. Economic Benchmark</h3>
<p>Table&nbsp;VI fills the benchmark that earlier drafts left blank, using only numbers from the recorded Gate-10 run. P1 improves both the mean and the tail relative to B0 and B2. B2’s in-sample edge over B0 is a modest 10&nbsp;EUR/day.</p>
<table>
<caption>TABLE VI<br/>GATE-10 OPTIMIZATION AND SETTLEMENT RESULTS (19 AUG 2026)</caption>
<thead><tr><th>Metric</th><th>B0</th><th>B2</th><th>P1</th></tr></thead>
<tbody>
<tr><td>HiGHS status</td><td>kOptimal</td><td>kOptimal</td><td>kOptimal</td></tr>
<tr><td>Expected profit (EUR)</td><td>11 497.86</td><td>11 508.28</td><td><b>11 991.79</b></td></tr>
<tr><td>CVaR<sub>0.95</sub> (EUR)</td><td>9 985.66</td><td>10 026.78</td><td><b>10 440.13</b></td></tr>
<tr><td>Std. dev. (EUR)</td><td>893.10</td><td>888.63</td><td><b>863.51</b></td></tr>
<tr><td>P5 / P50 / P95 profit (EUR)</td><td>10 619 / 11 419 / 13 270</td><td>10 624 / 11 431 / 13 299</td><td>11 105 / 11 924 / 13 828</td></tr>
<tr><td>Realized OOS profit (EUR)</td><td>10 938.36</td><td>10 964.67</td><td><b>11 486.96</b></td></tr>
<tr><td>DA energy (MWh)</td><td>−23.71</td><td>−25.80</td><td>−25.55</td></tr>
<tr><td>Reserve up / down (MW·h)</td><td>0 / 0</td><td>0 / 0</td><td>26.62 / 28.25</td></tr>
<tr><td>Reserve revenue (EUR)</td><td>0</td><td>0</td><td>588.82</td></tr>
<tr><td>OOS imbalance short / long (MWh)</td><td>2.054 / 0.955</td><td>0.650 / 1.649</td><td>0.646 / 1.735</td></tr>
<tr><td>OOS DG energy (MWh)</td><td>43.20</td><td>43.20</td><td>43.20</td></tr>
<tr><td>OOS battery throughput (MWh)</td><td>20.03</td><td>19.75</td><td>13.13</td></tr>
<tr><td>Curtailment (MWh)</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>N−1 / SoC-reserve violations</td><td>n/a</td><td>n/a</td><td>0</td></tr>
<tr><td>MIP gap</td><td>0 (LP)</td><td>0 (LP)</td><td>0 (LP)</td></tr>
<tr><td>Runtime (s)</td><td>0.011</td><td>0.173</td><td>0.303</td></tr>
</tbody>
</table>
<table>
<caption>TABLE VII<br/>REALIZED SETTLEMENT DECOMPOSITION (EUR), 19 AUG 2026</caption>
<thead><tr><th>Component</th><th>B0</th><th>B2</th><th>P1</th></tr></thead>
<tbody>
<tr><td>Load-service revenue</td><td>18 023.57</td><td>18 023.57</td><td>18 023.57</td></tr>
<tr><td>DA energy revenue</td><td>−3 894.99</td><td>−4 254.76</td><td>−4 343.29</td></tr>
<tr><td>Reserve revenue</td><td>0.00</td><td>0.00</td><td>588.82</td></tr>
<tr><td>Imbalance settlement</td><td>−222.59</td><td>163.07</td><td>175.16</td></tr>
<tr><td>DG fuel</td><td>2 937.60</td><td>2 937.60</td><td>2 937.60</td></tr>
<tr><td>Battery degradation</td><td>30.04</td><td>29.62</td><td>19.70</td></tr>
<tr><td>Net profit</td><td>10 938.36</td><td>10 964.67</td><td>11 486.96</td></tr>
</tbody>
</table>
{F['6']}
{F['7']}
{F['8']}
{F['9']}
{F['10']}
{F['11']}
<p>The ECDF in Fig.&nbsp;8 shows that P1’s scenario-profit law lies to the right of B0 and B2 over almost the entire support; B0 and B2 are nearly indistinguishable. Table&nbsp;VII shows that the 548&nbsp;EUR realized gap of P1 versus B0 is essentially the reserve capacity payment (589&nbsp;EUR) plus a better imbalance account and lower cycling, partly offset by a slightly more expensive DA energy position.</p>

<h3>E. Scenario Count</h3>
<p>Table&nbsp;VIII reports P1 at λ&nbsp;=&nbsp;0.05, α&nbsp;=&nbsp;0.95 for K ∈ {{30, 50, 100}}. Realized OOS profit is stable to within 9&nbsp;EUR/day. Expected profit declines slightly as K grows because additional tail scenarios enter the average; CVaR remains in a 150&nbsp;EUR band. K&nbsp;=&nbsp;50 is therefore retained as the default, not because it maximises profit, but because it is the smallest cardinality at which both the mean and the tail have stabilised relative to K&nbsp;=&nbsp;100 while remaining an order of magnitude faster.</p>
<table>
<caption>TABLE VIII<br/>P1 SCENARIO-COUNT EXPERIMENT (λ = 0.05, α = 0.95)</caption>
<thead><tr><th>K</th><th>E[profit] (EUR)</th><th>CVaR (EUR)</th><th>Std (EUR)</th><th>Realized (EUR)</th><th>Runtime (s)</th><th>Σ r↑</th><th>Σ r↓</th></tr></thead>
<tbody>
<tr><td>30</td><td>12 067.43</td><td>10 588.14</td><td>946.68</td><td>11 485.98</td><td>0.139</td><td>26.70</td><td>28.34</td></tr>
<tr><td>50</td><td>11 991.79</td><td>10 440.13</td><td>863.51</td><td>11 486.96</td><td>0.338</td><td>26.62</td><td>28.25</td></tr>
<tr><td>100</td><td>11 876.92</td><td>10 538.44</td><td>776.27</td><td>11 478.33</td><td>1.610</td><td>24.61</td><td>27.34</td></tr>
</tbody>
</table>

<h3>F. Risk-Aversion Sensitivity</h3>
<p>Table&nbsp;IX and Fig.&nbsp;17 vary λ at α&nbsp;=&nbsp;0.95, K&nbsp;=&nbsp;50. Moving from λ&nbsp;=&nbsp;0 to λ&nbsp;=&nbsp;0.20 raises CVaR by 113&nbsp;EUR and reduces expected profit by only 14&nbsp;EUR. Realized OOS profit is maximised near λ&nbsp;=&nbsp;0.05 (the default), not at λ&nbsp;=&nbsp;0, which is consistent with using CVaR as a regulariser of the first-stage bid rather than as a substitute for expected-profit maximisation.</p>
<table>
<caption>TABLE IX<br/>P1 SENSITIVITY TO λ (α = 0.95, K = 50)</caption>
<thead><tr><th>λ</th><th>E[profit]</th><th>CVaR<sub>0.95</sub></th><th>Realized</th><th>Runtime (s)</th></tr></thead>
<tbody>
<tr><td>0.00</td><td>11 992.62</td><td>10 418.03</td><td>11 477.34</td><td>0.182</td></tr>
<tr><td>0.01</td><td>11 992.59</td><td>10 422.84</td><td>11 481.60</td><td>0.246</td></tr>
<tr><td>0.02</td><td>11 992.50</td><td>10 428.98</td><td>11 484.48</td><td>0.309</td></tr>
<tr><td>0.05</td><td>11 991.79</td><td>10 440.13</td><td>11 486.96</td><td>0.338</td></tr>
<tr><td>0.10</td><td>11 985.80</td><td>10 511.62</td><td>11 474.33</td><td>0.369</td></tr>
<tr><td>0.20</td><td>11 978.20</td><td>10 531.24</td><td>11 472.46</td><td>0.426</td></tr>
</tbody>
</table>
{F['17']}

<h3>G. CVaR Confidence-Level Sensitivity</h3>
<p>Table&nbsp;X and Fig.&nbsp;18 vary α at λ&nbsp;=&nbsp;0.05, K&nbsp;=&nbsp;50. As α increases, the empirical CVaR (a more extreme tail average) falls, as it must; expected profit is essentially flat until α&nbsp;=&nbsp;0.99, where a slightly more conservative reserve schedule appears. The default α&nbsp;=&nbsp;0.95 is therefore not an isolated sweet spot.</p>
<table>
<caption>TABLE X<br/>P1 SENSITIVITY TO α (λ = 0.05, K = 50)</caption>
<thead><tr><th>α</th><th>E[profit]</th><th>CVaR</th><th>Realized</th><th>Runtime (s)</th></tr></thead>
<tbody>
<tr><td>0.90</td><td>11 992.23</td><td>10 715.40</td><td>11 488.42</td><td>0.331</td></tr>
<tr><td>0.95</td><td>11 991.79</td><td>10 440.13</td><td>11 486.96</td><td>0.338</td></tr>
<tr><td>0.99</td><td>11 986.91</td><td>10 107.65</td><td>11 471.27</td><td>0.362</td></tr>
</tbody>
</table>
{F['18']}

<h3>H. Reliability</h3>
<p>P1’s reserve constraints are imposed in every scenario, so the number of SoC/headroom violations on the operating day is zero and the reliability index RLI&nbsp;=&nbsp;1 − N<sub>viol</sub>/N<sub>events</sub> equals 1. B0 and B2 do not offer reserve, so N−1 is not applicable; their physical shortfall is the short-imbalance energy of Table&nbsp;VI. Renewable curtailment is zero in all models because available PV and wind are must-take in the power balance.</p>
<table>
<caption>TABLE XI<br/>RELIABILITY ON THE OPERATING DAY</caption>
<thead><tr><th>Model</th><th>N−1 / SoC-reserve violations</th><th>Shortfall (MWh, OOS short imb.)</th><th>Reliability index</th></tr></thead>
<tbody>
<tr><td>B0</td><td>n/a (no reserve offer)</td><td>2.054</td><td>n/a</td></tr>
<tr><td>B2</td><td>n/a (no reserve offer)</td><td>0.650</td><td>n/a</td></tr>
<tr><td>P1</td><td>0</td><td>0.646</td><td>1.000</td></tr>
</tbody>
</table>

<h3>I. Statistical Comparison</h3>
<p>Table&nbsp;XII reports paired tests. In sample, P1−B0 and P1−B2 are large and decisive (Cohen’s d&nbsp;&gt;&nbsp;6, both tests p&nbsp;&lt;&nbsp;10<sup>−9</sup>, bootstrap 95% CIs well above zero). B2−B0 is small (d&nbsp;=&nbsp;0.30) and only marginally significant. Out of sample over 14 days, P1 again dominates with d&nbsp;=&nbsp;9.39 versus B0 and d&nbsp;=&nbsp;12.15 versus B2; B2−B0 is not significant (p&nbsp;=&nbsp;0.33) and the CI includes zero. These tests treat paired daily (or scenario) differences as the primitive, as required by the experimental protocol of Section&nbsp;VI.</p>
<table>
<caption>TABLE XII<br/>PAIRED STATISTICAL TESTS ON PROFIT</caption>
<thead><tr><th>Comparison</th><th>n</th><th>Mean diff. (EUR)</th><th>t</th><th>p (t)</th><th>p (Wilcoxon)</th><th>Cohen’s d</th><th>Boot. 95% CI</th></tr></thead>
<tbody>
<tr><td>P1 − B0 (IS)</td><td>50</td><td>+493.92</td><td>44.46</td><td>2.88×10<sup>−41</sup></td><td>7.50×10<sup>−10</sup></td><td>6.29</td><td>[471.1, 514.5]</td></tr>
<tr><td>P1 − B2 (IS)</td><td>50</td><td>+483.51</td><td>44.66</td><td>2.33×10<sup>−41</sup></td><td>7.50×10<sup>−10</sup></td><td>6.32</td><td>[460.8, 502.3]</td></tr>
<tr><td>B2 − B0 (IS)</td><td>50</td><td>+10.41</td><td>2.14</td><td>0.037</td><td>0.036</td><td>0.30</td><td>[1.0, 20.0]</td></tr>
<tr><td>P1 − B0 (OOS)</td><td>14</td><td>+563.36</td><td>35.14</td><td>2.85×10<sup>−14</sup></td><td>1.22×10<sup>−4</sup></td><td>9.39</td><td>[533.0, 593.0]</td></tr>
<tr><td>P1 − B2 (OOS)</td><td>14</td><td>+569.92</td><td>45.47</td><td>1.02×10<sup>−15</sup></td><td>1.22×10<sup>−4</sup></td><td>12.15</td><td>[546.0, 593.2]</td></tr>
<tr><td>B2 − B0 (OOS)</td><td>14</td><td>−6.56</td><td>−1.02</td><td>0.325</td><td>0.326</td><td>−0.27</td><td>[−18.5, 5.5]</td></tr>
</tbody>
</table>
{F['19']}
{F['20']}
{F['22']}
<p>Fig.&nbsp;19 is the decision-level confirmation requested in earlier drafts: over fourteen consecutive OOS days, mean realized profit is 11&nbsp;639 (B0), 11&nbsp;633 (B2), and 12&nbsp;203 (P1) EUR/day. P1 is strictly above B0 and B2 on every day, including the low-price weekend of 16–18&nbsp;August.</p>

<h2>VIII. Discussion</h2>
<p>The Gate-10 experiment supports a precise, rather than rhetorical, conclusion. Statistical improvement of a copula, or solvability of a CVaR LP, does not automatically improve settlement. On these SMARD days the energy-only CVaR program B2 is almost economically equivalent to the deterministic EV program B0 once bids are frozen and realized (OOS p&nbsp;=&nbsp;0.33). What does improve settlement is the joint energy–reserve architecture of P1, which sells only SoC-feasible reserve and, as a side effect, cycles the battery less (13.1 versus 20.0&nbsp;MWh throughput). The 589&nbsp;EUR reserve payment accounts for essentially the entire OOS gap.</p>
<p>That finding does not make CVaR redundant. Table&nbsp;IX shows that a small λ improves realized profit relative to λ&nbsp;=&nbsp;0, i.e., CVaR is a useful regulariser of P1’s first-stage bid. It does mean that CVaR applied to an energy-only recourse set, without a reserve product whose feasibility depends on the tail, cannot be expected to move the OOS needle on this portfolio.</p>
<p>The information firewall is respected: each day’s scenarios are built from errors strictly before that day, and first-stage bids are frozen before realized prices, load, and RES are introduced into settlement. HiGHS is not claimed to be faster than commercial MIP solvers; it is claimed to have produced auditable kOptimal LPs on commodity hardware in under two seconds.</p>

<h2>IX. Limitations</h2>
<p>1) Demand response is not an observed VPP activation series in SMARD; the industrial load is treated as an exogenous obligation. DR should be read as a modeled capability, not as a measured DSM programme.</p>
<p>2) N−1 deliverability is enforced as SoC- and headroom-feasible reserve in every scenario, not as a full asset-level reliability assessment.</p>
<p>3) The VPP is a price-taker; strategic bidding is outside the scope.</p>
<p>4) Battery degradation is linear throughput.</p>
<p>5) The executed economic comparison is B0/B2/P1. A separately sampled Gaussian-copula generator (B1) is not re-solved in Gate&nbsp;10; the Gaussian versus Student-t comparison remains the earlier AIC/log-likelihood evidence.</p>
<p>6) The SMARD window used here is summer 2026. Winter weeks with scarcer PV and more negative prices may change the reserve–energy trade-off and should be added in an extension.</p>
<p>7) Scenario reduction quality is assessed by K-stability of profit and CVaR, not by Kantorovich distance to a 5&nbsp;000-trajectory pool on this particular Gate.</p>

<h2>X. Conclusion</h2>
<p>This paper has completed the decision-level experiment that earlier drafts of the manuscript deferred. A calibrated, dependence-aware, CVaR-constrained VPP bidding LP was posed, solved to proven optimality with HiGHS, and settled on real SMARD DE-LU data under a no-leakage protocol. On 19&nbsp;August&nbsp;2026 the proposed joint energy–reserve model P1 realized 11&nbsp;487&nbsp;EUR against 10&nbsp;938&nbsp;EUR for the deterministic EV benchmark and 10&nbsp;965&nbsp;EUR for the energy-only CVaR benchmark. The in-sample paired advantage of P1 over B0 is +494&nbsp;EUR/day (Cohen’s d&nbsp;=&nbsp;6.29); the 14-day rolling OOS advantage is +563&nbsp;EUR/day with strict daily dominance. The source of the gain is deliverable reserve that is feasible for the battery SoC in every scenario, not an in-sample overfit of the energy position. Energy-only CVaR (B2) does not significantly outperform B0 out of sample. These statements replace the withheld-superiority language of the previous draft and are tied to recorded run identifiers, solver statuses, and settlement accounts. Future work will extend the same firewall to winter weeks, an explicit Student-t sampler inside Gate&nbsp;10, and a measured DR activation series.</p>

<h2>Acknowledgment</h2>
<p>Day-ahead prices and public-power series are © Bundesnetzagentur | SMARD.de, republished without modification via Energy-Charts under CC&nbsp;BY&nbsp;4.0. Numerical programs were solved with the open-source HiGHS solver.</p>

<h2>References</h2>
<ol class="refs">
<li>H. Nemati, P. Sánchez-Martín, Á. Ortega, L. Sigrist, E. Lobato, and L. Rouco, “Flexible robust optimal bidding of renewable virtual power plants in sequential markets under asymmetric uncertainties,” <i>Sustainable Energy, Grids and Networks</i>, vol.&nbsp;43, Art.&nbsp;no.&nbsp;101801, 2025, doi: 10.1016/j.segan.2025.101801.</li>
<li>Y. Lu, J. Zhang, B. Lu, and Z. Tan, “A two-stage cooperative scheduling model for virtual power plants accounting for price stochastic perturbations,” <i>Energies</i>, vol.&nbsp;18, no.&nbsp;17, p.&nbsp;4586, 2025.</li>
<li>M. Vahedipour-Dahraie, H. Rashidizadeh-Kermani, M. Shafie-Khah, and J. P. S. Catalão, “Risk-averse optimal energy and reserve scheduling for virtual power plants incorporating demand response programs,” <i>IEEE Trans. Smart Grid</i>, vol.&nbsp;12, no.&nbsp;2, pp.&nbsp;1405–1415, Mar. 2021. (Corrected from an earlier draft that cited vol.&nbsp;11, pp.&nbsp;5075–5086.)</li>
<li>Y. Zhang <i>et al.</i>, “A distributionally robust optimization approach for virtual power plant scheduling under uncertainty,” <i>Appl. Energy</i>, 2023.</li>
<li>Z. Siqin <i>et al.</i>, “Two-stage distributionally robust bidding strategies for multi-energy virtual power plants in energy, reserve and carbon markets,” <i>Energy</i>, vol.&nbsp;334, Art.&nbsp;no.&nbsp;137455, 2025.</li>
<li>D. Xiao <i>et al.</i>, “CVaR-constrained stochastic bidding strategy for a virtual power plant with mobile energy storages,” in <i>Proc. IEEE ISGT Europe</i>, 2020.</li>
<li>Z. Wang <i>et al.</i>, “Stochastic bidding for VPPs enabled ancillary services: A case study,” <i>Appl. Energy</i>, vol.&nbsp;352, 2023.</li>
<li>A. Mujeeb <i>et al.</i>, “Optimizing virtual power plant operations in energy and frequency regulation reserve markets: A risk-averse two-stage scenario-oriented stochastic approach,” <i>Int. Trans. Electr. Energy Syst.</i>, 2025.</li>
<li>D. Xiao, “A review on risk-averse bidding strategies for virtual power plants with uncertainties: Resources, technologies, and future pathways,” <i>Technologies</i>, vol.&nbsp;13, no.&nbsp;11, Art.&nbsp;no.&nbsp;488, 2025.</li>
<li>H. Du, J. Hu, Y. Fang, and D. Xie, “Optimal bidding strategy for virtual power plant participating in joint energy and reserve market considering physical–economic feasible operation region,” <i>Energy</i>, vol.&nbsp;336, Art.&nbsp;no.&nbsp;138410, 2025.</li>
<li>W. Chang and Q. Yang, “Game-theoretic risk-averse day-ahead optimal bidding strategy of virtual power plant aggregated with heterogeneous distributed resources,” <i>Energy</i>, 2025.</li>
<li>Y. Jiang, J. Dong, and H. Huang, “Optimal bidding strategy for the price-maker virtual power plant in the day-ahead market based on multi-agent twin delayed deep deterministic policy gradient algorithm,” <i>Energy</i>, vol.&nbsp;306, 2024.</li>
<li>Q. Fan and D. Liu, “A Wasserstein-distance-based distributionally robust chance-constrained bidding model for virtual power plant considering electricity–carbon trading,” <i>IET Renew. Power Gener.</i>, vol.&nbsp;18, no.&nbsp;3, pp.&nbsp;545–557, 2024.</li>
<li>J. C. Do Prado and U. Chikezie, “A decision model for an electricity retailer with energy storage and virtual bidding under daily and hourly CVaR assessment,” <i>IEEE Access</i>, vol.&nbsp;9, pp.&nbsp;106181–106191, 2021.</li>
<li>Z. Tan, Q. Tan, and Y. Wang, “Bidding strategy of virtual power plant with energy storage power station and photovoltaic and wind power,” <i>J. Eng.</i>, Art.&nbsp;no.&nbsp;6139086, 2018.</li>
<li>Z. Wang, J. Gao, R. Zhao, J. Wang, and G. Li, “Optimal bidding strategy for virtual power plants considering the feasible region of vehicle-to-grid,” <i>Energy Convers. Econ.</i>, vol.&nbsp;1, no.&nbsp;3, pp.&nbsp;238–250, 2020.</li>
<li>J. Yoo and J. Kim, “A risk-aware bi-level bidding strategy for virtual power plant with power-to-hydrogen system,” arXiv:2503.05366, 2025.</li>
<li>Z. Wang, C. Shen, and F. Liu, “A conditional model of wind power forecast errors and its application in scenario generation,” <i>Appl. Energy</i>, vol.&nbsp;212, pp.&nbsp;771–785, 2018.</li>
<li>C. O’Connor, M. Bahloul, R. Rossi, S. Prestwich, and A. Visentin, “Conformal prediction for electricity price forecasting in the day-ahead and real-time balancing market,” <i>Energy and AI</i>, vol.&nbsp;21, Art.&nbsp;no.&nbsp;100571, 2025, doi: 10.1016/j.egyai.2025.100571.</li>
<li>C. O’Connor, S. Prestwich, and A. Visentin, “Conformal prediction techniques for electricity price forecasting,” in <i>AALTD 2024</i>, LNCS 15433, Springer, 2025, pp.&nbsp;1–17.</li>
<li>R. Gao and A. J. Kleywegt, “Distributionally robust stochastic optimization with Wasserstein distance,” <i>Math. Oper. Res.</i>, vol.&nbsp;48, no.&nbsp;2, pp.&nbsp;603–655, 2023. (Corrected pagination; an earlier draft listed pp.&nbsp;789–815.)</li>
<li>H. Heitsch and W. Römisch, “Scenario reduction algorithms in stochastic programming,” <i>Comput. Optim. Appl.</i>, vol.&nbsp;24, pp.&nbsp;187–206, 2003.</li>
<li>S. Pineda and J. M. Morales, “Capacity expansion of stochastic power generation under two-stage electricity markets,” <i>Comput. Oper. Res.</i>, 2016 / related decision-aware reduction literature.</li>
<li>S. Pineda, J. M. Morales, and A. J. Conejo, rolling-horizon stochastic bidding in real electricity markets; see also <i>IEEE Trans. Power Syst.</i> wind-bidding studies using moving-window evaluation.</li>
<li>ARPA-E, “PERFORM: Performance-based energy resource optimization and management,” U.S. DOE, 2024. [Online]. Available: https://arpa-e.energy.gov/technologies/programs/perform</li>
</ol>

<p class="note">Note on the bibliography. References [1], [3], [10], [19], [21] were checked against publisher records for this revision. Volume/page errors in earlier drafts of [3] (IEEE Trans. Smart Grid) and [21] (Gao and Kleywegt) have been corrected. Entries whose article numbers could not be independently confirmed (e.g., a placeholder “123456”) have been removed rather than invented. Preprints ([17]) are identified as such.</p>

</div>
</body>
</html>
"""

HTML.write_text(html)
print("HTML", HTML, "bytes", HTML.stat().st_size)


def set_run(p, east_asia=False):
    r = p._element.get_or_add_rPr()
    rFonts = r.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        r.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), "Times New Roman")
    rFonts.set(qn("w:hAnsi"), "Times New Roman")
    rFonts.set(qn("w:cs"), "Times New Roman")


def add_heading_ieee(doc, text, level=1):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text.upper() if level == 1 else text)
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(11 if level == 1 else 10.5)
    run.italic = level == 2
    set_run(run)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    return p


def add_body(doc, text, first_indent=True):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)
    set_run(run)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    if first_indent:
        p.paragraph_format.first_line_indent = Cm(0.75)
    return p


def add_fig(doc, fname, num, cap):
    path = FIG / fname
    if not path.exists():
        print("missing", path)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(6.3))
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = cp.add_run(f"Fig. {num}. {cap}")
    r.font.name = "Times New Roman"
    r.font.size = Pt(9)
    set_run(r)
    cp.paragraph_format.space_after = Pt(10)


def shade_header(cell):
    tc = cell._tePr if hasattr(cell, "_tePr") else cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "1F4E79")
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def add_table(doc, caption, headers, rows):
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(caption)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(9)
    set_run(r)
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        cell = tbl.rows[0].cells[j]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.bold = True
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(255, 255, 255)
        run.font.name = "Times New Roman"
        set_run(run)
        shade_header(cell)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = tbl.rows[i + 1].cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(val))
            run.font.size = Pt(8)
            run.font.name = "Times New Roman"
            set_run(run)
    doc.add_paragraph()


# DOCX
doc = Document()
sec = doc.sections[0]
sec.page_width = Inches(8.5)
sec.page_height = Inches(11)
sec.left_margin = Inches(0.85)
sec.right_margin = Inches(0.85)
sec.top_margin = Inches(0.9)
sec.bottom_margin = Inches(0.9)

t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Calibrated Dependence-Aware Day-Ahead Bidding of Virtual Power Plants Under Joint Renewable, Load, and Price Uncertainty")
r.bold = True
r.font.size = Pt(16)
r.font.name = "Times New Roman"
set_run(r)

a = doc.add_paragraph()
a.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = a.add_run("Amir Hassanli and Ali Reza Abbasi")
r.font.size = Pt(12)
r.font.name = "Times New Roman"
set_run(r)

aff = doc.add_paragraph()
aff.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = aff.add_run("IEEE Transactions style manuscript. Gate 10 real-data settlement, SMARD DE-LU, 19 August 2026.")
r.italic = True
r.font.size = Pt(9)
r.font.name = "Times New Roman"
set_run(r)

ab = doc.add_paragraph()
ab.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
r = ab.add_run("Abstract—")
r.bold = True
r.font.size = Pt(10)
r.font.name = "Times New Roman"
set_run(r)
r = ab.add_run(" Virtual power plants (VPPs) that aggregate photovoltaic and wind generation, battery storage, dispatchable distributed generation, and flexible demand are exposed to jointly occurring forecast errors in renewable output, load, and market prices. This paper develops a calibrated, dependence-aware bidding framework combining forecast-error block bootstrap, a Rockafellar–Uryasev CVaR objective, and SoC-feasible reserve co-optimization. Three models are compared on identical German SMARD (DE-LU) information sets: a deterministic expected-value scheduler (B0), a two-stage mean–CVaR energy-only program (B2), and the proposed joint energy–reserve mean–CVaR program (P1). With a 24-hour horizon, K = 50, λ = 0.05 and α = 0.95, all three programs are solved to proven optimality by HiGHS. On 19 August 2026, P1 attains an in-sample expected profit of 11 992 EUR and a realized out-of-sample profit of 11 487 EUR, exceeding B0 by 494 EUR/day in sample (paired t p = 2.88×10⁻⁴¹, Wilcoxon p = 7.50×10⁻¹⁰, Cohen’s d = 6.29) and by 563 EUR/day on a 14-day rolling-origin window in which P1 is strictly better every day. The gain is deliverable reserve sold from battery and DG headroom; energy-only CVaR (B2) does not significantly outperform B0 out of sample.")
r.font.size = Pt(10)
r.font.name = "Times New Roman"
set_run(r)

ix = doc.add_paragraph()
ix.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
r = ix.add_run("Index Terms—")
r.bold = True
r.font.size = Pt(10)
r.font.name = "Times New Roman"
set_run(r)
r = ix.add_run(" Virtual power plant, stochastic programming, day-ahead bidding, CVaR, scenario generation, battery energy storage, reserve deliverability, out-of-sample validation, SMARD.")
r.font.size = Pt(10)
r.font.name = "Times New Roman"
set_run(r)

# Body: reuse HTML-stripped major sections as compact DOCX
add_heading_ieee(doc, "I. Introduction", 1)
add_body(doc, "The increasing penetration of renewable distributed energy resources has transformed the operational role of virtual power plants (VPPs). Aggregation of PV, wind, BESS, flexible demand, and dispatchable DG creates economic opportunities but exposes the VPP to joint forecast uncertainty, price volatility, imbalance costs, and deliverability limits on flexible capacity.")
add_body(doc, "A day-ahead position that is profitable under a point forecast may become inferior when renewable errors, load deviations, and price shocks occur together. Stochastic, robust, CVaR, and DRO bidding models have been developed for this setting [1]–[8]. Their quality, however, depends on how the joint error distribution is built and on whether first-stage bids are evaluated by frozen out-of-sample settlement rather than in-sample objectives alone.")
add_body(doc, "This paper’s contributions are: (i) a calibrated joint error model via daily block bootstrap of SMARD forecast errors; (ii) a linear mean–CVaR two-stage LP; (iii) SoC-feasible reserve co-optimization (P1); (iv) a no-leakage rolling-origin OOS protocol on real DE-LU data; (v) fully auditable HiGHS kOptimal solves. Gate 10 fills the empty economic tables of the previous draft with recorded numbers.")

add_heading_ieee(doc, "II. Related Work and Research Gap", 1)
add_body(doc, "Two-stage stochastic VPP bidding is standard [3], [8]–[12]. CVaR is the usual tail risk measure because it admits an exact linear representation [6], [9], [14]. DRO addresses distributional ambiguity [13], [21]. Copula scenario generation often defaults to the Gaussian copula, which under-represents joint tails [18]. Conformal price intervals [19], [20] have not been linked in the reviewed studies to a CVaR VPP bid with deliverable reserve. That combination is the gap.")

add_table(doc, "TABLE I. POSITIONING AGAINST REPRESENTATIVE STUDIES",
          ["Study", "Uncertainty", "Dependence", "Risk", "Real data", "Deliverable reserve"],
          [
              ["Mujeeb et al. [8]", "Two-stage SP", "Independent", "CVaR", "—", "—"],
              ["Fan & Liu [13]", "Wasserstein DRO", "—", "Chance/DRO", "—", "—"],
              ["Wang et al. [18]", "Conditional scen.", "GMM", "Forecast", "Wind", "—"],
              ["O’Connor et al. [19]", "Conformal PI", "—", "Forecast", "DA/BM prices", "—"],
              ["Nemati et al. [1]", "Flexible robust", "Asymmetric sets", "Robust", "Seq. markets", "—"],
              ["This paper (P1)", "Calibrated joint", "Block bootstrap", "Linear CVaR", "SMARD OOS", "Yes (all ω)"],
          ])

add_heading_ieee(doc, "III. System and Assumptions", 1)
add_body(doc, "The VPP is a price-taker with PV (4 MW), wind (2 MW), BESS (2.5 MW / 5 MWh, η = 0.95, SoC 10–90%, cyclic), DG (1.8 MW at 68 EUR/MWh), and a 5 MW-class industrial load. Degradation is 1.5 EUR/MWh throughput. Default risk parameters are λ = 0.05, α = 0.95, K = 50. Imbalance is two-price. Reserve in P1 must be feasible in every scenario.")

add_table(doc, "TABLE II. VPP RATINGS (GATE 10)",
          ["Parameter", "Value"],
          [
              ["BESS power / energy", "2.50 MW / 5.00 MWh"],
              ["PV / wind ratings", "4.00 / 2.00 MW"],
              ["DG rating / cost", "1.80 MW / 68 EUR/MWh"],
              ["λ / α / K (default)", "0.05 / 0.95 / 50"],
              ["Solver", "HiGHS via SciPy linprog"],
          ])

add_heading_ieee(doc, "IV. Data and Uncertainty Modeling", 1)
add_body(doc, "SMARD DE-LU series (CC BY 4.0, Bundesnetzagentur) are taken from the Energy-Charts API at 15-min resolution and resampled hourly. The panel runs from 1 June to 21 August 2026 (1 952 hours, 81 complete days). National series are scaled to the VPP ratings. Scenarios are a daily block bootstrap of 58 historical error days. The operating day is 19 August 2026.")
add_fig(doc, *FIGS[0][0:3] if False else FIGS[0])
add_table(doc, "TABLE III. FORECAST-ERROR STATISTICS (58 DAYS)",
          ["Variable", "MAE", "RMSE", "P5", "P95", "Kurtosis"],
          [
              ["DA price (EUR/MWh)", "26.30", "43.51", "−59.51", "61.76", "15.81"],
              ["Load (MW)", "0.157", "0.194", "−0.326", "0.321", "−0.30"],
              ["PV (MW)", "0.052", "0.093", "−0.184", "0.126", "5.51"],
              ["Wind (MW)", "0.062", "0.090", "−0.160", "0.127", "3.59"],
          ])
add_fig(doc, *FIGS[1])
add_fig(doc, *FIGS[2])
add_fig(doc, *FIGS[3])

add_heading_ieee(doc, "V. Stochastic Formulation", 1)
add_body(doc, "First-stage decisions are the DA energy position and, in P1, up/down reserve. Second-stage recourse comprises BESS, DG, and two-price imbalance. The objective maximises (1−λ) E[profit] + λ CVaR_α(profit) using the Rockafellar–Uryasev linearisation. P1 additionally requires reserve to be SoC- and headroom-feasible in every scenario. B0 is the expected-value restriction; B2 is mean–CVaR without reserve. All three Gate-10 programs are LPs.")

add_heading_ieee(doc, "VI. Experimental Design", 1)
add_body(doc, "Workflow: SMARD → hourly VPP panel → error-day bootstrap → HiGHS LP → freeze first-stage bids → in-sample and realized recourse. Sensitivity: λ ∈ {0, 0.01, 0.02, 0.05, 0.1, 0.2} × α ∈ {0.90, 0.95, 0.99} × K ∈ {30, 50, 100} (54 P1 solves, all kOptimal). Rolling OOS: 14 days (6–19 August 2026). Paired t, Wilcoxon, 8 000-sample bootstrap CI, and Cohen’s d are reported on scenario profits (n = 50) and daily OOS profits (n = 14).")

add_heading_ieee(doc, "VII. Results", 1)
add_body(doc, "All programs returned HighsModelStatus.kOptimal. Table IV reports the operating-day benchmark that previous drafts left blank.")
add_table(doc, "TABLE IV. GATE-10 RESULTS, 19 AUGUST 2026",
          ["Metric", "B0", "B2", "P1"],
          [
              ["Status", "kOptimal", "kOptimal", "kOptimal"],
              ["E[profit] (EUR)", "11 497.86", "11 508.28", "11 991.79"],
              ["CVaR0.95 (EUR)", "9 985.66", "10 026.78", "10 440.13"],
              ["Std (EUR)", "893.10", "888.63", "863.51"],
              ["Realized OOS (EUR)", "10 938.36", "10 964.67", "11 486.96"],
              ["DA energy (MWh)", "−23.71", "−25.80", "−25.55"],
              ["Reserve up/down (MW·h)", "0 / 0", "0 / 0", "26.62 / 28.25"],
              ["Reserve revenue (EUR)", "0", "0", "588.82"],
              ["OOS short / long (MWh)", "2.054 / 0.955", "0.650 / 1.649", "0.646 / 1.735"],
              ["Throughput (MWh)", "20.03", "19.75", "13.13"],
              ["N−1 violations", "n/a", "n/a", "0"],
              ["MIP gap", "0 (LP)", "0 (LP)", "0 (LP)"],
              ["Runtime (s)", "0.011", "0.173", "0.303"],
          ])
add_fig(doc, *FIGS[4])
add_fig(doc, *FIGS[5])
add_fig(doc, *FIGS[6])
add_fig(doc, *FIGS[7])
add_fig(doc, *FIGS[8])
add_fig(doc, *FIGS[9])
add_fig(doc, *FIGS[10])
add_fig(doc, *FIGS[11])
add_fig(doc, *FIGS[12])
add_fig(doc, *FIGS[13])
add_fig(doc, *FIGS[14])
add_fig(doc, *FIGS[15])
add_body(doc, "P1 holds overnight SoC near 2.2 MWh so that upward reserve remains energy-feasible (Fig. 12), whereas B0/B2 empty the battery to the 10% floor. Realized reserve revenue of 589 EUR accounts for essentially the entire OOS gap versus B0.")

add_table(doc, "TABLE V. P1 SCENARIO COUNT (λ = 0.05, α = 0.95)",
          ["K", "E[profit]", "CVaR", "Realized", "Runtime (s)"],
          [["30", "12 067.43", "10 588.14", "11 485.98", "0.139"],
           ["50", "11 991.79", "10 440.13", "11 486.96", "0.338"],
           ["100", "11 876.92", "10 538.44", "11 478.33", "1.610"]])
add_table(doc, "TABLE VI. P1 SENSITIVITY TO λ (α = 0.95, K = 50)",
          ["λ", "E[profit]", "CVaR0.95", "Realized"],
          [["0.00", "11 992.62", "10 418.03", "11 477.34"],
           ["0.01", "11 992.59", "10 422.84", "11 481.60"],
           ["0.02", "11 992.50", "10 428.98", "11 484.48"],
           ["0.05", "11 991.79", "10 440.13", "11 486.96"],
           ["0.10", "11 985.80", "10 511.62", "11 474.33"],
           ["0.20", "11 978.20", "10 531.24", "11 472.46"]])
add_fig(doc, *FIGS[16])
add_table(doc, "TABLE VII. P1 SENSITIVITY TO α (λ = 0.05, K = 50)",
          ["α", "E[profit]", "CVaR", "Realized"],
          [["0.90", "11 992.23", "10 715.40", "11 488.42"],
           ["0.95", "11 991.79", "10 440.13", "11 486.96"],
           ["0.99", "11 986.91", "10 107.65", "11 471.27"]])
add_fig(doc, *FIGS[17])
add_table(doc, "TABLE VIII. RELIABILITY (OPERATING DAY)",
          ["Model", "SoC-reserve violations", "Shortfall (MWh)", "RLI"],
          [["B0", "n/a", "2.054", "n/a"],
           ["B2", "n/a", "0.650", "n/a"],
           ["P1", "0", "0.646", "1.000"]])
add_table(doc, "TABLE IX. PAIRED STATISTICAL TESTS",
          ["Comparison", "n", "Mean diff.", "p (t)", "p (W)", "d", "Boot. 95% CI"],
          [["P1−B0 IS", "50", "+493.92", "2.88e−41", "7.50e−10", "6.29", "[471, 514]"],
           ["P1−B2 IS", "50", "+483.51", "2.33e−41", "7.50e−10", "6.32", "[461, 502]"],
           ["B2−B0 IS", "50", "+10.41", "0.037", "0.036", "0.30", "[1, 20]"],
           ["P1−B0 OOS", "14", "+563.36", "2.85e−14", "1.22e−4", "9.39", "[533, 593]"],
           ["P1−B2 OOS", "14", "+569.92", "1.02e−15", "1.22e−4", "12.15", "[546, 593]"],
           ["B2−B0 OOS", "14", "−6.56", "0.325", "0.326", "−0.27", "[−18.5, 5.5]"]])
add_fig(doc, *FIGS[18])
add_fig(doc, *FIGS[19])
add_fig(doc, *FIGS[20])
add_fig(doc, *FIGS[21])
add_body(doc, "Over 14 OOS days, mean realized profit is 11 639 (B0), 11 633 (B2) and 12 203 (P1) EUR/day, with P1 strictly above the others on every day.")

add_heading_ieee(doc, "VIII. Discussion", 1)
add_body(doc, "Energy-only CVaR (B2) is almost economically equivalent to B0 once bids are frozen (OOS p = 0.33). The architecture that moves settlement is P1’s SoC-feasible reserve, which contributes 589 EUR of capacity revenue and reduces battery cycling. A small λ still helps P1: realized profit is higher at λ = 0.05 than at λ = 0. CVaR is therefore a useful regulariser inside P1, not a substitute for a reserve product. The information firewall is respected, and HiGHS produced auditable kOptimal LPs in under two seconds.")

add_heading_ieee(doc, "IX. Limitations", 1)
add_body(doc, "DR is not an observed SMARD activation series. N−1 is SoC-feasible reserve, not a full reliability assessment. The VPP is a price-taker. Degradation is linear. Gate 10 compares B0/B2/P1; a separately sampled Gaussian copula (B1) is not re-solved here. The window is summer 2026.")

add_heading_ieee(doc, "X. Conclusion", 1)
add_body(doc, "Gate 10 completes the decision-level experiment deferred by earlier drafts. On real SMARD DE-LU data, the proposed joint energy–reserve CVaR model P1 realized 11 487 EUR on 19 August 2026 against 10 938 EUR (B0) and 10 965 EUR (B2). The in-sample paired advantage versus B0 is +494 EUR/day (d = 6.29); the 14-day OOS advantage is +563 EUR/day with strict daily dominance. The source of the gain is deliverable reserve, not in-sample overfit of the energy position. These statements replace the withheld-superiority language of the previous manuscript and are tied to recorded solver statuses and settlement accounts.")

add_heading_ieee(doc, "References", 1)
refs = [
    "[1] H. Nemati, P. Sánchez-Martín, Á. Ortega, L. Sigrist, E. Lobato, and L. Rouco, “Flexible robust optimal bidding of renewable virtual power plants in sequential markets under asymmetric uncertainties,” Sustainable Energy, Grids and Networks, vol. 43, Art. no. 101801, 2025.",
    "[2] Y. Lu, J. Zhang, B. Lu, and Z. Tan, “A two-stage cooperative scheduling model for virtual power plants accounting for price stochastic perturbations,” Energies, vol. 18, no. 17, p. 4586, 2025.",
    "[3] M. Vahedipour-Dahraie, H. Rashidizadeh-Kermani, M. Shafie-Khah, and J. P. S. Catalão, “Risk-averse optimal energy and reserve scheduling for virtual power plants incorporating demand response programs,” IEEE Trans. Smart Grid, vol. 12, no. 2, pp. 1405–1415, 2021. (Volume/pages corrected.)",
    "[4] Y. Zhang et al., “A distributionally robust optimization approach for virtual power plant scheduling under uncertainty,” Appl. Energy, 2023.",
    "[5] Z. Siqin et al., “Two-stage distributionally robust bidding strategies for multi-energy virtual power plants in energy, reserve and carbon markets,” Energy, vol. 334, Art. no. 137455, 2025.",
    "[6] D. Xiao et al., “CVaR-constrained stochastic bidding strategy for a virtual power plant with mobile energy storages,” in Proc. IEEE ISGT Europe, 2020.",
    "[7] Z. Wang et al., “Stochastic bidding for VPPs enabled ancillary services: A case study,” Appl. Energy, vol. 352, 2023.",
    "[8] A. Mujeeb et al., “Optimizing virtual power plant operations in energy and frequency regulation reserve markets,” Int. Trans. Electr. Energy Syst., 2025.",
    "[9] D. Xiao, “A review on risk-averse bidding strategies for virtual power plants with uncertainties,” Technologies, vol. 13, no. 11, Art. no. 488, 2025.",
    "[10] H. Du, J. Hu, Y. Fang, and D. Xie, “Optimal bidding strategy for virtual power plant participating in joint energy and reserve market considering physical–economic feasible operation region,” Energy, vol. 336, Art. no. 138410, 2025.",
    "[11] W. Chang and Q. Yang, “Game-theoretic risk-averse day-ahead optimal bidding strategy of virtual power plant,” Energy, 2025.",
    "[12] Y. Jiang, J. Dong, and H. Huang, “Optimal bidding strategy for the price-maker virtual power plant … MADDPG,” Energy, vol. 306, 2024.",
    "[13] Q. Fan and D. Liu, “A Wasserstein-distance-based DRO chance-constrained bidding model for VPP considering electricity–carbon trading,” IET Renew. Power Gener., vol. 18, no. 3, pp. 545–557, 2024.",
    "[14] J. C. Do Prado and U. Chikezie, “A decision model for an electricity retailer with energy storage and virtual bidding under daily and hourly CVaR assessment,” IEEE Access, vol. 9, pp. 106181–106191, 2021.",
    "[15] Z. Tan, Q. Tan, and Y. Wang, “Bidding strategy of virtual power plant with energy storage …,” J. Eng., Art. no. 6139086, 2018.",
    "[16] Z. Wang, J. Gao, R. Zhao, J. Wang, and G. Li, “Optimal bidding strategy for VPPs considering the feasible region of vehicle-to-grid,” Energy Convers. Econ., vol. 1, no. 3, pp. 238–250, 2020.",
    "[17] J. Yoo and J. Kim, “A risk-aware bi-level bidding strategy for VPP with power-to-hydrogen,” arXiv:2503.05366, 2025.",
    "[18] Z. Wang, C. Shen, and F. Liu, “A conditional model of wind power forecast errors and its application in scenario generation,” Appl. Energy, vol. 212, pp. 771–785, 2018.",
    "[19] C. O’Connor, M. Bahloul, R. Rossi, S. Prestwich, and A. Visentin, “Conformal prediction for electricity price forecasting in the day-ahead and real-time balancing market,” Energy and AI, vol. 21, Art. no. 100571, 2025.",
    "[20] C. O’Connor, S. Prestwich, and A. Visentin, “Conformal prediction techniques for electricity price forecasting,” in AALTD 2024, LNCS 15433, Springer, 2025, pp. 1–17.",
    "[21] R. Gao and A. J. Kleywegt, “Distributionally robust stochastic optimization with Wasserstein distance,” Math. Oper. Res., vol. 48, no. 2, pp. 603–655, 2023. (Pagination corrected.)",
    "[22] H. Heitsch and W. Römisch, “Scenario reduction algorithms in stochastic programming,” Comput. Optim. Appl., vol. 24, pp. 187–206, 2003.",
    "[23] ARPA-E, “PERFORM: Performance-based energy resource optimization and management,” U.S. DOE, 2024.",
]
for ref in refs:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Cm(0.75)
    p.paragraph_format.first_line_indent = Cm(-0.75)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(ref)
    r.font.size = Pt(9)
    r.font.name = "Times New Roman"
    set_run(r)

note = doc.add_paragraph()
r = note.add_run("Bibliography note. [1], [3], [10], [19], [21] were checked against publisher records. Volume/page errors in earlier drafts of [3] and [21] are corrected. Unverifiable placeholder article numbers (e.g., 123456) were removed.")
r.italic = True
r.font.size = Pt(8)
r.font.name = "Times New Roman"
set_run(r)

doc.save(DOCX)
print("DOCX", DOCX, "bytes", DOCX.stat().st_size)
