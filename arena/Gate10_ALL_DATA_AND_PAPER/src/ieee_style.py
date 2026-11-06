"""IEEE-like matplotlib style for journal figures."""

from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

COL = {
    "B0": "#4477AA",
    "B2": "#EE6677",
    "P1": "#228833",
    "actual": "#000000",
    "forecast": "#CCBB44",
    "grid": "#cfcfcf",
    "accent": "#AA3377",
    "muted": "#BBBBBB",
    "blue2": "#66CCEE",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "navy": "#0072B2",
    "vermilion": "#D55E00",
    "purple": "#CC79A7",
}

MODEL_ORDER = ["B0", "B2", "P1"]
MODEL_LABEL = {
    "B0": "B0  EV deterministic",
    "B1": "B1",
    "B2": "B2  Stochastic mean–CVaR",
    "P1": "P1  Proposed (energy–reserve)",
}
MODEL_SHORT = {"B0": "B0 (EV)", "B2": "B2 (CVaR)", "P1": "P1 (proposed)"}


def apply_ieee():
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["DejaVu Serif", "STIX", "Times New Roman", "Times"],
            "mathtext.fontset": "stix",
            "font.size": 8.5,
            "axes.labelsize": 9,
            "axes.titlesize": 9.5,
            "legend.fontsize": 7.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "axes.linewidth": 0.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "lines.linewidth": 1.15,
            "lines.markersize": 4.5,
            "grid.color": "#d0d0d0",
            "grid.linewidth": 0.45,
            "grid.alpha": 0.9,
            "legend.frameon": False,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.04,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def savefig(fig, path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def hours():
    return np.arange(24)


def hour_labels(step=2):
    return [f"{h:02d}" for h in range(0, 24, step)]


def disable_internal_titles():
    """IEEE: captions live below the figure, not inside it."""
    import matplotlib.pyplot as plt
    def _blank_title(self, *args, **kwargs):
        return plt.Artist.set_label(self, "")
    plt.Axes.set_title = lambda self, *a, **k: None
    plt.Figure.suptitle = lambda self, *a, **k: None
