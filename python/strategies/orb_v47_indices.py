"""
ORB v4.7 — Opening Range Breakout solo LONG para indices.
Portado desde Pine Script v6 (estrategias/ORB_Strategy_v4.7_Indices.pine)

Logica:
  - Captura high/low de la primera vela 30min de NY (9:30-10:00 ET = 14:30-15:00 UTC)
    En M15, son las dos primeras velas de la sesion (14:30-14:45 + 14:45-15:00 UTC)
  - Entrada LONG si en 10:00-16:00 ET (15:00-21:00 UTC):
    * close cruza por encima de orb_high
    * close > EMA200 (tendencia alcista)
    * close > VWAP diario (o sin volumen, se permite)
    * orb range entre minRng y maxRng
    * max 2 trades por dia
  - SL = orb_low - bufPts
  - TP = orb_high + range * tpMult
"""
import pandas as pd
import numpy as np


DEFAULT_PARAMS = {
    'BufPts':    2.0,
    'MinRng':    3.0,
    'MaxRng':  300.0,
    'TpMult':    3.0,
    'EmaLen':  200,
    'MaxTpd':    2,
    'LotRiskPct': 0.5,
    'MaxLots':   4.0,
    'Commission': 0.05,  # %
}

# Sesion NY en UTC (asumiendo no DST por simplicidad — ajustar segun datos)
ORB_START_H = 14  # 14:30 UTC (9:30 ET)
ORB_START_M = 30
ORB_END_H   = 15  # 15:00 UTC (10:00 ET)
ORB_END_M   = 0
SESSION_END_H = 21  # 21:00 UTC (16:00 ET)


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    df = df.copy()
    df['ema200'] = df['close'].ewm(span=p['EmaLen'], adjust=False).mean()

    # VWAP diario (reset cada dia)
    df['tp_x_vol'] = ((df['high'] + df['low'] + df['close']) / 3) * df.get('volume', 0)
    df['date'] = df.index.date
    df['cum_tp_vol'] = df.groupby('date')['tp_x_vol'].cumsum()
    df['cum_vol'] = df.groupby('date')['volume'].cumsum() if 'volume' in df.columns else 0
    df['vwap'] = np.where(df['cum_vol'] > 0, df['cum_tp_vol'] / df['cum_vol'], np.nan)

    return df


def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 pip: float = 1.0, pip_val: float = 100.0) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    warmup = p['EmaLen'] * 2

    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    ema200 = df['ema200'].values
    vwap = df['vwap'].values
    idx = df.index

    buf       = p['BufPts']
    min_rng   = p['MinRng']
    max_rng   = p['MaxRng']
    tp_mult   = p['TpMult']
    max_tpd   = p['MaxTpd']
    lot_risk  = p['LotRiskPct'] / 100
    max_lots  = p['MaxLots']
    comm_pct  = p['Commission'] / 100

    orb_high = orb_low = None
    trades_today = 0
    last_date = None
    pos = None
    trades = []

    # Tracking de horas para detectar ventana ORB
    for i in range(warmup, len(df)):
        dt = idx[i]
        date = dt.date()
        hr   = dt.hour
        mn   = dt.minute

        # Reset diario
        if date != last_date:
            orb_high = None
            orb_low = None
            trades_today = 0
            last_date = date

        # Capturar ORB durante la ventana 14:30-15:00 UTC
        # Es una vela M15 si dt está en 14:30 o 14:45
        if hr == ORB_START_H and mn in (30, 45):
            if orb_high is None or h[i] > orb_high:
                orb_high = h[i]
            if orb_low is None or l[i] < orb_low:
                orb_low = l[i]

        # Gestion posicion abierta (cierre por SL/TP)
        if pos is not None:
            ep = et = None
            if l[i] <= pos['sl']:    ep, et = pos['sl'], 'SL'
            elif h[i] >= pos['tp']:  ep, et = pos['tp'], 'TP'
            # Cierre fin de sesion (21:00 UTC = 16:00 ET)
            elif hr >= SESSION_END_H:
                ep, et = c[i], 'EOD'

            if ep is not None:
                pnl_usd = (ep - pos['entry']) / pip * pip_val * pos['lots']
                # Comision (entrada + salida)
                comm_usd = comm_pct * (pos['entry'] + ep) * pos['lots']
                pnl_usd -= comm_usd
                equity = pos['equity_at_entry'] + pnl_usd
                trades.append((pos['entry_dt'], dt, 'long',
                               round(pnl_usd, 2), et, round(equity, 2),
                               pos['lots'], round(pos['sl_dist'] / pip, 1)))
                pos = None
                continue  # no buscar entrada misma barra
        if pos is not None:
            continue

        # Solo intentamos entrar en ventana NY 15:00-21:00 UTC
        if hr < 15 or hr >= SESSION_END_H:
            continue
        # Filtros pre-entrada
        if orb_high is None or orb_low is None:
            continue
        rng = orb_high - orb_low
        if rng < min_rng or rng > max_rng:
            continue
        if c[i-1] >= orb_high or c[i] <= orb_high:
            # Necesitamos cross UP: previous close <= orbH, current close > orbH
            continue
        if c[i] <= ema200[i]:
            continue
        v = vwap[i]
        if not np.isnan(v) and c[i] <= v:
            continue
        if trades_today >= max_tpd:
            continue

        # Entrada
        sl_price = orb_low - buf
        tp_price = orb_high + rng * tp_mult
        entry = c[i]  # entrada al cierre del cruce
        sl_dist = entry - sl_price
        if sl_dist <= 0:
            continue
        # Equity actual: capital inicial + suma de trades cerrados
        prev_pnl = sum(t[3] for t in trades)
        equity = initial_capital + prev_pnl
        lots = min(round((equity * lot_risk) / (sl_dist / pip * pip_val), 4), max_lots)
        lots = max(lots, 0.0001)

        pos = {
            'dir': 'long', 'entry': entry,
            'sl': sl_price, 'tp': tp_price,
            'sl_dist': sl_dist, 'lots': lots,
            'entry_dt': dt, 'equity_at_entry': equity,
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
