"""
GBPJPY ORB DD23 — Tests de Robustez
Config: LONDON BOTH TP1=1.5x TP2=2.0x Range=5-30p
Walk-Forward: IS 2020-2022 vs OOS 2023-2025
Monte Carlo: 500 permutaciones
"""
import os, warnings
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

CSV_PATH = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv"
CAPITAL  = 50_000.0
PIP      = 0.01
PIP_USD  = 6.9
NY_OPEN  = 8*60       # Londres 08:00
NY_END   = 16*60
MIN_RNG  = 5  * PIP
MAX_RNG  = 30 * PIP
TP1      = 1.5
TP2      = 2.0
MC_RUNS  = 500
RISK_PCT = 0.005
DIRECTION= "BOTH"


def load_m15(start_year, end_year):
    from datetime import datetime
    df = pd.read_csv(CSV_PATH, header=None,
         names=["date","time","open","high","low","close","volume","v2","sp"],
         dtype={"date":str,"time":str})
    df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M")
    df = df.set_index("dt")[["open","high","low","close","volume"]]
    df = df[(df.index >= datetime(start_year,1,1)) & (df.index <= datetime(end_year,12,31))]
    m = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return m


def make_signals(m15):
    bm  = m15.index.hour * 60 + m15.index.minute
    dow = m15.index.dayofweek
    di  = m15.index.normalize()

    is_open = (bm == NY_OPEN) & (dow < 5)
    rng_bar = m15['high'] - m15['low']
    valid   = is_open & (rng_bar >= MIN_RNG) & (rng_bar <= MAX_RNG)

    orb_day = pd.DataFrame({
        'date': di[valid],
        'orb_h': m15['high'].values[valid],
        'orb_l': m15['low'].values[valid],
    }).set_index('date')
    orb_day = orb_day[~orb_day.index.duplicated(keep='first')]

    df_tmp = pd.DataFrame({'date': di}, index=m15.index).join(orb_day, on='date')

    after_open = bm > NY_OPEN
    before_end = bm < NY_END
    sess_mask  = after_open & before_end & (dow < 5)
    valid_sess = sess_mask & df_tmp['orb_h'].notna()

    m = m15.copy()
    m['orb_h'] = np.where(valid_sess, df_tmp['orb_h'], np.nan)
    m['orb_l'] = np.where(valid_sess, df_tmp['orb_l'], np.nan)
    m['orb_r'] = m['orb_h'] - m['orb_l']
    m['in_s']  = valid_sess
    return m


def run_bt(sig, capital=CAPITAL):
    has_orb   = sig['orb_h'].notna() & sig['in_s']
    long_sig  = has_orb & (sig['close'] > sig['orb_h'])
    short_sig = has_orb & (sig['close'] < sig['orb_l'])
    date_s    = pd.Series(sig.index.normalize(), index=sig.index)
    long_sig  = long_sig  & (~long_sig.groupby(date_s).cumsum().shift(1, fill_value=0).astype(bool))
    short_sig = short_sig & (~short_sig.groupby(date_s).cumsum().shift(1, fill_value=0).astype(bool))

    arr_h  = sig['high'].values;   arr_l  = sig['low'].values
    arr_c  = sig['close'].values
    arr_oh = sig['orb_h'].values;  arr_ol = sig['orb_l'].values
    arr_r  = sig['orb_r'].values
    arr_ls = long_sig.values;      arr_ss = short_sig.values

    records = []; positions = []

    def close_p(pos, price):
        nonlocal capital
        d    = pos[0]
        dist = (price - pos[1]) if d == 1 else (pos[1] - price)
        pnl  = dist / PIP * PIP_USD * pos[4]
        capital += pnl
        records.append(pnl)

    for i in range(len(sig)):
        h, l = arr_h[i], arr_l[i]
        nxt = []
        for pos in positions:
            d, entry, sl, tp_val, lots, pid = pos
            sl_hit = (d==1 and l<=sl) or (d==-1 and h>=sl)
            tp_hit = (d==1 and h>=tp_val) or (d==-1 and l<=tp_val)
            if sl_hit and tp_hit: tp_hit = False
            if sl_hit:
                close_p(pos, sl)
                for p2 in nxt:
                    if p2[5]==pid: nxt[nxt.index(p2)] = (p2[0],p2[1],entry,p2[3],p2[4],p2[5])
            elif tp_hit:
                close_p(pos, tp_val)
                for p2 in nxt:
                    if p2[5]==pid: nxt[nxt.index(p2)] = (p2[0],p2[1],entry,p2[3],p2[4],p2[5])
            else:
                nxt.append(pos)
        positions = nxt

        for d, is_sig in [(1, arr_ls[i]), (-1, arr_ss[i])]:
            if not is_sig: continue
            entry = arr_c[i]
            sl    = arr_ol[i] if d==1 else arr_oh[i]
            rng   = arr_r[i]
            if np.isnan(sl) or np.isnan(rng) or rng<=0: continue
            sl_p  = abs(entry-sl)/PIP
            if sl_p<1: continue
            lots  = min(max(capital*RISK_PCT/(sl_p*PIP_USD), 0.01), 4.0)
            positions.append((d, entry, sl, entry+rng*TP1*d, lots, i))
            positions.append((d, entry, sl, entry+rng*TP2*d, lots, i))

    for pos in positions:
        close_p(pos, arr_c[-1])

    if len(records)<5: return None
    t    = np.array(records)
    wins = (t>0).sum()
    gp   = t[t>0].sum(); gl = abs(t[t<=0].sum())
    pf   = gp/gl if gl>0 else 0
    pnl  = t.sum()
    eq   = CAPITAL + np.cumsum(t)
    peak = np.maximum.accumulate(eq)
    dd   = ((peak-eq)/peak*100).max()
    wr   = wins/len(t)
    return {'trades':len(t),'wr':round(wr*100,1),'pf':round(pf,2),
            'pnl':round(pnl,0),'dd':round(dd,1),'records':t}


def main():
    print("="*65, flush=True)
    print("  GBPJPY ORB DD23 — Tests de Robustez", flush=True)
    print("  Config: LONDON BOTH TP1=1.5x TP2=2.0x Rng=5-30p", flush=True)
    print("="*65, flush=True)

    print("\n[1] Backtest completo 2020-2025...", flush=True)
    m15 = load_m15(2020, 2025)
    sig = make_signals(m15)
    r   = run_bt(sig)
    if r:
        print(f"  Trades:{r['trades']} | WR:{r['wr']}% | PF:{r['pf']} | "
              f"P&L:${r['pnl']:+,.0f} | DD:{r['dd']}%", flush=True)
    else:
        print("  Sin resultados.", flush=True); return

    print("\n[2] Walk-Forward: IS=2020-2022 vs OOS=2023-2025", flush=True)
    r_is  = run_bt(make_signals(load_m15(2020, 2022)))
    r_oos = run_bt(make_signals(load_m15(2023, 2025)))
    if r_is and r_oos:
        print(f"  In-Sample  (2020-22): Trades={r_is['trades']:4d} | WR={r_is['wr']:5.1f}% | "
              f"PF={r_is['pf']:.2f} | P&L=${r_is['pnl']:+,.0f} | DD={r_is['dd']:.1f}%", flush=True)
        print(f"  Out-Sample (2023-25): Trades={r_oos['trades']:4d} | WR={r_oos['wr']:5.1f}% | "
              f"PF={r_oos['pf']:.2f} | P&L=${r_oos['pnl']:+,.0f} | DD={r_oos['dd']:.1f}%", flush=True)
        ratio  = r_oos['pf']/r_is['pf'] if r_is['pf']>0 else 0
        status = "PASS" if r_oos['pf']>=1.0 and ratio>=0.5 else "FAIL"
        print(f"  WF Ratio OOS/IS = {ratio:.2f}  →  {status}", flush=True)

    print("\n[3] Resultados por ano:", flush=True)
    anos = []
    for yr in range(2020, 2026):
        r_yr = run_bt(make_signals(load_m15(yr, yr)))
        if r_yr:
            print(f"  {yr}: Trades={r_yr['trades']:4d} | WR={r_yr['wr']:5.1f}% | "
                  f"PF={r_yr['pf']:.2f} | P&L=${r_yr['pnl']:+,.0f} | DD={r_yr['dd']:.1f}%", flush=True)
            anos.append({'year':yr, **{k:v for k,v in r_yr.items() if k!='records'}})
        else:
            print(f"  {yr}: Sin trades suficientes", flush=True)
    neg = sum(1 for a in anos if a['pnl']<0)
    print(f"\n  Anos negativos: {neg}/6  →  {'PASS' if neg==0 else 'PRECAUCION'}", flush=True)

    print(f"\n[4] Monte Carlo ({MC_RUNS} permutaciones)...", flush=True)
    mc_dds=[]; mc_pnls=[]
    rng_gen = np.random.default_rng(42)
    for _ in range(MC_RUNS):
        s   = rng_gen.permutation(r['records'])
        eq  = CAPITAL + np.cumsum(s)
        pk  = np.maximum.accumulate(eq)
        mc_dds.append(((pk-eq)/pk*100).max())
        mc_pnls.append(float(eq[-1]-CAPITAL))

    dd_p50=np.percentile(mc_dds,50); dd_p95=np.percentile(mc_dds,95); dd_p99=np.percentile(mc_dds,99)
    pct_pos=(np.array(mc_pnls)>0).mean()*100
    print(f"  DD  P50/P95/P99: {dd_p50:.1f}% / {dd_p95:.1f}% / {dd_p99:.1f}%", flush=True)
    print(f"  % permutaciones positivas: {pct_pos:.1f}%", flush=True)
    print(f"  MC status: {'PASS' if dd_p95<35 and pct_pos>60 else 'REVISAR'}", flush=True)

    os.makedirs("reports", exist_ok=True)
    pd.DataFrame([{
        'total_trades':r['trades'],'wr':r['wr'],'pf':r['pf'],'pnl':r['pnl'],'dd':r['dd'],
        'is_pf':r_is['pf'] if r_is else None,'oos_pf':r_oos['pf'] if r_oos else None,
        'mc_dd_p50':round(dd_p50,1),'mc_dd_p95':round(dd_p95,1),'mc_dd_p99':round(dd_p99,1),
        'mc_pct_positive':round(pct_pos,1)
    }]).to_csv("reports/robustness_gbpjpy_dd23.csv", index=False)
    if anos:
        pd.DataFrame(anos).to_csv("reports/yearly_gbpjpy_dd23.csv", index=False)
    print("\n  Guardado: reports/robustness_gbpjpy_dd23.csv", flush=True)
    print("=== ROBUSTEZ DD23 COMPLETADA ===", flush=True)

if __name__ == "__main__":
    main()
