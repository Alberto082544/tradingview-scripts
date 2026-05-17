"""Optimizacion paramétrica de los combos que tenían suficiente N en el test base:
  - #2 Jasper OB EURUSD: grid RR + BufferATR + opciones de filtros
  - #5 ORB GBPJPY: grid sesion + rangos + multiplicador SL + RR
"""
import sys, os, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000


# ============================================================
# OPTIMIZACION #2: Jasper OB EURUSD
# ============================================================
def opt_jasper_eurusd():
    print("\n" + "="*88)
    print("  OPT #2: Jasper OB EURUSD — grid RR + BufferATR + filtros")
    print("="*88)
    from strategies.jasper_ob_filtered_m15 import (
        add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

    df = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'),
                     index_col=0, parse_dates=True)

    GRID = {
        'RR':            [1.5, 2.0, 2.5, 3.0],
        'BufferATR':     [0.3, 0.5, 1.0],
        'UseEMA200H4':   [1],
        'UseWick':       [0, 1],
        'UseADXH4':      [0, 1],
        'UseVWAP':       [0, 1],
        'UseStoch':      [0, 1],
    }

    keys = list(GRID.keys())
    combos = [dict(zip(keys, v)) for v in itertools.product(*GRID.values())]
    print(f"  Total combos: {len(combos)}")

    results = []
    for i, c in enumerate(combos, 1):
        p = {**DEFAULT_PARAMS, **c}
        try:
            df_ind = add_indicators(df, p)
            df_is  = df_ind.loc[:'2021-12-31']
            df_oos = df_ind.loc['2022-01-01':]
            t_is  = run_backtest(df_is,  p, INITIAL, pip=0.0001, pip_val=10.0)
            t_oos = run_backtest(df_oos, p, INITIAL, pip=0.0001, pip_val=10.0)
            m_is  = compute_metrics(t_is,  INITIAL)
            m_oos = compute_metrics(t_oos, INITIAL)
        except Exception:
            continue
        if m_is['n'] < 100 or m_oos['n'] < 50: continue
        wf = m_oos['pf']/m_is['pf'] if m_is['pf']>0 else 0
        results.append({**c, 'is_pf':m_is['pf'], 'is_dd':m_is['dd_pct'], 'is_n':m_is['n'],
                        'oos_pf':m_oos['pf'], 'oos_dd':m_oos['dd_pct'], 'oos_n':m_oos['n'],
                        'oos_ann':m_oos['ann_pct'], 'wf':round(wf,2)})
        if i % 12 == 0: print(f"    {i}/{len(combos)}...", flush=True)

    rdf = pd.DataFrame(results)
    if len(rdf) == 0:
        print("  Sin resultados validos")
        return
    # Filtrar por criterio + ordenar
    apt = rdf[(rdf['oos_pf']>1.3) & (rdf['oos_dd']<10) & (rdf['wf']>0.85)].sort_values('oos_ann', ascending=False)
    print(f"  Validos: {len(rdf)} | Aptos criterio: {len(apt)}")
    if len(apt):
        print(f"\n  TOP 5:")
        print(apt.head(5).to_string(index=False))
    else:
        print(f"\n  Top 5 por OOS PF (sin criterio estricto):")
        print(rdf.sort_values('oos_pf', ascending=False).head(5).to_string(index=False))


# ============================================================
# OPTIMIZACION #5: ORB GBPJPY
# ============================================================
def opt_orb_gbpjpy():
    print("\n" + "="*88)
    print("  OPT #5: ORB GBPJPY — grid sesion + rango + SL_mult + RR")
    print("="*88)
    df = pd.read_csv(os.path.join(DATA, 'GBPJPY_M15_dukas.csv'),
                     index_col=0, parse_dates=True)
    PIP = 0.01
    PIP_VAL = 6.5
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl,hc,lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    df_is  = df.loc[:'2021-12-31']
    df_oos = df.loc['2022-01-01':]

    def run(df_sub, params):
        orb_h_start = params['OrbStartHour']
        sl_mult = params['SLMult']
        rr      = params['RR']
        min_rng_pips = params['MinRng']
        max_rng_pips = params['MaxRng']
        long_only = params['LongOnly']

        trades = []
        equity = INITIAL
        orb_high = orb_low = None
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
                orb_high = None; orb_low = None
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
                    trades.append((pos['entry_dt'], dt, pnl, equity))
                    pos = None
                if pos is not None: continue
            # ORB durante la primera hora
            if hr == orb_h_start and mn in (0,15,30,45):
                if orb_high is None or h[i] > orb_high: orb_high = h[i]
                if orb_low is None  or l[i] < orb_low:  orb_low = l[i]
                continue
            if orb_high is None or traded_today: continue
            # Ventana operativa: 6h tras ORB
            if hr < orb_h_start+1 or hr >= orb_h_start+8: continue
            atr1 = atr[i]
            if np.isnan(atr1) or atr1 <= 0: continue
            rng = orb_high - orb_low
            if rng < min_rng_pips*PIP or rng > max_rng_pips*PIP: continue
            if c[i] > orb_high and c[i-1] <= orb_high:
                entry = c[i]
                sl = orb_low - sl_mult * atr1
                sld = entry - sl
                if sld <= 0: continue
                tp = entry + sld*rr
                lots = max(0.01, min(round((equity*0.005)/(sld/PIP*PIP_VAL),2), 4.0))
                pos = {'dir':'long','entry':entry,'sl':sl,'tp':tp,'lots':lots,'entry_dt':dt}
                traded_today = True
            elif not long_only and c[i] < orb_low and c[i-1] >= orb_low:
                entry = c[i]
                sl = orb_high + sl_mult * atr1
                sld = sl - entry
                if sld <= 0: continue
                tp = entry - sld*rr
                lots = max(0.01, min(round((equity*0.005)/(sld/PIP*PIP_VAL),2), 4.0))
                pos = {'dir':'short','entry':entry,'sl':sl,'tp':tp,'lots':lots,'entry_dt':dt}
                traded_today = True
        return trades

    def metrics(trades):
        if not trades: return {'n':0,'pf':0,'dd_pct':0,'ann_pct':0}
        pnls = [t[2] for t in trades]
        n = len(pnls); pnl = sum(pnls)
        wins = sum(p for p in pnls if p>0); loss = sum(p for p in pnls if p<0)
        pf = wins/abs(loss) if loss!=0 else 0
        eq = [INITIAL] + [t[3] for t in trades]
        peak = INITIAL; dd = 0
        for e in eq:
            if e > peak: peak = e
            cur = (peak-e)/peak*100
            if cur > dd: dd = cur
        yrs = (trades[-1][1] - trades[0][0]).days / 365.25
        ann = ((INITIAL+pnl)/INITIAL)**(1/max(yrs,0.01)) - 1
        return {'n':n,'pf':round(pf,2),'dd_pct':round(dd,2),'ann_pct':round(ann*100,2)}

    GRID = {
        'OrbStartHour': [7, 8, 13],         # Londres (7-8 UTC) o NY (13)
        'SLMult':       [1.0, 1.5, 2.0],
        'RR':           [2.0, 3.0, 4.0],
        'MinRng':       [5, 10, 20],
        'MaxRng':       [50, 100],
        'LongOnly':     [True, False],
    }
    keys = list(GRID.keys())
    combos = [dict(zip(keys,v)) for v in itertools.product(*GRID.values())]
    print(f"  Total combos: {len(combos)}")

    results = []
    for i, p in enumerate(combos, 1):
        try:
            t_is = run(df_is, p); t_oos = run(df_oos, p)
            m_is = metrics(t_is); m_oos = metrics(t_oos)
        except Exception:
            continue
        if m_is['n'] < 100 or m_oos['n'] < 50: continue
        wf = m_oos['pf']/m_is['pf'] if m_is['pf']>0 else 0
        results.append({**p, 'is_pf':m_is['pf'], 'is_n':m_is['n'],
                        'oos_pf':m_oos['pf'], 'oos_dd':m_oos['dd_pct'], 'oos_n':m_oos['n'],
                        'oos_ann':m_oos['ann_pct'], 'wf':round(wf,2)})
        if i % 30 == 0: print(f"    {i}/{len(combos)}...", flush=True)

    rdf = pd.DataFrame(results)
    print(f"  Validos: {len(rdf)}")
    if len(rdf):
        apt = rdf[(rdf['oos_pf']>1.3) & (rdf['oos_dd']<10) & (rdf['wf']>0.85)].sort_values('oos_ann', ascending=False)
        print(f"  Aptos criterio: {len(apt)}")
        if len(apt):
            print(f"\n  TOP 5:")
            print(apt.head(5).to_string(index=False))
        else:
            print(f"\n  Top 5 por OOS PF:")
            print(rdf.sort_values('oos_pf', ascending=False).head(5).to_string(index=False))


def main():
    opt_jasper_eurusd()
    opt_orb_gbpjpy()


if __name__ == '__main__':
    main()
