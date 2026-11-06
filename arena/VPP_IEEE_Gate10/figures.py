"""
Figures for the VPP bidding paper — each function takes real data as input.
Two are runnable now with values already validated in the paper (Sec. IV-D, IV-F);
the rest are ready-to-use templates: call them once the OOS/benchmark numbers exist.
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
plt.rcParams.update({"font.size": 11, "figure.dpi": 150})

# 1) Asymptotic tail dependence of the Student-t copula (theory only — no data needed)
def fig_tail_dependence(nus=(2, 4, 8, 18.55, 32, 64), path="fig1_tail_dependence.png"):
    rho = np.linspace(-0.999, 0.999, 400)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for nu in nus:
        t = -np.sqrt((nu + 1) * (1 - rho) / (1 + rho))
        lam = 2 * stats.t.cdf(t, df=nu + 1)
        ax.plot(rho, lam, label=f"ν={nu:g}")
    ax.set_xlabel("ρ"); ax.set_ylabel("λ_U = λ_L")
    ax.set_title("Asymptotic tail dependence of the Student-t copula")
    ax.legend(title="ν", fontsize=9); fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 2) Fitted copula: simulated dependence structure, Gaussian vs Student-t (uses fitted ν, R)
def fig_copula_scatter(R, nu=18.5515, n=8000, path="fig2_copula_fit.png", seed=0):
    rng = np.random.default_rng(seed)
    d = R.shape[0]
    z_g = rng.multivariate_normal(np.zeros(d), R, n)
    u_g = stats.norm.cdf(z_g)
    g = rng.chisquare(nu, n) / nu
    z_t = rng.multivariate_normal(np.zeros(d), R, n) / np.sqrt(g)[:, None]
    u_t = stats.t.cdf(z_t, df=nu)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, u, ttl in zip(axes, [u_g, u_t], ["Gaussian copula (fit)", "Student-t copula (fit)"]):
        ax.scatter(u[:, 0], u[:, 1], s=4, alpha=0.25, color="orange")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_xlabel("u₁"); ax.set_ylabel("u₂"); ax.set_title(ttl)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 3) Kendall's tau dependence heatmap across the 5 uncertain variables
def fig_kendall_heatmap(tau_matrix, labels, path="fig3_kendall_heatmap.png"):
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    im = ax.imshow(tau_matrix, cmap="PuOr_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right"); ax.set_yticklabels(labels)
    fig.colorbar(im, label="Kendall's τ"); ax.set_title("Forecast-error dependence (Kendall's τ)")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 4) Temporal-dependence validation: actual vs generated ACF by lag
def fig_acf_validation(lags, acf_actual, acf_generated, path="fig4_acf_validation.png"):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(lags, acf_actual, "o-", label="Actual", color="black")
    ax.plot(lags, acf_generated, "s--", label="Generated (scenarios)", color="tab:blue")
    ax.set_xlabel("Lag"); ax.set_ylabel("Autocorrelation"); ax.legend()
    ax.set_title("Temporal-dependence validation (pooled ACF)")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 5) Scenario fan chart: reduced scenarios vs realized trajectory, one variable/day
def fig_scenario_fan(hours, scenarios, realized, forecast, path="fig5_scenario_fan.png"):
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(hours, scenarios.T, color="gray", alpha=0.15, lw=0.8)
    ax.plot(hours, forecast, "--", color="tab:red", label="Point forecast")
    ax.plot(hours, realized, color="black", lw=2, label="Realized")
    ax.set_xlabel("Hour"); ax.set_ylabel("Value"); ax.legend()
    ax.set_title("Reduced scenario set vs. realized trajectory")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 6) Benchmark comparison bars (B0/B1/B2/P1) — profit, CVaR, imbalance (fill after OOS run)
def fig_benchmark_bars(models, profit, cvar95, imbalance, path="fig6_benchmark_bars.png"):
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6))
    for ax, vals, ttl in zip(axes, [profit, cvar95, imbalance], ["Realized profit", "CVaR₉₅", "Imbalance energy"]):
        ax.bar(models, vals, color=["#888", "#4C72B0", "#DD8452", "#55A868"][:len(models)])
        ax.set_title(ttl)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 7) Risk-return trade-off (efficient-frontier style) across benchmark models
def fig_risk_return(models, cvar95, profit, path="fig7_risk_return.png"):
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    ax.scatter(cvar95, profit, s=90)
    for m, x, y in zip(models, cvar95, profit):
        ax.annotate(m, (x, y), textcoords="offset points", xytext=(6, 4))
    ax.set_xlabel("CVaR₉₅ loss"); ax.set_ylabel("Realized profit")
    ax.set_title("Risk–return positioning of B0/B1/B2/P1")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

# 8) Sensitivity curves: profit & CVaR vs risk-aversion λ, and vs scenario count K
def fig_sensitivity(lam, profit_lam, cvar_lam, K, profit_K, runtime_K, path="fig8_sensitivity.png"):
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4))
    ax = axes[0]; ax.plot(lam, profit_lam, "o-", label="Profit")
    ax2 = ax.twinx(); ax2.plot(lam, cvar_lam, "s--", color="tab:red", label="CVaR₉₅")
    ax.set_xlabel("λ (risk aversion)"); ax.set_title("Sensitivity to λ")
    ax = axes[1]; ax.plot(K, profit_K, "o-", label="Profit")
    ax2 = ax.twinx(); ax2.plot(K, runtime_K, "s--", color="tab:green", label="Runtime (s)")
    ax.set_xlabel("K (scenario count)"); ax.set_title("Sensitivity to K")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    # --- Runnable now, using values already validated in the paper (Sec. IV-D) ---
    fig_tail_dependence()
    R_fit = np.array([[1, .55, .40, -.30, -.20],
                       [.55, 1, .60, -.25, -.18],
                       [.40, .60, 1, -.20, -.15],
                       [-.30, -.25, -.20, 1, .35],
                       [-.20, -.18, -.15, .35, 1]])  # placeholder R — replace with fitted matrix
    fig_copula_scatter(R_fit, nu=18.5515)
    print("Generated: fig1_tail_dependence.png, fig2_copula_fit.png")
    print("Templates ready (call with real arrays): fig_kendall_heatmap, fig_acf_validation,")
    print("fig_scenario_fan, fig_benchmark_bars, fig_risk_return, fig_sensitivity")
