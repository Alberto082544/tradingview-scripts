"""Validacion completa del combo ORB GBPJPY ganador.
ORB Londres 7:00 UTC, SL=1.5*ATR, RR=4, Long only.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'GBPJPY_M15_dukas.csv')
INITIAL = 50_000
PIP = 0.01
PIP_VAL = 6.5

PARAMS = {
    'OrbStartHour': 7, 'SLMult': 1.5, 'RR': 4.0,
    'MinRng': 10, 'MaxRng': 100, 'LongOnly': True
}


def run_bt(df_sub, p):
    trades = []
    equity = INITIAL
    orb_h = orb_l = None
    last_date = None
    traded_today = False
    pos = None

    o = df_sub['open'].values; h = df_sub['high'].values
    l = df_sub['low'].values;  c = df_sub['close'].values
    atr = df_sub['atr'].values
    idx = df_sub.index

    for i in range(20, len(df_sub)):
        dt = idx[i]
        d = dt.date(); hr = dt.hour; mn = dt.minute
        if d != last_date:
            orb_h = None; orb_l = None
            traded_today = False
            last_date = d
        if pos is not None:
            ep = et = None
            if pos['dir']=='long':
                if l[i]<=pos['sl']: ep,et=pos['sl'],'SL'
                elif h[i]>=pos['tp']: ep,et=pos['tp'],'TP'
            else:
                if h[i]>=pos['sl']: ep,et=pos['sl'],'SL'
                elif l[i]<=pos['tp']: ep,et=pos['tp'],'TP'
            if ep:
                pnl = ((ep-pos['entry']) if pos['dir']=='long' else (pos['entry']-ep))/PIP*PIP_VAL*pos['lots']
                equity += pnl
                trades.append((pos['entry_dt'], dt, pos['dir'], round(pnl,2), round(equity,2)))
                pos = None
            if pos is not None: continue
        if hr == p['OrbStartHour'] and mn in (0,15,30,45):
            if orb_h is None or h[i] > orb_h: orb_h = h[i]
            if orb_l is None or l[i] < orb_l: orb_l = l[i]
            continue
        if orb_h is None or traded_today: continue
        if hr < p['OrbStartHour']+1 or hr >= p['OrbStartHour']+8: continue
        atr1 = atr[i]
        if np.isnan(atr1) or atr1<=0: continue
        rng = orb_h - orb_l
        if rng < p['MinRng']*PIP or rng > p['MaxRng']*PIP: continue
        if c[i] > orb_h and c[i-1] <= orb_h:
            entry = c[i]
            sl = orb_l - p['SLMult'] * atr1
            sld = entry - sl
            if sld <= 0: continue
            tp = entry + sld * p['RR']
            lots = max(0.01, min(round((equity*0.005)/(sld/PIP*PIP_VAL),2), 4.0))
            pos = {'dir':'long','entry':entry,'sl':sl,'tp':tp,'lots':lots,'entry_dt':dt}
            traded_today = True
    return pd.DataFrame(trades, columns=['entry_dt','exit_dt','dir','pnl','equity'])


def metrics_year(t, year):
    t2 = t.copy()
    t2['entry_dt'] = pd.to_datetime(t2['entry_dt'])
    t_y = t2[t2['entry_dt'].dt.year == year]
    if len(t_y) == 0: return None
    pnl = t_y['pnl'].sum()
    wins = t_y.loc[t_y['pnl']>0,'pnl']; loss = t_y.loc[t_y['pnl']<0,'pnl']
    pf = wins.sum()/abs(loss.sum()) if len(loss) and loss.sum()!=0 else 0
    eq = INITIAL + t_y.sort_values('entry_dt')['pnl'].cumsum().values
    eq = np.concatenate([[INITIAL], eq])
    pk = np.maximum.accumulate(eq)
    dd = abs(((eq-pk)/pk).min())*100
    return {'year':year, 'n':len(t_y), 'pf':round(pf,2),
            'dd':round(dd,2), 'ann':round(pnl/INITIAL*100,2)}


def metrics(t):
    if len(t)==0: return {'n':0,'pf':0,'dd_pct':0,'ann_pct':0,'pnl':0}
    n = len(t); pnl = t['pnl'].sum()
    wins = t.loc[t['pnl']>0,'pnl']; loss = t.loc[t['pnl']<0,'pnl']
    pf = wins.sum()/abs(loss.sum()) if len(loss) and loss.sum()!=0 else 0
    eq = np.concatenate([[INITIAL], t['equity'].values])
    pk = np.maximum.accumulate(eq)
    dd = abs(((eq-pk)/pk).min())*100
    yrs = (pd.to_datetime(t['exit_dt'].iloc[-1]) - pd.to_datetime(t['entry_dt'].iloc[0])).days/365.25
    ann = ((INITIAL+pnl)/INITIAL)**(1/max(yrs,0.01)) - 1
    return {'n':n,'pf':round(pf,2),'dd_pct':round(dd,2),'ann_pct':round(ann*100,2),'pnl':round(pnl,0)}


def mc_dd(pnls, n=1000):
    rng = np.random.default_rng(42)
    dds = np.empty(n)
    for i in range(n):
        order = rng.permutation(len(pnls))
        eq = INITIAL + np.cumsum(pnls[order])
        peak = np.maximum.accumulate(eq)
        dds[i] = ((eq-peak)/peak).min()*-100
    return {'p50':np.percentile(dds,50), 'p95':np.percentile(dds,95),
            'p99':np.percentile(dds,99), 'max':dds.max()}


def main():
    print("="*78)
    print("  VALIDACION  ORB GBPJPY Londres 7UTC SL=1.5xATR RR=4 Long")
    print("="*78)
    df = pd.read_csv(DATA, index_col=0, parse_dates=True)
    hl = df['high']-df['low']
    hc = (df['high']-df['close'].shift()).abs()
    lc = (df['low']-df['close'].shift()).abs()
    tr = pd.concat([hl,hc,lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    df_is  = df.loc[:'2021-12-31']
    df_oos = df.loc['2022-01-01':]
    t_is = run_bt(df_is, PARAMS); t_oos = run_bt(df_oos, PARAMS)
    t_full = pd.concat([t_is, t_oos], ignore_index=True)
    m_is = metrics(t_is); m_oos = metrics(t_oos)

    t_full['entry_dt'] = pd.to_datetime(t_full['entry_dt'])
    years = sorted(t_full['entry_dt'].dt.year.unique())
    yearly = [metrics_year(t_full, y) for y in years if metrics_year(t_full, y)]
    print(f"\n  YEAR-BY-YEAR:")
    print(f"  {'Año':<6} {'N':>4} {'PF':>6} {'DD%':>6} {'Ann%':>8}")
    for y in yearly:
        f = 'OK' if y['ann']>0 else 'X'
        print(f"  {y['year']:<6} {y['n']:>4} {y['pf']:>6} {y['dd']:>6} {y['ann']:>+8.2f}  {f}")

    pos = sum(1 for y in yearly if y['ann']>0)
    peor = min(y['ann'] for y in yearly)
    mc = mc_dd(t_oos['pnl'].values)
    print(f"\n  MONTE CARLO OOS (1000 sims):")
    print(f"    DD real: {m_oos['dd_pct']}%")
    print(f"    P50: {mc['p50']:.2f}%  P95: {mc['p95']:.2f}%  P99: {mc['p99']:.2f}%  Max: {mc['max']:.2f}%")

    wf = m_oos['pf']/m_is['pf'] if m_is['pf']>0 else 0
    ann_r = m_oos['ann_pct']/m_is['ann_pct'] if m_is['ann_pct']!=0 else 0
    dd_r = m_oos['dd_pct']/m_is['dd_pct'] if m_is['dd_pct']!=0 else 99

    c1 = wf >= 0.85
    c2 = pos >= len(yearly)*10/12
    c3 = ann_r >= 0.5
    c4 = dd_r <= 2.0
    c5 = m_is['n'] >= 200 and m_oos['n'] >= 100
    c6 = peor >= -20
    c7 = mc['p95'] < 10.0

    def m(x): return 'OK' if x else 'X'
    print(f"\n  CHECKLIST 7 PUNTOS:")
    print(f"  1. WF {wf:.3f}>=0.85:           {m(c1)}")
    print(f"  2. {pos}/{len(yearly)} años positivos:        {m(c2)}")
    print(f"  3. OOS/IS Ann {ann_r:.2f}>=0.5:    {m(c3)}")
    print(f"  4. OOS/IS DD {dd_r:.2f}<=2.0:      {m(c4)}")
    print(f"  5. N IS={m_is['n']} OOS={m_oos['n']}: {m(c5)}")
    print(f"  6. Peor año {peor:.1f}% >= -20%:   {m(c6)}")
    print(f"  7. MC P95 {mc['p95']:.1f}% < 10%:    {m(c7)}")
    print(f"\n  VEREDICTO: {sum([c1,c2,c3,c4,c5,c6,c7])}/7 pasados")
    print(f"  Metricas OOS: PF={m_oos['pf']} DD={m_oos['dd_pct']}% Ann={m_oos['ann_pct']}% N={m_oos['n']}")
    print(f"  Profit estimado en $15k: ${15000*m_oos['ann_pct']/100/12:.0f}/mes")


if __name__ == '__main__':
    main()
