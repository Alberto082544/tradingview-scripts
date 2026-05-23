"""
SMC Tendencia FVG — Port simplificado del EA MQL5 v9.4 a Python.

Lógica:
- H4: detección de tendencia (swings + EMA200)
- TF FVG (configurable: H1, M30, M15): detecta FVGs en dirección de tendencia
- M15: state machine de FVG (ACTIVE → TOUCHED → FILLED) + entrada con patrones de vela

Simplificaciones vs MQL5 original:
- 1 ticket por trade (en lugar de 2 con TP1/TP2)
- TP fijo a 1:2 RR
- BE+buffer no implementado (solo trailing manual opcional)
- Sesión y spread filter dejados como opciones simples

Uso:
    from strategies.smc_fvg import run_backtest, DEFAULT_PARAMS, compute_metrics
    trades = run_backtest(df_m15, params={'FVG_TF':'H1', 'SL_ATR_Mult':1.5})
    print(compute_metrics(trades))
"""
import numpy as np
import pandas as pd


DEFAULT_PARAMS = {
    # Riesgo
    'RiskPercent':       1.0,    # % balance por trade
    'TP_RR':             2.0,    # ratio TP/SL (1:2)
    'SL_ATR_Mult':       1.5,    # SL = ATR_H1 * mult
    'MaxSLPips':         80.0,
    # Tendencia H4
    'SwingLookback':     30,
    'TrendBars':         3,
    'EMA200_TF':         '4h',
    # FVG
    'FVG_TF':            'H1',   # 'H1', 'M30', 'M15'
    'FVG_Lookback':      50,
    'ImpulseMinPips':    8.0,
    'MaxFVG_Age_Hours':  72,
    # Confirmación M15
    'MaxM15Confirm':     12,
    'MinBodyRatio':      0.25,
    'DojiMaxBody':       0.20,
    'PinbarMinWick':     0.60,
    'PinbarMaxBody':     0.35,
    'EngulfMinRatio':    1.10,
    # Filtros
    'UseRSIFilter':      True,
    'RSI_Period':        14,
    'RSI_OB':            72.0,
    'RSI_OS':            28.0,
    'UseEMAFilter':      True,
    'EMA50_TF':          '1h',
    'UseSessionFilter':  True,
    'SessionStart':      7,
    'SessionEnd':        21,
    # ATR
    'ATR_TF':            '1h',
    'ATR_Period':        14,
}


def _ema(s, period):
    return s.ewm(span=period, adjust=False, min_periods=period).mean()


def _atr(df, period):
    h, l, c = df['high'], df['low'], df['close']
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _rsi(s, period):
    d = s.diff()
    up = d.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    dn = (-d).clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _resample(df, tf):
    return df.resample(tf).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()


def _detect_trend_h4(df_h4, lookback=30, trend_bars=3):
    """Devuelve serie con valores 1=BULL, -1=BEAR, 0=NONE indexada por H4."""
    ema200 = _ema(df_h4['close'], 200)
    trend = pd.Series(0, index=df_h4.index)
    high = df_h4['high'].values
    low = df_h4['low'].values
    close = df_h4['close'].values
    n = len(df_h4)

    for i in range(lookback + 1, n):
        bull_sw = bear_sw = 0
        last_h = last_l = 0
        for j in range(lookback, 1, -1):
            idx = i - j
            if idx <= 0 or idx + 1 >= n:
                continue
            # swing high
            if high[idx] > high[idx + 1] and high[idx] > high[idx - 1]:
                if last_h > 0:
                    if high[idx] > last_h:
                        bull_sw += 1
                    else:
                        bear_sw += 1
                last_h = high[idx]
            # swing low
            if low[idx] < low[idx + 1] and low[idx] < low[idx - 1]:
                if last_l > 0:
                    if low[idx] > last_l:
                        bull_sw += 1
                    else:
                        bear_sw += 1
                last_l = low[idx]
        c = close[i - 1]
        ema = ema200.iloc[i - 1]
        if pd.isna(ema):
            continue
        if bull_sw >= trend_bars and c > ema:
            trend.iloc[i] = 1
        elif bear_sw >= trend_bars and c < ema:
            trend.iloc[i] = -1
    return trend


def _detect_fvgs(df_fvg, trend_at_time, pip, impulse_min_pips, lookback, max_age_hours):
    """Detecta FVGs en df_fvg. trend_at_time es función que devuelve trend en un timestamp.
    Devuelve lista de dicts con: time, upper, lower, direction (1/-1)."""
    fvgs = []
    n = len(df_fvg)
    min_body = impulse_min_pips * pip
    open_ = df_fvg['open'].values
    close = df_fvg['close'].values
    high = df_fvg['high'].values
    low = df_fvg['low'].values
    times = df_fvg.index

    for i in range(1, n - 1):
        # vela media = i, vela anterior = i-1, siguiente = i+1
        h_prev = high[i - 1]; l_prev = low[i - 1]
        h_next = high[i + 1]; l_next = low[i + 1]
        body = abs(close[i] - open_[i])
        trend = trend_at_time(times[i])

        if trend == 1:
            # Bull FVG: low siguiente > high anterior
            if l_next > h_prev and body >= min_body:
                fvgs.append({
                    'time': times[i],
                    'upper': l_next,
                    'lower': h_prev,
                    'direction': 1,
                    'state': 'ACTIVE',
                    'pullback_extreme': 0.0,
                    'filled_at': None,
                })
        elif trend == -1:
            # Bear FVG: high siguiente < low anterior
            if h_next < l_prev and body >= min_body:
                fvgs.append({
                    'time': times[i],
                    'upper': l_prev,
                    'lower': h_next,
                    'direction': -1,
                    'state': 'ACTIVE',
                    'pullback_extreme': 0.0,
                    'filled_at': None,
                })
    return fvgs


def _is_doji(o, h, l, c, max_body):
    rng = h - l
    return rng > 0 and abs(c - o) / rng <= max_body


def _is_pinbar_bull(o, h, l, c, min_wick, max_body):
    rng = h - l
    if rng <= 0:
        return False
    wick_down = min(o, c) - l
    body = abs(c - o)
    return wick_down / rng >= min_wick and body / rng <= max_body


def _is_pinbar_bear(o, h, l, c, min_wick, max_body):
    rng = h - l
    if rng <= 0:
        return False
    wick_up = h - max(o, c)
    body = abs(c - o)
    return wick_up / rng >= min_wick and body / rng <= max_body


def _is_engulf_bull(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, min_ratio):
    if b1_c <= b1_o:  # no es vela alcista
        return False
    b2_body = abs(b2_c - b2_o)
    return (b1_c - b1_o) >= b2_body * min_ratio and b1_c > b2_h and b1_o < b2_l


def _is_engulf_bear(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, min_ratio):
    if b1_c >= b1_o:
        return False
    b2_body = abs(b2_c - b2_o)
    return (b1_o - b1_c) >= b2_body * min_ratio and b1_c < b2_l and b1_o > b2_h


def run_backtest(df_m15, params=None, initial_capital=15000, pip=0.0001):
    """
    df_m15: DataFrame OHLC con índice DatetimeIndex en M15.
    Devuelve DataFrame de trades.
    """
    if params is None:
        params = DEFAULT_PARAMS
    p = {**DEFAULT_PARAMS, **params}

    # Detección JPY (pip = 0.01 para pares JPY)
    # Si el usuario pasa pip distinto, respetar

    # 1) Resample para H4 (tendencia), TF FVG, ATR
    df_h4 = _resample(df_m15, '4h')
    df_fvg_tf = _resample(df_m15, p['FVG_TF'].lower().replace('h1', '1h').replace('m30', '30min').replace('m15', '15min'))
    df_atr_tf = _resample(df_m15, '1h')
    df_rsi_tf = df_atr_tf.copy()
    df_ema_tf = df_atr_tf.copy()

    # Indicadores
    atr_h1 = _atr(df_atr_tf, p['ATR_Period'])
    rsi_h1 = _rsi(df_rsi_tf['close'], p['RSI_Period'])
    ema50_h1 = _ema(df_ema_tf['close'], 50)

    # 2) Tendencia H4
    trend_h4 = _detect_trend_h4(df_h4, p['SwingLookback'], p['TrendBars'])
    trend_h4_ff = trend_h4.reindex(df_m15.index, method='ffill').fillna(0).astype(int)

    def trend_at(t):
        # devuelve la tendencia H4 vigente al momento t
        try:
            idx = trend_h4.index.searchsorted(t, side='right') - 1
            if idx < 0:
                return 0
            return int(trend_h4.iloc[idx])
        except Exception:
            return 0

    # 3) Detectar FVGs
    fvgs = _detect_fvgs(df_fvg_tf, trend_at, pip, p['ImpulseMinPips'], p['FVG_Lookback'], p['MaxFVG_Age_Hours'])

    # 4) Iterar barras M15 y gestionar trades
    trades = []
    equity = initial_capital
    pos = None
    times = df_m15.index
    o15 = df_m15['open'].values
    h15 = df_m15['high'].values
    l15 = df_m15['low'].values
    c15 = df_m15['close'].values

    max_sl_dist = p['MaxSLPips'] * pip
    max_age = pd.Timedelta(hours=p['MaxFVG_Age_Hours'])
    max_confirm = pd.Timedelta(minutes=15 * p['MaxM15Confirm'])

    # Índice de FVGs por estado (mutable)
    fvg_list = fvgs.copy()

    for i in range(2, len(df_m15)):
        t = times[i]
        b1_o, b1_c, b1_h, b1_l = o15[i - 1], c15[i - 1], h15[i - 1], l15[i - 1]
        b2_o, b2_c, b2_h, b2_l = o15[i - 2], c15[i - 2], h15[i - 2], l15[i - 2]

        # Gestión de posición abierta
        if pos is not None:
            ep, et = None, None
            if pos['dir'] == 1:  # LONG
                if l15[i] <= pos['sl']:
                    ep, et = pos['sl'], 'SL'
                elif h15[i] >= pos['tp']:
                    ep, et = pos['tp'], 'TP'
            else:  # SHORT
                if h15[i] >= pos['sl']:
                    ep, et = pos['sl'], 'SL'
                elif l15[i] <= pos['tp']:
                    ep, et = pos['tp'], 'TP'

            if ep is not None:
                pnl_pips = (ep - pos['entry']) if pos['dir'] == 1 else (pos['entry'] - ep)
                pnl_usd = pnl_pips / pip * pos['pip_val'] * pos['lots']
                equity += pnl_usd
                trades.append({
                    'entry_dt': pos['entry_dt'], 'exit_dt': t, 'dir': pos['dir'],
                    'entry': pos['entry'], 'exit': ep, 'exit_type': et,
                    'pnl': round(pnl_usd, 2), 'equity': round(equity, 2),
                    'lots': pos['lots'], 'sl_pips': round(pos['sl_dist'] / pip, 1),
                })
                pos = None
            else:
                continue

        # Filtros de sesión
        if p['UseSessionFilter']:
            hr = t.hour
            if hr < p['SessionStart'] or hr >= p['SessionEnd']:
                continue

        # Trend actual
        trend = trend_h4_ff.iloc[i]
        if trend == 0:
            continue

        # ATR e indicadores en H1 vigentes
        try:
            atr_now = atr_h1.asof(t)
            rsi_now = rsi_h1.asof(t)
            ema_now = ema50_h1.asof(t)
        except Exception:
            continue
        if pd.isna(atr_now) or atr_now <= 0:
            continue

        # Actualizar estado de FVGs y buscar uno apto para entrar
        for fvg in fvg_list:
            if fvg['state'] in ('EXPIRED', 'INVALIDATED', 'FILLED_USED'):
                continue
            # Edad
            if t - fvg['time'] > max_age:
                fvg['state'] = 'EXPIRED'
                continue

            sz = fvg['upper'] - fvg['lower']
            if sz <= 0:
                continue

            if fvg['direction'] == 1:  # Bull
                if b1_c < fvg['lower'] - sz * 0.5:
                    fvg['state'] = 'INVALIDATED'
                    continue
                if fvg['state'] == 'ACTIVE':
                    if b1_l <= fvg['upper']:
                        fvg['state'] = 'TOUCHED'
                        fvg['pullback_extreme'] = b1_l
                elif fvg['state'] == 'TOUCHED':
                    if b1_l < fvg['pullback_extreme']:
                        fvg['pullback_extreme'] = b1_l
                    if b1_c > fvg['lower']:
                        fvg['state'] = 'FILLED'
                        fvg['filled_at'] = t
            else:  # Bear
                if b1_c > fvg['upper'] + sz * 0.5:
                    fvg['state'] = 'INVALIDATED'
                    continue
                if fvg['state'] == 'ACTIVE':
                    if b1_h >= fvg['lower']:
                        fvg['state'] = 'TOUCHED'
                        fvg['pullback_extreme'] = b1_h
                elif fvg['state'] == 'TOUCHED':
                    if b1_h > fvg['pullback_extreme']:
                        fvg['pullback_extreme'] = b1_h
                    if b1_c < fvg['upper']:
                        fvg['state'] = 'FILLED'
                        fvg['filled_at'] = t

        # Buscar FVG FILLED para entrar
        if pos is not None:
            continue
        for fvg in fvg_list:
            if fvg['state'] != 'FILLED' or fvg['filled_at'] is None:
                continue
            if t - fvg['filled_at'] > max_confirm:
                continue
            if fvg['direction'] != trend:
                continue

            # Filtros RSI/EMA
            if fvg['direction'] == 1:
                if p['UseRSIFilter'] and rsi_now > p['RSI_OB']:
                    continue
                if p['UseEMAFilter'] and not pd.isna(ema_now) and c15[i] < ema_now:
                    continue
            else:
                if p['UseRSIFilter'] and rsi_now < p['RSI_OS']:
                    continue
                if p['UseEMAFilter'] and not pd.isna(ema_now) and c15[i] > ema_now:
                    continue

            # Patrones de confirmación (3 ORs)
            if fvg['direction'] == 1:
                pat_A = (_is_doji(b2_o, b2_h, b2_l, b2_c, p['DojiMaxBody']) or
                          _is_pinbar_bull(b2_o, b2_h, b2_l, b2_c, p['PinbarMinWick'], p['PinbarMaxBody'])) and \
                          _is_engulf_bull(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, p['EngulfMinRatio'])
                pat_B = _is_pinbar_bull(b1_o, b1_h, b1_l, b1_c, p['PinbarMinWick'], p['PinbarMaxBody'])
                rng = b1_h - b1_l
                pat_C = b1_c > b1_o and rng > 0 and (b1_c - b1_o) / rng >= p['MinBodyRatio']
            else:
                pat_A = (_is_doji(b2_o, b2_h, b2_l, b2_c, p['DojiMaxBody']) or
                          _is_pinbar_bear(b2_o, b2_h, b2_l, b2_c, p['PinbarMinWick'], p['PinbarMaxBody'])) and \
                          _is_engulf_bear(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, p['EngulfMinRatio'])
                pat_B = _is_pinbar_bear(b1_o, b1_h, b1_l, b1_c, p['PinbarMinWick'], p['PinbarMaxBody'])
                rng = b1_h - b1_l
                pat_C = b1_c < b1_o and rng > 0 and (b1_o - b1_c) / rng >= p['MinBodyRatio']

            if not (pat_A or pat_B or pat_C):
                continue

            # Cierre respeta FVG
            if fvg['direction'] == 1 and b1_c < fvg['lower']:
                continue
            if fvg['direction'] == -1 and b1_c > fvg['upper']:
                continue

            # Calcular SL/TP
            entry = o15[i]
            if fvg['direction'] == 1:
                sl = fvg['pullback_extreme'] - atr_now * p['SL_ATR_Mult']
                sl_dist = entry - sl
                tp = entry + sl_dist * p['TP_RR']
            else:
                sl = fvg['pullback_extreme'] + atr_now * p['SL_ATR_Mult']
                sl_dist = sl - entry
                tp = entry - sl_dist * p['TP_RR']

            if sl_dist <= 0 or sl_dist > max_sl_dist:
                fvg['state'] = 'FILLED_USED'
                continue

            # Sizing
            pip_val = 10.0  # USD por pip por lote 1.0 (aprox forex)
            # JPY ajusta valor en función del precio; aprox pip_val = 6-9 según par
            risk_usd = equity * p['RiskPercent'] / 100
            lots = risk_usd / (sl_dist / pip * pip_val)
            lots = max(0.01, min(4.0, round(lots, 2)))

            pos = {
                'dir': fvg['direction'], 'entry': entry, 'sl': sl, 'tp': tp,
                'sl_dist': sl_dist, 'lots': lots, 'pip_val': pip_val,
                'entry_dt': t,
            }
            fvg['state'] = 'FILLED_USED'
            break

    if not trades:
        return pd.DataFrame()
    return pd.DataFrame(trades)


def compute_metrics(trades, initial_capital=15000):
    if trades is None or len(trades) == 0:
        return {'n': 0, 'pnl': 0, 'wr': 0, 'pf': 0, 'dd_pct': 0, 'ann_pct': 0}
    n = len(trades)
    pnl = trades['pnl'].sum()
    wr = (trades['pnl'] > 0).mean() * 100
    wins = trades.loc[trades['pnl'] > 0, 'pnl']
    losses = trades.loc[trades['pnl'] < 0, 'pnl']
    pf = wins.sum() / abs(losses.sum()) if len(losses) > 0 and losses.sum() != 0 else 0
    eq = np.concatenate([[initial_capital], trades['equity'].values])
    pk = np.maximum.accumulate(eq)
    dd = abs(((eq - pk) / pk).min()) * 100
    yrs = (pd.to_datetime(trades['exit_dt'].iloc[-1]) -
           pd.to_datetime(trades['entry_dt'].iloc[0])).days / 365.25
    ann = ((initial_capital + pnl) / initial_capital) ** (1 / max(yrs, 0.01)) - 1
    return {
        'n': n, 'pnl': round(pnl, 0), 'wr': round(wr, 1), 'pf': round(pf, 2),
        'dd_pct': round(dd, 1), 'ann_pct': round(ann * 100, 2),
    }
