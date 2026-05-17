"""Jasper OB Strategy — Order Block + FVG (Smart Money Concepts).

Portado del Pine Script v6 'Jasper Working OB Strategy' añadiendo
gestion de riesgo (SL/TP) para hacerlo backtestable.

LOGICA:
1. Order Block VALIDO (en barra i):
   - bullDisplacement: close[i-1] > open[i-1]  (vela alcista grande)
   - bullConfirm:     close[i]   > open[i]    (siguiente vela tambien)
   - bullFVG:         low[i]     > high[i-2]  (hueco entre i-2 y i)
   - Pre-filter: no debe haber FVG previo entre i-3 y i-2 o i-1
   - Zona OB: high[i-2] (top) / low[i-2] (bot) — la vela DE ORIGEN

2. Una vez detectado el OB, se guarda la zona y se marca "no tocado"
3. Touch memory: cuando el precio vuelve a entrar en la zona, queda marcada
4. Reversal entry: tras tocar la zona, si close > high[i-1] (long) → señal
5. Latch: solo UNA señal por OB (no se rearma)
6. Invalidacion: si el precio cierra FUERA de la zona, el OB queda invalidado

GESTION RIESGO (añadida al port):
- SL: extremo opuesto del OB (low si long, high si short) + buffer ATR
- TP: SL_dist * RR  (RR configurable, default 2.0)
- Lotaje: % riesgo del capital
"""
import pandas as pd
import numpy as np


DEFAULT_PARAMS = {
    'RR':           2.0,    # Take Profit en R
    'BufferATR':    0.5,    # SL = extremo OB + buffer * ATR (margen de seguridad)
    'ATR_Period':   14,
    'MinSLPips':    5.0,    # SL minimo en pips
    'MaxSLPips':  200.0,    # SL maximo en pips
    'MaxOBBars':    50,     # Caducidad: si la zona no genera trade en N barras, descartar
    'MaxTradesDay':  3,
    'SessionStart':  0,
    'SessionEnd':   23,
    'LotRiskPct':   0.5,
    'MaxLots':      4.0,
    'BadHour':      -1,
}


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p  = DEFAULT_PARAMS if params is None else params
    df = df.copy()
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/p['ATR_Period'], adjust=False, min_periods=p['ATR_Period']).mean()
    return df


def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 pip: float = 0.0001,
                 pip_val: float = 10.0) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    warmup = max(p['ATR_Period'], p['MaxOBBars']) + 5

    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    atr = df['atr'].values
    idx = df.index

    rr        = p['RR']
    buf_atr   = p['BufferATR']
    min_sl    = p['MinSLPips'] * pip
    max_sl    = p['MaxSLPips'] * pip
    max_bars  = p['MaxOBBars']
    max_td    = p['MaxTradesDay']
    sess_s    = p['SessionStart']
    sess_e    = p['SessionEnd']
    bad_h     = p['BadHour']
    lot_risk  = p['LotRiskPct'] / 100
    max_lots  = p['MaxLots']

    # Listas de OBs activos: (top, bot, dir, created_idx, touched)
    bull_obs = []  # cada item: [top, bot, created_at, touched]
    bear_obs = []

    equity = initial_capital
    pos = None
    trades = []
    trades_today = 0
    last_date = None

    for i in range(warmup, len(df)):
        dt = idx[i]
        d  = dt.date()
        if d != last_date:
            trades_today = 0
            last_date = d

        # === Gestion posicion abierta ===
        if pos is not None:
            ep = et = None
            if pos['dir'] == 'long':
                if l[i] <= pos['sl']:   ep, et = pos['sl'], 'SL'
                elif h[i] >= pos['tp']: ep, et = pos['tp'], 'TP'
            else:
                if h[i] >= pos['sl']:   ep, et = pos['sl'], 'SL'
                elif l[i] <= pos['tp']: ep, et = pos['tp'], 'TP'
            if ep is not None:
                pnl_usd = ((ep - pos['entry']) if pos['dir']=='long' else (pos['entry']-ep)) / pip * pip_val * pos['lots']
                equity += pnl_usd
                trades.append((pos['entry_dt'], dt, pos['dir'],
                               round(pnl_usd, 2), et, round(equity, 2),
                               pos['lots'], round(pos['sl_dist']/pip, 1)))
                pos = None

        if pos is not None:
            continue

        # === Limpieza OBs caducados/invalidados ===
        # Bull OBs: invalidar si close < bot
        bull_obs = [ob for ob in bull_obs
                    if c[i] >= ob[1] and (i - ob[2]) <= max_bars]
        bear_obs = [ob for ob in bear_obs
                    if c[i] <= ob[0] and (i - ob[2]) <= max_bars]

        # === Detectar nuevo OB en la barra actual (mira i-2, i-1, i) ===
        # OB BULLISH:
        if (c[i-1] > o[i-1] and c[i] > o[i] and l[i] > h[i-2]):
            # Pre-filter: no debe haber FVG entre i-3 y i-2 o i-1
            pre_fvg = (l[i-2] > h[i-3]) or (l[i-1] > h[i-3])
            if not pre_fvg:
                # Zona OB = barra i-2 (vela de origen del movimiento alcista)
                top = h[i-2]; bot = l[i-2]
                # Evitar OBs duplicados muy cercanos
                if not any(abs(ob[0]-top) < pip*2 for ob in bull_obs):
                    bull_obs.append([top, bot, i, False])
        # OB BEARISH:
        if (c[i-1] < o[i-1] and c[i] < o[i] and h[i] < l[i-2]):
            pre_fvg = (h[i-2] < l[i-3]) or (h[i-1] < l[i-3])
            if not pre_fvg:
                top = h[i-2]; bot = l[i-2]
                if not any(abs(ob[1]-bot) < pip*2 for ob in bear_obs):
                    bear_obs.append([top, bot, i, False])

        # === Detectar touch en OBs activos ===
        for ob in bull_obs:
            if not ob[3] and l[i] <= ob[0] and h[i] >= ob[1]:
                ob[3] = True  # touched
        for ob in bear_obs:
            if not ob[3] and l[i] <= ob[0] and h[i] >= ob[1]:
                ob[3] = True

        # === Filtros entrada ===
        hr = dt.hour
        if hr < sess_s or hr >= sess_e: continue
        if bad_h >= 0 and hr == bad_h: continue
        if dt.weekday() >= 5 or (dt.weekday() == 4 and hr >= 22): continue
        if trades_today >= max_td: continue

        atr1 = atr[i]
        if np.isnan(atr1) or atr1 <= 0: continue

        # === Buscar señal LONG: OB bullish tocado + close[i] > high[i-1] ===
        cond_long = None
        for ob in bull_obs:
            if ob[3] and c[i] > h[i-1] and c[i] > ob[0]:
                cond_long = ob
                break

        cond_short = None
        if cond_long is None:
            for ob in bear_obs:
                if ob[3] and c[i] < l[i-1] and c[i] < ob[1]:
                    cond_short = ob
                    break

        if cond_long is None and cond_short is None:
            continue

        # === Setup posicion ===
        if cond_long:
            ob = cond_long
            entry = c[i]
            sl = ob[1] - buf_atr * atr1  # bot del OB - buffer
            sl_dist = entry - sl
            direc = 'long'
            bull_obs.remove(ob)  # latch: usado, no rearmar
        else:
            ob = cond_short
            entry = c[i]
            sl = ob[0] + buf_atr * atr1
            sl_dist = sl - entry
            direc = 'short'
            bear_obs.remove(ob)

        if sl_dist <= 0: continue
        sl_dist = max(sl_dist, min_sl)
        if sl_dist > max_sl: continue
        tp = entry + sl_dist * rr if direc == 'long' else entry - sl_dist * rr

        lots = min(round((equity * lot_risk) / (sl_dist / pip * pip_val), 2), max_lots)
        lots = max(lots, 0.01)

        pos = {
            'dir': direc, 'entry': entry,
            'sl': entry - sl_dist if direc == 'long' else entry + sl_dist,
            'tp': tp, 'sl_dist': sl_dist, 'lots': lots,
            'entry_dt': dt,
        }
        trades_today += 1

    if not trades:
        return pd.DataFrame(columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])
    return pd.DataFrame(trades, columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])


def compute_metrics(trades: pd.DataFrame, initial_capital: float = 50_000) -> dict:
    if trades is None or len(trades) == 0:
        return {'n':0,'pnl':0,'wr':0,'pf':0,'dd_pct':0,'ann_pct':0}
    n = len(trades)
    pnl = trades['pnl'].sum()
    wr = (trades['pnl'] > 0).mean() * 100
    wins = trades.loc[trades['pnl'] > 0, 'pnl']
    loss = trades.loc[trades['pnl'] < 0, 'pnl']
    pf = wins.sum() / abs(loss.sum()) if len(loss) > 0 and loss.sum() != 0 else 0
    eq = np.concatenate([[initial_capital], trades['equity'].values])
    pk = np.maximum.accumulate(eq)
    dd = abs(((eq - pk) / pk).min()) * 100
    yrs = (pd.to_datetime(trades['exit_dt'].iloc[-1]) -
           pd.to_datetime(trades['entry_dt'].iloc[0])).days / 365.25
    ann = ((initial_capital + pnl) / initial_capital) ** (1 / max(yrs, 0.01)) - 1
    return {'n':n, 'pnl':round(pnl,0), 'wr':round(wr,1), 'pf':round(pf,2),
            'dd_pct':round(dd,2), 'ann_pct':round(ann*100,2)}
