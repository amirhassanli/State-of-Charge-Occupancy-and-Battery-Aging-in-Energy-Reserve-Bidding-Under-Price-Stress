**State-of-Charge Occupancy and Battery Aging in Energy–Reserve Bidding Under Price Stress: A Diagnostic Using Public German System Data**

**Amir Hassanli**

Abstract—This paper asks whether adding state-of-charge (SoC) occupancy aging changes joint day-ahead energy/aFRR bidding by a 2.5-MW/5-MWh battery. We examine 262 days of public German DE-LU data. The available reconstruction does not reproduce the reported 1 May 2026 bid reversal: the P1−B2 wholesale differential remains negative for throughput, daily-depth, and ReLCCA aging in the exclusive MILP at K = 30, 50, 100, and 200. This is a failure of the available reconstruction to reproduce the reported result, not a test of the original implementation. A separate E4 crossed sensitivity on 1 May (relaxed LP, K = 30) yields gaps of −1,928/−1,964/−1,944 EUR/day under proxy optimization and observed reBAP settlement (throughput/Xu/ReLCCA). If the optimizer is instead given that day’s realized reBAP, the reBAP-settled gaps are +848/+839/+845 EUR/day. This is a perfect-foresight, LEAKY case; it is not ex-ante performance or a pure settlement-only comparison. Equal-cost calibration places the structural aging-law spread at about 11 EUR/day, while reserve-sustainment assumptions can change the gap’s sign. With no cell telemetry or temperature histories, block-average reserve prices, and a baseline imbalance proxy, the findings are diagnostic and conditional on reconstruction assumptions.

Index Terms—battery energy storage, battery degradation, calendar aging, CVaR, energy–reserve bidding, linear programming, SMARD, virtual power plant.

**I. INTRODUCTION**

Virtual power plants (VPPs) aggregate distributed energy resources and expose a heterogeneous portfolio to electricity markets through coordinated scheduling \[1\]–\[4\]. Their short-term value depends on the interaction between uncertain renewable production, load, market prices, storage flexibility, and ancillary-service commitments. This has motivated stochastic, robust, and risk-aware bidding models for VPPs and storage resources \[5\]–\[8\].

For BESSs, however, the economic value of flexibility is inseparable from degradation. Battery aging is commonly separated into cycle aging and calendar aging. Experimental and semi-empirical studies have shown that degradation depends on operating depth, state of charge, temperature, time, and electrochemical conditions \[9\]–\[14\]. Market-oriented optimization has consequently adopted throughput costs, cycle-depth functions, and more detailed aging representations to maintain computational tractability \[15\]–\[20\].

A specific modeling issue arises when the same BESS is used for energy arbitrage and reserve capacity. An upward reserve commitment requires sufficient energy to remain available for deployment. Thus, some stored energy is deliberately parked rather than cycled. If calendar aging depends on SoC, the economic exposure of this parked energy is not represented by a pure throughput penalty. The resulting effect is potentially indirect: a small change in the degradation term can alter the marginal value of stored energy and, through the optimization constraints, change the preferred market position.

The objective is not to claim that calendar-aware degradation is universally superior to cycle-centric formulations. Instead, the paper asks a narrower question: under what price and residual-portfolio conditions does explicit pricing of SoC occupancy change an optimized mean–CVaR energy–reserve position? The question is examined through paired comparisons in which the plant, scenario inputs, market assumptions, risk parameters, and solver are held fixed while the aging representation is changed. The analysis is a model diagnostic, not a population-wide test or validation of a cell-aging law.

The contributions are fourfold. First, a documented reconstruction fails to reproduce a reported 1 May reversal, with sign stability across K = 30–200 and an LP/MILP charge/discharge-overlap diagnostic (11.99 → 10⁻¹⁴ MWh). Second, equal-cost calibration separates the small structural aging-law effect from larger scenario and reserve-duration sensitivities. Third, a 3×3 position-valuation matrix separates changes in the optimized position from changes in its valuation. Fourth, the E4 crossed optimization-input/settlement comparison makes the information set explicit and labels use of realized reBAP in optimization as LEAKY. These are reconstruction diagnostics; they neither reproduce the original implementation nor establish universal superiority of an aging law.

**II. RELATED WORK AND RESEARCH GAP**

The literature relevant to this study can be organized into four strands: VPP market participation, uncertainty and risk, battery degradation, and energy–reserve co-optimization. Foundational VPP studies established aggregation and coordinated market participation as an operational paradigm \[1\]–\[4\]. Stochastic and robust formulations subsequently addressed uncertainty in renewable production and prices, including price-taker and adaptive-robust offering models \[5\]–\[7\]. Risk-averse energy and reserve scheduling has also been studied explicitly for VPPs \[8\].

A second strand concerns battery aging. Foundational reviews and experiments distinguish calendar and cycle mechanisms and document the dependence of calendar aging on SoC \[9\]–\[14\]. Optimization studies translate these relationships into computational models. Hesse et al. use mixed-integer linear optimization for aging- and efficiency-aware arbitrage \[15\]. Xu et al. develop market-oriented cycle-aging cost formulations \[16\], \[17\]; this study adopts only a daily-range depth cost in the style of \[16\], without rainflow counting, while Shi et al. analyze cycle-aging mechanisms in pay-for-performance operation \[18\]. More recent work considers convex-hull and electro-thermal representations to balance aging fidelity and optimization complexity \[19\], \[20\].

A third strand concerns reserve participation. Storage has been co-optimized across energy and reserve products, including formulations with probabilistic delivery guarantees and German secondary-control-reserve applications \[21\]–\[24\]. These studies establish that reserve commitments impose operational and opportunity-cost constraints. Related wind–battery VPP models incorporate degradation and reserve scheduling jointly \[24\], \[25\].

A fourth strand is risk-aware bidding. CVaR provides a tractable representation of lower-tail risk \[26\]–\[28\] and has been applied to VPP, PV-storage, and energy–frequency-regulation bidding \[8\], \[29\]–\[31\]. Distributionally robust VPP models further extend the treatment of uncertainty \[32\].

The gap addressed here is narrower than any of these individual topics. The paper does not claim novelty in degradation, CVaR, stochastic bidding, or reserve participation separately. Rather, it isolates the incremental effect of making SoC occupancy economically visible while retaining cycle-related costs, upward-reserve parking, and a common mean–CVaR market model. The empirical component is framed as a diagnostic because reserve-capacity and imbalance series in the study package are proxies rather than day-specific German settlement records.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE I. Comparison of representative studies and positioning of the present work Qualitative comparison; no quantitative SoC-occupancy isolation claim is made for any cited study, and the table is not referenced in the numerical sections.</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 19%" />
<col style="width: 19%" />
<col style="width: 20%" />
<col style="width: 19%" />
<col style="width: 20%" />
</colgroup>
<thead>
<tr>
<th><strong>Study</strong></th>
<th><strong>Aging</strong></th>
<th><strong>Risk / uncertainty</strong></th>
<th><strong>Energy–reserve</strong></th>
<th><strong>Relevance</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th>Hesse et al. [15]</th>
<td>Aging + efficiency</td>
<td>Deterministic</td>
<td>Energy arbitrage</td>
<td>Optimization-aware degradation</td>
</tr>
<tr>
<th>Xu et al. [16], [17]</th>
<td>Cycle depth</td>
<td>Market uncertainty</td>
<td>Energy / reserve</td>
<td>Market-oriented cycle cost</td>
</tr>
<tr>
<th>Shi et al. [18]</th>
<td>Cycle aging</td>
<td>Operational uncertainty</td>
<td>Regulation</td>
<td>Cycle-aging control</td>
</tr>
<tr>
<th>Toubeau et al. [21]</th>
<td>—</td>
<td>Probabilistic</td>
<td>Energy / reserve</td>
<td>Reserve delivery</td>
</tr>
<tr>
<th>Merten et al. [22], [23]</th>
<td>Battery-aware</td>
<td>Market forecasting</td>
<td>aFRR</td>
<td>German reserve participation</td>
</tr>
<tr>
<th>Fernández-Muñoz and Pérez-Díaz [24]</th>
<td>DoD / rate</td>
<td>Stochastic</td>
<td>DA + secondary reserve</td>
<td>Wind–battery VPP</td>
</tr>
<tr>
<th>Ghanaee et al. [25]</th>
<td>Calendar + cycle</td>
<td>Deterministic</td>
<td>DA + reserve</td>
<td>Recent degradation benchmark</td>
</tr>
<tr>
<th>Wang et al. [30]</th>
<td>Operational constraints</td>
<td>CVaR</td>
<td>Energy + regulation</td>
<td>Risk-aware benchmark</td>
</tr>
<tr>
<th>This work</th>
<td>Occupancy + cycle</td>
<td>Mean–CVaR</td>
<td>DA + aFRR capacity</td>
<td>Controlled diagnosis of bid changes</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

Among the studies summarized in Table I, \[25\] combines calendar and cycle aging with day-ahead energy–reserve scheduling, but uses deterministic inputs. The present comparison examines the additional effect of SoC-dependent aging in a mean–CVaR bid. This positioning is limited to the studies reviewed here and should not be read as an exhaustive claim about the entire literature.

**III. SYSTEM, DATA, AND INFORMATION STRUCTURE**

A. VPP configuration

The VPP is modeled as a price-taking portfolio in the German DE-LU bidding area. It contains a 5 MW-class industrial load, 4 MW photovoltaic generation, 2 MW wind generation, a 2.5 MW/5 MWh stationary BESS, and a 1.8 MW dispatchable generator. The BESS has 0.95 charging and discharging efficiencies and operates within a 10–90% SoC range. A cyclic daily boundary condition is imposed. The generator has a marginal operating cost of 68 EUR/MWh and a 1.2 MW/h ramp limit. The default aggregate reserve cap is 1.5 MW. These values are fixed study parameters and are not fitted to the reported outcomes.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE II. VPP, battery, market, and risk parameters used in the numerical study</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 33%" />
<col style="width: 33%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Parameter</strong></th>
<th style="text-align: center;"><strong>Value</strong></th>
<th style="text-align: center;"><strong>Role</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th style="text-align: center;">BESS power / energy</th>
<td style="text-align: center;">2.50 MW / 5.00 MWh</td>
<td style="text-align: center;">Study plant</td>
</tr>
<tr>
<th style="text-align: center;">PV / wind / load class</th>
<td style="text-align: center;">4 / 2 / 5 MW</td>
<td style="text-align: center;">Study plant</td>
</tr>
<tr>
<th style="text-align: center;">ηc / ηd</th>
<td style="text-align: center;">0.95 / 0.95</td>
<td style="text-align: center;">Efficiency</td>
</tr>
<tr>
<th style="text-align: center;">SoC range</th>
<td style="text-align: center;">10–90%</td>
<td style="text-align: center;">Operational constraint</td>
</tr>
<tr>
<th style="text-align: center;">DG capacity / cost</th>
<td style="text-align: center;">1.8 MW / 68 EUR/MWh</td>
<td style="text-align: center;">Dispatchable resource</td>
</tr>
<tr>
<th style="text-align: center;">DG ramp</th>
<td style="text-align: center;">1.2 MW/h</td>
<td style="text-align: center;">Operational constraint</td>
</tr>
<tr>
<th style="text-align: center;">Reserve cap</th>
<td style="text-align: center;">1.5 MW</td>
<td style="text-align: center;">Default sensitivity parameter</td>
</tr>
<tr>
<th style="text-align: center;">CVaR confidence α</th>
<td style="text-align: center;">0.95</td>
<td style="text-align: center;">Tail confidence</td>
</tr>
<tr>
<th style="text-align: center;">CVaR weight β</th>
<td style="text-align: center;">0.05</td>
<td style="text-align: center;">Risk weight</td>
</tr>
<tr>
<th style="text-align: center;">SoC bands N</th>
<td style="text-align: center;">8</td>
<td style="text-align: center;">Default ReLCCA resolution</td>
</tr>
<tr>
<th style="text-align: center;">Solver</th>
<td style="text-align: center;">HiGHS</td>
<td style="text-align: center;">Open-source LP solver</td>
</tr>
<tr>
<th style="text-align: center;">Random seed</th>
<td style="text-align: center;">20260821</td>
<td style="text-align: center;">Reproducibility</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

Table II lists the parameters specified for the reported study. The manuscript does not state the reserve-sustainment duration τ, initial SoC, or band-specific cycle coefficients γ used by the available reconstruction; those defaults are not treated as original study values.

B. Data and scaling

The panel covers 1 December 2025 00:00 through 21 August 2026 07:00 Berlin time. It contains 6,319 hourly rows across 264 calendar dates: 262 complete days, the 23-hour daylight-saving day on 29 March, and the first 8 hours of 21 August. Day-ahead prices for DE-LU are sourced through the Energy-Charts API from Bundesnetzagentur \| SMARD.de; German load, solar, and wind series are from Fraunhofer ISE Energy-Charts \[33\], \[34\]. The API's 15-minute observations are averaged to local-time hourly values. Load is scaled so its study-period 95th percentile maps to 5 MW; the study-window solar maximum maps to 4 MW, and the combined onshore/offshore wind maximum maps to 2 MW. Price forecasts use the mean of 48- and 168-hour lags; load, PV, and wind use 48-hour persistence. Daily forecast-error vectors are block-bootstrapped from complete days no later than D−2, with uniform scenario weights. Raw responses, the processed panel, retrieval timestamp, licenses, URLs, scaling factors, and SHA-256 hashes are archived with the data package. These are national system series, not battery telemetry.

The information structure separates first-stage market commitments from scenario-dependent operating recourse. Day-ahead energy and reserve positions are common across scenarios, whereas charging, discharging, generator output, imbalance, and band-level operating variables respond to each scenario. Scenario probabilities are uniform within the daily scenario set.

C. Reserve and imbalance representation

The reserve-capacity inputs are six positive- and negative-direction German aFRR four-hour block means reported by Modo Energy and Pexapark \[35\], \[36\]: positive values are 4.5, 12.0, 47.1, 18.4, 35.6, and 8.0 EUR/MW/h; negative values are 6.0, 15.0, 36.9, 57.4, 20.0, and 2.4 EUR/MW/h. They are held fixed across operating days and serve as capacity-price proxies, not daily auction results.

The imbalance component is represented by a documented two-price proxy based on the day-ahead price. For a short deviation, the settlement proxy is λDA + 18 + 0.12\|λDA\|; for a long deviation it is λDA − 10 − 0.08\|λDA\|, subject to minimum/maximum spreads of +5 and −3 EUR/MWh, respectively. A 150 EUR/MWh clipping case is evaluated only as a robustness test. Because directly mounted day-specific reBAP data were not available in the study package, the reported wholesale results are **simulated profits under these settlement assumptions**, not realized German settlement profits.

**IV. MATHEMATICAL FORMULATION**

A. Common market model

All three aging laws are embedded in the same daily optimization problem. Let t denote hour, ω scenario, and ℓ SoC band. The first-stage variables are the day-ahead energy position p_t^DA and reserve commitments r_t↑ and r_t↓. Recourse variables include battery charging p_tω^ch, discharging p_tω^dis, stored energy E_tω, generator output g_tω, net imbalance z_tω, and ReLCCA band variables.

The physical balance for each hour and scenario is written as

| 
``` math
- P_{t}^{DA} + z_{t,\omega} + P_{t,\omega}^{dis} - P_{t,\omega}^{ch} + g_{t,\omega} + W_{t,\omega} + {PV}_{t,\omega} = L_{t,\omega}
``` | \(1\) |
|----|----|

A positive p_t^DA denotes a day-ahead sale, and a positive z_t,ω denotes energy purchased in the imbalance market. The balance therefore subtracts the day-ahead sale and adds the imbalance purchase. At a negative price, a positive purchase is a long position. The implementation uses separate nonnegative short and long imbalance variables; z represents their signed net position. Renewable and generator limits are linear, and generator ramping is represented by intertemporal inequalities.$`P_{t}^{DA}`$$`z_{t,\omega}`$

B. Battery dynamics and reserve feasibility

| 
``` math
E_{t,\omega} = E_{t - 1,\omega} + \eta_{c}P_{t,\omega}^{ch}\Delta t - \frac{P_{t,\omega}^{dis}}{\eta_{d}}\Delta t
``` | \(2\) |
|----|----|
| 
``` math
E_{\min}\  \leq \ E_{t,\omega}\  \leq \ E_{\max},\ 0\  \leq \ P_{t,\omega}^{ch}\  \leq \ P_{B},\ 0\  \leq \ P_{t,\omega}^{dis}\  \leq \ P_{B}
``` | \(3\) |
| E\_{t,ω} = E_min + Σ_ℓ ΔE_ℓ u\_{t,ω,ℓ}, 0 ≤ u\_{t,ω,ℓ} ≤ u\_{t,ω,ℓ−1} ≤ 1 | (3a) |
| E\_(0,ω)=E\_(T,ω) | \(4\) |

The cyclic condition is applied separately to each scenario. Upward reserve is constrained by both power capability and an energy-parking requirement. A generic form consistent with the implemented model is

| 
``` math
r_{t}^{\uparrow} \leq {\overline{P}}_{B} - \ P_{t,\omega}^{dis}
``` | \(5\) |
|----|----|
| 
``` math
E_{t,\omega} \geq E_{\min} + \frac{\tau^{\uparrow}r_{t}^{\uparrow}}{\eta_{d}}
``` | \(6\) |
| r_t^↓ ≤ P_B − p^ch\_{t,ω}, E\_{t,ω} + η_c τ^↓ r_t^↓ ≤ E_max | (6a) |

where τ↑ is the fixed reserve-sustainment parameter used by the study. The constraint prices the energy that must remain available for upward deployment; it does not simulate the detailed activation trajectory or mileage of an aFRR signal. The full constraint set applied in the reconstruction is, for each scenario ω and hour t:  
r↑\_t ≤ P_B - p^{dis}\_{t,ω}, r↓\_t ≤ P_B - p^{ch}\_{t,ω} (power capability);  
E\_{t,ω} ≥ E_min + τ↑ r↑\_t/η_d, E\_{t,ω} + η_c τ↓ r↓\_t ≤ E_max (energy parking);  
r↑\_t, r↓\_t ≥ 0.  
Two market readings are possible: (a) two separate products, so 1.5 MW may be offered in each direction independently (the reconstruction's default, r↑ ≤ 1.5 and r↓ ≤ 1.5 separately); or (b) an aggregate cap r↑ + r↓ ≤ 1.5 MW. Reading (a) yields aFRR revenue of ≈1,384 EUR and a negative P1−B2 differential; reading (b) yields ≈920 EUR and a positive differential (Table VII). The aggregation rule is undocumented in the original run set and is the single largest driver of the reported reversal.

The baseline LP omits binary charge/discharge exclusivity, so simultaneous charging and discharging are feasible. The economic terms do not guarantee that this overlap is zero; we therefore report an overlap diagnostic and a binary-exclusive MILP sensitivity case. LP results apply only to the relaxed formulation. In the accompanying reconstruction's relaxed-LP runs for 1 May 2026, the per-scenario daily summed simultaneous charge–discharge reaches 11.99 MWh over the 24 hours under the Xu law (mean 6.44 MWh per day, present in 87% of scenarios), i.e., at most about 0.5 MWh per hour against a 2.5 MW power rating, whereas the binary-exclusive MILP re-solves reduce it to order 10⁻¹⁴ MWh, i.e., numerical noise, for all three aging laws. The LP dispatch therefore overstates usable intraday arbitrage flexibility within each scenario; LP outputs are reported only as relaxation checks, never as final results.

C. Three aging representations

1\) Throughput model. The benchmark assigns a constant marginal aging cost to charge and discharge:

| $`C_{t,\omega}^{THR} = c_{thr}\left( P_{t,\omega}^{dis} + P_{t,\omega}^{ch} \right)\Delta t\ ,\ c_{thr} = 1.5\ `$EUR/MWh | \(7\) |
|----|----|

Idle stored energy is not directly priced by this term.

2\) Daily DoD model. The daily-range (Xu-style) benchmark takes from \[16\] only the daily-depth idea: its cost scales with the normalized range of stored energy. Let Emax,d and Emin,d be the maximum and minimum daily stored energy. The daily depth variable d_d satisfies

|                                                  
 ``` math                                          
 d_{d} \geq \frac{{E_{max,d} - E}_{min,d}}{E_{B}}  
 ```                                               | \(8\) |
|--------------------------------------------------|-------|

and its cost is represented by a convex piecewise-linear epigraph with segment widths 0.20, 0.30, 0.30, and 0.20 and slopes 10, 40, 80, and 120 EUR per unit depth \[16\].

| 
``` math
d_{d} = \sum_{k = 1}^{4}\delta_{d,k}
``` | \(9\) |
|----|----|
| 
``` math
C_{d}^{DoD} = \sum_{k = 1}^{4}{m_{k}\delta_{d,k}}
``` | \(10\) |
| 
``` math
0 \leq \delta_{d,k} \leq w_{k}\ ,\ k = 1,..,4\ ,\ w = \lbrack 0.2,0.3,0.3,0.2\rbrack,\ m = \lbrack 10,40,80,120\rbrack
``` | \(11\) |

3\) ReLCCA. The usable interval \[$`E_{\min}`$, $`E_{\max}`$\] is divided into N equal-width SoC bands. Occupancy variables $`u_{t,\omega,l}`$ are represented cumulatively so that band filling is monotone. Band-level charge and discharge flows connect occupancy changes to battery movement. The ReLCCA aging cost is

| 
``` math
C_{t,\omega}^{ReLCCA} = \sum_{\mathcal{l}}^{}k_{\mathcal{l}}u_{t,\omega,l}\Delta E_{l}\Delta t + \sum_{l}^{}{\gamma_{l}^{ch}P_{t,\omega,l}^{ch}}\Delta t + \sum_{l}^{}{\gamma_{l}^{dis}P_{t,\omega,l}^{dis}}\Delta t
``` | \(12\) |
|----|----|
| * *$`k_{\mathcal{l}} = \left\{ \begin{array}{r}
0.247\ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \mathcal{l}\epsilon L_{low} \\
0.493\ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \mathcal{l}\epsilon L_{mid}\ \ \ \ \  \\
0.822\ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \mathcal{l}\epsilon L_{high}
\end{array} \right.\ \lbrack EUR/MWh/h\rbrack`$ | \(13\) |

The first term is the defining occupancy component: energy retained in a high-SoC band incurs a calendar-aging cost even when no energy is cycled during that hour. The second term retains cycle-related costs. All coefficients are fixed parameters, so the formulation remains affine. Each κ comes from one formula: κ = (fade over ten months × 12/10 × replacement cost) / 8,760 h. For the mid plateau this is 0.024 × 1.2 × 150,000 / 8,760 = 0.493 EUR/MWh/h; the factor 1.2 is a DoD-margin (depth-of-discharge) multiplier applied to the ten-month fade to account for the cycling share of aging, and is not a fitted cell parameter. If it is removed, all three κ plateaus shift down by 20% and the structural aging effect shrinks below the 11 EUR/day reported in Table VII.

The default eight-band κ map uses three plateaus derived from the supplied Keil-based calibration: 0.247, 0.493, and 0.822 EUR/MWh/h for low-, mid-, and high-SoC bands, respectively \[12\]. These are economic inputs based on published calendar-aging relationships, not a fitted cell-aging model.

D. Mean–CVaR objective

For scenario $`\omega`$, wholesale profit is represented as

| 
``` math
П_{\omega} = R_{DA,\omega} + R_{aFRR,\omega} - C_{imb,\omega} - C_{DG,\omega} - C_{age,\omega}
``` | \(14\) |
|----|----|

In the profit identity, both the day-ahead price λ^{DA}\_t and the first-stage position p^{DA}\_t are scenario-independent, so R^{DA} = Σ_t λ^{DA}\_t p^{DA}\_t is a single deterministic quantity and scenario dependence enters Π_ω only through imbalance, generator and aging recourse. If price uncertainty at bid time is represented, λ^{DA} must be scenario-indexed, in which case R^{DA} varies across ω through the price, not through the schedule; the present model adopts the deterministic-price convention, so the price bootstrap affects only the imbalance term.

A retail load-service overlay, when reported, is added after the wholesale optimization and therefore cannot change the market-decision ranking. Formally, the reported profit equals the wholesale objective plus this post-optimization overlay term, which is computed from the realized dispatch schedule. It therefore shifts profit levels without entering the optimization itself; the inter-model ranking in Tables III–VI is driven by the wholesale objective, which is evaluated under identical prices, scenarios, and constraints for all three aging laws, and the overlay is added to each law under exactly the same rule.

Let $`L_{\omega}`$ = −$`П_{\omega}`$ denote scenario loss. With confidence level α = 0.95, the Rockafellar–Uryasev representation introduces a threshold ζ and nonnegative excess variables $`s_{\omega}`$:

| 
``` math
s_{\omega} \geq L_{\omega} - \zeta\ \ ,\ s_{\omega} \geq 0
``` | \(15\) |
|----|----|
| 
``` math
{CVaR}_{\alpha}(L) = \zeta\  + \frac{1}{1 - \alpha}\sum_{\omega}^{}{\pi_{\omega}s}_{\omega}\ \ ,\ \alpha = 0.95
``` | \(16\) |

The implemented objective maximizes expected profit while penalizing lower-tail loss with CVaR risk weight β = 0.05 (Table II):

| 
``` math
\max\sum_{\omega}^{}{\pi_{\omega}П}_{\omega} - \beta{CVaR}_{\alpha}(L)\ \ ,\ \beta = 0.05
``` | \(17\) |
|----|----|

Here πω (ω = 1…K) is the scenario probability, used identically in the expectation and inside the CVaR term, while sω denotes only the nonnegative excess loss below the threshold ζ; both terms are affine in (ζ, sω), so the objective remains linear.

Without binary charge/discharge exclusivity, the objective and constraints are affine and the baseline problem is an LP. The exclusive sensitivity case adds binary variables and is a MILP. The daily DoD epigraph and CVaR use auxiliary variables and linear constraints.

**V. EXPERIMENTAL DESIGN**

A. Paired identification principle

B2 is the energy-only bid; P1 jointly offers day-ahead energy and aFRR capacity. P1−B2 is the difference in simulated wholesale profit after settlement. For each day, bids are optimized over the same scenario set, then first-stage positions are fixed while recourse is re-optimized on the observed day. Plant, prices, risk settings, and solver are held constant within each aging-law comparison.

B. Isolation days

Four isolation dates are used to represent ordinary and stressed conditions: 20 January, 5 April, 1 May, and 19 August. The default scenario count is K = 30. These dates are diagnostic examples rather than a representative random sample.

C. Counterfactual negative-price intervention

To test whether negative-price depth alone is sufficient to reproduce the observed reversal, the 19 August residual portfolio is frozen while the selected midday price interval is replaced by scaled copies of the 1 May trough. The injected minimum is varied across −50, −80, −200, −300, −414, and −499 EUR/MWh (−499 EUR/MWh is the EPEX day-ahead price floor, so the last case is a market-rule boundary rather than an arbitrary stress level). The experiment therefore changes price severity while preserving the underlying residual structure; it is a counterfactual intervention, not a market forecast.

D. Historical negative-price scan

We scan days with a minimum day-ahead price below −20 EUR/MWh. The 20 qualifying days form an in-sample event set, not a random sample; the scan is descriptive and does not estimate a population probability.

E. Profit decomposition and robustness

Whenever aging formulations produce materially different market positions, wholesale profit is decomposed into day-ahead energy, reserve, imbalance, generator, and aging components. Robustness checks vary the number of SoC bands, calendar coefficient mapping, calendar/cycle components, scenario count, calendar annualization, imbalance clipping, reserve cap, and battery energy capacity. These tests evaluate sign stability within the model and do not constitute electrochemical validation.

**VI. RESULTS**

The numerical values in Tables III–VI and Figs. 1–3 are the values reported by the original manuscript runs. They are retained here for transparent documentation, but have not been reproduced by the author's self-reconstruction on the archived public panel (Section VIII); they remain reported, unverified values. Accordingly, they are reported results rather than verified outputs of the archived reconstruction. The reconstruction discrepancy is stated explicitly wherever it affects interpretation.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><p><strong>TABLE III. Paired isolation-day results under the three battery-aging representations.</strong></p>
<p>K = 30, 180 EUR/MWh load-service overlay included (Differences are computed from unrounded values)</p></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 9%" />
<col style="width: 26%" />
<col style="width: 21%" />
<col style="width: 21%" />
<col style="width: 21%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Day</strong></th>
<th style="text-align: center;"><strong>Law</strong></th>
<th style="text-align: center;"><strong>B2 (EUR)</strong></th>
<th style="text-align: center;"><strong>P1 (EUR)</strong></th>
<th style="text-align: center;"><strong>P1−B2 (EUR)</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th style="text-align: center;">20 Jan</th>
<td style="text-align: center;">Throughput / Xu / ReLCCA</td>
<td style="text-align: center;">10,330 / 10,332 / 9,886</td>
<td style="text-align: center;">11,260 / 11,258 / 11,100</td>
<td style="text-align: center;">+930 / +926 / +1,214</td>
</tr>
<tr>
<th style="text-align: center;">5 Apr</th>
<td style="text-align: center;">Throughput / Xu / ReLCCA</td>
<td style="text-align: center;">15,475 / 15,475 / 15,215</td>
<td style="text-align: center;">16,676 / 16,676 / 16,603</td>
<td style="text-align: center;">+1,201 / +1,201 / +1,389</td>
</tr>
<tr>
<th style="text-align: center;">1 May</th>
<td style="text-align: center;">Throughput / Xu / ReLCCA</td>
<td style="text-align: center;">14,492 / 14,492 / 13,180</td>
<td style="text-align: center;">14,246 / 14,225 / 13,696</td>
<td style="text-align: center;">−246 / −266 / +515</td>
</tr>
<tr>
<th style="text-align: center;">19 Aug</th>
<td style="text-align: center;">Throughput / Xu / ReLCCA</td>
<td style="text-align: center;">10,961 / 10,961 / 10,766</td>
<td style="text-align: center;">12,268 / 12,268 / 12,245</td>
<td style="text-align: center;">+1,307 / +1,306 / +1,480</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

A. Paired isolation-day results

For the three non-event dates, the original manuscript reports positive P1−B2 values under all three aging laws. For 1 May, it reports a negative differential for throughput and Xu but a positive differential for ReLCCA. The available reconstruction does not reproduce this ranking; the original table values therefore remain unverified. Table III reports isolation-day results with K = 30 and the 180 EUR/MWh load-service overlay, whereas Table V reports the historical negative-price scan with K = 20 and no overlay; values for the same calendar day may therefore differ between the two tables. The reconstruction reproduces the same qualitative pattern on 1 May: its throughput gap is nearly invariant across the K = 30 relaxed-LP and K = 20 scan settings (−321.4 vs −320.6 EUR), while the Xu and ReLCCA gaps shift by roughly +102 and +68 EUR between the same two settings; day-specific differentials may therefore reflect scenario-sample sensitivity rather than a data inconsistency.

B. Controlled price-trough experiment

In the original manuscript's 19 August portfolio intervention, P1−B2 remains positive across the injected troughs: throughput declines from +1,145 to +790 EUR and ReLCCA from +1,353 to +1,056 EUR. Deepening the trough alone did not reproduce the 1 May reversal in this frozen portfolio. These are original reported values, not independently reproduced outputs; the counterfactual is neither a forecast nor a general causal test.

| <img src="figures/media/image1.png" style="width:4.27163in;height:2.56298in" /> |
|----|
| **Fig. 1. Controlled negative-price trough experiment using the 19 August residual structure. The intervention varies only the injected midday price minimum; it is not a forecast. The profile values are the original manuscript's reported, unverified results and have not been reproduced by the available reconstruction.** |

C. 1 May profit decomposition

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE IV. 1 May 2026 wholesale profit by component, K = 30, no overlay. B2 = energy-only, P1 = energy + reserve. Column entries are rounded to the nearest EUR; rows are computed from unrounded components, so a few rows may differ by EUR 1 from the sum of the rounded columns.</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 14%" />
<col style="width: 14%" />
<col style="width: 14%" />
<col style="width: 14%" />
<col style="width: 14%" />
<col style="width: 14%" />
<col style="width: 14%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Model</strong></th>
<th style="text-align: center;"><strong>DA energy</strong></th>
<th style="text-align: center;"><strong>aFRR</strong></th>
<th style="text-align: center;"><strong>Imbalance</strong></th>
<th style="text-align: center;"><strong>DG</strong></th>
<th style="text-align: center;"><strong>Aging</strong></th>
<th style="text-align: center;"><strong>Wholesale</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th style="text-align: center;">B2–Throughput</th>
<td style="text-align: center;">+978</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">+600</td>
<td style="text-align: center;">−1,714</td>
<td style="text-align: center;">−58</td>
<td style="text-align: center;">−194</td>
</tr>
<tr>
<th style="text-align: center;">P1–Throughput</th>
<td style="text-align: center;">−541</td>
<td style="text-align: center;">+1,333</td>
<td style="text-align: center;">+436</td>
<td style="text-align: center;">−1,635</td>
<td style="text-align: center;">−32</td>
<td style="text-align: center;">−440</td>
</tr>
<tr>
<th style="text-align: center;">B2–ReLCCA</th>
<td style="text-align: center;">−268</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">+462</td>
<td style="text-align: center;">−1,647</td>
<td style="text-align: center;">−54</td>
<td style="text-align: center;">−1,506</td>
</tr>
<tr>
<th style="text-align: center;">P1–ReLCCA</th>
<td style="text-align: center;">−1,238</td>
<td style="text-align: center;">+1,457</td>
<td style="text-align: center;">+474</td>
<td style="text-align: center;">−1,635</td>
<td style="text-align: center;">−49</td>
<td style="text-align: center;">−991</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

| <img src="figures/media/image2.png" style="width:5.04434in;height:2.77439in" /> |
|:--:|
| **Fig. 2. 1 May 2026 wholesale profit decomposition for the energy-only bid (B2) under the throughput and ReLCCA aging representations The plotted values are the original manuscript’s reported results and have not been independently reproduced.** |

The original manuscript's decomposition reports that B2–Throughput and B2–ReLCCA differ by EUR 1,246 in day-ahead energy revenue (+978 versus −268 EUR) but by only EUR 4 in direct aging cost (−58 versus −54 EUR). Their reported wholesale profits differ by EUR 1,312 (−194 versus −1,506 EUR). If reproduced, this decomposition would locate most of the difference in the optimized market position rather than in direct aging expenditure. The available reconstruction does not reproduce these values, so this mechanism remains a hypothesis supported by the original reported decomposition, not a verified result.

D. Historical negative-price scan

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE V. Historical negative-price days below −50 EUR/MWh and corresponding model differentials</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table style="width:100%;">
<colgroup>
<col style="width: 15%" />
<col style="width: 21%" />
<col style="width: 21%" />
<col style="width: 21%" />
<col style="width: 21%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Day</strong></th>
<th style="text-align: center;"><strong>Minimum DA price</strong></th>
<th style="text-align: center;"><strong>Throughput P1−B2</strong></th>
<th style="text-align: center;"><strong>Xu P1−B2</strong></th>
<th style="text-align: center;"><strong>ReLCCA P1−B2</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th style="text-align: center;">1 May</th>
<td style="text-align: center;">−499</td>
<td style="text-align: center;">−246</td>
<td style="text-align: center;">−251</td>
<td style="text-align: center;">+531</td>
</tr>
<tr>
<th style="text-align: center;">26 Apr</th>
<td style="text-align: center;">−414</td>
<td style="text-align: center;">+139</td>
<td style="text-align: center;">+137</td>
<td style="text-align: center;">+869</td>
</tr>
<tr>
<th style="text-align: center;">25 Apr</th>
<td style="text-align: center;">−191</td>
<td style="text-align: center;">+812</td>
<td style="text-align: center;">+850</td>
<td style="text-align: center;">+1,114</td>
</tr>
<tr>
<th style="text-align: center;">2 May</th>
<td style="text-align: center;">−130</td>
<td style="text-align: center;">+887</td>
<td style="text-align: center;">+887</td>
<td style="text-align: center;">+1,188</td>
</tr>
<tr>
<th style="text-align: center;">6 Apr</th>
<td style="text-align: center;">−126</td>
<td style="text-align: center;">+1,043</td>
<td style="text-align: center;">+1,043</td>
<td style="text-align: center;">+1,382</td>
</tr>
<tr>
<th style="text-align: center;">5 Apr</th>
<td style="text-align: center;">−105</td>
<td style="text-align: center;">+1,182</td>
<td style="text-align: center;">+1,182</td>
<td style="text-align: center;">+1,381</td>
</tr>
<tr>
<th style="text-align: center;">11 Apr</th>
<td style="text-align: center;">−80</td>
<td style="text-align: center;">+1,100</td>
<td style="text-align: center;">+1,100</td>
<td style="text-align: center;">+1,246</td>
</tr>
<tr>
<th style="text-align: center;">24 May</th>
<td style="text-align: center;">−76</td>
<td style="text-align: center;">+1,115</td>
<td style="text-align: center;">+1,115</td>
<td style="text-align: center;">+1,316</td>
</tr>
<tr>
<th style="text-align: center;">29 Apr</th>
<td style="text-align: center;">−60</td>
<td style="text-align: center;">+1,074</td>
<td style="text-align: center;">+1,060</td>
<td style="text-align: center;">+1,273</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

The original manuscript's scan reports one throughput reversal among the twenty days with minimum day-ahead prices below −20 EUR/MWh: on 1 May. ReLCCA is reported positive (P1−B2 \> 0) on all twenty qualifying days. Table V lists the nine qualifying days whose minimum price is below −50 EUR/MWh; the remaining eleven qualify under the −20 EUR/MWh threshold. These are in-sample counts over days with different portfolio states, not probability estimates. The available reconstruction produces two reversals for each aging law; the original scan result is therefore unverified.

E. Numerical and parameter robustness

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE VI. Robustness and sensitivity checks for the ReLCCA P1−B2 differential. Values are transcribed from the original manuscript's runs; the scenario-count setting behind each row is not stated in the available reproduction materials, so differences between rows may also reflect K-setting differences, as analysed for Table III versus Table V. UNVERIFIED: the scenario-count setting behind each row is not stated in the available reproduction materials, so this table is retained for documentation only and is not treated as evidence.</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 50%" />
<col style="width: 49%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Check</strong></th>
<th style="text-align: center;"><strong>ReLCCA P1−B2 (EUR)</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th style="text-align: center;">N = 4 / 6 / 8 / 12, K = 20</th>
<td style="text-align: center;">+565 / +533 / +576 / +561</td>
</tr>
<tr>
<th style="text-align: center;">κ step / all-mid / all-high / 100% top, K = 30</th>
<td style="text-align: center;">+515 / +514 / +512 / +515</td>
</tr>
<tr>
<th style="text-align: center;">Calendar only / cycle only / both, K = 30</th>
<td style="text-align: center;">+587 / +512 / +515</td>
</tr>
<tr>
<th style="text-align: center;">K = 20 / K = 30</th>
<td style="text-align: center;">+576 / +515</td>
</tr>
<tr>
<th style="text-align: center;">√t annualization (κ × 0.913)</th>
<td style="text-align: center;">+516</td>
</tr>
<tr>
<th style="text-align: center;">Imbalance |DA| clipped at 150</th>
<td style="text-align: center;">+541 (throughput −232)</td>
</tr>
<tr>
<th style="text-align: center;">rmax = 0.5 / 2.5 MW, K = 20</th>
<td style="text-align: center;">+234 / +800 (throughput −91 / −262)</td>
</tr>
<tr>
<th style="text-align: center;">Eb = 2 MWh, K = 20</th>
<td style="text-align: center;">+409 (throughput +19)</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

The original manuscript's component checks report P1−B2 values of +587 EUR for calendar-only, +512 EUR for cycle-only, and +515 EUR for the combined model. These values would suggest that SoC dependence, rather than the calendar term alone, drives the reported distinction; however, the checks have not been independently reproduced. A κ→0 ablation isolating the calendar term from the band-cycle term, and an equal-cost-at-reference calibration across the three laws, are therefore named as determinative checks; the κ→0 ablation is performed in the accompanying reconstruction and reported in Section VIII.

| <img src="figures/media/image3.png" style="width:3.96937in;height:2.44269in" /> |
|----|
| **Fig. 3. ReLCCA P1−B2 differential across SoC-band resolutions (N = 4, 6, 8, 12; K = 20) on 1 May 2026; these are the original manuscript's values and have not been independently reproduced.** |

The original manuscript's sensitivity runs report a ReLCCA P1−B2 gap of +234 to +800 EUR across tested reserve caps and positive values for 4, 6, 8, and 12 SoC bands (+565, +533, +576, and +561 EUR). Throughput is reported negative except for the 2 MWh case (+19 EUR). These values describe the original runs and have not been independently reproduced.

**VII. DISCUSSION**

A. Interpretation of the market-position mechanism

Throughput and daily-depth costs depend on energy processed or the SoC excursion. ReLCCA also prices energy retained in each SoC band. Under an upward-reserve commitment, that occupancy cost can alter the marginal value of stored energy and the selected day-ahead position. The original 1 May decomposition reports a much larger difference in day-ahead energy revenue than in direct aging cost. The reconstruction does not reproduce that decomposition; under the reconstruction the P1−B2 differential is negative for all three laws and sign-stable across K = 30–200, and the direct aging-cost difference between throughput and ReLCCA is of order 4 EUR (Table IV). The proposed market-position mechanism is therefore a hypothesis consistent with the reported decomposition, not a demonstrated causal effect; the 3×3 position-valuation matrix of Table VII is the test that would separate a position effect from a valuation effect.

**B. Scope of the empirical evidence**

The evidence does not establish universal superiority of ReLCCA, a universal negative-price threshold, a population-level reversal probability, or a validated cell-level degradation law. Reserve and imbalance prices are proxies, so the reported euro values are simulated wholesale-profit outputs under the stated proxy assumptions, not realized German settlements.

**VIII. LIMITATIONS AND REPRODUCIBILITY**

Limitations of the data and sample: The original manuscript reports one reversal in 262 complete days, and the panel does not cover September through November. That frequency cannot be generalized to a full year. The panel spans 1 December 2025 through 21 August 2026 and contains national system series, not battery telemetry.

Limitations of the market model: aFRR capacity prices are repeated four-hour block means rather than day-specific cleared auction records, and activation trajectories are not simulated. Imbalance prices use a two-price proxy rather than observed reBAP settlements, and the proxy is a deterministic function of the day-ahead price, which removes uncertainty from the realized imbalance cost. Recourse is also resolved with perfect foresight of each scenario's realized daily path, so within-scenario operating profit is an upper bound on a rolling myopic policy. The VPP is a price taker and omits network constraints and strategic price-making. The event scan is limited to the available panel.

Limitations of the battery and aging model: ReLCCA is an optimization-oriented encoding of published aging relationships, not a cell-level electrochemical model. Its coefficients require chemistry-, temperature-, and history-specific calibration. The calendar-cost annualization is linear in time, while the square-root-time case is only a sensitivity test. The EUR 150/kWh replacement value is a cell-cost assumption, not installed EPC cost. The Xu benchmark represents daily depth and is not rainflow counting. The reconstruction's code assumptions are E0 = 2.5 MWh (the mid-band level, with a cyclic start/end at the same level), a reserve-sustainment duration of τ = 1 h, and band-specific cycle coefficients; none of these is a manuscript-reported value. Because both the initial level and the cyclic end condition are assumptions, the reconstruction additionally re-tests lower and higher initial levels (1.25 and 3.75 MWh), τ = 2 and 4 h, and a free terminal-energy variant; results are reported in Table VII.

Scenario-count sensitivity (reconstruction, 1 May 2026, MILP): the P1−B2 gaps remain negative at every tested scenario count. With K = 30 they are −98.7 (throughput), −97.2 (Xu), and −102.5 (ReLCCA) EUR; with K = 50, −134.6, −103.2, and −132.7; with K = 100, −269.0, −104.5, and −244.0; and with K = 200, −280.7, −253.1, and −253.5. The reconstruction therefore does not reproduce the original positive ReLCCA result at any tested K, so the non-reproduction is a property of the model and input snapshot rather than an artifact of the K = 30 scenario sample. Gap magnitudes vary across K because the MILP dispatch schedule itself changes with the scenario sample; the controlled diagnostic is sign stability, and it holds for all three aging laws. The 20-day scan paired difference (ReLCCA minus throughput) has mean −3.81 EUR (Wilcoxon p = 0.330; block-bootstrap 95% CI \[−9.78, +1.24\] EUR; SD ≈ 11.8, SE ≈ 2.63). The minimum detectable effect at 80% power is ≈7.8 EUR/day, so the reconstruction could have detected the reported 11 EUR structural effect and would have excluded effects above ≈30 EUR; the reported 500–1,300 EUR reversal is therefore excluded by the re-derivation, not merely unconfirmed. A TOST at ±10 EUR establishes equivalence to zero (p = 0.0148), which is stronger than the non-significant Wilcoxon result.

Component ablation (reconstruction, 1 May 2026, MILP, K = 30, seed 20260821): removing the calendar SoC-occupancy term (κ → 0, band-cycle term retained) yields a P1−B2 differential of −98.6 EUR versus −102.5 EUR for the full ReLCCA model, while a calendar-only run yields −91.6 EUR; throughput and Xu remain at −98.7 and −97.2 EUR on the identical scenario set. The sign of the differential is therefore insensitive to the presence of the SoC-occupancy term in the reconstruction, which supports the associated observation that the calendar term is small relative to the position effect; an equal-cost-at-reference calibration across the three laws remains an open requirement for the original runs.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE VII. Summary of labelled reconstruction diagnostics (1 May 2026 and the twenty-day negative-price scan; raw outputs are archived separately and must not replace Tables III–VI)</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 50%" />
<col style="width: 49%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>Reconstruction check</strong></th>
<th style="text-align: center;"><strong>Labelled reconstruction result</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th style="text-align: center;">Paired event scan (20 days, relaxed LP, K = 20)</th>
<td style="text-align: center;">P1−B2 is positive on 18 of 20 days for each law (two reversals each); paired ReLCCA−throughput mean −3.81 EUR, Wilcoxon p = 0.330, reproducible moving-block-bootstrap 95% CI [−8.30, +1.14] EUR (block length 7, 4,000 replicates, seed 0).</td>
</tr>
<tr>
<th style="text-align: center;">Scenario-count sweep (1 May, MILP)</th>
<td style="text-align: center;">P1−B2 negative at every K for all three laws: throughput −98.7 → −280.7; Xu −97.2 → −253.1; ReLCCA −102.5 → −253.5 EUR; sign-stable, magnitudes vary with the scenario sample</td>
</tr>
<tr>
<th style="text-align: center;">Component ablation (1 May, MILP, K = 30)</th>
<td style="text-align: center;">κ→0 (cycle-only) −98.6; calendar-only −91.6; full ReLCCA −102.5 EUR; sign unchanged under every calendar/cycle weighting</td>
</tr>
<tr>
<th style="text-align: center;">Equal-cost-at-reference calibration</th>
<td style="text-align: center;">coefficients rescaled so that the B2 aging cost is equal at reference (29.5 EUR/day): −110.8 (throughput), −99.5 (Xu), −102.5 (ReLCCA) EUR; ranking and sign unchanged</td>
</tr>
<tr>
<th style="text-align: center;">Imbalance-proxy spread (1 May, MILP)</th>
<td style="text-align: center;">base −98.7 / −97.2 / −102.5; half-spread −102.7 / −97.2 / −109.2; zero-spread −119.1 / −112.9 / −96.1 EUR (throughput / Xu / ReLCCA); all negative even with zero spread</td>
</tr>
<tr>
<th style="text-align: center;">Reserve-sustainment τ and SoC-boundary variants (1 May, MILP, K = 30)</th>
<td style="text-align: center;">E0 = 1.5 and 3.5 MWh and free terminal energy keep all three differentials negative (throughput −87.2/−97.1, Xu −80.3/−91.6, ReLCCA −93.3/−102.4, and −53.5/−37.7/−55.5 EUR); τ = 2 h shifts the differentials upward, flipping the sign for throughput and ReLCCA (+16.9 and +70.0 EUR; Xu −7.0), and τ = 4 h reverses the sign for all three laws (approx. +428 to +439 EUR). The reconstruction's negative differential is therefore conditional on the unstated τ = 1 h assumption.</td>
</tr>
<tr>
<th style="text-align: center;">E4 crossed optimization/settlement sensitivity (1 May, relaxed LP, K = 30)</th>
<td style="text-align: center;">Proxy→proxy: −321.3/−237.0/−244.7; proxy→reBAP: −1,927.5/−1,964.2/−1,943.9; LEAKY reBAP→proxy: +339.1/+313.7/+335.1; LEAKY→reBAP: +848.4/+839.2/+844.6 EUR (throughput/Xu/ReLCCA). The LEAKY rows use realized same-day prices in optimization and are not ex-ante results.</td>
</tr>
<tr>
<th style="text-align: center;">Contiguous 20-day evaluation (1–20 Aug 2026, K = 30)</th>
<td style="text-align: center;">P1−B2 positive on all 20 days for all three laws (cumulative +23,105 / +23,269 / +23,016 EUR); sign opposite to the negative-price regime. Daily cyclic boundary reset each day; terminal energy is not carried across days in this run.</td>
</tr>
<tr>
<th style="text-align: center;">Reserve-cap aggregation rule (1 May, MILP, K = 30)</th>
<td style="text-align: center;">Per-direction caps (r↑ ≤ 1.5, r↓ ≤ 1.5) give −98.7/−97.2/−102.5 EUR; an aggregate cap (r↑ + r↓ ≤ 1.5) gives +67.4/+87.2/+76.0 EUR and cuts aFRR revenue from ≈1,384 to ≈920 EUR. The aggregation rule alone flips the sign; it is undocumented in the original run set.</td>
</tr>
<tr>
<th style="text-align: center;">Position-valuation matrix (1 May, MILP, K = 30)</th>
<td style="text-align: center;">Fixing each law's optimal bid and valuing it under all three laws gives a 4,447–4,469 EUR range (≈18 EUR spread); the aging law barely moves the optimal position, so the P1−B2 gap is a valuation/commitment effect, not a position effect.</td>
</tr>
<tr>
<th style="text-align: center;">Reserve-sustainment τ (0.5/1/2/4 h, 1 May, MILP, K = 30)</th>
<td style="text-align: center;">Gaps (thr/Xu/ReLCCA, EUR): τ = 0.5 → +499/+483/+494; τ = 1 → −98.7/−97.2/−102.5; τ = 2 → +16.9/−7.0/+70.0; τ = 4 → +428/+439/+428. At τ = 4 the required energy (6.3 MWh) exceeds the 4 MWh window, so r↑ is effectively capped at ≈0.95 MW.</td>
</tr>
<tr>
<th style="text-align: center;">Zero reserve-revenue (lambda^R = 0), 20 scan days</th>
<td style="text-align: center;">When aFRR reserve revenue is set to zero, P1−B2 = 0 for every day and every law (cumulative 0 EUR). Reserve revenue alone explains the entire differential; the aging-law contribution is of order 11 EUR/day (Table VII equal-cost row) and is negligible against it.</td>
</tr>
<tr>
<th style="text-align: center;">LP-relaxation co-charge (1 May)</th>
<td style="text-align: center;">daily-summed simultaneous charge–discharge up to 11.99 MWh (Xu) under relaxed LP; ≤ 10⁻¹⁴ MWh under binary-exclusive MILP</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr>
<th style="text-align: center;"><strong>TABLE VIII. E4 crossed optimization-input and settlement sensitivity (1 May 2026, reconstruction relaxed LP, K = 30). Rows: optimization input; columns: settlement model. Entries are P1−B2 wholesale profit (EUR); realized-reBAP optimization is LEAKY and not ex ante.</strong></th>
</tr>
</thead>
<tbody>
<tr>
<th><table>
<colgroup>
<col style="width: 33%" />
<col style="width: 33%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr>
<th>Optimization input \ Settlement</th>
<th>Proxy</th>
<th>Observed reBAP</th>
</tr>
</thead>
<tbody>
<tr>
<th>Proxy (deterministic spread)</th>
<td>−321.3 (thr) / −237.0 (Xu) / −244.7 (ReLCCA)</td>
<td>−1,927.5 / −1,964.2 / −1,943.9</td>
</tr>
<tr>
<th>Realized reBAP (LEAKY)</th>
<td>+339.1 / +313.7 / +335.1</td>
<td>+848.4 / +839.2 / +844.6</td>
</tr>
</tbody>
</table></th>
</tr>
</tbody>
</table>

The E4 2×2 crossed comparison (Table VIII) separates the optimization input from the settlement rule. Under proxy optimization, reBAP settlement gives P1−B2 gaps of −1,927.5/−1,964.2/−1,943.9 EUR for throughput/Xu/ReLCCA; proxy settlement gives −321.3/−237.0/−244.7 EUR. When the optimizer receives the realized 1 May reBAP series, the reBAP-settled gaps become +848.4/+839.2/+844.6 EUR. This realized-price case is perfect-foresight and is labelled LEAKY; it is not an ex-ante bid. The roughly 2.7-kEUR contrast between the two reBAP-settled rows compares different optimized bids, not a pure settlement effect. The approximately 9-EUR spread in the LEAKY row does not establish a ReLCCA advantage.

| <img src="figures/media/image4.png" style="width:3.96937in;height:2.44269in" /> |
|----|
| **Fig. 4. Reconstruction (relaxed LP, K = 20, seed 20260821) P1−B2 wholesale differentials across all twenty qualifying negative-price days, ordered by decreasing price depth; each bid is settled under its own aging law. The differential is positive on 18 of 20 days for every law (two reversals each). The differential values are reconstruction outputs on the archived public panel, not the original manuscript's reported values.** |

| <img src="figures/media/image5.png" style="width:3.96937in;height:2.44269in" /> |
|----|
| **Fig. 5. Bid profiles (p^{DA}, r^{\u2191}, r^{\u2193}, SoC) for 1 May 2026 (MILP, K = 30) under throughput and ReLCCA aging laws. First-stage variables are common across scenarios; the SoC trajectory is the scenario mean. Reported reconstruction on the archived public panel; not the original manuscript's values.** |

Limitations of reproducibility: The original manuscript reports Python/Pyomo with HiGHS and seed 20260821, but the original source code, input snapshot, and exact run configuration were not supplied. This reconstruction uses SciPy’s LP/MILP interface to HiGHS; its initial SoC (E0 = 2.5 MWh, mid-band and cyclic start/end), reserve-sustainment duration (τ = 1 h), and cycle-aging coefficients are assumptions, not evidence of the original settings. The reconstruction does not reproduce the reported 1 May ranking, so Tables III–VI remain values reported by the original manuscript rather than results reproduced by this code. In the 20-day negative-price reconstruction scan, P1−B2 is positive on 18 days for each law, with two reversals per law. The paired ReLCCA−throughput difference is −3.81 EUR on average (Wilcoxon p = 0.330; moving-block-bootstrap 95% CI \[−8.30, +1.14\] EUR, block length 7, 4,000 replicates, seed 0); ReLCCA has the largest differential on 6 of 20 days. These are in-sample diagnostics, not population event rates. Table VIII’s E4 results use the relaxed LP, and its realized-reBAP optimization cells are LEAKY. The reconstruction is author-produced and is not an independent replication; the original tables remain unverified pending access to the original code, inputs, and parameters.

Consolidated limitations. The panel contains national system series scaled to a synthetic portfolio, not battery telemetry; the repository has no cell chemistry, temperature history, or measured SoC/degradation data. ReLCCA is an optimization-oriented encoding of published aging relationships, not a cell-level electrochemical model, and its coefficients are not temperature- or chemistry-calibrated. The portfolio is assumed to be a price-taker, so strategic market impact—particularly at extreme prices—is not represented. aFRR prices are six four-hour block means, not day-specific cleared auction records, and activation trajectories are not simulated. Baseline imbalance settlement uses a deterministic day-ahead-price proxy. E4’s use of realized reBAP in optimization is a separate LEAKY perfect-foresight sensitivity, not an ex-ante strategy or a settlement-only test. The critical 1 May event is one day in a 262-day panel; the 20-day negative-price scan is too limited to estimate long-run event frequencies. Reserve-sustainment duration and the reserve-cap aggregation rule are not specified in the original run materials and can change the reconstruction’s differential sign. Recourse is resolved with perfect foresight within each scenario, so reported operating profit is an upper bound on a rolling policy. The original model and configuration remain unavailable; results must be read as conditional diagnostics, not as empirical battery-aging validation or an independent reproduction.

**IX. CONCLUSION**

This study examines whether SoC-occupancy aging changes a BESS energy–reserve decision under stressed prices. The original manuscript reports a 1 May 2026 reversal between throughput/Xu and ReLCCA, but the available reconstruction does not reproduce it: the exclusive-MILP P1−B2 differential is negative for all three laws and remains negative across K = 30–200. The 20-day scan likewise shows no systematic ReLCCA advantage. E4 shows that the sign can change when the optimizer is given the same day’s realized reBAP, but that perfect-foresight case is LEAKY and changes the optimized bid as well as the information set; it cannot be interpreted as a pure settlement effect or as ex-ante market performance. The defensible conclusion is therefore diagnostic: the reported reversal is not validated by the available reconstruction, and current evidence cannot attribute it to SoC-occupancy aging. Conclusions about market value require the original implementation and settings, a leak-free imbalance forecast, richer reserve-market data, and battery measurements that support chemistry- and temperature-specific aging parameters.

**ACKNOWLEDGMENT**

The authors acknowledge the public German market and physical data made available through Bundesnetzagentur \| SMARD and Fraunhofer ISE Energy-Charts. The reported optimization used Pyomo and HiGHS; the accompanying reconstruction uses SciPy's MILP interface to HiGHS.

**REFERENCES**

\[1\] D. Pudjianto, C. Ramsay, and G. Strbac, “Virtual power plant and system integration of distributed energy resources,” *IET Renew. Power Gener.*, vol. 1, no. 1, pp. 10–16, Mar. 2007.

\[2\] S. M. Nosratabadi, R.-A. Hooshmand, and E. Gholipour, “A comprehensive review on microgrid and virtual power plant concepts employed for distributed energy resources scheduling in power systems,” *Renew. Sustain. Energy Rev.*, vol. 67, pp. 341–363, Jan. 2017, doi: 10.1016/j.rser.2016.09.025.

\[3\] H. Pandžić, I. Kuzle, and T. Capuder, “Virtual power plant mid-term dispatch optimization,” *Appl. Energy*, vol. 101, pp. 134–141, Jan. 2013.

\[4\] M. Giuntoli and D. Poli, “Optimized thermal and electrical scheduling of a large scale virtual power plant in the presence of energy storages,” *IEEE Trans. Smart Grid*, vol. 4, no. 2, pp. 942–955, Jun. 2013.

\[5\] A. J. Conejo, M. Carrión, and J. M. Morales, *Decision Making Under Uncertainty in Electricity Markets*. New York, NY, USA: Springer, 2010.

\[6\] A. Baringo and L. Baringo, “A stochastic adaptive robust optimization approach for the offering strategy of a virtual power plant,” *IEEE Trans. Power Syst.*, vol. 32, no. 5, pp. 3492–3504, Sep. 2017, doi: 10.1109/TPWRS.2016.2633546.

\[7\] M. Rahimiyan and L. Baringo, “Strategic bidding for a virtual power plant in the day-ahead and real-time markets: A price-taker robust optimization approach,” *IEEE Trans. Power Syst.*, vol. 31, no. 4, pp. 2676–2687, Jul. 2016.

\[8\] M. Vahedipour-Dahraie, H. Rashidizadeh-Kermani, M. Shafie-khah, and J. P. S. Catalão, “Risk-averse optimal energy and reserve scheduling for virtual power plants incorporating demand response programs,” *IEEE Trans. Smart Grid*, vol. 12, no. 2, pp. 1405–1415, Mar. 2021.

\[9\] J. Vetter *et al.*, “Ageing mechanisms in lithium-ion batteries,” *J. Power Sources*, vol. 147, no. 1–2, pp. 269–281, Sep. 2005.

\[10\] M. Broussely *et al.*, “Main aging mechanisms in Li ion batteries,” *J. Power Sources*, vol. 146, no. 1–2, pp. 90–96, Aug. 2005.

\[11\] A. Barré, B. Deguilhem, S. Grolleau, M. Gérard, F. Suard, and D. Riu, “A review on lithium-ion battery ageing mechanisms and estimations for automotive applications,” *J. Power Sources*, vol. 241, pp. 680–689, Nov. 2013.

\[12\] P. Keil *et al.*, “Calendar aging of lithium-ion batteries,” *J. Electrochem. Soc.*, vol. 163, no. 9, pp. A1872–A1880, 2016, doi: 10.1149/2.0411609jes.

\[13\] J. Schmalstieg, S. Käbitz, M. Ecker, and D. U. Sauer, “A holistic aging model for Li(NiMnCo)O₂ based 18650 lithium-ion batteries,” *J. Power Sources*, vol. 257, pp. 325–334, 2014, doi: 10.1016/j.jpowsour.2014.02.012.

\[14\] M. Naumann, M. Schimpe, P. Keil, H. C. Hesse, and A. Jossen, “Analysis and modeling of calendar aging of a commercial LiFePO₄/graphite cell,” *J. Energy Storage*, vol. 17, pp. 153–169, 2018, doi: 10.1016/j.est.2018.01.019.

\[15\] H. C. Hesse *et al.*, “Ageing and efficiency aware battery dispatch for arbitrage markets using mixed integer linear programming,” *Energies*, vol. 12, no. 6, Art. no. 999, 2019, doi: 10.3390/en12060999.

\[16\] B. Xu, J. Zhao, T. Zheng, E. Litvinov, and D. S. Kirschen, “Factoring the cycle aging cost of batteries participating in electricity markets,” IEEE Trans. Power Syst., vol. 33, no. 2, pp. 2248–2259, Mar. 2018.

\[17\] B. Xu, A. Oudalov, A. Ulbig, G. Andersson, and D. S. Kirschen, “Modeling of lithium-ion battery degradation for cell life assessment,” *IEEE Trans. Smart Grid*, vol. 9, no. 2, pp. 1131–1140, Mar. 2018, doi: 10.1109/TSG.2016.2578950.

\[18\] Y. Shi, B. Xu, Y. Tan, D. Kirschen, and B. Zhang, “Optimal battery control under cycle aging mechanisms in pay for performance settings,” *IEEE Trans. Autom. Control*, vol. 64, no. 6, pp. 2324–2339, Jun. 2019, doi: 10.1109/TAC.2018.2867507.

\[19\] G. K. Petrin, S. Arens, P. Schoenfeldt, P. Klement, and S. Schlüters, “Modeling battery aging in linear energy system optimizations by applying convex hulls: accuracy benefits and computational costs,” *Appl. Energy*, vol. 399, Art. no. 126492, Dec. 2025, doi: 10.1016/j.apenergy.2025.126492.

\[20\] V. Kumtepeli, H. C. Hesse, M. Schimpe, A. Tripathi, Y. Wang, and A. Jossen, “Energy arbitrage optimization with battery storage: 3D-MILP for electro-thermal performance and semi-empirical aging models,” *IEEE Access*, vol. 8, pp. 204325–204341, 2020, doi: 10.1109/ACCESS.2020.3035504.

\[21\] J.-F. Toubeau, J. Bottieau, Z. De Grève, F. Vallée, and K. Bruninx, “Data-driven scheduling of energy storage in day-ahead energy and reserve markets with probabilistic guarantees on real-time delivery,” *IEEE Trans. Power Syst.*, vol. 36, no. 4, pp. 2815–2828, Jul. 2021, doi: 10.1109/TPWRS.2020.3046710.

\[22\] M. Merten, C. Olk, I. Schoeneberger, and D. U. Sauer, “Bidding strategy for battery storage systems in the secondary control reserve market,” *Appl. Energy*, vol. 268, Art. no. 114951, 2020, doi: 10.1016/j.apenergy.2020.114951.

\[23\] M. Merten, F. Rücker, I. Schoeneberger, and D. U. Sauer, “Automatic frequency restoration reserve market prediction: Methodology and comparison of various approaches,” *Appl. Energy*, vol. 268, Art. no. 114978, 2020, doi: 10.1016/j.apenergy.2020.114978.

\[24\] D. Fernández-Muñoz and J. I. Pérez-Díaz, “Optimisation models for the day-ahead energy and reserve self-scheduling of a hybrid wind–battery virtual power plant,” *J. Energy Storage*, vol. 57, Art. no. 106296, 2023, doi: 10.1016/j.est.2022.106296.

\[25\] E. Ghanaee, J. I. Pérez-Díaz, D. Fernández-Muñoz, J. Nájera, M. Chazarra, and S. Castaño-Solís, “Optimal scheduling of a hybrid wind–battery power plant in the day-ahead and reserve markets considering battery degradation cost,” in *Proc. IEEE Int. Conf. Smart Energy Syst. Technol. (SEST)*, 2024, doi: 10.1109/SEST61601.2024.10694289.

\[26\] P. Artzner, F. Delbaen, J.-M. Eber, and D. Heath, “Coherent measures of risk,” *Math. Finance*, vol. 9, no. 3, pp. 203–228, Jul. 1999.

\[27\] R. T. Rockafellar and S. Uryasev, “Optimization of conditional value-at-risk,” *J. Risk*, vol. 2, no. 3, pp. 21–41, 2000.

\[28\] R. T. Rockafellar and S. Uryasev, “Conditional value-at-risk for general loss distributions,” *J. Banking Finance*, vol. 26, no. 7, pp. 1443–1471, Jul. 2002.

\[29\] A. Mujeeb, Z. Hu, J. Wang, R. Diao, L. Liu, and Z. Bao, “Optimizing virtual power plant operations in energy and frequency regulation reserve markets: A risk-averse two-stage scenario-oriented stochastic approach,” *Int. Trans. Elect. Energy Syst.*, vol. 2025, no. 1, Art. no. 6640754, 2025, doi: 10.1155/etep/6640754.

\[30\] X. Wang, K. Lei, H. Wu, B. Xu, and J. Ding, “A conditional value-at-risk-based bidding strategy for PVSS participation in energy and frequency regulation ancillary markets,” *Sustainability*, vol. 18, no. 2, Art. no. 1122, 2026, doi: 10.3390/su18021122.

\[31\] O. N. Onsomu, E. Terciyanlı, and B. Yeşilata, “Optimal dispatch of a virtual power plant considering distributed energy resources under uncertainty,” *Energies*, vol. 18, no. 15, Art. no. 4012, Jul. 2025, doi: 10.3390/en18154012.

\[32\] R. Gao and A. J. Kleywegt, “Distributionally robust stochastic optimization with Wasserstein distance,” *Math. Oper. Res.*, vol. 48, no. 2, pp. 603–655, May 2023, doi: 10.1287/moor.2022.1275.

\[33\] Bundesnetzagentur, “SMARD – Strommarktdaten,” SMARD.de. \[Online\]. Available: https://www.smard.de. Accessed: Oct. 30, 2026.

\[34\] B. Burger, “Energy-Charts,” Fraunhofer Institute for Solar Energy Systems ISE, Freiburg, Germany. \[Online\]. Available: https://www.energy-charts.info. Accessed: Oct. 30, 2026.

\[35\] Modo Energy, “German aFRR market data explained: How Ko can analyse it.” \[Online\]. Available: https://modoenergy.com/research/en/germany-afrr-data-explained-ko-analysis. Accessed: Oct. 30, 2026.

\[36\] C. Meili, “High Downward aFRR Prices Can Drive Additional Income for Solar Assets in Germany – Pexapark Analysis,” Pexapark, Jan. 6, 2026. \[Online\]. Available: https://pexapark.com/blog/high-downward-afrr-prices-can-drive-additional-income-for-solar-assets-in-germany-pexapark-analysis/. Accessed: Oct. 30, 2026.

\[37\] Q. Huangfu and J. A. J. Hall, “Parallelizing the dual revised simplex method,” Math. Program. Comput., vol. 10, no. 1, pp. 119–142, 2018, doi: 10.1007/s12532-017-0130-5.

\[38\] P. Virtanen et al., “SciPy 1.0: Fundamental algorithms for scientific computing in Python,” Nat. Methods, vol. 17, pp. 261–272, 2020, doi: 10.1038/s41592-019-0686-2.
