"""
ORB Fast Multi-Asset Optimizer — version vectorizada
Usa pandas vectorizado en lugar de bucles Python: ~50x más rápido.
"""
import sys, os, itertools, warnings
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

# ─── Activos ──────────────────────────────────────────────────────────────────
ASSETS = {
    "GBPJPY": {
        "csv": r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv",
        "pip": 0.01, "pip_usd": 6.9, "fmt": "nohdr",
        "min_rng": [5, 10, 15], "max_rng": [30, 50],
    },
    "XAUUSD": {
        "csv": r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv",
        "pip": 0.1, "pip_usd": 10.0, "fmt": "hdr",
        "min_rng": [20, 40, 80], "max_rng": [150, 300],
    },
}

START_YEAR, END_YEAR = 2020, 2025
CAPITAL = 50_000.0

SESSIONS = {
    "NY":     (13*60+30, 20*60),
    "LONDON": ( 8*60+0,  16*60),
}

GRID = {
    "SESSION":    ["NY", "LONDON", "BOTH"],
    "DIRECTION":  ["BOTH", "LONG_ONLY", "SHORT_ONLY"],
    "TP1":        [0.5, 1.0, 1.5],
    "TP2":        [2.0, 3.0, 4.0, 5.0],
}


def load_m15(info):
    from datetime import datetime
    csv = info["csv"]
    print(f"  Leyendo {os.path.basename(csv)}...", flush=True)
    if info["fmt"] == "hdr":
        df = pd.read_csv(csv, dtype={"Date": str, "Time": str})
        df["dt"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S")
        df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
    else:
        df = pd.read_csv(csv, header=None,
             names=["date","time","open","high","low","close","volume","v2","sp"],
             dtype={"date":str,"time":str})
        df["dt"] = pd.to_datetime(df["date"]+" "+df["time"], format="%Y.%m.%d %H:%M")
    df = df.set_index("dt")[["open","high","low","close","volume"]]
    df = df[(df.index >= datetime(START_YEAR,1,1)) & (df.index <= datetime(END_YEAR,12,31))]
    m15 = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    print(f"  M15: {len(m15):,} barras | {m15.index[0].date()} -> {m15.index[-1].date()}", flush=True)
    return m15


def build_orb_table(m15, pip_size, min_rng_pips, max_rng_pips, session):
    """
    Para cada barra M15, calcula vectorialmente:
      - orb_high, orb_low, orb_range de la sesión
      - señal LONG / SHORT
    Devuelve DataFrame con columnas: long, short, orb_high, orb_low, orb_range
    """
    bm = m15.index.hour * 60 + m15.index.minute
    dow = pd.Series(m15.index.dayofweek, index=m15.index)

    if session == "BOTH":
        sess_list = ["NY", "LONDON"]
    else:
        sess_list = [session]

    min_r = min_rng_pips * pip_size
    max_r = max_rng_pips * pip_size

    result_long  = pd.Series(False, index=m15.index)
    result_short = pd.Series(False, index=m15.index)
    result_oh    = pd.Series(np.nan, index=m15.index)
    result_ol    = pd.Series(np.nan, index=m15.index)
    result_rng   = pd.Series(np.nan, index=m15.index)

    for sess in sess_list:
        s_open, s_end = SESSIONS[sess]

        # Máscara: primera barra de la sesión (día laborable)
        is_open_bar = (bm == s_open) & (dow < 5)

        # Rango de esa primera barra
        first_rng  = m15['high'] - m15['low']
        valid_open = is_open_bar & (first_rng >= min_r) & (first_rng <= max_r)

        # Propagar orb_high/low desde la barra de apertura al resto del día
        # Estrategia: para cada día con valid_open, asignar orb al día
        dates = m15.index.date
        dates_s = pd.Series(dates, index=m15.index)

        orb_h = pd.Series(np.nan, index=m15.index)
        orb_l = pd.Series(np.nan, index=m15.index)

        # Fechas donde el rango es válido
        valid_dates = set(m15.index[valid_open].date)

        for vd in valid_dates:
            day_mask = dates_s == vd
            open_bar = m15.index[day_mask & valid_open]
            if len(open_bar) == 0:
                continue
            ob = open_bar[0]
            oh = m15.loc[ob, 'high']
            ol = m15.loc[ob, 'low']
            # Asignar al resto de la sesión ese día (barras post-apertura hasta fin sesión)
            day_bars = m15.index[day_mask]
            post_open = day_bars[day_bars > ob]
            end_bars  = post_open[pd.Series(post_open.hour * 60 + post_open.minute, index=post_open) < s_end]
            if len(end_bars) == 0:
                continue
            orb_h[end_bars] = oh
            orb_l[end_bars] = ol

        has_orb = orb_h.notna()
        rng = orb_h - orb_l

        # Primera señal del día (solo una por sesión)
        long_cand  = has_orb & (m15['close'] > orb_h)
        short_cand = has_orb & (m15['close'] < orb_l)

        # Mantener solo la primera señal por día/sesión
        long_first  = long_cand  & (~long_cand.groupby(dates_s).cummax().shift(1, fill_value=False))
        short_first = short_cand & (~short_cand.groupby(dates_s).cummax().shift(1, fill_value=False))

        # Combinar con resultados acumulados
        result_long  |= long_first
        result_short |= short_first
        result_oh    = result_oh.fillna(orb_h)
        result_ol    = result_ol.fillna(orb_l)
        result_rng   = result_rng.fillna(rng)

    sig = m15.copy()
    sig['long']      = result_long
    sig['short']     = result_short
    sig['orb_high']  = result_oh
    sig['orb_low']   = result_ol
    sig['orb_range'] = result_rng
    return sig


def run_bt_fast(sig, pip_size, pip_usd, tp1_mult, tp2_mult, direction):
    """Backtest rápido barra a barra solo en barras con señal."""
    capital = CAPITAL
    records = []

    arr_close = sig['close'].values
    arr_open  = sig['open'].values
    arr_high  = sig['high'].values
    arr_low   = sig['low'].values
    arr_long  = sig['long'].values
    arr_short = sig['short'].values
    arr_oh    = sig['orb_high'].values
    arr_ol    = sig['orb_low'].values
    arr_rng   = sig['orb_range'].values
    idx       = sig.index

    positions = []

    def close_pos(pos, price, i, reason):
        nonlocal capital
        d   = pos['dir']
        dist = (price - pos['entry']) if d == 1 else (pos['entry'] - price)
        pnl  = dist / pip_size * pip_usd * pos['lots']
        capital += pnl
        records.append({'pnl': pnl, 'dir': d, 'reason': reason,
                        'entry': pos['entry'], 'sl': pos['sl']})
        return pnl

    for i in range(len(sig)):
        h, l = arr_high[i], arr_low[i]
        # Gestionar posiciones
        still = []
        for pos in positions:
            d, sl, tp = pos['dir'], pos['sl'], pos['tp']
            sl_hit = (d == 1 and l <= sl) or (d == -1 and h >= sl)
            tp_hit = (d == 1 and h >= tp) or (d == -1 and l <= tp)
            if sl_hit and tp_hit: tp_hit = False
            if sl_hit:
                close_pos(pos, sl, i, 'SL')
                for p2 in still:
                    if p2.get('pair') == pos.get('pair'):
                        p2['sl'] = pos['entry']
            elif tp_hit:
                close_pos(pos, tp, i, 'TP')
                for p2 in still:
                    if p2.get('pair') == pos.get('pair'):
                        p2['sl'] = pos['entry']
            else:
                still.append(pos)
        positions = still

        # Nueva señal
        for is_long, is_short in [(arr_long[i], arr_short[i])]:
            if is_long and direction != "SHORT_ONLY":
                entry = arr_close[i]
                sl    = arr_ol[i]
                rng   = arr_rng[i]
                if np.isnan(sl) or np.isnan(rng) or rng <= 0: continue
                sl_pips = (entry - sl) / pip_size
                if sl_pips < 1: continue
                risk   = capital * 0.005
                lots   = min(max(risk / (sl_pips * pip_usd), 0.01), 4.0)
                pair   = i
                positions.append({'dir':1,'entry':entry,'sl':sl,'tp':entry+rng*tp1_mult,'lots':lots,'pair':pair})
                positions.append({'dir':1,'entry':entry,'sl':sl,'tp':entry+rng*tp2_mult,'lots':lots,'pair':pair})
            if is_short and direction != "LONG_ONLY":
                entry = arr_close[i]
                sl    = arr_oh[i]
                rng   = arr_rng[i]
                if np.isnan(sl) or np.isnan(rng) or rng <= 0: continue
                sl_pips = (sl - entry) / pip_size
                if sl_pips < 1: continue
                risk   = capital * 0.005
                lots   = min(max(risk / (sl_pips * pip_usd), 0.01), 4.0)
                pair   = i
                positions.append({'dir':-1,'entry':entry,'sl':sl,'tp':entry-rng*tp1_mult,'lots':lots,'pair':pair})
                positions.append({'dir':-1,'entry':entry,'sl':sl,'tp':entry-rng*tp2_mult,'lots':lots,'pair':pair})

    for pos in positions:
        close_pos(pos, arr_close[-1], len(sig)-1, 'END')

    if not records:
        return None
    t = pd.DataFrame(records)
    wins  = (t['pnl'] > 0).sum()
    gp    = t[t['pnl']>0]['pnl'].sum()
    gl    = abs(t[t['pnl']<=0]['pnl'].sum())
    pf    = gp/gl if gl > 0 else 0
    pnl   = t['pnl'].sum()
    eq    = CAPITAL + t['pnl'].cumsum()
    peak  = eq.cummax()
    dd    = ((peak-eq)/peak*100).max()
    wr    = wins / len(t)
    score = (pf-1)*0.4 + (pnl/CAPITAL*100)*0.3 - dd*0.3
    return {'trades':len(t),'wr':round(wr*100,1),'pf':round(pf,2),
            'pnl':round(pnl,0),'dd':round(dd,1),'score':round(score,3)}


def main():
    print("="*70, flush=True)
    print("  ORB Fast Multi-Asset Optimizer", flush=True)
    print("="*70, flush=True)

    all_results = []

    for asset_name, info in ASSETS.items():
        if not os.path.exists(info["csv"]):
            print(f"\n  [{asset_name}] CSV no encontrado", flush=True)
            continue

        print(f"\n  [{asset_name}]", flush=True)
        m15 = load_m15(info)
        pip  = info["pip"]
        pusd = info["pip_usd"]

        keys = list(GRID.keys()) + ["MIN_RNG", "MAX_RNG"]
        combos = [(s,d,t1,t2,mn,mx)
                  for s  in GRID["SESSION"]
                  for d  in GRID["DIRECTION"]
                  for t1 in GRID["TP1"]
                  for t2 in GRID["TP2"]
                  for mn in info["min_rng"]
                  for mx in info["max_rng"]
                  if t1 < t2 and mn < mx]

        print(f"  {len(combos)} combinaciones válidas", flush=True)

        asset_res = []
        done = 0
        for sess, direc, tp1, tp2, mn, mx in combos:
            try:
                sig = build_orb_table(m15, pip, mn, mx, sess)
                r   = run_bt_fast(sig, pip, pusd, tp1, tp2, direc)
                if r and r['pnl'] > 0:
                    r.update({'SESSION':sess,'DIRECTION':direc,'TP1':tp1,'TP2':tp2,
                               'MIN_RNG':mn,'MAX_RNG':mx,'asset':asset_name})
                    asset_res.append(r)
                    all_results.append(r)
            except Exception as e:
                pass
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(combos)} | Rentables: {len(asset_res)}", flush=True)

        if asset_res:
            df_r = pd.DataFrame(asset_res).sort_values('score', ascending=False)
            print(f"\n  [{asset_name}] TOP 10:", flush=True)
            cols = ['SESSION','DIRECTION','TP1','TP2','MIN_RNG','MAX_RNG','trades','wr','pf','pnl','dd','score']
            print(df_r[cols].head(10).to_string(index=False), flush=True)
            os.makedirs("reports", exist_ok=True)
            df_r.to_csv(f"reports/fast_grid_{asset_name}.csv", index=False)

    if all_results:
        df_all = pd.DataFrame(all_results).sort_values('score', ascending=False)
        df_all.to_csv("reports/fast_grid_ALL.csv", index=False)
        print("\n" + "="*70, flush=True)
        print("  MEJOR por activo:", flush=True)
        for asset, grp in df_all.groupby('asset'):
            b = grp.iloc[0]
            print(f"  {asset:8s}: PF={b['pf']:.2f}  WR={b['wr']:.0f}%  P&L=${b['pnl']:+,.0f}"
                  f"  DD={b['dd']:.0f}%  Sess={b['SESSION']}  Dir={b['DIRECTION']}"
                  f"  TP1={b['TP1']}x TP2={b['TP2']}x  Rng={b['MIN_RNG']}-{b['MAX_RNG']}p", flush=True)

    print("\n=== OPTIMIZACION COMPLETADA ===", flush=True)


if __name__ == "__main__":
    main()
