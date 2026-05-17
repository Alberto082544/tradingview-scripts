"""Jasper OB + filtros de nuestros bots ganadores.

Versión mejorada del Jasper OB añadiendo combinaciones de:
  - EMA200 H4 (filtro tendencia mayor — de MA Cross)
  - ADX H4 (filtro régimen — de Ranger C)
  - VWAP diario (de EMA9+VWAP+RSI)
  - Stochastic confirmation (de Ranger C / EMA9)
  - Vela de rechazo wick ratio (de EMA9+VWAP+RSI)
  - Sesión NY 13-21 UTC (de XAUUSD ORB)

Todos los filtros son opcionales via flags para A/B testing.
"""
import pandas as pd
import numpy as np


DEFAULT_PARAMS = {
    # ORIGINAL JASPER OB
    'RR':           2.0,
    'BufferATR':    0.5,
    'ATR_Period':   14,
    'MinSLPips':    5.0,
    'MaxSLPips':  200.0,
    'MaxOBBars':    50,
    'MaxTradesDay':  3,
    'LotRiskPct':   0.5,
    'MaxLots':      4.0,
    # FILTROS OPCIONALES (cada uno con flag)
    'UseEMA200H4':       0,   # 1 = solo OBs a favor de EMA200 H4
    'EMA200H4_Period':   200,
    'UseADXH4':          0,   # 1 = exigir ADX H4 > UmbralADX
    'ADXH4_Period':       14,
    'ADXH4_Min':          20,
    'UseVWAP':           0,   # 1 = solo OBs a favor del VWAP diario
    'UseStoch':          0,   # 1 = confirmar con Stochastic
    'Stoch_K':            5,
    'Stoch_D':            3,
    'Stoch_Long_Max':    30,  # long: K < 30 (sobreventa)
    'Stoch_Short_Min':   70,  # short: K > 70 (sobrecompra)
    'UseWick':           0,   # 1 = exigir vela de rechazo
    'WickRatio':        1.5,
    'UseNYSession':      0,   # 1 = solo opera 13-21 UTC
    'SessionStart':       0,
    'SessionEnd':        23,
}


def _calc_adx(df_h4: pd.DataFrame, period: int) -> pd.Series:
    hl = df_h4['high'] - df_h4['low']
    hc = (df_h4['high'] - df_h4['close'].shift()).abs()
    lc = (df_h4['low']  - df_h4['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    up = df_h4['high'].diff()
    dn = (-df_h4['low'].diff())
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = 1 / period
    atr = tr.ewm(alpha=a, adjust=False, min_periods=period).mean()
    pdi = 100 * pd.Series(pdm, index=df_h4.index).ewm(alpha=a, adjust=False, min_periods=period).mean() / atr
    mdi = 100 * pd.Series(mdm, index=df_h4.index).ewm(alpha=a, adjust=False, min_periods=period).mean() / atr
    dx = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).fillna(0)
    return dx.ewm(alpha=a, adjust=False, min_periods=period).mean()


def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    df = df.copy()

    # ATR M15
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/p['ATR_Period'], adjust=False, min_periods=p['ATR_Period']).mean()

    # EMA200 H4 (filtro tendencia mayor)
    if p.get('UseEMA200H4', 0):
        df_h4 = df[['close']].resample('4h').last().dropna()
        ema = df_h4['close'].ewm(span=p['EMA200H4_Period'], adjust=False).mean()
        df['ema200_h4'] = ema.reindex(df.index, method='ffill')
        df['close_h4'] = df_h4['close'].reindex(df.index, method='ffill')

    # ADX H4
    if p.get('UseADXH4', 0):
        df_h4 = df[['high','low','close']].resample('4h').agg(
            {'high':'max','low':'min','close':'last'}).dropna()
        adx_h4 = _calc_adx(df_h4, p['ADXH4_Period'])
        df['adx_h4'] = adx_h4.reindex(df.index, method='ffill')

    # VWAP diario
    if p.get('UseVWAP', 0):
        tp = (df['high'] + df['low'] + df['close']) / 3
        vol = df.get('volume', pd.Series(1.0, index=df.index))
        df['date'] = df.index.date
        cum_tpv = (tp * vol).groupby(df['date']).cumsum()
        cum_vol = vol.groupby(df['date']).cumsum()
        df['vwap'] = cum_tpv / cum_vol.replace(0, np.nan)
        df.drop(columns=['date'], inplace=True)

    # Stochastic
    if p.get('UseStoch', 0):
        sk = p['Stoch_K']; sd = p['Stoch_D']
        low_k = df['low'].rolling(sk).min()
        high_k = df['high'].rolling(sk).max()
        df['stoch_k'] = 100 * (df['close'] - low_k) / (high_k - low_k).replace(0, np.nan)
        df['stoch_k'] = df['stoch_k'].rolling(sd).mean()

    return df


def _es_vela_rechazo(o, h, l, c, ratio):
    body = abs(c - o)
    if body == 0: body = 1e-9
    if c > o:
        wick = min(o, c) - l
    else:
        wick = h - max(o, c)
    return wick >= ratio * body


def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 pip: float = 0.0001,
                 pip_val: float = 10.0) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    warmup = max(p['ATR_Period'], p['MaxOBBars'], 200) + 5

    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    atr = df['atr'].values
    idx = df.index

    use_ema200 = p.get('UseEMA200H4', 0)
    ema200 = df['ema200_h4'].values if use_ema200 else None
    close_h4 = df['close_h4'].values if use_ema200 else None

    use_adx = p.get('UseADXH4', 0)
    adx_h4 = df['adx_h4'].values if use_adx else None
    adx_min = p['ADXH4_Min']

    use_vwap = p.get('UseVWAP', 0)
    vwap = df['vwap'].values if use_vwap else None

    use_stoch = p.get('UseStoch', 0)
    stoch_k = df['stoch_k'].values if use_stoch else None
    stoch_lo = p['Stoch_Long_Max']
    stoch_hi = p['Stoch_Short_Min']

    use_wick = p.get('UseWick', 0)
    wick_ratio = p['WickRatio']

    use_ny = p.get('UseNYSession', 0)

    rr = p['RR']
    buf_atr = p['BufferATR']
    min_sl = p['MinSLPips'] * pip
    max_sl = p['MaxSLPips'] * pip
    max_bars = p['MaxOBBars']
    max_td = p['MaxTradesDay']
    sess_s = p['SessionStart']
    sess_e = p['SessionEnd']
    lot_risk = p['LotRiskPct'] / 100
    max_lots = p['MaxLots']

    bull_obs = []
    bear_obs = []
    equity = initial_capital
    pos = None
    trades = []
    trades_today = 0
    last_date = None

    for i in range(warmup, len(df)):
        dt = idx[i]
        d = dt.date()
        if d != last_date:
            trades_today = 0
            last_date = d

        # Gestion posicion abierta
        if pos is not None:
            ep = et = None
            if pos['dir'] == 'long':
                if l[i] <= pos['sl']: ep, et = pos['sl'], 'SL'
                elif h[i] >= pos['tp']: ep, et = pos['tp'], 'TP'
            else:
                if h[i] >= pos['sl']: ep, et = pos['sl'], 'SL'
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

        # Limpieza OBs
        bull_obs = [ob for ob in bull_obs if c[i] >= ob[1] and (i - ob[2]) <= max_bars]
        bear_obs = [ob for ob in bear_obs if c[i] <= ob[0] and (i - ob[2]) <= max_bars]

        # Detectar nuevo OB
        if (c[i-1] > o[i-1] and c[i] > o[i] and l[i] > h[i-2]):
            pre_fvg = (l[i-2] > h[i-3]) or (l[i-1] > h[i-3])
            if not pre_fvg:
                top = h[i-2]; bot = l[i-2]
                if not any(abs(ob[0]-top) < pip*2 for ob in bull_obs):
                    bull_obs.append([top, bot, i, False])
        if (c[i-1] < o[i-1] and c[i] < o[i] and h[i] < l[i-2]):
            pre_fvg = (h[i-2] < l[i-3]) or (h[i-1] < l[i-3])
            if not pre_fvg:
                top = h[i-2]; bot = l[i-2]
                if not any(abs(ob[1]-bot) < pip*2 for ob in bear_obs):
                    bear_obs.append([top, bot, i, False])

        # Touch
        for ob in bull_obs:
            if not ob[3] and l[i] <= ob[0] and h[i] >= ob[1]: ob[3] = True
        for ob in bear_obs:
            if not ob[3] and l[i] <= ob[0] and h[i] >= ob[1]: ob[3] = True

        # === FILTROS ENTRADA ===
        hr = dt.hour
        if use_ny:
            if hr < 13 or hr >= 21: continue
        else:
            if hr < sess_s or hr >= sess_e: continue
        if dt.weekday() >= 5 or (dt.weekday() == 4 and hr >= 22): continue
        if trades_today >= max_td: continue

        atr1 = atr[i]
        if np.isnan(atr1) or atr1 <= 0: continue

        # Filtros macro
        trend_up_ok = True
        trend_down_ok = True
        if use_ema200:
            if np.isnan(ema200[i]):
                continue
            trend_up_ok = (close_h4[i] > ema200[i])
            trend_down_ok = (close_h4[i] < ema200[i])
        if use_adx:
            if np.isnan(adx_h4[i]) or adx_h4[i] < adx_min:
                continue
        if use_vwap and not np.isnan(vwap[i]):
            trend_up_ok = trend_up_ok and (c[i] > vwap[i])
            trend_down_ok = trend_down_ok and (c[i] < vwap[i])

        # Buscar señal LONG
        cond_long = None
        if trend_up_ok:
            for ob in bull_obs:
                if ob[3] and c[i] > h[i-1] and c[i] > ob[0]:
                    if use_stoch and not np.isnan(stoch_k[i-1]):
                        if stoch_k[i-1] >= stoch_lo: continue
                    if use_wick and not _es_vela_rechazo(o[i-1], h[i-1], l[i-1], c[i-1], wick_ratio):
                        continue
                    cond_long = ob
                    break

        cond_short = None
        if cond_long is None and trend_down_ok:
            for ob in bear_obs:
                if ob[3] and c[i] < l[i-1] and c[i] < ob[1]:
                    if use_stoch and not np.isnan(stoch_k[i-1]):
                        if stoch_k[i-1] <= stoch_hi: continue
                    if use_wick and not _es_vela_rechazo(o[i-1], h[i-1], l[i-1], c[i-1], wick_ratio):
                        continue
                    cond_short = ob
                    break

        if cond_long is None and cond_short is None:
            continue

        # Setup
        if cond_long:
            ob = cond_long
            entry = c[i]
            sl = ob[1] - buf_atr * atr1
            sl_dist = entry - sl
            direc = 'long'
            bull_obs.remove(ob)
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


def compute_metrics(trades, initial_capital=50_000):
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
    return {'n':n,'pnl':round(pnl,0),'wr':round(wr,1),'pf':round(pf,2),
            'dd_pct':round(dd,2),'ann_pct':round(ann*100,2)}
