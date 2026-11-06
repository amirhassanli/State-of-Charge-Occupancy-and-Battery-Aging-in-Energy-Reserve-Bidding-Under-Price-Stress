import numpy as np
from scipy import stats

def wilson(k, n, conf=0.95):
    z = stats.norm.ppf(0.5+conf/2); p = k/n
    d = 1+z*z/n; c = p+z*z/(2*n); h = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return (c-h)/d, (c+h)/d

def clopper_pearson(k, n, conf=0.95):
    a = 1-conf
    lo = 0.0 if k == 0 else stats.beta.ppf(a/2, k, n-k+1)
    hi = 1.0 if k == n else stats.beta.ppf(1-a/2, k+1, n-k)
    return lo, hi

def block_bootstrap_mean(x, block=7, B=4000, seed=0, conf=0.95):
    """Moving-block bootstrap CI for the mean of a (serially dependent) daily series."""
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x); rng = np.random.default_rng(seed)
    nb = int(np.ceil(n/block)); m = np.empty(B)
    for i in range(B):
        st = rng.integers(0, max(n-block+1, 1), nb)
        m[i] = np.concatenate([x[s:s+block] for s in st])[:n].mean()
    return float(x.mean()), tuple(np.quantile(m, [(1-conf)/2, 1-(1-conf)/2]))

def paired_summary(a, b):
    d = np.asarray(a, float)-np.asarray(b, float); d = d[~np.isnan(d)]
    out = dict(n=len(d), mean=d.mean(), median=np.median(d))
    out["mean_ci_block"] = block_bootstrap_mean(d)[1]
    try: out["wilcoxon_p"] = stats.wilcoxon(d).pvalue
    except ValueError: out["wilcoxon_p"] = np.nan
    return out
