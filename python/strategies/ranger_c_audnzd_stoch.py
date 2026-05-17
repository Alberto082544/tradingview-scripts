"""
Ranger C AUDNZD STOCH — Mean Reversion H4+M15 con Estocastico
Familia: Ranger C | Par: AUDNZD (ambas direcciones)

Variante con Estocastico anyadida al AUDNZD original.
Recomendacion CrewAI: Stochastic(5,3,3) + ADX_H4 < 20 para mean reversion forex.

  pip = 0.0001 (4 decimales)
  pip_val = pip * 100000 * NZDUSD
  ADX H4 < umbral como filtro de regimen (lateral)
  StochMode: 0=RSI solo (baseline), 1=Stoch solo, 2=ambos confirman
"""
import pandas as pd
import numpy as np

PIP    = 0.0001
NZDUSD = 0.60

DEFAULT_PARAMS = {
    'BB_Period':        20,
    'BB_StdDev':       2.0,
    'RSI_Period':       14,
    'RSI_Long_Max':     45,
    'RSI_Short_Min':    55,
    'RSI_Confirm':       1,
    # Estocástico (StochMode: 0=RSI solo, 1=Stoch solo, 2=ambos)
    'StochMode':         0,
    'Stoch_K':           5,
    'Stoch_D':           3,
    'Stoch_Long_Max':   25,
    'Stoch_Short_Min':  75,
    'ADX_H4_Period':    14,
    'ADX_H4_Max':       25,
    'ATR_Period':       14,
    'SL_ATR_Mult':     1.5,
    'MinSLPips':        10,
    'MaxSLPips':       999,
    'BB_Mid_TP':         1,
    'TP_ATR_Mult':       0,
    'TrailActivate':   0.5,
    'TrailDistPips':    10,
    'ExitBars':         16,
    'SessionStart':      0,
    'SessionEnd':       23,
    'BadHour':          -1,
    'MaxTradesDay':      5,
    'LotRiskPct':      0.7,
    'MaxLots':         4.0,
}


def _calc_adx(df: pd.DataFrame, period: int) -> pd.Series:
    hl  = df['high'] - df['low']
    hc  = (df['high'] - df['close'].shift()).abs()
    lc  = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    up  = df['high'].diff()
    dn  = (-df['low'].diff())
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a   = 1 / period
    atr = tr.ewm(alpha=a, adjust=False, min_periods=period).mean()
    pdi = 100 * pd.Series(pdm, index=df.index).ewm(alpha=a, adjust=False, min_periods=period).mean() / atr
    mdi = 100 * pd.Series(mdm, index=df.index).ewm(alpha=a, adjust=False, min_periods=period).mean() / atr
    dx  = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).fillna(0)
    return dx.ewm(alpha=a, adjust=False, min_periods=period).mean()


def _calc_stoch(df: pd.DataFrame, k: int, d: int) -> pd.DataFrame:
    low_k  = df['low'].rolling(k).min()
    high_k = df['high'].rolling(k).max()
    pct_k  = 100 * (df['close'] - low_k) / (high_k - low_k).replace(0, np.nan)
    pct_d  = pct_k.rolling(d).mean()
    return pct_k, pct_d


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p  = DEFAULT_PARAMS if params is None else params
    df = df.copy()

    df['bb_mid']   = df['close'].rolling(p['BB_Period']).mean()
    df['bb_std']   = df['close'].rolling(p['BB_Period']).std(ddof=0)
    df['bb_upper'] = df['bb_mid'] + p['BB_StdDev'] * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - p['BB_StdDev'] * df['bb_std']

    delta    = df['close'].diff()
    avg_gain = delta.clip(lower=0).ewm(com=p['RSI_Period']-1, min_periods=p['RSI_Period']).mean()
    avg_loss = (-delta).clip(lower=0).ewm(com=p['RSI_Period']-1, min_periods=p['RSI_Period']).mean()
    df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, np.nan)))

    df['stoch_k'], df['stoch_d'] = _calc_stoch(df, p['Stoch_K'], p['Stoch_D'])

    hl  = df['high'] - df['low']
    hc  = (df['high'] - df['close'].shift()).abs()
    lc  = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/p['ATR_Period'], adjust=False, min_periods=p['ATR_Period']).mean()

    df_h4 = df[['high','low','close']].resample('4h').agg(
        {'high':'max','low':'min','close':'last'}).dropna()
    df['adx_h4'] = _calc_adx(df_h4, p['ADX_H4_Period']).reindex(df.index, method='ffill')

    return df


def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 nzdusd: float = NZDUSD) -> pd.DataFrame:
    p       = DEFAULT_PARAMS if params is None else params
    pip_val = PIP * 100_000 * nzdusd
    warmup  = p['BB_Period'] * 8 + p['ATR_Period'] + 2

    o        = df['open'].values
    h        = df['high'].values
    l        = df['low'].values
    c        = df['close'].values
    bb_up    = df['bb_upper'].values
    bb_lo    = df['bb_lower'].values
    bb_mi    = df['bb_mid'].values
    rsi_arr  = df['rsi'].values
    atr_arr  = df['atr'].values
    adx_arr  = df['adx_h4'].values
    idx      = df.index

    adx_max     = p['ADX_H4_Max']
    rsi_lo      = p['RSI_Long_Max']
    rsi_hi      = p['RSI_Short_Min']
    rsi_confirm = p.get('RSI_Confirm', 1)
    stoch_mode  = p.get('StochMode', 0)
    stoch_lo    = p.get('Stoch_Long_Max', 25)
    stoch_hi    = p.get('Stoch_Short_Min', 75)
    stoch_k_arr = df['stoch_k'].values
    stoch_d_arr = df['stoch_d'].values
    bb_mid_tp   = p['BB_Mid_TP']
    min_sl      = p['MinSLPips'] * PIP
    max_sl      = p['MaxSLPips'] * PIP
    sl_mult     = p['SL_ATR_Mult']
    tp_fix      = 999 * PIP
    trail_dist  = p['TrailDistPips'] * PIP
    trail_act   = p['TrailActivate']
    exit_bars   = p['ExitBars']
    sess_s      = p['SessionStart']
    sess_e      = p['SessionEnd']
    bad_h       = p['BadHour']
    max_td      = p['MaxTradesDay']
    lot_risk    = p['LotRiskPct'] / 100
    max_lots    = p['MaxLots']

    equity = initial_capital
    pos    = None
    trades = []
    trades_today = 0
    last_date    = None

    for i in range(warmup, len(df)):
        dt   = idx[i]
        date = dt.date()
        if date != last_date:
            trades_today = 0
            last_date    = date

        o_i = o[i]; h_i = h[i]; l_i = l[i]; c_i = c[i]

        if pos is not None:
            if pos['dir'] == 'long':
                if (o_i - pos['entry']) >= trail_act * pos['sl_dist']:
                    new_sl = o_i - trail_dist
                    if new_sl > pos['sl']:
                        pos['sl'] = new_sl
            else:
                if (pos['entry'] - o_i) >= trail_act * pos['sl_dist']:
                    new_sl = o_i + trail_dist
                    if new_sl < pos['sl']:
                        pos['sl'] = new_sl

        if pos is not None:
            ep = et = None
            if pos['dir'] == 'long':
                if l_i <= pos['sl']:                          ep, et = pos['sl'], 'SL'
                elif h_i >= pos['tp']:                        ep, et = pos['tp'], 'TP'
                elif bb_mid_tp and h_i >= pos['bb_mid_entry']:ep, et = pos['bb_mid_entry'], 'BB_MID'
            else:
                if h_i >= pos['sl']:                          ep, et = pos['sl'], 'SL'
                elif l_i <= pos['tp']:                        ep, et = pos['tp'], 'TP'
                elif bb_mid_tp and l_i <= pos['bb_mid_entry']:ep, et = pos['bb_mid_entry'], 'BB_MID'

            if ep is None and (i - pos['bar_idx']) >= exit_bars:
                ep, et = c_i, 'TIME'

            if ep is not None:
                pnl_usd = ((ep - pos['entry']) if pos['dir'] == 'long' else (pos['entry'] - ep)) / PIP * pip_val * pos['lots']
                equity += pnl_usd
                trades.append((pos['entry_dt'], dt, pos['dir'],
                                round(pnl_usd, 2), et, round(equity, 2),
                                pos['lots'], round(pos['sl_dist'] / PIP, 1)))
                pos = None

        if pos is not None:
            continue

        hr = dt.hour
        if hr < sess_s or hr >= sess_e: continue
        if hr == bad_h:                 continue
        if dt.weekday() >= 5 or (dt.weekday() == 4 and hr >= 22): continue
        if trades_today >= max_td:      continue

        adx1 = adx_arr[i-1]
        if np.isnan(adx1) or adx1 >= adx_max: continue

        atr1 = atr_arr[i-1]
        rsi1 = rsi_arr[i-1]; rsi2 = rsi_arr[i-2]
        sk1  = stoch_k_arr[i-1]; sd1 = stoch_d_arr[i-1]
        if np.isnan(atr1) or atr1 <= 0 or np.isnan(rsi1): continue

        # Filtro RSI
        rsi_ok_long  = rsi1 < rsi_lo and (not rsi_confirm or rsi1 > rsi2)
        rsi_ok_short = rsi1 > rsi_hi and (not rsi_confirm or rsi1 < rsi2)
        # Filtro Estocástico (K < umbral y K > D para confirmación de giro)
        stoch_ok_long  = (not np.isnan(sk1)) and sk1 < stoch_lo and sk1 > sd1
        stoch_ok_short = (not np.isnan(sk1)) and sk1 > stoch_hi and sk1 < sd1

        # Combinar según modo
        if stoch_mode == 0:    # RSI solo
            ok_long = rsi_ok_long;   ok_short = rsi_ok_short
        elif stoch_mode == 1:  # Estocástico solo
            ok_long = stoch_ok_long; ok_short = stoch_ok_short
        else:                  # Ambos deben confirmar
            ok_long = rsi_ok_long  and stoch_ok_long
            ok_short = rsi_ok_short and stoch_ok_short

        cond_long  = (c[i-1] <= bb_lo[i-1] * 1.001 and ok_long)
        cond_short = (not cond_long and c[i-1] >= bb_up[i-1] * 0.999 and ok_short)

        if not cond_long and not cond_short: continue

        sl_dist = max(atr1 * sl_mult, min_sl)
        if sl_dist > max_sl: continue

        entry = o_i
        lots  = min(round((equity * lot_risk) / (sl_dist / PIP * pip_val), 2), max_lots)
        lots  = max(lots, 0.01)
        direc = 'long' if cond_long else 'short'

        pos = {
            'dir': direc,
            'entry': entry,
            'sl': entry - sl_dist if direc == 'long' else entry + sl_dist,
            'tp': entry + tp_fix  if direc == 'long' else entry - tp_fix,
            'sl_dist': sl_dist, 'lots': lots,
            'bar_idx': i, 'entry_dt': dt,
            'bb_mid_entry': bb_mi[i-1],
        }
        trades_today += 1

    if not trades:
        return pd.DataFrame(columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])
    return pd.DataFrame(trades, columns=['entry_dt','exit_dt','direction','pnl','exit_type','equity','lots','sl_pips'])


def compute_metrics(trades: pd.DataFrame, initial_capital: float = 50_000) -> dict:
    if trades is None or len(trades) == 0:
        return {'n':0,'pnl':0,'wr':0,'pf':0,'dd_pct':0,'ann_pct':0,'calmar':0,'avg_w':0,'avg_l':0}
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
            'dd_pct':round(dd,1),'ann_pct':round(ann*100,2),
            'calmar':round((ann*100)/dd,2) if dd>0 else 0,
            'avg_w':round(wins.mean(),0) if len(wins)>0 else 0,
            'avg_l':round(loss.mean(),0) if len(loss)>0 else 0,
            'exits':trades['exit_type'].value_counts().to_dict()}
