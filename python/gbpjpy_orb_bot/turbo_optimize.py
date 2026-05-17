"""
ORB Turbo Optimizer — 100% vectorizado con pandas.
Sin bucles Python en signal generation. ~100x más rápido.
"""
import sys, os, itertools, warnings, time
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

SESSIONS = {"NY": (13*60+30, 20*60), "LONDON": (8*60, 16*60)}
TP1_LIST  = [0.5, 1.0, 1.5]
TP2_LIST  = [2.0, 3.0, 4.0, 5.0]
DIRS      = ["BOTH", "LONG_ONLY", "SHORT_ONLY"]


# ─── Carga de datos ───────────────────────────────────────────────────────────
def load_m15(info):
    from datetime import datetime
    print(f"  Leyendo {os.path.basename(info['csv'])}...", flush=True)
    if info["fmt"] == "hdr":
        df = pd.read_csv(info["csv"], dtype={"Date": str, "Time": str})
        df["dt"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S")
        df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
    else:
        df = pd.read_csv(info["csv"], header=None,
             names=["date","time","open","high","low","close","volume","v2","sp"],
             dtype={"date":str,"time":str})
        df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M")
    df = df.set_index("dt")[["open","high","low","close","volume"]]
    df = df[(df.index >= datetime(START_YEAR,1,1)) & (df.index <= datetime(END_YEAR,12,31))]
    m = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    print(f"  {len(m):,} barras M15 | {m.index[0].date()} -> {m.index[-1].date()}", flush=True)
    return m


# ─── Generación de señales 100% vectorizada ───────────────────────────────────
def make_signals(m15, pip, sess_name, min_rng_pips, max_rng_pips):
    """
    Devuelve m15 con columnas: orb_h, orb_l, orb_rng, in_session
    Completamente vectorizado — sin bucles Python.
    """
    min_r = min_rng_pips * pip
    max_r = max_rng_pips * pip

    bm  = m15.index.hour * 60 + m15.index.minute
    dow = m15.index.dayofweek
    date_idx = m15.index.normalize()   # fecha sin hora

    sessions = [sess_name] if sess_name != "BOTH" else ["NY", "LONDON"]

    # Acumuladores
    orb_h   = pd.Series(np.nan, index=m15.index, dtype=float)
    orb_l   = pd.Series(np.nan, index=m15.index, dtype=float)
    in_sess = pd.Series(False,  index=m15.index)

    for sn in sessions:
        s_open, s_end = SESSIONS[sn]

        # ── Marca las barras "apertura de sesión" ────────────────────────────
        is_open = (bm == s_open) & (dow < 5)
        rng_bar = m15['high'] - m15['low']
        valid   = is_open & (rng_bar >= min_r) & (rng_bar <= max_r)

        # DataFrame con orb_h/l en la barra de apertura válida
        orb_day = pd.DataFrame({
            'date': date_idx[valid],
            'orb_h': m15['high'].values[valid],
            'orb_l': m15['low'].values[valid],
        }).set_index('date')
        # Si hay duplicados (raro) quedarse con el primero
        orb_day = orb_day[~orb_day.index.duplicated(keep='first')]

        # ── Propagar orb al día entero usando merge por fecha ────────────────
        df_tmp = pd.DataFrame({'date': date_idx}, index=m15.index)
        df_tmp = df_tmp.join(orb_day, on='date')

        # Máscara: barra dentro de la sesión (post-apertura, pre-fin)
        after_open = bm > s_open
        before_end = bm < s_end
        is_weekday = dow < 5
        sess_mask  = after_open & before_end & is_weekday

        # Solo llenar donde hay orb válido y estamos en sesión
        valid_sess = sess_mask & df_tmp['orb_h'].notna()
        orb_h  = orb_h.where(~valid_sess,  df_tmp['orb_h'].where(valid_sess))
        orb_l  = orb_l.where(~valid_sess,  df_tmp['orb_l'].where(valid_sess))
        in_sess = in_sess | valid_sess

    m = m15.copy()
    m['orb_h']    = orb_h
    m['orb_l']    = orb_l
    m['orb_rng']  = orb_h - orb_l
    m['in_sess']  = in_sess
    return m


# ─── Backtest vectorizado (simplificado para velocidad) ───────────────────────
def run_bt(sig, pip, pip_usd, tp1, tp2, direction):
    """
    Backtest barra a barra solo sobre filas con señal.
    Aún iterativo pero solo ~2k filas por combinación.
    """
    has_orb = sig['orb_h'].notna() & sig['in_sess']
    long_sig  = has_orb & (sig['close'] > sig['orb_h'])
    short_sig = has_orb & (sig['close'] < sig['orb_l'])

    # Limitar a primera señal por día
    date_s = pd.Series(sig.index.normalize(), index=sig.index)
    long_sig  = long_sig  & (~long_sig.groupby(date_s).cumsum().shift(1, fill_value=0).astype(bool))
    short_sig = short_sig & (~short_sig.groupby(date_s).cumsum().shift(1, fill_value=0).astype(bool))

    if direction == "LONG_ONLY":  short_sig[:] = False
    if direction == "SHORT_ONLY": long_sig[:] = False

    n_sig = long_sig.sum() + short_sig.sum()
    if n_sig < 10:
        return None

    capital = CAPITAL
    records = []
    positions = []

    arr_h   = sig['high'].values
    arr_l   = sig['low'].values
    arr_c   = sig['close'].values
    arr_oh  = sig['orb_h'].values
    arr_ol  = sig['orb_l'].values
    arr_rng = sig['orb_rng'].values
    arr_ls  = long_sig.values
    arr_ss  = short_sig.values

    def close_p(pos, price):
        nonlocal capital
        d    = pos[0]
        dist = (price - pos[1]) if d == 1 else (pos[1] - price)
        pnl  = dist / pip * pip_usd * pos[4]
        capital += pnl
        records.append(pnl)
        return pnl

    for i in range(len(sig)):
        h, l = arr_h[i], arr_l[i]
        nxt = []
        for pos in positions:
            d, entry, sl, tp_val, lots, pair_id = pos
            sl_hit = (d == 1 and l <= sl) or (d == -1 and h >= sl)
            tp_hit = (d == 1 and h >= tp_val) or (d == -1 and l <= tp_val)
            if sl_hit and tp_hit: tp_hit = False
            if sl_hit:
                close_p(pos, sl)
                for p2 in nxt:
                    if p2[5] == pair_id: nxt[nxt.index(p2)] = (p2[0],p2[1],entry,p2[3],p2[4],p2[5])
            elif tp_hit:
                close_p(pos, tp_val)
                for p2 in nxt:
                    if p2[5] == pair_id: nxt[nxt.index(p2)] = (p2[0],p2[1],entry,p2[3],p2[4],p2[5])
            else:
                nxt.append(pos)
        positions = nxt

        for d, is_sig in [(1, arr_ls[i]), (-1, arr_ss[i])]:
            if not is_sig: continue
            entry = arr_c[i]
            sl    = arr_ol[i] if d == 1 else arr_oh[i]
            rng   = arr_rng[i]
            if np.isnan(sl) or np.isnan(rng) or rng <= 0: continue
            sl_p  = abs(entry - sl) / pip
            if sl_p < 1: continue
            lots  = min(max(capital * 0.005 / (sl_p * pip_usd), 0.01), 4.0)
            pid   = i
            if d == 1:
                positions.append((d, entry, sl, entry + rng*tp1, lots, pid))
                positions.append((d, entry, sl, entry + rng*tp2, lots, pid))
            else:
                positions.append((d, entry, sl, entry - rng*tp1, lots, pid))
                positions.append((d, entry, sl, entry - rng*tp2, lots, pid))

    for pos in positions:
        close_p(pos, arr_c[-1])

    if len(records) < 10: return None
    t   = np.array(records)
    wins = (t > 0).sum()
    gp   = t[t>0].sum()
    gl   = abs(t[t<=0].sum())
    pf   = gp/gl if gl > 0 else 0
    pnl  = t.sum()
    eq   = CAPITAL + np.cumsum(t)
    peak = np.maximum.accumulate(eq)
    dd   = ((peak - eq) / peak * 100).max()
    wr   = wins / len(t)
    score = (pf-1)*0.4 + (pnl/CAPITAL*100)*0.3 - dd*0.3
    return {'trades':len(t),'wr':round(wr*100,1),'pf':round(pf,2),
            'pnl':round(pnl,0),'dd':round(dd,1),'score':round(score,3)}


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    print("="*65, flush=True)
    print("  ORB Turbo Optimizer (100% vectorizado)", flush=True)
    print("="*65, flush=True)

    all_results = []

    for asset_name, info in ASSETS.items():
        if not os.path.exists(info["csv"]):
            print(f"\n  [{asset_name}] CSV no encontrado: {info['csv']}", flush=True)
            continue

        print(f"\n  [{asset_name}]", flush=True)
        m15  = load_m15(info)
        pip  = info["pip"]
        pusd = info["pip_usd"]

        # Calcular tablas de señal únicas (solo varían sess, min_rng, max_rng)
        sig_keys = list(itertools.product(
            ["NY","LONDON","BOTH"],
            info["min_rng"],
            info["max_rng"]
        ))
        sig_keys = [(s,mn,mx) for s,mn,mx in sig_keys if mn < mx]
        print(f"  Pre-calculando {len(sig_keys)} tablas de señal...", flush=True)

        sig_cache = {}
        for k in sig_keys:
            sess, mn, mx = k
            sig_cache[k] = make_signals(m15, pip, sess, mn, mx)
        print(f"  Señales listas en {time.time()-t0:.1f}s", flush=True)

        # Grid de parámetros de trading (TP1, TP2, direction)
        trade_combos = [(t1,t2,d)
                        for t1 in TP1_LIST
                        for t2 in TP2_LIST
                        for d  in DIRS
                        if t1 < t2]

        total = len(sig_keys) * len(trade_combos)
        print(f"  {total} combinaciones totales", flush=True)

        asset_res = []
        done = 0
        for sess, mn, mx in sig_keys:
            sig = sig_cache[(sess, mn, mx)]
            for tp1, tp2, direc in trade_combos:
                r = run_bt(sig, pip, pusd, tp1, tp2, direc)
                if r and r['pnl'] > 0:
                    r.update({'SESSION':sess,'DIRECTION':direc,'TP1':tp1,'TP2':tp2,
                               'MIN_RNG':mn,'MAX_RNG':mx,'asset':asset_name})
                    asset_res.append(r)
                    all_results.append(r)
                done += 1
            if done % 100 == 0:
                print(f"  {done}/{total} | Rentables: {len(asset_res)} | {time.time()-t0:.0f}s", flush=True)

        if asset_res:
            df_r = pd.DataFrame(asset_res).sort_values('score', ascending=False)
            cols = ['SESSION','DIRECTION','TP1','TP2','MIN_RNG','MAX_RNG','trades','wr','pf','pnl','dd','score']
            print(f"\n  [{asset_name}] TOP 10:", flush=True)
            print(df_r[cols].head(10).to_string(index=False), flush=True)
            os.makedirs("reports", exist_ok=True)
            df_r.to_csv(f"reports/turbo_{asset_name}.csv", index=False)
            print(f"  Guardado: reports/turbo_{asset_name}.csv", flush=True)
        else:
            print(f"  [{asset_name}] Sin combinaciones rentables.", flush=True)

    if all_results:
        df_all = pd.DataFrame(all_results).sort_values('score', ascending=False)
        df_all.to_csv("reports/turbo_ALL.csv", index=False)
        print("\n" + "="*65, flush=True)
        print("  MEJOR POR ACTIVO:", flush=True)
        for asset, grp in df_all.groupby('asset'):
            b = grp.iloc[0]
            print(f"  {asset:8s}: PF={b['pf']:.2f}  WR={b['wr']:.0f}%  "
                  f"P&L=${b['pnl']:+,.0f}  DD={b['dd']:.0f}%  "
                  f"Sess={b['SESSION']}  Dir={b['DIRECTION']}  "
                  f"TP1={b['TP1']}x TP2={b['TP2']}x  Rng={b['MIN_RNG']}-{b['MAX_RNG']}p", flush=True)

    print(f"\n  Tiempo total: {time.time()-t0:.1f}s", flush=True)
    print("=== OPTIMIZACION COMPLETADA ===", flush=True)


if __name__ == "__main__":
    main()
