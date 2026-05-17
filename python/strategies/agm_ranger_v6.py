"""
AGM_Ranger v6 — Motor de backtest Python
Mejoras sobre v5:
  - Filtro ADX en H4 (regimen de mercado en temporalidad principal)
  - Gatillo de entrada en M30 (BB + RSI)
  - ADX M30 opcional como filtro adicional
GBPJPY M30 | H4 analisis | Sesion 07-19 UTC | pip = 0.01
"""
import pandas as pd
import numpy as np

PIP    = 0.01
USDJPY = 145.0

DEFAULT_PARAMS = {
    # Bollinger Bands (M30)
    'BB_Period':        20,
    'BB_StdDev':       2.0,
    # RSI (M30)
    'RSI_Period':       14,
    'RSI_Oversold':     32,
    'RSI_Overbought':   68,
    # ADX M30 (micro-filtro rango en temporalidad de entrada)
    'ADX_Period':       14,
    'ADX_Threshold':   999,   # 999 = desactivado; <30 = solo rango en M30
    # ADX H4 (NUEVO: macro-filtro rango en temporalidad principal)
    'ADX_H4_Period':    14,
    'ADX_H4_Threshold': 25,   # solo operar si ADX H4 < umbral; 999 = desactivado
    # Stop Loss
    'SL_ATR_Mult':     1.5,
    'ATR_Period':       14,
    'MaxSLPips':       999,
    'MinSLPips':       350,
    # Trailing
    'TrailActivate':   0.5,
    'TrailDistPips':   120,
    # TP fijo (0 = desactivado, usa solo trailing/BB_Mid/tiempo)
    'TP_Pips':           0,
    # BB Media como TP
    'BB_Mid_TP':         0,
    # Salida por tiempo
    'ExitBars':         12,
    # Sesion
    'SessionStart':      7,
    'SessionEnd':       19,
    'BadHour':           8,
    'MaxTradesDay':      3,
    # Riesgo
    'LotRiskPct':      0.7,
    'MaxLots':         4.0,
}


# ── Calculo ADX (Wilder) ───────────────────────────────────────────────────────

def _calc_adx(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, close = df['high'], df['low'], df['close']
    hl   = high - low
    hc   = (high - close.shift()).abs()
    lc   = (low  - close.shift()).abs()
    tr   = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    up   = high.diff()
    dn   = (-low.diff())
    pdm  = np.where((up > dn) & (up > 0), up, 0.0)
    mdm  = np.where((dn > up) & (dn > 0), dn, 0.0)

    alpha = 1 / period
    atr_s = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    pdi   = 100 * pd.Series(pdm, index=df.index).ewm(
                alpha=alpha, adjust=False, min_periods=period).mean() / atr_s
    mdi   = 100 * pd.Series(mdm, index=df.index).ewm(
                alpha=alpha, adjust=False, min_periods=period).mean() / atr_s

    di_sum = pdi + mdi
    dx     = (100 * (pdi - mdi).abs() / di_sum.replace(0, np.nan)).fillna(0)
    return dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()


# ── Indicadores ────────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params
    df = df.copy()

    # Bollinger Bands (M30)
    df['bb_mid']   = df['close'].rolling(p['BB_Period']).mean()
    df['bb_std']   = df['close'].rolling(p['BB_Period']).std(ddof=0)
    df['bb_upper'] = df['bb_mid'] + p['BB_StdDev'] * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - p['BB_StdDev'] * df['bb_std']

    # RSI (Wilder EMA, M30)
    delta    = df['close'].diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=p['RSI_Period'] - 1, min_periods=p['RSI_Period']).mean()
    avg_loss = loss.ewm(com=p['RSI_Period'] - 1, min_periods=p['RSI_Period']).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    # ATR (Wilder, M30)
    hl  = df['high'] - df['low']
    hc  = (df['high'] - df['close'].shift()).abs()
    lc  = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1 / p['ATR_Period'], adjust=False,
                       min_periods=p['ATR_Period']).mean()

    # ADX M30 (micro-filtro)
    df['adx_m30'] = _calc_adx(df, p['ADX_Period'])

    # ADX H4 (macro-filtro — temporalidad principal)
    df_h4 = df[['high','low','close']].resample('4h').agg(
        {'high':'max','low':'min','close':'last'}).dropna()
    adx_h4_series = _calc_adx(df_h4, p['ADX_H4_Period'])
    # Forward-fill al indice M30
    df['adx_h4'] = adx_h4_series.reindex(df.index, method='ffill')

    return df


# ── Motor de backtest ─────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, params: dict = None,
                 initial_capital: float = 50_000,
                 usdjpy: float = USDJPY,
                 tz_offset: int = 0) -> pd.DataFrame:
    p = DEFAULT_PARAMS if params is None else params

    pip_val      = (PIP * 100_000) / usdjpy
    equity       = initial_capital
    position     = None
    trades       = []
    trades_today = 0
    last_date    = None

    adx_m30_thr = p.get('ADX_Threshold',    999)
    adx_h4_thr  = p.get('ADX_H4_Threshold', 999)
    bb_mid_tp   = p.get('BB_Mid_TP', 0)

    warmup = max(p['BB_Period'], p['RSI_Period'], p['ATR_Period'],
                 p.get('ADX_Period', 14), p.get('ADX_H4_Period', 14)) * 8 + 2

    for i in range(warmup, len(df)):
        row  = df.iloc[i]
        dt   = df.index[i]
        date = dt.date()

        if date != last_date:
            trades_today = 0
            last_date    = date

        # ── 1. TRAILING ──────────────────────────────────────────────────────
        if position is not None:
            trail_dist      = p['TrailDistPips'] * PIP
            activation_gain = p['TrailActivate'] * position['sl_dist']
            ref             = row['open']

            if position['direction'] == 'long':
                if (ref - position['entry']) >= activation_gain:
                    new_sl = ref - trail_dist
                    if new_sl > position['sl']:
                        position['sl'] = new_sl
            else:
                if (position['entry'] - ref) >= activation_gain:
                    new_sl = ref + trail_dist
                    if new_sl < position['sl']:
                        position['sl'] = new_sl

        # ── 2. SALIDAS: SL / TP / BB-MEDIA / TIEMPO ──────────────────────────
        if position is not None:
            sl         = position['sl']
            tp         = position['tp']
            bb_mid_pos = position['bb_mid_entry']
            exit_price = exit_type = None

            if position['direction'] == 'long':
                if row['low'] <= sl:
                    exit_price, exit_type = sl,         'SL'
                elif row['high'] >= tp:
                    exit_price, exit_type = tp,         'TP'
                elif bb_mid_tp and row['high'] >= bb_mid_pos:
                    exit_price, exit_type = bb_mid_pos, 'BB_MID'
            else:
                if row['high'] >= sl:
                    exit_price, exit_type = sl,         'SL'
                elif row['low'] <= tp:
                    exit_price, exit_type = tp,         'TP'
                elif bb_mid_tp and row['low'] <= bb_mid_pos:
                    exit_price, exit_type = bb_mid_pos, 'BB_MID'

            if exit_price is None:
                if (i - position['bar_idx']) >= p['ExitBars']:
                    exit_price, exit_type = row['close'], 'TIME'

            if exit_price is not None:
                pnl_pips = (exit_price - position['entry']) / PIP
                if position['direction'] == 'short':
                    pnl_pips = -pnl_pips
                pnl_usd = pnl_pips * pip_val * position['lots']
                equity += pnl_usd
                trades.append({
                    'entry_dt':  position['entry_dt'],
                    'exit_dt':   dt,
                    'direction': position['direction'],
                    'pnl':       round(pnl_usd, 2),
                    'exit_type': exit_type,
                    'equity':    round(equity, 2),
                    'lots':      position['lots'],
                    'sl_pips':   round(position['sl_dist'] / PIP, 0),
                })
                position = None

        # ── 3. ENTRADA ───────────────────────────────────────────────────────
        if position is not None:
            continue

        utc_hour = (dt.hour - tz_offset) % 24
        if utc_hour < p['SessionStart'] or utc_hour >= p['SessionEnd']:
            continue
        if utc_hour == p['BadHour']:
            continue
        if dt.weekday() >= 5:
            continue
        if dt.weekday() == 4 and utc_hour >= 20:
            continue
        if trades_today >= p['MaxTradesDay']:
            continue

        prev1 = df.iloc[i - 1]
        prev2 = df.iloc[i - 2]

        close1    = prev1['close']
        bb_lower1 = prev1['bb_lower']
        bb_upper1 = prev1['bb_upper']
        bb_mid1   = prev1['bb_mid']
        rsi1      = prev1['rsi']
        rsi2      = prev2['rsi']
        atr1      = prev1['atr']
        adx_m30   = prev1['adx_m30']
        adx_h4    = prev1['adx_h4']

        if pd.isna(atr1) or atr1 <= 0:
            continue
        if pd.isna(adx_m30) or pd.isna(adx_h4):
            continue

        # Filtro ADX H4: mercado en rango en temporalidad principal
        if adx_h4 >= adx_h4_thr:
            continue

        # Filtro ADX M30: mercado en rango en temporalidad de entrada (opcional)
        if adx_m30 >= adx_m30_thr:
            continue

        cond_long  = (close1 <= bb_lower1 * 1.001 and
                      rsi1 < p['RSI_Oversold'] and
                      rsi1 > rsi2)

        cond_short = (not cond_long and
                      close1 >= bb_upper1 * 0.999 and
                      rsi1 > p['RSI_Overbought'] and
                      rsi1 < rsi2)

        if not cond_long and not cond_short:
            continue

        sl_dist = atr1 * p['SL_ATR_Mult']
        sl_pips = sl_dist / PIP
        if sl_pips > p['MaxSLPips']:
            continue
        if sl_pips < p['MinSLPips']:
            sl_dist = p['MinSLPips'] * PIP

        tp_dist     = (p['TP_Pips'] if p.get('TP_Pips', 0) > 0 else 999) * PIP
        entry_price = row['open']

        risk_usd = equity * p['LotRiskPct'] / 100
        lots     = risk_usd / (sl_dist / PIP * pip_val)
        lots     = min(round(lots, 2), p['MaxLots'])
        lots     = max(lots, 0.01)

        if cond_long:
            sl = entry_price - sl_dist
            tp = entry_price + tp_dist
        else:
            sl = entry_price + sl_dist
            tp = entry_price - tp_dist

        position = {
            'direction':       'long' if cond_long else 'short',
            'entry':           entry_price,
            'sl':              sl,
            'tp':              tp,
            'sl_dist':         sl_dist,
            'lots':            lots,
            'bar_idx':         i,
            'entry_dt':        dt,
            'equity_at_entry': equity,
            'bb_mid_entry':    bb_mid1,
        }
        trades_today += 1

    return pd.DataFrame(trades) if trades else pd.DataFrame(
        columns=['entry_dt','exit_dt','direction','pnl',
                 'exit_type','equity','lots','sl_pips'])


# ── Metricas ──────────────────────────────────────────────────────────────────

def compute_metrics(trades: pd.DataFrame, initial_capital: float = 50_000) -> dict:
    if trades is None or len(trades) == 0:
        return {'n':0,'pnl':0,'wr':0,'pf':0,'dd_pct':0,'ann_pct':0,
                'calmar':0,'avg_w':0,'avg_l':0}

    n    = len(trades)
    pnl  = trades['pnl'].sum()
    wr   = (trades['pnl'] > 0).mean() * 100
    wins = trades.loc[trades['pnl'] > 0, 'pnl']
    loss = trades.loc[trades['pnl'] < 0, 'pnl']
    pf   = wins.sum() / abs(loss.sum()) if len(loss) > 0 and loss.sum() != 0 else 0

    eq_curve = np.concatenate([[initial_capital], trades['equity'].values])
    peaks    = np.maximum.accumulate(eq_curve)
    max_dd   = abs(((eq_curve - peaks) / peaks).min()) * 100

    years   = (pd.to_datetime(trades['exit_dt'].iloc[-1]) -
               pd.to_datetime(trades['entry_dt'].iloc[0])).days / 365.25
    ann_ret = ((initial_capital + pnl) / initial_capital) ** (1 / max(years, 0.01)) - 1
    calmar  = (ann_ret * 100) / max_dd if max_dd > 0 else 0

    return {
        'n':       n,
        'pnl':     round(pnl, 0),
        'wr':      round(wr, 1),
        'pf':      round(pf, 2),
        'dd_pct':  round(max_dd, 1),
        'ann_pct': round(ann_ret * 100, 2),
        'calmar':  round(calmar, 2),
        'avg_w':   round(wins.mean(), 0) if len(wins) > 0 else 0,
        'avg_l':   round(loss.mean(), 0) if len(loss) > 0 else 0,
        'exits':   trades['exit_type'].value_counts().to_dict(),
    }
