"""
Estrategia EMA9 + EMA21 + VWAP + Stochastic (intraday daytrading)

Variante de ema9_vwap_rsi.py donde el RSI se sustituye por Stochastic(K,D).

Reglas:
1. CONTEXTO: tendencia si EMA9 > EMA21 > VWAP (compras), inverso (ventas).
2. FILTRO direccional VWAP.
3. DISPARADOR: retroceso a EMA9 + vela rechazo + STOCH en rango operable.
4. SL: bajo minimo vela rechazo (long) o sobre maximo (short).
5. TP: TP1 fijo a 1.5R parcial, resto trailing por EMA9.

StochMode:
  1 = filtro simple: Stoch_K en rango [Stoch_Buy_Min, Stoch_Buy_Max] (long) /
      [Stoch_Sell_Min, Stoch_Sell_Max] (short)
  2 = filtro + giro: ademas K > D para long (giro al alza) o K < D para short
"""
import pandas as pd
import numpy as np


DEFAULT_PARAMS = {
    'EMA_Fast':       9,
    'EMA_Mid':       21,
    'Stoch_K':        5,
    'Stoch_D':        3,
    'Stoch_Slow':     3,
    'Stoch_Buy_Min':  20,
    'Stoch_Buy_Max':  70,
    'Stoch_Sell_Min': 30,
    'Stoch_Sell_Max': 80,
    'StochMode':      1,   # 1 = solo rango, 2 = rango + giro K>D
    'ATR_Period':    14,
    'SL_ATR_Mult':  1.5,
    'MinSLPips':    0.3,
    'BE_Mult':      2.0,
    'TP1_Mult':     1.5,
    'TP1_Pct':      0.5,
    'Trail_EMA':      1,
    'WickRatio':    1.5,
    'MaxTradesDay':   3,
    'SessionStart':   0,
    'SessionEnd':    23,
    'LotRiskPct':   0.5,
    'MaxLots':      4.0,
    'Commission':   0.0,
}


def _vwap_diario(df: pd.DataFrame) -> pd.Series:
    df_ = df.copy()
    tp = (df_['high'] + df_['low'] + df_['close']) / 3
    vol = df_.get('volume', pd.Series(1.0, index=df.index))
    tpv = tp * vol
    df_['date'] = df_.index.date
    cum_tpv = tpv.groupby(df_['date']).cumsum()
    cum_vol = vol.groupby(df_['date']).cumsum()
    return cum_tpv / cum_vol.replace(0, np.nan)


def _stoch(df: pd.DataFrame, k: int, d: int, slow: int) -> tuple:
    low_k = df['low'].rolling(k).min()
    high_k = df['high'].rolling(k).max()
    rng = (high_k - low_k).replace(0, np.nan)
    pct_k_raw = 100 * (df['close'] - low_k) / rng
    pct_k = pct_k_raw.rolling(slow).mean()
    pct_d = pct_k.rolling(d).mean()
    return pct_k, pct_d


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    df = df.copy()
    df['ema9']  = df['close'].ewm(span=p['EMA_Fast'], adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=p['EMA_Mid'], adjust=False).mean()
    df['vwap']  = _vwap_diario(df)
    sk, sd = _stoch(df, p['Stoch_K'], p['Stoch_D'], p['Stoch_Slow'])
    df['stoch_k'] = sk
    df['stoch_d'] = sd
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/p['ATR_Period'], adjust=False, min_periods=p['ATR_Period']).mean()
    return df


def _es_vela_rechazo(o, h, l, c, ratio):
    body = abs(c - o)
    if body == 0:
        body = 1e-9
    if c > o:
        wick = min(o, c) - l
    else:
        wick = h - max(o, c)
    return wick >= ratio * body


def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 pip: float = 1.0, pip_val: float = 100.0) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    warmup = max(p['EMA_Mid'], p['ATR_Period'], p['Stoch_K'] + p['Stoch_D'] + p['Stoch_Slow']) * 4 + 2

    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    ema9 = df['ema9'].values; ema21 = df['ema21'].values
    vwap = df['vwap'].values
    sk_arr = df['stoch_k'].values
    sd_arr = df['stoch_d'].values
    atr  = df['atr'].values
    idx  = df.index

    sl_mult   = p['SL_ATR_Mult']
    min_sl    = p['MinSLPips'] * pip
    be_mult   = p['BE_Mult']
    tp1_mult  = p['TP1_Mult']
    tp1_pct   = p['TP1_Pct']
    trail_ema = p['Trail_EMA']
    wick_ratio= p['WickRatio']
    bmin = p['Stoch_Buy_Min'];  bmax = p['Stoch_Buy_Max']
    smin = p['Stoch_Sell_Min']; smax = p['Stoch_Sell_Max']
    stoch_mode = p['StochMode']
    max_td    = p['MaxTradesDay']
    sess_s    = p['SessionStart']; sess_e   = p['SessionEnd']
    lot_risk  = p['LotRiskPct'] / 100
    max_lots  = p['MaxLots']

    pos = None
    trades = []
    trades_today = 0
    last_date = None
    equity = initial_capital

    for i in range(warmup, len(df)):
        dt = idx[i]
        date = dt.date()
        if date != last_date:
            trades_today = 0
            last_date = date

        if pos is not None:
            if pos['dir'] == 'long':
                profit_R = (o[i] - pos['entry']) / pos['sl_dist']
                if profit_R >= be_mult and pos['sl'] < pos['entry']:
                    pos['sl'] = pos['entry']
            else:
                profit_R = (pos['entry'] - o[i]) / pos['sl_dist']
                if profit_R >= be_mult and pos['sl'] > pos['entry']:
                    pos['sl'] = pos['entry']

            if not pos['tp1_hit']:
                if pos['dir'] == 'long' and h[i] >= pos['tp1']:
                    pnl_part = (pos['tp1'] - pos['entry']) / pip * pip_val * pos['lots'] * tp1_pct
                    equity += pnl_part
                    pos['lots'] *= (1 - tp1_pct)
                    pos['tp1_hit'] = True
                    pos['pnl_part'] = pnl_part
                elif pos['dir'] == 'short' and l[i] <= pos['tp1']:
                    pnl_part = (pos['entry'] - pos['tp1']) / pip * pip_val * pos['lots'] * tp1_pct
                    equity += pnl_part
                    pos['lots'] *= (1 - tp1_pct)
                    pos['tp1_hit'] = True
                    pos['pnl_part'] = pnl_part

            if pos['tp1_hit'] and trail_ema:
                if pos['dir'] == 'long' and c[i-1] < ema9[i-1]:
                    pnl_rest = (c[i] - pos['entry']) / pip * pip_val * pos['lots']
                    equity += pnl_rest
                    trades.append((pos['entry_dt'], dt, pos['dir'],
                                   round(pos.get('pnl_part', 0) + pnl_rest, 2), 'TRAIL',
                                   round(equity,2), pos['lots_open'],
                                   round(pos['sl_dist']/pip, 2)))
                    pos = None
                    continue
                elif pos['dir'] == 'short' and c[i-1] > ema9[i-1]:
                    pnl_rest = (pos['entry'] - c[i]) / pip * pip_val * pos['lots']
                    equity += pnl_rest
                    trades.append((pos['entry_dt'], dt, pos['dir'],
                                   round(pos.get('pnl_part', 0) + pnl_rest, 2), 'TRAIL',
                                   round(equity,2), pos['lots_open'],
                                   round(pos['sl_dist']/pip, 2)))
                    pos = None
                    continue

            ep = et = None
            if pos['dir'] == 'long':
                if l[i] <= pos['sl']:
                    ep, et = pos['sl'], 'SL'
            else:
                if h[i] >= pos['sl']:
                    ep, et = pos['sl'], 'SL'

            if ep is not None:
                pnl_close = ((ep - pos['entry']) if pos['dir']=='long' else (pos['entry']-ep)) / pip * pip_val * pos['lots']
                pnl_part = pos.get('pnl_part', 0)
                equity += pnl_close
                trades.append((pos['entry_dt'], dt, pos['dir'],
                               round(pnl_part + pnl_close, 2), et,
                               round(equity,2), pos['lots_open'],
                               round(pos['sl_dist']/pip, 2)))
                pos = None
                continue

        if pos is not None:
            continue

        hr = dt.hour
        if hr < sess_s or hr >= sess_e: continue
        if dt.weekday() >= 5: continue
        if trades_today >= max_td: continue
        if i < warmup + 1: continue

        e9 = ema9[i-1]; e21 = ema21[i-1]; vw = vwap[i-1]
        sk = sk_arr[i-1]; sd = sd_arr[i-1]
        a1 = atr[i-1]
        if np.isnan(e9) or np.isnan(e21) or np.isnan(vw) or np.isnan(sk) or np.isnan(a1):
            continue
        if a1 <= 0: continue

        cond_trend_up   = (e9 > e21 > vw and c[i-1] > vw)
        cond_trend_down = (e9 < e21 < vw and c[i-1] < vw)
        if not cond_trend_up and not cond_trend_down: continue

        toco_ema9 = (l[i-1] <= e9 <= h[i-1])
        if not toco_ema9: continue

        vela_rechazo = _es_vela_rechazo(o[i-1], h[i-1], l[i-1], c[i-1], wick_ratio)
        if not vela_rechazo: continue

        # Stoch filter
        stoch_ok_long  = (bmin <= sk <= bmax)
        stoch_ok_short = (smin <= sk <= smax)
        if stoch_mode == 2:
            stoch_ok_long  = stoch_ok_long  and (sk > sd)
            stoch_ok_short = stoch_ok_short and (sk < sd)

        cond_long  = cond_trend_up   and c[i-1] > o[i-1] and stoch_ok_long
        cond_short = cond_trend_down and c[i-1] < o[i-1] and stoch_ok_short

        if not cond_long and not cond_short: continue

        entry = o[i]
        if cond_long:
            sl_price = l[i-1]
        else:
            sl_price = h[i-1]
        sl_dist = abs(entry - sl_price)
        sl_dist = max(sl_dist, min_sl)
        if sl_dist > a1 * sl_mult * 2:
            sl_dist = a1 * sl_mult * 2

        tp1 = entry + sl_dist * tp1_mult if cond_long else entry - sl_dist * tp1_mult
        lots = min(round((equity * lot_risk) / (sl_dist / pip * pip_val), 4), max_lots)
        lots = max(lots, 0.0001)

        pos = {
            'dir': 'long' if cond_long else 'short',
            'entry': entry, 'sl_dist': sl_dist,
            'sl': entry - sl_dist if cond_long else entry + sl_dist,
            'tp1': tp1, 'tp1_hit': False, 'pnl_part': 0,
            'lots': lots, 'lots_open': lots, 'entry_dt': dt,
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
