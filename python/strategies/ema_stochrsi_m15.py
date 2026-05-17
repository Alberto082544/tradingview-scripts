"""
Strategy: EMA200+StochRSI (Trend Following H4+M15)

Idea (hilo @aza_92i de X/Twitter, sin codigo previo):
  H4: EMA200 define direccion estructural (close > EMA200 = alcista, viceversa)
  H4: zona de recarga entre EMA13 y EMA32 — pullback dentro de la tendencia
  M15: Stoch RSI extremo dispara la entrada
       Long  → StochRSI < Stoch_Buy_Max  (sobreventa en M15)
       Short → StochRSI > Stoch_Sell_Min (sobrecompra en M15)

Gestion:
  SL = ATR(M15) * SL_ATR_Mult, con min/max
  TP = SL * RR
  BE  + Trailing opcionales
"""
import pandas as pd
import numpy as np


DEFAULT_PARAMS = {
    'EMA_Long_H4':    200,
    'EMA_Fast_H4':     13,
    'EMA_Slow_H4':     32,
    'StochRSI_Period': 14,
    'StochRSI_K':       3,
    'Stoch_Buy_Max':   15,    # umbral sobreventa en M15
    'Stoch_Sell_Min':  85,    # umbral sobrecompra en M15
    'ATR_Period':      14,
    'SL_ATR_Mult':    1.5,
    'MinSLPips':       10,
    'MaxSLPips':      200,
    'RR':              2.0,
    'BE_Trigger':      1.0,
    'BE_Offset':      0.0002,
    'Trail_Start':     1.5,
    'Trail_Dist':      0.5,
    'LotRiskPct':      0.5,
    'MaxLots':         4.0,
    'BadHour':         -1,
    'SessionStart':     0,
    'SessionEnd':      23,
    'MaxTradesDay':     5,
    'UsePullbackZone':  1,   # 1 = exigir que el precio este en EMA13-EMA32, 0 = solo direccion
}


def _stoch_rsi(close: pd.Series, period: int, k_smooth: int) -> pd.Series:
    """StochRSI: aplica el oscilador Stochastic sobre el RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period-1, min_periods=period).mean()
    loss = (-delta).clip(lower=0).ewm(com=period-1, min_periods=period).mean()
    rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    lo  = rsi.rolling(period).min()
    hi  = rsi.rolling(period).max()
    sk  = 100 * (rsi - lo) / (hi - lo).replace(0, np.nan)
    return sk.rolling(k_smooth).mean()


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p  = DEFAULT_PARAMS if params is None else params
    df = df.copy()

    # H4 — direccion y zona de recarga
    df_h4 = df[['close']].resample('4h').last().dropna()
    df_h4['ema200'] = df_h4['close'].ewm(span=p['EMA_Long_H4'], adjust=False).mean()
    df_h4['ema13']  = df_h4['close'].ewm(span=p['EMA_Fast_H4'], adjust=False).mean()
    df_h4['ema32']  = df_h4['close'].ewm(span=p['EMA_Slow_H4'], adjust=False).mean()
    df_h4['close_h4'] = df_h4['close']

    for col in ['ema200', 'ema13', 'ema32', 'close_h4']:
        df[col] = df_h4[col].reindex(df.index, method='ffill')

    # M15 — StochRSI y ATR
    df['stochrsi'] = _stoch_rsi(df['close'], p['StochRSI_Period'], p['StochRSI_K'])

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
    p      = DEFAULT_PARAMS if params is None else params
    warmup = p['EMA_Long_H4'] * 8 + p['StochRSI_Period'] + 2

    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    ema200 = df['ema200'].values; ema13 = df['ema13'].values
    ema32  = df['ema32'].values;  close_h4 = df['close_h4'].values
    stoch  = df['stochrsi'].values
    atr    = df['atr'].values
    idx    = df.index

    sl_mult   = p['SL_ATR_Mult']
    rr        = p['RR']
    be_trig   = p['BE_Trigger']
    be_off    = p['BE_Offset']
    tr_start  = p['Trail_Start']
    tr_dist   = p['Trail_Dist']
    min_sl    = p['MinSLPips'] * pip
    max_sl    = p['MaxSLPips'] * pip
    buy_max   = p['Stoch_Buy_Max']
    sell_min  = p['Stoch_Sell_Min']
    lot_risk  = p['LotRiskPct'] / 100
    max_lots  = p['MaxLots']
    bad_h     = p['BadHour']
    sess_s    = p['SessionStart']
    sess_e    = p['SessionEnd']
    max_td    = p['MaxTradesDay']
    use_zone  = p.get('UsePullbackZone', 1)

    equity = initial_capital
    pos    = None
    trades = []
    trades_today = 0
    last_date    = None

    for i in range(warmup, len(df)):
        dt = idx[i]
        d  = dt.date()
        if d != last_date:
            trades_today = 0
            last_date    = d

        o_i = o[i]; h_i = h[i]; l_i = l[i]; c_i = c[i]

        # === Gestion posicion abierta ===
        if pos is not None:
            atr_now = atr[i]
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

        # === Filtros ===
        hr = dt.hour
        if hr < sess_s or hr >= sess_e: continue
        if bad_h >= 0 and hr == bad_h:  continue
        if dt.weekday() >= 5 or (dt.weekday() == 4 and hr >= 22): continue
        if trades_today >= max_td:      continue

        atr1 = atr[i-1]
        if np.isnan(atr1) or atr1 <= 0: continue
        if np.isnan(ema200[i-1]) or np.isnan(stoch[i-1]): continue

        # === Condiciones de entrada ===
        bull_trend = close_h4[i-1] > ema200[i-1]
        bear_trend = close_h4[i-1] < ema200[i-1]

        # Zona de recarga (precio entre EMA13 y EMA32)
        in_zone_long  = (close_h4[i-1] >= min(ema13[i-1], ema32[i-1]) and
                         close_h4[i-1] <= max(ema13[i-1], ema32[i-1]))
        in_zone_short = in_zone_long  # misma zona, distinta direccion

        cond_long  = bull_trend and (not use_zone or in_zone_long)  and stoch[i-1] < buy_max
        cond_short = bear_trend and (not use_zone or in_zone_short) and stoch[i-1] > sell_min
        if not cond_long and not cond_short:
            continue

        # SL/TP
        sl_dist = max(atr1 * sl_mult, min_sl)
        if sl_dist > max_sl: continue
        tp_dist = sl_dist * rr

        entry = o_i
        lots  = min(round((equity * lot_risk) / (sl_dist / pip * pip_val), 2), max_lots)
        lots  = max(lots, 0.01)
        direc = 'long' if cond_long else 'short'

        pos = {
            'dir': direc, 'entry': entry,
            'sl': entry - sl_dist if direc == 'long' else entry + sl_dist,
            'tp': entry + tp_dist if direc == 'long' else entry - tp_dist,
            'sl_dist': sl_dist, 'lots': lots,
            'atr_entry': atr1, 'entry_dt': dt,
        }
        trades_today += 1

    if not trades:
        return pd.DataFrame(columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])
    return pd.DataFrame(trades, columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])


def compute_metrics(trades: pd.DataFrame, initial_capital: float = 50_000) -> dict:
    if trades is None or len(trades) == 0:
        return {'n':0,'pnl':0,'wr':0,'pf':0,'dd_pct':0,'ann_pct':0,'calmar':0}
    n    = len(trades)
    pnl  = trades['pnl'].sum()
    wr   = (trades['pnl'] > 0).mean() * 100
    wins = trades.loc[trades['pnl'] > 0, 'pnl']
    loss = trades.loc[trades['pnl'] < 0, 'pnl']
    pf   = wins.sum() / abs(loss.sum()) if len(loss) > 0 and loss.sum() != 0 else 0
    eq   = np.concatenate([[initial_capital], trades['equity'].values])
    pk   = np.maximum.accumulate(eq)
    dd   = abs(((eq - pk) / pk).min()) * 100
    yrs  = (pd.to_datetime(trades['exit_dt'].iloc[-1]) -
            pd.to_datetime(trades['entry_dt'].iloc[0])).days / 365.25
    ann  = ((initial_capital + pnl) / initial_capital) ** (1 / max(yrs, 0.01)) - 1
    return {'n':n,'pnl':round(pnl,0),'wr':round(wr,1),'pf':round(pf,2),
            'dd_pct':round(dd,2),'ann_pct':round(ann*100,2),
            'calmar':round((ann*100)/dd,2) if dd>0 else 0}
