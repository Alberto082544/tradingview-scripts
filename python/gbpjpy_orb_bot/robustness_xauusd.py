"""
XAUUSD ORB — Tests de Robustez
Walk-Forward: IS 2020-2022 vs OOS 2023-2025
Monte Carlo: 500 permutaciones del orden de trades
"""
import sys, os, warnings, time
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

CSV_PATH   = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv"
CAPITAL    = 50_000.0
PIP        = 0.1
PIP_USD    = 10.0
# Config optima
SESSION    = "NY"
NY_OPEN    = 13*60 + 30
NY_END     = 20*60
MIN_RNG    = 40 * PIP
MAX_RNG    = 150 * PIP
TP1        = 0.5
TP2        = 4.0
MC_RUNS    = 500
RISK_PCT   = 0.005


def load_m15(start_year, end_year):
    from datetime import datetime
    df = pd.read_csv(CSV_PATH, dtype={"Date": str, "Time": str})
    df["dt"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S")
    df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
    df = df.set_index("dt")[["open","high","low","close","volume"]]
    df = df[(df.index >= datetime(start_year,1,1)) & (df.index <= datetime(end_year,12,31))]
    m = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return m


def make_signals(m15):
    bm      = m15.index.hour * 60 + m15.index.minute
    dow     = m15.index.dayofweek
    di      = m15.index.normalize()

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
    date_s    = pd.Series(sig.index.normalize(), index=sig.index)
    long_sig  = long_sig & (~long_sig.groupby(date_s).cumsum().shift(1, fill_value=0).astype(bool))

    arr_h  = sig['high'].values
    arr_l  = sig['low'].values
    arr_c  = sig['close'].values
    arr_oh = sig['orb_h'].values
    arr_ol = sig['orb_l'].values
    arr_r  = sig['orb_r'].values
    arr_ls = long_sig.values

    records   = []
    positions = []

    def close_p(pos, price):
        nonlocal capital
        dist = price - pos[1]
        pnl  = dist / PIP * PIP_USD * pos[4]
        capital += pnl
        records.append(pnl)

    for i in range(len(sig)):
        h, l = arr_h[i], arr_l[i]
        nxt = []
        for pos in positions:
            d, entry, sl, tp_val, lots, pid = pos
            sl_hit = l <= sl
            tp_hit = h >= tp_val
            if sl_hit and tp_hit: tp_hit = False
            if sl_hit:
                close_p(pos, sl)
                for p2 in nxt:
                    if p2[5] == pid: nxt[nxt.index(p2)] = (p2[0],p2[1],entry,p2[3],p2[4],p2[5])
            elif tp_hit:
                close_p(pos, tp_val)
                for p2 in nxt:
                    if p2[5] == pid: nxt[nxt.index(p2)] = (p2[0],p2[1],entry,p2[3],p2[4],p2[5])
            else:
                nxt.append(pos)
        positions = nxt

        if arr_ls[i]:
            entry  = arr_c[i]
            sl     = arr_ol[i]
            rng    = arr_r[i]
            if np.isnan(sl) or np.isnan(rng) or rng <= 0: continue
            sl_p   = (entry - sl) / PIP
            if sl_p < 1: continue
            lots   = min(max(capital * RISK_PCT / (sl_p * PIP_USD), 0.01), 4.0)
            positions.append((1, entry, sl, entry + rng*TP1, lots, i))
            positions.append((1, entry, sl, entry + rng*TP2, lots, i))

    for pos in positions:
        close_p(pos, arr_c[-1])

    if len(records) < 5:
        return None
    t    = np.array(records)
    wins = (t > 0).sum()
    gp   = t[t>0].sum()
    gl   = abs(t[t<=0].sum())
    pf   = gp/gl if gl > 0 else 0
    pnl  = t.sum()
    eq   = CAPITAL + np.cumsum(t)
    peak = np.maximum.accumulate(eq)
    dd   = ((peak - eq) / peak * 100).max()
    wr   = wins / len(t)
    return {'trades':len(t),'wr':round(wr*100,1),'pf':round(pf,2),
            'pnl':round(pnl,0),'dd':round(dd,1),'records':t}


def stats_from_records(records, cap=CAPITAL):
    t    = np.array(records)
    wins = (t > 0).sum()
    gp   = t[t>0].sum()
    gl   = abs(t[t<=0].sum())
    pf   = gp/gl if gl > 0 else 0
    pnl  = t.sum()
    eq   = cap + np.cumsum(t)
    peak = np.maximum.accumulate(eq)
    dd   = ((peak - eq) / peak * 100).max()
    wr   = wins / len(t)
    return {'trades':len(t),'wr':round(wr*100,1),'pf':round(pf,2),
            'pnl':round(pnl,0),'dd':round(dd,1)}


def main():
    print("="*65, flush=True)
    print("  XAUUSD ORB — Tests de Robustez", flush=True)
    print("  Config: NY LONG_ONLY TP1=0.5x TP2=4.0x Rng=40-150p", flush=True)
    print("="*65, flush=True)

    # ── 1. Backtest completo 2020-2025 ────────────────────────────
    print("\n[1] Backtest completo 2020-2025...", flush=True)
    m15 = load_m15(2020, 2025)
    sig = make_signals(m15)
    r   = run_bt(sig)
    if r:
        print(f"  Trades: {r['trades']} | WR: {r['wr']}% | PF: {r['pf']} | "
              f"P&L: ${r['pnl']:+,.0f} | DD: {r['dd']}%", flush=True)
    else:
        print("  Sin resultados suficientes.", flush=True)
        return

    # ── 2. Walk-Forward ───────────────────────────────────────────
    print("\n[2] Walk-Forward: IS=2020-2022 vs OOS=2023-2025", flush=True)
    m_is  = load_m15(2020, 2022)
    m_oos = load_m15(2023, 2025)
    r_is  = run_bt(make_signals(m_is))
    r_oos = run_bt(make_signals(m_oos))

    if r_is and r_oos:
        print(f"\n  In-Sample  (2020-2022): Trades={r_is['trades']:4d} | WR={r_is['wr']:5.1f}% | "
              f"PF={r_is['pf']:.2f} | P&L=${r_is['pnl']:+,.0f} | DD={r_is['dd']:.1f}%", flush=True)
        print(f"  Out-of-Sample(2023-25): Trades={r_oos['trades']:4d} | WR={r_oos['wr']:5.1f}% | "
              f"PF={r_oos['pf']:.2f} | P&L=${r_oos['pnl']:+,.0f} | DD={r_oos['dd']:.1f}%", flush=True)
        ratio = r_oos['pf'] / r_is['pf'] if r_is['pf'] > 0 else 0
        status = "PASS" if r_oos['pf'] >= 1.0 and ratio >= 0.5 else "FAIL"
        print(f"\n  WF Ratio PF (OOS/IS) = {ratio:.2f}  →  {status}", flush=True)

    # ── 3. Analisis anual ─────────────────────────────────────────
    print("\n[3] Resultados por ano:", flush=True)
    anos = []
    for yr in range(2020, 2026):
        m_yr = load_m15(yr, yr)
        r_yr = run_bt(make_signals(m_yr))
        if r_yr:
            print(f"  {yr}: Trades={r_yr['trades']:4d} | WR={r_yr['wr']:5.1f}% | "
                  f"PF={r_yr['pf']:.2f} | P&L=${r_yr['pnl']:+,.0f} | DD={r_yr['dd']:.1f}%", flush=True)
            anos.append({'year':yr, **{k:v for k,v in r_yr.items() if k!='records'}})
        else:
            print(f"  {yr}: Sin trades suficientes", flush=True)

    neg_years = sum(1 for a in anos if a['pnl'] < 0)
    print(f"\n  Anos negativos: {neg_years}/6  →  {'PASS' if neg_years == 0 else 'PRECAUCION'}", flush=True)

    # ── 4. Monte Carlo ────────────────────────────────────────────
    print(f"\n[4] Monte Carlo ({MC_RUNS} permutaciones)...", flush=True)
    base_records = r['records']
    mc_pnls = []
    mc_dds  = []
    rng_gen = np.random.default_rng(42)
    for _ in range(MC_RUNS):
        shuffled = rng_gen.permutation(base_records)
        eq  = CAPITAL + np.cumsum(shuffled)
        pk  = np.maximum.accumulate(eq)
        dd  = ((pk - eq) / pk * 100).max()
        mc_pnls.append(float(eq[-1] - CAPITAL))
        mc_dds.append(dd)

    pnl_p5  = np.percentile(mc_pnls, 5)
    pnl_p50 = np.percentile(mc_pnls, 50)
    pnl_p95 = np.percentile(mc_pnls, 95)
    dd_p50  = np.percentile(mc_dds, 50)
    dd_p95  = np.percentile(mc_dds, 95)
    dd_p99  = np.percentile(mc_dds, 99)
    pct_pos = (np.array(mc_pnls) > 0).mean() * 100

    print(f"\n  P&L P5/P50/P95 : ${pnl_p5:+,.0f} / ${pnl_p50:+,.0f} / ${pnl_p95:+,.0f}", flush=True)
    print(f"  DD  P50/P95/P99: {dd_p50:.1f}% / {dd_p95:.1f}% / {dd_p99:.1f}%", flush=True)
    print(f"  % permutaciones positivas: {pct_pos:.1f}%", flush=True)
    mc_status = "PASS" if dd_p95 < 30 and pct_pos > 80 else "REVISAR"
    print(f"  MC status: {mc_status}", flush=True)

    # ── 5. Guardar resultados ─────────────────────────────────────
    os.makedirs("reports", exist_ok=True)
    summary = {
        'total_trades': r['trades'], 'wr': r['wr'], 'pf': r['pf'],
        'pnl_total': r['pnl'], 'dd_total': r['dd'],
        'is_trades': r_is['trades'] if r_is else None,
        'is_pf': r_is['pf'] if r_is else None,
        'oos_trades': r_oos['trades'] if r_oos else None,
        'oos_pf': r_oos['pf'] if r_oos else None,
        'mc_pnl_p5': round(pnl_p5, 0), 'mc_pnl_p95': round(pnl_p95, 0),
        'mc_dd_p95': round(dd_p95, 1), 'mc_dd_p99': round(dd_p99, 1),
        'mc_pct_positive': round(pct_pos, 1),
    }
    pd.DataFrame([summary]).to_csv("reports/robustness_xauusd.csv", index=False)
    if anos:
        pd.DataFrame(anos).to_csv("reports/yearly_xauusd.csv", index=False)
    print("\n  Guardado: reports/robustness_xauusd.csv", flush=True)
    print("=== ROBUSTEZ COMPLETADA ===", flush=True)


if __name__ == "__main__":
    main()
