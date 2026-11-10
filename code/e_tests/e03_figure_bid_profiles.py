"""E3 - Reconstructed 24 h bid and scenario-mean SoC profiles for one day."""
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from common import *
def main(day="2026-05-01", K=30):
    _, _, _, sc, real = load(day, K); pl = plant()
    fig, ax = plt.subplots(2, 2, figsize=(10, 6.2), sharex=True); h = np.arange(24)
    for law, ls in zip(LAWS, ("-", "--", ":")):
        for flag, col in ((False, "tab:blue"), (True, "tab:red")):
            o = optimise(pl, sc, law, flag, exclusive=True); b = o["bid"]
            ax[0,0].plot(h, b["pda"], ls, color=col, label=f"{law}-{'P1' if flag else 'B2'}")
            if flag:
                ax[0,1].plot(h, b["rup"], ls, color="tab:red"); ax[1,0].plot(h, -b["rdn"], ls, color="tab:green")
                soc = np.stack([o["res"].x[s["E"]] for s in o["spec"]["sol"]])
                ax[1,1].plot(h, soc.mean(axis=0), ls, color="tab:purple", label=law)
    ax[1,1].set_ylabel("scenario-mean SoC [MWh]")
    ax[0,0].set_ylabel("p_DA [MW] (+sale)"); ax[0,1].set_ylabel("r_up [MW]"); ax[1,0].set_ylabel("-r_dn [MW]")
    ax[0,0].legend(fontsize=7, ncol=2); ax[1,1].legend(fontsize=7); [a.set_xlabel("hour") for a in ax[1]]
    fig.suptitle(f"First-stage bids and scenario-mean SoC, {day}, K={K} (exclusive MILP reconstruction)"); fig.tight_layout()
    fig.savefig("results/E03_bid_profiles.png", dpi=300); print("saved results/E03_bid_profiles.png")
if __name__ == "__main__":
    os.makedirs("results", exist_ok=True); main()
