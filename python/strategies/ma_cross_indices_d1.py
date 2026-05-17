"""
MA Cross D1 para Índices — Cruce EMA/SMA diario con filtro semanal
Lógica idéntica a ma_cross_m15.py pero adaptada a D1 + filtro W1.

W1: EMA(dir_fast) > SMA(dir_slow)  → solo longs
    EMA(dir_fast) < SMA(dir_slow)  → solo shorts
D1: cruce EMA(fast) sobre SMA(slow) en dirección del W1
SL: ATR * sl_mult
BE + Trailing como en la versión M15

Índices: pip = 1 punto = 1.0 | pip_val depende del broker (por defecto $1/punto/lote)
"""
import pandas as pd
import numpy as np

DEFAULT_PARAMS = {
    'EMA_Fast':       8,
    'SMA_Slow':      21,
    'Dir_EMA_Fast':   8,
    'Dir_SMA_Slow':  21,
    'ATR_Period':    14,
    'SL_ATR_Mult':  1.5,
    'RR':           2.0,
    'BE_Trigger':   1.0,
    'BE_Offset':    1.0,    # 1 punto de offset
    'Trail_Start':  1.5,
    'Trail_Dist':   1.0,
    'LotRiskPct':   0.5,
    'MaxLots':      4.0,
}

INDEX_CONFIG = {
    'NAS100': {'pip': 1.0, 'pip_val': 1.0},   # $1/punto/lote
    'SP500':  {'pip': 1.0, 'pip_val': 1.0},   # $1/punto/lote
    'DAX40':  {'pip': 1.0, 'pip_val': 1.0},   # €1/punto/lote (usamos USD aprox)
    'UK100':  {'pip': 1.0, 'pip_val': 1.28},  # £1/punto → ~$1.28
}


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p  = DEFAULT_PARAMS if params is None else {**DEFAULT_PARAMS, **params}
    df = df.copy()

    df['ema_fast'] = df['close'].ewm(span=p['EMA_Fast'], adjust=False).mean()
    df['sma_slow'] = df['close'].rolling(p['SMA_Slow']).mean()

    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/p['ATR_Period'], adjust=False, min_periods=p['ATR_Period']).mean()

    df_w = df[['close']].resample('W').last().dropna()
    df_w['dir_ema'] = df_w['close'].ewm(span=p['Dir_EMA_Fast'], adjust=False).mean()
    df_w['dir_sma'] = df_w['close'].rolling(p['Dir_SMA_Slow']).mean()
    df['dir_ema'] = df_w['dir_ema'].reindex(df.index, method='ffill')
    df['dir_sma'] = df_w['dir_sma'].reindex(df.index, method='ffill')

    return df


def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 pip: float = 1.0,
                 pip_val: float = 1.0) -> pd.DataFrame:
    p      = DEFAULT_PARAMS if params is None else {**DEFAULT_PARAMS, **params}
    warmup = max(p['SMA_Slow'], p['Dir_SMA_Slow']) * 5 + p['ATR_Period'] + 2

    o        = df['open'].values
    h        = df['high'].values
    l        = df['low'].values
    ema_fast = df['ema_fast'].values
    sma_slow = df['sma_slow'].values
    atr_arr  = df['atr'].values
    dir_ema  = df['dir_ema'].values
    dir_sma  = df['dir_sma'].values
    idx      = df.index

    sl_mult  = p['SL_ATR_Mult']
    rr       = p['RR']
    be_trig  = p['BE_Trigger']
    be_off   = p['BE_Offset']
    tr_start = p['Trail_Start']
    tr_dist  = p['Trail_Dist']
    lot_risk = p['LotRiskPct'] / 100
    max_lots = p['MaxLots']

    equity = initial_capital
    pos    = None
    trades = []

    for i in range(warmup, len(df)):
        dt  = idx[i]
        o_i = o[i]; h_i = h[i]; l_i = l[i]

        if pos is not None:
            atr_now = atr_arr[i]
            profit_dist = (o_i - pos['entry']) if pos['dir'] == 'long' else (pos['entry'] - o_i)

            if be_trig > 0 and profit_dist >= be_trig * pos['atr_entry']:
                be_sl = (pos['entry'] + be_off) if pos['dir'] == 'long' else (pos['entry'] - be_off)
                if pos['dir'] == 'long'  and be_sl > pos['sl']: pos['sl'] = be_sl
                if pos['dir'] == 'short' and be_sl < pos['sl']: pos['sl'] = be_sl

            if tr_start > 0 and profit_dist >= tr_start * pos['atr_entry']:
                if pos['dir'] == 'long':
                    new_sl = o_i - tr_dist * atr_now
                    if new_sl > pos['sl']: pos['sl'] = new_sl
                else:
                    new_sl = o_i + tr_dist * atr_now
                    if new_sl < pos['sl']: pos['sl'] = new_sl

            ep = et = None
            if pos['dir'] == 'long':
                if l_i <= pos['sl']:   ep, et = pos['sl'], 'SL'
                elif h_i >= pos['tp']: ep, et = pos['tp'], 'TP'
            else:
                if h_i >= pos['sl']:   ep, et = pos['sl'], 'SL'
                elif l_i <= pos['tp']: ep, et = pos['tp'], 'TP'

            if ep is not None:
                pnl_usd = ((ep - pos['entry']) if pos['dir'] == 'long' else (pos['entry'] - ep)) / pip * pip_val * pos['lots']
                equity += pnl_usd
                trades.append((pos['entry_dt'], dt, pos['dir'],
                                round(pnl_usd, 2), et, round(equity, 2),
                                pos['lots'], round(pos['sl_dist'] / pip, 1)))
                pos = None

        if pos is not None:
            continue

        atr1 = atr_arr[i-1]
        if np.isnan(atr1) or atr1 <= 0: continue

        ema_prev = ema_fast[i-2]; ema_curr = ema_fast[i-1]
        sma_prev = sma_slow[i-2]; sma_curr = sma_slow[i-1]
        cross_up   = (ema_prev <= sma_prev and ema_curr > sma_curr)
        cross_down = (ema_prev >= sma_prev and ema_curr < sma_curr)
        if not cross_up and not cross_down: continue

        bias_bull = dir_ema[i-1] > dir_sma[i-1]
        bias_bear = dir_ema[i-1] < dir_sma[i-1]
        if cross_up   and not bias_bull: continue
        if cross_down and not bias_bear: continue

        sl_dist = atr1 * sl_mult
        tp_dist = sl_dist * rr if rr > 0 else 9999 * pip
        entry   = o_i
        lots    = min(round((equity * lot_risk) / (sl_dist / pip * pip_val), 2), max_lots)
        lots    = max(lots, 0.01)
        direc   = 'long' if cross_up else 'short'

        pos = {
            'dir': direc, 'entry': entry,
            'sl':  entry - sl_dist if direc == 'long' else entry + sl_dist,
            'tp':  entry + tp_dist if direc == 'long' else entry - tp_dist,
            'sl_dist': sl_dist, 'lots': lots,
            'atr_entry': atr1, 'entry_dt': dt,
        }

    if not trades:
        return pd.DataFrame(columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])
    return pd.DataFrame(trades, columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])


def compute_metrics(trades: pd.DataFrame, initial_capital: float = 50_000) -> dict:
    if trades is None or len(trades) == 0:
        return {'n':0,'pnl':0,'wr':0,'pf':0,'dd_pct':0,'ann_pct':0}
    n   = len(trades)
    pnl = trades['pnl'].sum()
    wr  = (trades['pnl'] > 0).mean() * 100
    wins = trades.loc[trades['pnl'] > 0, 'pnl']
    loss = trades.loc[trades['pnl'] < 0, 'pnl']
    pf  = wins.sum() / abs(loss.sum()) if len(loss) > 0 and loss.sum() != 0 else 0
    eq  = np.concatenate([[initial_capital], trades['equity'].values])
    pk  = np.maximum.accumulate(eq)
    dd  = abs(((eq - pk) / pk).min()) * 100
    yrs = (pd.to_datetime(trades['exit_dt'].iloc[-1]) -
           pd.to_datetime(trades['entry_dt'].iloc[0])).days / 365.25
    ann = ((initial_capital + pnl) / initial_capital) ** (1 / max(yrs, 0.01)) - 1
    return {'n':n,'pnl':round(pnl,0),'wr':round(wr,1),'pf':round(pf,2),
            'dd_pct':round(dd,1),'ann_pct':round(ann*100,2)}
