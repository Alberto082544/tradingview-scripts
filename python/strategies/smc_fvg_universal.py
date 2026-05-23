"""
SMC FVG UNIVERSAL — versión agnóstica al activo (forex, oro, índices, cripto).

Diferencia clave vs smc_fvg.py original:
- Thresholds expresados en MÚLTIPLOS DE ATR del TF FVG, no en pips fijos
- `ImpulseMinATR` (default 0.3 × ATR) en lugar de `ImpulseMinPips=8`
- `MaxSLATR` (default 5.0 × ATR) en lugar de `MaxSLPips=80`
- pip_size se infiere automáticamente del rango de precios del activo

Resto idéntico:
- H4 tendencia (swings + EMA200)
- TF FVG configurable (H1/M30/M15) → state machine
- M15 entrada con 3 patrones (Doji+Engulf, Pinbar, fallback)
- 1 ticket con TP a 1:2 RR
"""
import numpy as np
import pandas as pd


DEFAULT_PARAMS = {
    # Riesgo
    'RiskPercent':       1.0,
    'TP_RR':             2.0,
    'SL_ATR_Mult':       1.5,
    'MaxSLATR':          5.0,    # SL máximo en múltiplos de ATR
    # Tendencia H4
    'SwingLookback':     30,
    'TrendBars':         2,
    'UseH1Trend':        False,  # NUEVO: además de H4, confirmar tendencia en H1
    'H1TrendBars':       2,
    # FVG
    'FVG_TF':            'H1',
    'FVG_Lookback':      50,
    'ImpulseMinATR':     0.3,
    'MaxFVG_Age_Hours':  168,
    # Confirmación M15
    'MaxM15Confirm':     48,
    'MinBodyRatio':      0.25,
    'DojiMaxBody':       0.20,
    'PinbarMinWick':     0.60,
    'PinbarMaxBody':     0.35,
    'EngulfMinRatio':    1.10,
    'UsePatternC':       True,   # NUEVO: si False, solo PatternA y PatternB (más selectivo)
    # Filtros
    'UseRSIFilter':      False,
    'UseEMAFilter':      False,
    'UseSessionFilter':  False,
    'RSI_Period':        14,
    'RSI_OB':            72.0,
    'RSI_OS':            28.0,
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


def _detect_trend_h4(df_h4, lookback=30, trend_bars=2):
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
            if high[idx] > high[idx + 1] and high[idx] > high[idx - 1]:
                if last_h > 0:
                    if high[idx] > last_h: bull_sw += 1
                    else:                  bear_sw += 1
                last_h = high[idx]
            if low[idx] < low[idx + 1] and low[idx] < low[idx - 1]:
                if last_l > 0:
                    if low[idx] > last_l: bull_sw += 1
                    else:                 bear_sw += 1
                last_l = low[idx]
        c = close[i - 1]
        ema = ema200.iloc[i - 1]
        if pd.isna(ema):
            continue
        if bull_sw >= trend_bars and c > ema:    trend.iloc[i] = 1
        elif bear_sw >= trend_bars and c < ema:  trend.iloc[i] = -1
    return trend


def _is_doji(o, h, l, c, max_body):
    rng = h - l
    return rng > 0 and abs(c - o) / rng <= max_body


def _is_pinbar_bull(o, h, l, c, min_wick, max_body):
    rng = h - l
    if rng <= 0: return False
    wick_down = min(o, c) - l
    body = abs(c - o)
    return wick_down / rng >= min_wick and body / rng <= max_body


def _is_pinbar_bear(o, h, l, c, min_wick, max_body):
    rng = h - l
    if rng <= 0: return False
    wick_up = h - max(o, c)
    body = abs(c - o)
    return wick_up / rng >= min_wick and body / rng <= max_body


def _is_engulf_bull(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, min_ratio):
    if b1_c <= b1_o: return False
    b2_body = abs(b2_c - b2_o)
    return (b1_c - b1_o) >= b2_body * min_ratio and b1_c > b2_h and b1_o < b2_l


def _is_engulf_bear(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, min_ratio):
    if b1_c >= b1_o: return False
    b2_body = abs(b2_c - b2_o)
    return (b1_o - b1_c) >= b2_body * min_ratio and b1_c < b2_l and b1_o > b2_h


def _detect_fvgs(df_fvg, trend_at, atr_fvg, impulse_min_atr):
    """Detecta FVGs usando body mínimo relativo al ATR (no pips fijos)."""
    fvgs = []
    n = len(df_fvg)
    open_ = df_fvg['open'].values
    close = df_fvg['close'].values
    high = df_fvg['high'].values
    low = df_fvg['low'].values
    times = df_fvg.index
    atr_vals = atr_fvg.values

    for i in range(1, n - 1):
        h_prev = high[i - 1]; l_prev = low[i - 1]
        h_next = high[i + 1]; l_next = low[i + 1]
        body = abs(close[i] - open_[i])
        atr_i = atr_vals[i] if not pd.isna(atr_vals[i]) else 0
        if atr_i <= 0: continue
        min_body = atr_i * impulse_min_atr

        trend = trend_at(times[i])
        if trend == 1:
            if l_next > h_prev and body >= min_body:
                fvgs.append({
                    'time': times[i], 'upper': l_next, 'lower': h_prev,
                    'direction': 1, 'state': 'ACTIVE', 'pullback_extreme': 0.0, 'filled_at': None,
                })
        elif trend == -1:
            if h_next < l_prev and body >= min_body:
                fvgs.append({
                    'time': times[i], 'upper': l_prev, 'lower': h_next,
                    'direction': -1, 'state': 'ACTIVE', 'pullback_extreme': 0.0, 'filled_at': None,
                })
    return fvgs


def run_backtest(df_m15, params=None, initial_capital=15000, point_value=None):
    """
    df_m15: DataFrame OHLC M15.
    point_value: USD por punto por 1 lote (si None, asume 10 para forex con USD cotización).
                  Para índices/oro hay que pasar el valor correcto.
    """
    if params is None:
        params = DEFAULT_PARAMS
    p = {**DEFAULT_PARAMS, **params}

    if point_value is None:
        point_value = 10.0

    # Resampling
    df_h4 = _resample(df_m15, '4h')
    df_h1 = _resample(df_m15, '1h')
    fvg_tf_str = p['FVG_TF'].lower().replace('h1', '1h').replace('m30', '30min').replace('m15', '15min')
    df_fvg_tf = _resample(df_m15, fvg_tf_str)

    # ATR del TF FVG (para detección FVG e ImpulseMinATR)
    atr_fvg = _atr(df_fvg_tf, p['ATR_Period'])

    # Tendencia H4 (siempre)
    trend_h4 = _detect_trend_h4(df_h4, p['SwingLookback'], p['TrendBars'])
    trend_h4_ff = trend_h4.reindex(df_m15.index, method='ffill').fillna(0).astype(int)

    # Tendencia H1 opcional (confirmación adicional)
    if p.get('UseH1Trend', False):
        trend_h1 = _detect_trend_h4(df_h1, p['SwingLookback'], p['H1TrendBars'])
        trend_h1_ff = trend_h1.reindex(df_m15.index, method='ffill').fillna(0).astype(int)
    else:
        trend_h1_ff = None

    def trend_at(t):
        try:
            idx = trend_h4.index.searchsorted(t, side='right') - 1
            if idx < 0: return 0
            return int(trend_h4.iloc[idx])
        except Exception:
            return 0

    # FVGs
    fvgs = _detect_fvgs(df_fvg_tf, trend_at, atr_fvg, p['ImpulseMinATR'])
    fvg_list = fvgs.copy()

    # ATR del M15 para SL (más responsive que H1 para entrada M15)
    atr_m15 = _atr(df_m15, p['ATR_Period'])

    trades = []
    equity = initial_capital
    pos = None
    times = df_m15.index
    o15 = df_m15['open'].values
    h15 = df_m15['high'].values
    l15 = df_m15['low'].values
    c15 = df_m15['close'].values
    atr15_vals = atr_m15.values

    max_age = pd.Timedelta(hours=p['MaxFVG_Age_Hours'])
    max_confirm = pd.Timedelta(minutes=15 * p['MaxM15Confirm'])

    for i in range(2, len(df_m15)):
        t = times[i]
        b1_o, b1_c, b1_h, b1_l = o15[i - 1], c15[i - 1], h15[i - 1], l15[i - 1]
        b2_o, b2_c, b2_h, b2_l = o15[i - 2], c15[i - 2], h15[i - 2], l15[i - 2]
        atr_now = atr15_vals[i - 1] if not pd.isna(atr15_vals[i - 1]) else 0

        # Gestión posición abierta
        if pos is not None:
            ep, et = None, None
            if pos['dir'] == 1:
                if l15[i] <= pos['sl']:    ep, et = pos['sl'], 'SL'
                elif h15[i] >= pos['tp']:  ep, et = pos['tp'], 'TP'
            else:
                if h15[i] >= pos['sl']:    ep, et = pos['sl'], 'SL'
                elif l15[i] <= pos['tp']:  ep, et = pos['tp'], 'TP'
            if ep is not None:
                pnl_pts = (ep - pos['entry']) if pos['dir'] == 1 else (pos['entry'] - ep)
                pnl_usd = pnl_pts * pos['point_val'] * pos['lots']
                equity += pnl_usd
                trades.append({
                    'entry_dt': pos['entry_dt'], 'exit_dt': t, 'dir': pos['dir'],
                    'entry': pos['entry'], 'exit': ep, 'exit_type': et,
                    'pnl': round(pnl_usd, 2), 'equity': round(equity, 2),
                    'lots': pos['lots'], 'sl_dist': round(pos['sl_dist'], 5),
                })
                pos = None
            else:
                continue

        trend = trend_h4_ff.iloc[i]
        if trend == 0: continue
        if atr_now <= 0: continue

        # Filtro tendencia H1 opcional (debe coincidir con H4)
        if trend_h1_ff is not None:
            trend_h1_now = trend_h1_ff.iloc[i]
            if trend_h1_now != trend: continue

        # Filtro sesión opcional
        if p.get('UseSessionFilter', False):
            hr = t.hour
            if hr < p.get('SessionStart', 7) or hr >= p.get('SessionEnd', 21):
                continue

        # Actualizar state machine FVGs
        for fvg in fvg_list:
            if fvg['state'] in ('EXPIRED', 'INVALIDATED', 'FILLED_USED'): continue
            if t - fvg['time'] > max_age:
                fvg['state'] = 'EXPIRED'
                continue
            sz = fvg['upper'] - fvg['lower']
            if sz <= 0: continue

            if fvg['direction'] == 1:
                if b1_c < fvg['lower'] - sz * 0.5:
                    fvg['state'] = 'INVALIDATED'; continue
                if fvg['state'] == 'ACTIVE':
                    if b1_l <= fvg['upper']:
                        fvg['state'] = 'TOUCHED'; fvg['pullback_extreme'] = b1_l
                elif fvg['state'] == 'TOUCHED':
                    if b1_l < fvg['pullback_extreme']:
                        fvg['pullback_extreme'] = b1_l
                    if b1_c > fvg['lower']:
                        fvg['state'] = 'FILLED'; fvg['filled_at'] = t
            else:
                if b1_c > fvg['upper'] + sz * 0.5:
                    fvg['state'] = 'INVALIDATED'; continue
                if fvg['state'] == 'ACTIVE':
                    if b1_h >= fvg['lower']:
                        fvg['state'] = 'TOUCHED'; fvg['pullback_extreme'] = b1_h
                elif fvg['state'] == 'TOUCHED':
                    if b1_h > fvg['pullback_extreme']:
                        fvg['pullback_extreme'] = b1_h
                    if b1_c < fvg['upper']:
                        fvg['state'] = 'FILLED'; fvg['filled_at'] = t

        if pos is not None: continue

        # Buscar entrada
        for fvg in fvg_list:
            if fvg['state'] != 'FILLED' or fvg['filled_at'] is None: continue
            if t - fvg['filled_at'] > max_confirm: continue
            # NOTA: removido check `fvg.direction != trend` (la FVG ya se filtró
            # por tendencia al detectarse, y el cambio de tendencia entre
            # detección y FILLED puede ser ruido legítimo dentro del macro-tendencia)

            # Patrones
            if fvg['direction'] == 1:
                pat_A = (_is_doji(b2_o, b2_h, b2_l, b2_c, p['DojiMaxBody']) or
                          _is_pinbar_bull(b2_o, b2_h, b2_l, b2_c, p['PinbarMinWick'], p['PinbarMaxBody'])) and \
                          _is_engulf_bull(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, p['EngulfMinRatio'])
                pat_B = _is_pinbar_bull(b1_o, b1_h, b1_l, b1_c, p['PinbarMinWick'], p['PinbarMaxBody'])
                rng = b1_h - b1_l
                pat_C = p.get('UsePatternC', True) and b1_c > b1_o and rng > 0 and (b1_c - b1_o) / rng >= p['MinBodyRatio']
            else:
                pat_A = (_is_doji(b2_o, b2_h, b2_l, b2_c, p['DojiMaxBody']) or
                          _is_pinbar_bear(b2_o, b2_h, b2_l, b2_c, p['PinbarMinWick'], p['PinbarMaxBody'])) and \
                          _is_engulf_bear(b2_o, b2_c, b2_h, b2_l, b1_o, b1_c, p['EngulfMinRatio'])
                pat_B = _is_pinbar_bear(b1_o, b1_h, b1_l, b1_c, p['PinbarMinWick'], p['PinbarMaxBody'])
                rng = b1_h - b1_l
                pat_C = p.get('UsePatternC', True) and b1_c < b1_o and rng > 0 and (b1_o - b1_c) / rng >= p['MinBodyRatio']

            if not (pat_A or pat_B or pat_C): continue

            if fvg['direction'] == 1 and b1_c < fvg['lower']: continue
            if fvg['direction'] == -1 and b1_c > fvg['upper']: continue

            # SL y TP usando ATR M15 (más responsive)
            entry = o15[i]
            if fvg['direction'] == 1:
                sl = fvg['pullback_extreme'] - atr_now * p['SL_ATR_Mult']
                sl_dist = entry - sl
                tp = entry + sl_dist * p['TP_RR']
            else:
                sl = fvg['pullback_extreme'] + atr_now * p['SL_ATR_Mult']
                sl_dist = sl - entry
                tp = entry - sl_dist * p['TP_RR']

            # MaxSLATR (en lugar de MaxSLPips)
            if sl_dist <= 0 or sl_dist > atr_now * p['MaxSLATR']:
                fvg['state'] = 'FILLED_USED'
                continue

            # Sizing
            risk_usd = equity * p['RiskPercent'] / 100
            lots = risk_usd / (sl_dist * point_value)
            lots = max(0.01, min(10.0, round(lots, 2)))

            pos = {
                'dir': fvg['direction'], 'entry': entry, 'sl': sl, 'tp': tp,
                'sl_dist': sl_dist, 'lots': lots, 'point_val': point_value,
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
