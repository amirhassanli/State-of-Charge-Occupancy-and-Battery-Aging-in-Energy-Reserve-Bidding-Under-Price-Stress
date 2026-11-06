"""Reproducible ex-post battery-aging mechanism audit on SMARD hourly prices.

This is deliberately a battery-only diagnostic, NOT a forecast or realized VPP bid.
It uses realized DA prices for each local market day to isolate the dispatch mechanism.
It uses MILP charge/discharge exclusivity, cyclic SoC, and the three aging costs.
"""
from pathlib import Path
import json, warnings, time
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix, csr_matrix

ROOT=Path(__file__).resolve().parent
IN=ROOT/'SMARD_data_2021_2026.csv'
OUT=ROOT/'core_model_audit_results'
OUT.mkdir(exist_ok=True)
ETA_C=ETA_D=0.95
P_MAX=2.5
E_MAX=5.0
SOC_MIN=0.1*E_MAX
SOC_MAX=0.9*E_MAX
THROUGHPUT_EUR_MWH=1.5
KAPPA=np.array([0.247]*2+[0.493]*3+[0.822]*3,dtype=float)
BAND_WIDTH=(SOC_MAX-SOC_MIN)/8
DOD_WIDTH=np.array([0.20,0.30,0.30,0.20])
DOD_SLOPE=np.array([10.,40.,80.,120.])

raw=pd.read_csv(IN)
raw['ts_utc']=pd.to_datetime(raw['timestamp_utc'],utc=True,errors='raise')
raw['ts_berlin']=raw['ts_utc'].dt.tz_convert('Europe/Berlin')
raw['local_date']=raw['ts_berlin'].dt.date
raw=raw.sort_values('ts_utc').reset_index(drop=True)
assert raw.ts_utc.is_monotonic_increasing and not raw.ts_utc.duplicated().any()
assert raw['DA_price_EUR_per_MWh'].notna().all()

# Variable indexing for a daily MILP. All variables continuous except charge-mode z.
def solve_day(prices, law, kappa_scale=1.0, mip=True):
    p=np.asarray(prices,dtype=float); H=len(p)
    # c(H), d(H), E(H+1), z(H); DoD: emax, emin, segment depth(4); ReLCCA: band fill(H*8)
    idx={}; n=0
    for name,size in [('c',H),('d',H),('E',H+1),('z',H)]: idx[name]=np.arange(n,n+size); n+=size
    if law=='Xu':
        idx['emax']=np.array([n]); n+=1
        idx['emin']=np.array([n]); n+=1
        idx['depth']=np.arange(n,n+4); n+=4
    if law=='ReLCCA': idx['band']=np.arange(n,n+H*8).reshape(H,8); n+=H*8
    cobj=np.zeros(n)
    cobj[idx['c']]=p+THROUGHPUT_EUR_MWH
    cobj[idx['d']]=-p+THROUGHPUT_EUR_MWH
    # For minimization, add convex daily DoD cost.
    if law=='Xu': cobj[idx['depth']]=DOD_SLOPE
    # Occupancy/calendar exposure paid per hour for energy stored in each band.
    if law=='ReLCCA': cobj[idx['band']]=np.tile(KAPPA*kappa_scale,(H,1))
    integrality=np.zeros(n,dtype=int); integrality[idx['z']]=1
    lb=np.zeros(n); ub=np.full(n,np.inf)
    lb[idx['c']]=0; ub[idx['c']]=P_MAX
    lb[idx['d']]=0; ub[idx['d']]=P_MAX
    lb[idx['E']]=SOC_MIN; ub[idx['E']]=SOC_MAX
    lb[idx['z']]=0; ub[idx['z']]=1
    if law=='Xu':
        lb[idx['emax']]=SOC_MIN; ub[idx['emax']]=SOC_MAX
        lb[idx['emin']]=SOC_MIN; ub[idx['emin']]=SOC_MAX
        lb[idx['depth']]=0; ub[idx['depth']]=DOD_WIDTH
    if law=='ReLCCA':
        lb[idx['band']]=0; ub[idx['band']]=BAND_WIDTH
    rows=[]; lows=[]; highs=[]
    def add(coeff,lo=-np.inf,hi=np.inf):
        rows.append(coeff); lows.append(lo); highs.append(hi)
    # SOC dynamics: E[t+1]-E[t]-eta_c*c+d/eta_d=0
    for t in range(H):
        a={idx['E'][t+1]:1,idx['E'][t]:-1,idx['c'][t]:-ETA_C,idx['d'][t]:1/ETA_D}
        add(a,0,0)
        # mutually exclusive modes: c <= P*z; d <= P*(1-z)
        add({idx['c'][t]:1,idx['z'][t]:-P_MAX},hi=0)
        add({idx['d'][t]:1,idx['z'][t]:P_MAX},hi=P_MAX)
    # cyclic boundary
    add({idx['E'][0]:1,idx['E'][H]:-1},0,0)
    if law=='Xu':
        for t in range(H+1):
            add({idx['E'][t]:1,idx['emax'][0]:-1},hi=0)
            add({idx['E'][t]:1,idx['emin'][0]:-1},lo=0)
        # sum depth-segment fractions = (emax-emin)/E_MAX
        a={idx['depth'][j]:1 for j in range(4)}
        a[idx['emax'][0]]=-1/E_MAX; a[idx['emin'][0]]=1/E_MAX
        add(a,0,0)
    if law=='ReLCCA':
        for t in range(H):
            a={idx['E'][t]:1}
            for j in range(8): a[idx['band'][t,j]]=-1
            add(a,SOC_MIN,SOC_MIN)
    A=lil_matrix((len(rows),n),dtype=float)
    for i,row in enumerate(rows):
        for j,v in row.items(): A[i,j]=v
    cons=LinearConstraint(csr_matrix(A),np.asarray(lows),np.asarray(highs))
    res=milp(c=cobj,integrality=integrality if mip else np.zeros(n,dtype=int),
             bounds=Bounds(lb,ub),constraints=cons,
             options={'time_limit':10.0,'mip_rel_gap':1e-8})
    if not res.success or res.x is None:
        return {'success':False,'status':int(res.status),'message':res.message}
    x=res.x
    charge=x[idx['c']]; discharge=x[idx['d']]; energy=x[idx['E']]
    revenue=float(np.dot(p,discharge-charge))
    throughput_cost=float(THROUGHPUT_EUR_MWH*np.sum(charge+discharge))
    dod_cost=float(np.dot(DOD_SLOPE,x[idx['depth']])) if law=='Xu' else 0.0
    occupancy_cost=float(np.sum(x[idx['band']]*KAPPA*kappa_scale)) if law=='ReLCCA' else 0.0
    return {'success':True,'status':int(res.status),'profit_eur':revenue-throughput_cost-dod_cost-occupancy_cost,
            'energy_revenue_eur':revenue,'throughput_cost_eur':throughput_cost,
            'dod_cost_eur':dod_cost,'occupancy_cost_eur':occupancy_cost,
            'throughput_mwh':float(np.sum(charge+discharge)),
            'max_simultaneous_mw':float(np.max(np.minimum(charge,discharge))),
            'soc_min_mwh':float(np.min(energy)),'soc_max_mwh':float(np.max(energy)),
            'charge_mwh':float(np.sum(charge)),'discharge_mwh':float(np.sum(discharge)),
            'hours':H}

# Full-sample empirical price regime diagnostics
price=raw['DA_price_EUR_per_MWh']
raw['negative_hour']=price<0
raw['deep_negative_hour']=price<=-50
raw['local_year']=raw['ts_berlin'].dt.year
raw['local_month']=raw['ts_berlin'].dt.month
annual=raw.groupby('local_year').agg(hours=('DA_price_EUR_per_MWh','size'),mean_DA=('DA_price_EUR_per_MWh','mean'),
    min_DA=('DA_price_EUR_per_MWh','min'),negative_hours=('negative_hour','sum'),deep_negative_hours=('deep_negative_hour','sum'),
    PV_mean_MW=('PV_generation_MW','mean'),wind_mean_MW=('Wind_generation_MW','mean'),load_mean_MW=('Grid_load_MW','mean')).reset_index()
annual.to_csv(OUT/'annual_market_diagnostics.csv',index=False)

# Local-day groups respect 23/25-hour DST market days.
days=[]
for date,g in raw.groupby('local_date',sort=True):
    g=g.sort_values('ts_utc')
    if len(g) not in (23,24,25):
        continue
    prices=g['DA_price_EUR_per_MWh'].to_numpy(float)
    # Paired day-by-day MILP for the three aging representations.
    results={law:solve_day(prices,law) for law in ['Throughput','Xu','ReLCCA']}
    if not all(v.get('success',False) for v in results.values()):
        days.append({'date':str(date),'hours':len(g),'min_price':prices.min(),'max_price':prices.max(),'solve_ok':False})
        continue
    row={'date':str(date),'hours':len(g),'min_price':float(prices.min()),'mean_price':float(prices.mean()),
         'negative_hours':int(np.sum(prices<0)),'deep_negative_hours':int(np.sum(prices<=-50)),
         'PV_mean_MW':float(g.PV_generation_MW.mean()),'wind_mean_MW':float(g.Wind_generation_MW.mean()),
         'load_mean_MW':float(g.Grid_load_MW.mean()),'solve_ok':True}
    for law,v in results.items():
        for k,val in v.items():
            if k not in ('success','status','message'): row[f'{law}_{k}']=val
    row['ReLCCA_minus_Throughput_EUR']=results['ReLCCA']['profit_eur']-results['Throughput']['profit_eur']
    row['ReLCCA_minus_Xu_EUR']=results['ReLCCA']['profit_eur']-results['Xu']['profit_eur']
    row['Xu_minus_Throughput_EUR']=results['Xu']['profit_eur']-results['Throughput']['profit_eur']
    days.append(row)
    if len(days)%100==0: print('solved local days',len(days),flush=True)
resdf=pd.DataFrame(days)
resdf.to_csv(OUT/'daily_paired_dispatch_results.csv',index=False)

ok=resdf[resdf.solve_ok==True].copy()
ok['year']=pd.to_datetime(ok.date).dt.year
ok['negative_day']=ok.min_price<0
ok['deep_negative_day']=ok.min_price<=-50
summary=ok.groupby('year').agg(days=('date','count'),negative_days=('negative_day','sum'),deep_negative_days=('deep_negative_day','sum'),
    throughput_profit=('Throughput_profit_eur','sum'),xu_profit=('Xu_profit_eur','sum'),relcca_profit=('ReLCCA_profit_eur','sum'),
    mean_relcca_minus_throughput=('ReLCCA_minus_Throughput_EUR','mean'),median_relcca_minus_throughput=('ReLCCA_minus_Throughput_EUR','median'),
    positive_relcca_diff_share=('ReLCCA_minus_Throughput_EUR',lambda s:float((s>1e-6).mean())),
    negative_relcca_diff_share=('ReLCCA_minus_Throughput_EUR',lambda s:float((s<-1e-6).mean()))).reset_index()
summary.to_csv(OUT/'annual_model_comparison.csv',index=False)

# Event-study summaries. Do not call these probabilities; this is a finite historical census.
event_rows=[]
for label,mask in [('all_days',np.ones(len(ok),dtype=bool)),('negative_min',ok.min_price<0),('deep_negative_min',ok.min_price<=-50),('extreme_min_le_minus200',ok.min_price<=-200)]:
    z=ok.loc[mask]
    for metric in ['ReLCCA_minus_Throughput_EUR','ReLCCA_minus_Xu_EUR','Xu_minus_Throughput_EUR']:
        s=z[metric].dropna()
        event_rows.append({'subset':label,'metric':metric,'n_days':len(s),'mean_eur':s.mean() if len(s) else np.nan,
            'median_eur':s.median() if len(s) else np.nan,'q05_eur':s.quantile(.05) if len(s) else np.nan,
            'q25_eur':s.quantile(.25) if len(s) else np.nan,'q75_eur':s.quantile(.75) if len(s) else np.nan,
            'q95_eur':s.quantile(.95) if len(s) else np.nan,'share_positive':(s>0).mean() if len(s) else np.nan,
            'share_negative':(s<0).mean() if len(s) else np.nan})
pd.DataFrame(event_rows).to_csv(OUT/'event_study_summary.csv',index=False)

# Targeted kappa scale sweep: all days with min DA <= -50 EUR/MWh; same realized price paths.
stress=raw.groupby('local_date').filter(lambda g: len(g) in (23,24,25) and g['DA_price_EUR_per_MWh'].min()<=-50)
stress_dates=sorted(stress.local_date.unique())
sweep=[]
for date in stress_dates:
    g=raw[raw.local_date==date].sort_values('ts_utc'); p=g.DA_price_EUR_per_MWh.to_numpy(float)
    for scale in [0.1,0.25,0.5,1.0,2.0,5.0,10.0]:
        r=solve_day(p,'ReLCCA',kappa_scale=scale)
        if r.get('success'):
            sweep.append({'date':str(date),'min_price':float(p.min()),'kappa_scale':scale,**{k:v for k,v in r.items() if k not in ('success','status','message')}})
pd.DataFrame(sweep).to_csv(OUT/'relcca_kappa_stress_sweep.csv',index=False)

# Paired moving-block bootstrap for daily profit differences. Blocks preserve short-run
# dependence in the ordered daily sequence; this quantifies finite-panel uncertainty,
# not uncertainty from model misspecification or missing reserve/settlement data.
rng=np.random.default_rng(20261020)
def moving_block_ci(values, block_len=30, replicates=10000):
    x=np.asarray(values,dtype=float); n=len(x)
    nblocks=int(np.ceil(n/block_len))
    starts=rng.integers(0, n-block_len+1, size=(replicates,nblocks))
    offsets=np.arange(block_len)
    indices=(starts[:,:,None]+offsets[None,None,:]).reshape(replicates,-1)[:,:n]
    means=x[indices].mean(axis=1)
    return np.quantile(means,[0.025,0.5,0.975]).tolist()
boot_rows=[]
for col in ['ReLCCA_minus_Throughput_EUR','ReLCCA_minus_Xu_EUR','Xu_minus_Throughput_EUR']:
    lo,med,hi=moving_block_ci(ok[col].to_numpy())
    boot_rows.append({'paired_difference':col,'n_days':len(ok),'mean_EUR_per_day':float(ok[col].mean()),
                      'median_EUR_per_day':float(ok[col].median()),'moving_block_length_days':30,
                      'bootstrap_replicates':10000,'moving_block_95pct_low':float(lo),'bootstrap_median':float(med),
                      'moving_block_95pct_high':float(hi)})
pd.DataFrame(boot_rows).to_csv(OUT/'paired_difference_block_bootstrap.csv',index=False)

# Integrity report and manuscript-ready summary.
report={
 'input_file':IN.name,'rows':int(len(raw)),'start_utc':str(raw.ts_utc.min()),'end_utc':str(raw.ts_utc.max()),
 'days_solved':int(len(ok)),'days_failed':int((resdf.solve_ok==False).sum()),
 'negative_price_hours':int((raw.DA_price_EUR_per_MWh<0).sum()),'deep_negative_hours_le_minus50':int((raw.DA_price_EUR_per_MWh<=-50).sum()),
 'negative_price_days':int((ok.min_price<0).sum()),'deep_negative_days':int((ok.min_price<=-50).sum()),
 'simultaneous_charge_discharge_days_throughput':int((ok.Throughput_max_simultaneous_mw>1e-6).sum()),
 'simultaneous_charge_discharge_days_xu':int((ok.Xu_max_simultaneous_mw>1e-6).sum()),
 'simultaneous_charge_discharge_days_relcca':int((ok.ReLCCA_max_simultaneous_mw>1e-6).sum()),
 'interpretation':'Ex-post perfect-foresight battery-only diagnostic using realized day-ahead prices; not a forecast, not a reserve bid, not realized VPP profit.',
 'assumptions':{'power_MW':P_MAX,'energy_MWh':E_MAX,'soc_min_MWh':SOC_MIN,'soc_max_MWh':SOC_MAX,'eta_charge':ETA_C,'eta_discharge':ETA_D,
 'throughput_cost_EUR_per_MWh':THROUGHPUT_EUR_MWH,'ReLCCA_kappa_EUR_per_MWh_hour':KAPPA.tolist(),'Xu_segment_widths':DOD_WIDTH.tolist(),'Xu_slopes_EUR_per_depth':DOD_SLOPE.tolist(),
 'charge_discharge_exclusivity':'binary MILP'}
}
(OUT/'audit_report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
print('\nANNUAL MODEL COMPARISON\n',summary.to_string(index=False))
print('\nEVENT STUDY\n',pd.DataFrame(event_rows).to_string(index=False))
