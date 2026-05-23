"""
DEBUG del SMC FVG Universal — diagnostica DÓNDE se mueren los trades.

Cuenta:
1. FVGs detectadas (total)
2. FVGs que llegan a TOUCHED
3. FVGs que llegan a FILLED
4. Veces que se intenta entrar (estado FILLED + tiempo válido + trend match)
5. Cuántas rechazan por patrón de vela
6. Cuántas rechazan por SL_dist > MaxSLATR
7. Trades finalmente abiertos

Ejecutar:
    python -X utf8 -m backtest.debug_smc_fvg EURUSD
    python -X utf8 -m backtest.debug_smc_fvg AUDCAD
"""
import os
import sys
import time
import warnings
from pathlib import Path
import pandas as pd
import numpy as np

warnings.simplefilter("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from strategies.smc_fvg_universal import (
    _ema, _atr, _resample, _detect_trend_h4, _detect_fvgs,
    _is_doji, _is_pinbar_bull, _is_pinbar_bear,
    _is_engulf_bull, _is_engulf_bear, DEFAULT_PARAMS,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

ASSETS = {
    'EURUSD': ('EURUSD_M15_histdata.csv', 'time', 10.0, 'H1'),
    'AUDCAD': ('AUDCAD_M15_histdata.csv', 'time',  7.0, 'H1'),
    'NAS100': ('NAS100_proxy_M15_twelvedata.csv', 'time', 1.0, 'M30'),
    'US500':  ('US500_M15_mt5.csv', 'time', 1.0, 'M30'),
}


def debug_run(name, df, params, point_value):
    p = {**DEFAULT_PARAMS, **params}

    # === Contadores diagnóstico ===
    stats = {
        'total_bars_m15': len(df),
        'fvgs_detected': 0,
        'fvgs_bull': 0,
        'fvgs_bear': 0,
        'fvgs_touched': 0,
        'fvgs_filled': 0,
        'fvgs_invalidated': 0,
        'fvgs_expired': 0,
        'entry_attempts': 0,
        'reject_no_trend': 0,
        'reject_no_pattern': 0,
        'reject_cierre_no_respeta_fvg': 0,
        'reject_sl_too_big': 0,
        'reject_sl_negative': 0,
        'trades_opened': 0,
    }

    # Resampling
    df_h4 = _resample(df, '4h')
    fvg_tf_str = p['FVG_TF'].lower().replace('h1', '1h').replace('m30', '30min').replace('m15', '15min')
    df_fvg_tf = _resample(df, fvg_tf_str)

    print(f"  Bars M15: {len(df):,}")
    print(f"  Bars H4: {len(df_h4):,}")
    print(f"  Bars FVG_TF ({p['FVG_TF']}): {len(df_fvg_tf):,}")

    # ATR
    atr_fvg = _atr(df_fvg_tf, p['ATR_Period'])
    atr_m15 = _atr(df, p['ATR_Period'])
    print(f"  ATR_FVG mean: {atr_fvg.mean():.6f}")
    print(f"  ATR_M15 mean: {atr_m15.mean():.6f}")

    # Tendencia
    trend_h4 = _detect_trend_h4(df_h4, p['SwingLookback'], p['TrendBars'])
    n_bull = (trend_h4 == 1).sum()
    n_bear = (trend_h4 == -1).sum()
    n_none = (trend_h4 == 0).sum()
    print(f"  Tendencia H4 — BULL: {n_bull} | BEAR: {n_bear} | NONE: {n_none} (de {len(trend_h4)})")

    trend_h4_ff = trend_h4.reindex(df.index, method='ffill').fillna(0).astype(int)

    def trend_at(t):
        try:
            idx = trend_h4.index.searchsorted(t, side='right') - 1
            return int(trend_h4.iloc[idx]) if idx >= 0 else 0
        except Exception:
            return 0

    # FVGs
    fvgs = _detect_fvgs(df_fvg_tf, trend_at, atr_fvg, p['ImpulseMinATR'])
    stats['fvgs_detected'] = len(fvgs)
    stats['fvgs_bull'] = sum(1 for f in fvgs if f['direction'] == 1)
    stats['fvgs_bear'] = sum(1 for f in fvgs if f['direction'] == -1)
    print(f"  FVGs detectadas: {len(fvgs)} (Bull: {stats['fvgs_bull']}, Bear: {stats['fvgs_bear']})")

    if len(fvgs) == 0:
        print("  ❌ NINGUNA FVG. El problema está en _detect_fvgs o en la tendencia.")
        return stats

    # Simular state machine + entradas
    fvg_list = fvgs.copy()
    times = df.index
    o15 = df['open'].values
    h15 = df['high'].values
    l15 = df['low'].values
    c15 = df['close'].values
    atr15 = atr_m15.values

    max_age = pd.Timedelta(hours=p['MaxFVG_Age_Hours'])
    max_confirm = pd.Timedelta(minutes=15 * p['MaxM15Confirm'])

    pos = None
    fvg_filled_history = []  # tiempo de cada FILLED

    for i in range(2, len(df)):
        t = times[i]
        b1_o, b1_c, b1_h, b1_l = o15[i - 1], c15[i - 1], h15[i - 1], l15[i - 1]
        b2_o, b2_c, b2_h, b2_l = o15[i - 2], c15[i - 2], h15[i - 2], l15[i - 2]
        atr_now = atr15[i - 1] if not pd.isna(atr15[i - 1]) else 0
        trend = trend_h4_ff.iloc[i]

        if pos is not None:
            ep, et = None, None
            if pos['dir'] == 1:
                if l15[i] <= pos['sl']: ep = pos['sl']
                elif h15[i] >= pos['tp']: ep = pos['tp']
            else:
                if h15[i] >= pos['sl']: ep = pos['sl']
                elif l15[i] <= pos['tp']: ep = pos['tp']
            if ep is not None:
                pos = None
            else:
                continue

        if trend == 0 or atr_now <= 0:
            continue

        # State machine
        for fvg in fvg_list:
            if fvg['state'] in ('EXPIRED', 'INVALIDATED', 'FILLED_USED'): continue
            if t - fvg['time'] > max_age:
                fvg['state'] = 'EXPIRED'
                stats['fvgs_expired'] += 1
                continue
            sz = fvg['upper'] - fvg['lower']
            if sz <= 0: continue

            old_state = fvg['state']
            if fvg['direction'] == 1:
                if b1_c < fvg['lower'] - sz * 0.5:
                    fvg['state'] = 'INVALIDATED'
                    if old_state != 'INVALIDATED': stats['fvgs_invalidated'] += 1
                    continue
                if fvg['state'] == 'ACTIVE':
                    if b1_l <= fvg['upper']:
                        fvg['state'] = 'TOUCHED'
                        fvg['pullback_extreme'] = b1_l
                        stats['fvgs_touched'] += 1
                elif fvg['state'] == 'TOUCHED':
                    if b1_l < fvg['pullback_extreme']:
                        fvg['pullback_extreme'] = b1_l
                    if b1_c > fvg['lower']:
                        fvg['state'] = 'FILLED'
                        fvg['filled_at'] = t
                        stats['fvgs_filled'] += 1
                        fvg_filled_history.append(t)
            else:
                if b1_c > fvg['upper'] + sz * 0.5:
                    fvg['state'] = 'INVALIDATED'
                    if old_state != 'INVALIDATED': stats['fvgs_invalidated'] += 1
                    continue
                if fvg['state'] == 'ACTIVE':
                    if b1_h >= fvg['lower']:
                        fvg['state'] = 'TOUCHED'
                        fvg['pullback_extreme'] = b1_h
                        stats['fvgs_touched'] += 1
                elif fvg['state'] == 'TOUCHED':
                    if b1_h > fvg['pullback_extreme']:
                        fvg['pullback_extreme'] = b1_h
                    if b1_c < fvg['upper']:
                        fvg['state'] = 'FILLED'
                        fvg['filled_at'] = t
                        stats['fvgs_filled'] += 1
                        fvg_filled_history.append(t)

        if pos is not None: continue

        # Buscar entrada
        for fvg in fvg_list:
            if fvg['state'] != 'FILLED' or fvg['filled_at'] is None: continue
            if t - fvg['filled_at'] > max_confirm: continue
            if fvg['direction'] != trend:
                stats['reject_no_trend'] += 1
                continue

            stats['entry_attempts'] += 1

            # Patrones
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
                stats['reject_no_pattern'] += 1
                continue

            if fvg['direction'] == 1 and b1_c < fvg['lower']:
                stats['reject_cierre_no_respeta_fvg'] += 1
                continue
            if fvg['direction'] == -1 and b1_c > fvg['upper']:
                stats['reject_cierre_no_respeta_fvg'] += 1
                continue

            entry = o15[i]
            if fvg['direction'] == 1:
                sl = fvg['pullback_extreme'] - atr_now * p['SL_ATR_Mult']
                sl_dist = entry - sl
                tp = entry + sl_dist * p['TP_RR']
            else:
                sl = fvg['pullback_extreme'] + atr_now * p['SL_ATR_Mult']
                sl_dist = sl - entry
                tp = entry - sl_dist * p['TP_RR']

            if sl_dist <= 0:
                stats['reject_sl_negative'] += 1
                fvg['state'] = 'FILLED_USED'
                continue

            if sl_dist > atr_now * p['MaxSLATR']:
                stats['reject_sl_too_big'] += 1
                fvg['state'] = 'FILLED_USED'
                continue

            stats['trades_opened'] += 1
            pos = {'dir': fvg['direction'], 'entry': entry, 'sl': sl, 'tp': tp,
                   'sl_dist': sl_dist, 'lots': 0.01, 'point_val': point_value, 'entry_dt': t}
            fvg['state'] = 'FILLED_USED'
            break

    return stats


def main():
    activo = sys.argv[1] if len(sys.argv) > 1 else 'EURUSD'
    if activo not in ASSETS:
        print(f"Activo no disponible: {activo}. Opciones: {list(ASSETS.keys())}")
        return
    fname, col, pv, fvg_tf = ASSETS[activo]
    df = pd.read_csv(DATA_DIR / fname, parse_dates=[col]).set_index(col)
    df = df[df.index >= '2018-01-01']

    print("=" * 70)
    print(f"  DEBUG SMC FVG Universal — {activo}")
    print("=" * 70)

    params = dict(DEFAULT_PARAMS)
    params['FVG_TF'] = fvg_tf

    t0 = time.time()
    stats = debug_run(activo, df, params, pv)
    print(f"\n  Tiempo: {time.time()-t0:.1f}s")

    print("\n=== EMBUDO DE DECISIÓN ===")
    print(f"  FVGs detectadas:           {stats['fvgs_detected']}")
    print(f"  FVGs TOUCHED:              {stats['fvgs_touched']}  ({stats['fvgs_touched']/max(1,stats['fvgs_detected'])*100:.1f}%)")
    print(f"  FVGs FILLED:               {stats['fvgs_filled']}  ({stats['fvgs_filled']/max(1,stats['fvgs_detected'])*100:.1f}%)")
    print(f"  FVGs INVALIDATED:          {stats['fvgs_invalidated']}")
    print(f"  FVGs EXPIRED:              {stats['fvgs_expired']}")
    print(f"\n  Intentos de entrada:       {stats['entry_attempts']}")
    print(f"  Rechazo por no_trend:      {stats['reject_no_trend']}")
    print(f"  Rechazo por no_pattern:    {stats['reject_no_pattern']}")
    print(f"  Rechazo por cierre_FVG:    {stats['reject_cierre_no_respeta_fvg']}")
    print(f"  Rechazo por SL_negative:   {stats['reject_sl_negative']}")
    print(f"  Rechazo por SL_too_big:    {stats['reject_sl_too_big']}")
    print(f"\n  ✓ TRADES ABIERTOS:         {stats['trades_opened']}")

    # Cuellos de botella
    print("\n=== DIAGNÓSTICO ===")
    if stats['fvgs_detected'] < 100:
        print(f"  ⚠️ POCAS FVGs detectadas ({stats['fvgs_detected']}). Causa probable:")
        print(f"     - TrendBars muy alto (actual {params['TrendBars']})")
        print(f"     - ImpulseMinATR muy alto (actual {params['ImpulseMinATR']})")
    if stats['fvgs_filled'] < stats['fvgs_touched'] * 0.5 and stats['fvgs_touched'] > 0:
        print(f"  ⚠️ Pocas FVGs llegan a FILLED ({stats['fvgs_filled']}/{stats['fvgs_touched']} TOUCHED)")
        print(f"     - State machine puede tener bug en transición TOUCHED→FILLED")
    if stats['reject_no_pattern'] > stats['entry_attempts'] * 0.7:
        print(f"  ⚠️ Mayoría de FILLED rechazadas por patrón ({stats['reject_no_pattern']}/{stats['entry_attempts']})")
        print(f"     - Patrones (Doji/Pinbar/Engulfing) muy estrictos")


if __name__ == '__main__':
    main()
