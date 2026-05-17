"""Ejecuta los combos propuestos por DeepSeek Strategy Combiner.

3 combos viables con codigo existente:
  #2: Jasper OB + EMA200 H4 + Wick en EURUSD
  #3: MultiPullback EMA200/EMA9 en QQQ
  #5: ORB con ATR stop en GBPJPY (adaptado del XAUUSD)

Reporta metricas IS/OOS y veredicto checklist resumido.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from datetime import datetime

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000

CRITERIO = {
    'pf_min': 1.3, 'dd_max': 10.0, 'wf_min': 0.85, 'n_min': 50,
}


def check_criterio(m_is, m_oos):
    wf = m_oos['pf']/m_is['pf'] if m_is['pf']>0 else 0
    ok = (m_oos['pf'] >= CRITERIO['pf_min']
          and m_oos['dd_pct'] <= CRITERIO['dd_max']
          and wf >= CRITERIO['wf_min']
          and m_oos['n'] >= CRITERIO['n_min'])
    return ok, wf


# ============================================================
# COMBO #2: Jasper OB + EMA200 H4 + Wick en EURUSD
# ============================================================
def combo_2_jasper_eurusd():
    print("\n" + "="*88)
    print("  COMBO #2: Jasper OB + EMA200 H4 + Wick en EURUSD")
    print("="*88)
    from strategies.jasper_ob_filtered_m15 import (
        add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)
    p = {**DEFAULT_PARAMS, 'UseEMA200H4':1, 'UseWick':1}
    df = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'), index_col=0, parse_dates=True)
    df_ind = add_indicators(df, p)
    df_is  = df_ind.loc[:'2021-12-31']
    df_oos = df_ind.loc['2022-01-01':]
    t_is  = run_backtest(df_is,  p, INITIAL, pip=0.0001, pip_val=10.0)
    t_oos = run_backtest(df_oos, p, INITIAL, pip=0.0001, pip_val=10.0)
    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)
    ok, wf = check_criterio(m_is, m_oos)
    print(f"  IS:  PF={m_is['pf']:.2f} DD={m_is['dd_pct']:.1f}% N={m_is['n']}")
    print(f"  OOS: PF={m_oos['pf']:.2f} DD={m_oos['dd_pct']:.1f}% N={m_oos['n']} Ann={m_oos['ann_pct']}% WF={wf:.2f}")
    print(f"  Veredicto: {'✓ VIABLE' if ok else 'x no pasa criterio'}")
    return {'combo':'#2 Jasper OB EURUSD', 'is':m_is, 'oos':m_oos, 'wf':wf, 'ok':ok}


# ============================================================
# COMBO #3: MultiPullback EMA200 H4 + EMA9 M15 + RSI extremo en QQQ
# Es básicamente el EMA9+VWAP+RSI pero filtrando con EMA200 H4 además
# ============================================================
def combo_3_multipullback_qqq():
    print("\n" + "="*88)
    print("  COMBO #3: MultiPullback EMA9 + EMA200 H4 + RSI extremo en QQQ")
    print("="*88)
    # Usamos ema9_vwap_rsi pero modificamos: aumentamos restricción RSI
    from strategies.ema9_vwap_rsi import (
        add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)
    p = {**DEFAULT_PARAMS,
         'EMA_Fast': 9, 'EMA_Mid': 21,
         'RSI_Buy_Min': 30, 'RSI_Buy_Max': 50,   # mas estricto (sobreventa)
         'RSI_Sell_Min': 50, 'RSI_Sell_Max': 70, # mas estricto (sobrecompra)
         'SL_ATR_Mult': 1.0, 'TP1_Mult': 2.0,
         'WickRatio': 1.5}
    df = pd.read_csv(os.path.join(DATA, 'NAS100_proxy_M15_twelvedata.csv'),
                     parse_dates=['time'], index_col='time')
    df_ind = add_indicators(df, p)
    df_is  = df_ind.loc[:'2022-12-31']
    df_oos = df_ind.loc['2023-01-01':]
    t_is  = run_backtest(df_is,  p, INITIAL, pip=1.0, pip_val=100.0)
    t_oos = run_backtest(df_oos, p, INITIAL, pip=1.0, pip_val=100.0)
    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)
    ok, wf = check_criterio(m_is, m_oos)
    print(f"  IS:  PF={m_is['pf']:.2f} DD={m_is['dd_pct']:.1f}% N={m_is['n']}")
    print(f"  OOS: PF={m_oos['pf']:.2f} DD={m_oos['dd_pct']:.1f}% N={m_oos['n']} Ann={m_oos['ann_pct']}% WF={wf:.2f}")
    print(f"  Veredicto: {'✓ VIABLE' if ok else 'x no pasa criterio'}")
    return {'combo':'#3 MultiPullback QQQ RSI extremo', 'is':m_is, 'oos':m_oos, 'wf':wf, 'ok':ok}


# ============================================================
# COMBO #5: ORB con ATR stop en GBPJPY M15
# Adaptado del XAUUSD ORB pero para GBPJPY (JPY pair, pip=0.01)
# Definimos rango ORB como primera vela H1 de sesion Londres (8:00 UTC)
# ============================================================
def combo_5_orb_gbpjpy():
    print("\n" + "="*88)
    print("  COMBO #5: ORB sesión Londres con ATR stop en GBPJPY")
    print("="*88)
    df = pd.read_csv(os.path.join(DATA, 'GBPJPY_M15_dukas.csv'), index_col=0, parse_dates=True)
    # ORB simple: high/low de la primera 1h de Londres (8:00-9:00 UTC)
    # SL = orbLow - 1.5*ATR, TP = SL_dist * 3
    # Entrada: rotura ORB con cierre arriba
    PIP = 0.01
    PIP_VAL = 6.5
    # ATR
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl,hc,lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()

    df_is  = df.loc[:'2021-12-31']
    df_oos = df.loc['2022-01-01':]

    def run(df_sub):
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
            d = dt.date()
            hr = dt.hour
            mn = dt.minute

            if d != last_date:
                orb_high = None; orb_low = None
                traded_today = False
                last_date = d

            # Pos abierta
            if pos is not None:
                ep = et = None
                if pos['dir'] == 'long':
                    if l[i] <= pos['sl']: ep, et = pos['sl'], 'SL'
                    elif h[i] >= pos['tp']: ep, et = pos['tp'], 'TP'
                else:
                    if h[i] >= pos['sl']: ep, et = pos['sl'], 'SL'
                    elif l[i] <= pos['tp']: ep, et = pos['tp'], 'TP'
                if ep:
                    pnl = ((ep-pos['entry']) if pos['dir']=='long' else (pos['entry']-ep)) / PIP * PIP_VAL * pos['lots']
                    equity += pnl
                    trades.append((pos['entry_dt'], dt, pos['dir'], round(pnl,2), et, round(equity,2), pos['lots']))
                    pos = None
                if pos is not None: continue

            # ORB Londres 8:00-9:00 UTC = velas 8:00, 8:15, 8:30, 8:45
            if hr == 8 and mn in (0, 15, 30, 45):
                if orb_high is None or h[i] > orb_high: orb_high = h[i]
                if orb_low is None or l[i] < orb_low:  orb_low  = l[i]
                continue  # capturando, no operar todavia

            if orb_high is None or traded_today: continue
            if hr < 9 or hr >= 17: continue
            atr1 = atr[i]
            if np.isnan(atr1) or atr1 <= 0: continue

            rng = orb_high - orb_low
            min_rng = 5 * PIP   # 5 pips min
            max_rng = 50 * PIP  # 50 pips max
            if rng < min_rng or rng > max_rng: continue

            # Senal LONG si close cruza orb_high
            if c[i] > orb_high and c[i-1] <= orb_high:
                entry = c[i]
                sl = orb_low - 1.5 * atr1
                sl_dist = entry - sl
                if sl_dist <= 0: continue
                tp = entry + sl_dist * 3.0
                lots = max(0.01, min(round((equity * 0.005) / (sl_dist/PIP * PIP_VAL), 2), 4.0))
                pos = {'dir':'long','entry':entry,'sl':sl,'tp':tp,'lots':lots,'entry_dt':dt}
                traded_today = True
            elif c[i] < orb_low and c[i-1] >= orb_low:
                entry = c[i]
                sl = orb_high + 1.5 * atr1
                sl_dist = sl - entry
                if sl_dist <= 0: continue
                tp = entry - sl_dist * 3.0
                lots = max(0.01, min(round((equity * 0.005) / (sl_dist/PIP * PIP_VAL), 2), 4.0))
                pos = {'dir':'short','entry':entry,'sl':sl,'tp':tp,'lots':lots,'entry_dt':dt}
                traded_today = True

        return pd.DataFrame(trades, columns=['entry_dt','exit_dt','dir','pnl','exit_type','equity','lots'])

    t_is = run(df_is)
    t_oos = run(df_oos)

    def metrics(t):
        if len(t) == 0: return {'n':0,'pf':0,'dd_pct':0,'ann_pct':0,'pnl':0}
        n = len(t); pnl = t['pnl'].sum()
        wins = t.loc[t['pnl']>0,'pnl']; loss = t.loc[t['pnl']<0,'pnl']
        pf = wins.sum()/abs(loss.sum()) if len(loss) and loss.sum()!=0 else 0
        eq = np.concatenate([[INITIAL], t['equity'].values])
        pk = np.maximum.accumulate(eq)
        dd = abs(((eq-pk)/pk).min())*100
        yrs = (pd.to_datetime(t['exit_dt'].iloc[-1]) - pd.to_datetime(t['entry_dt'].iloc[0])).days/365.25
        ann = ((INITIAL+pnl)/INITIAL)**(1/max(yrs,0.01)) - 1
        return {'n':n,'pf':round(pf,2),'dd_pct':round(dd,2),'ann_pct':round(ann*100,2),'pnl':round(pnl,0)}

    m_is = metrics(t_is); m_oos = metrics(t_oos)
    ok, wf = check_criterio(m_is, m_oos)
    print(f"  IS:  PF={m_is['pf']:.2f} DD={m_is['dd_pct']:.1f}% N={m_is['n']}")
    print(f"  OOS: PF={m_oos['pf']:.2f} DD={m_oos['dd_pct']:.1f}% N={m_oos['n']} Ann={m_oos['ann_pct']}% WF={wf:.2f}")
    print(f"  Veredicto: {'✓ VIABLE' if ok else 'x no pasa criterio'}")
    return {'combo':'#5 ORB Londres GBPJPY', 'is':m_is, 'oos':m_oos, 'wf':wf, 'ok':ok}


def main():
    print(f"Ejecutando 3 combos del Strategy Combiner...")
    print(f"Criterio: PF OOS>{CRITERIO['pf_min']}, DD<{CRITERIO['dd_max']}%, WF>{CRITERIO['wf_min']}, N>={CRITERIO['n_min']}")

    resultados = []
    try: resultados.append(combo_2_jasper_eurusd())
    except Exception as e: print(f"  Combo 2 error: {e}")
    try: resultados.append(combo_3_multipullback_qqq())
    except Exception as e: print(f"  Combo 3 error: {e}")
    try: resultados.append(combo_5_orb_gbpjpy())
    except Exception as e: print(f"  Combo 5 error: {e}")

    print("\n" + "="*88)
    print("  RESUMEN FINAL")
    print("="*88)
    print(f"\n  {'Combo':<40} {'PF OOS':>7} {'DD %':>6} {'Ann %':>7} {'WF':>5} {'N OOS':>6} {'Estado':>10}")
    for r in resultados:
        print(f"  {r['combo']:<40} {r['oos']['pf']:>7.2f} {r['oos']['dd_pct']:>6.1f} {r['oos']['ann_pct']:>+7.1f} {r['wf']:>5.2f} {r['oos']['n']:>6} {'✓ VIABLE' if r['ok'] else 'x':>10}")

    # Guardar
    out = os.path.join(os.path.dirname(__file__), '..', 'reports',
                       f"combos_resultados_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"# Resultados combos Strategy Combiner — {datetime.now()}\n\n")
        f.write(f"## Criterio\nPF OOS>{CRITERIO['pf_min']}, DD<{CRITERIO['dd_max']}%, WF>{CRITERIO['wf_min']}, N>={CRITERIO['n_min']}\n\n")
        for r in resultados:
            f.write(f"## {r['combo']}\n")
            f.write(f"- IS: PF {r['is']['pf']} DD {r['is']['dd_pct']}% N {r['is']['n']}\n")
            f.write(f"- OOS: PF {r['oos']['pf']} DD {r['oos']['dd_pct']}% N {r['oos']['n']} Ann {r['oos']['ann_pct']}%\n")
            f.write(f"- WF: {r['wf']:.2f}\n")
            f.write(f"- {'VIABLE' if r['ok'] else 'NO VIABLE'}\n\n")
    print(f"\n  Guardado: {out}")


if __name__ == '__main__':
    main()
