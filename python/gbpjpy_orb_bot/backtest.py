"""
GBPJPY ORB — Motor de backtest barra a barra.
Doble entrada: Posición 1 cierra en TP1, Posición 2 tiene BE tras TP1 y cierra en TP2.
"""
import numpy as np
import pandas as pd

PIP = 0.01


def _pip_val(capital, risk_pct, sl_pips, pip_usd=6.9, half=False):
    risk = capital * (risk_pct / 2 if half else risk_pct)
    if sl_pips <= 0:
        return 0.01
    lots = risk / (sl_pips * pip_usd)
    return max(0.01, round(lots, 2))


def run_backtest(df: pd.DataFrame, cfg) -> pd.DataFrame:
    capital   = cfg.INITIAL_CAPITAL
    pip_usd   = getattr(cfg, '_pip_usd', 6.9)   # por defecto GBPJPY
    pip_size  = getattr(cfg, '_pip', PIP)         # tamaño de pip del activo
    be_buf    = cfg.BE_OFFSET_PIPS * pip_size
    records   = []

    arr_high  = df['high'].values
    arr_low   = df['low'].values
    arr_close = df['close'].values
    arr_open  = df['open'].values
    arr_idx   = df.index

    # Posiciones abiertas: lista de dicts
    positions = []

    def _close_pos(pos, price, bar_idx, reason):
        nonlocal capital
        dist  = (price - pos['entry']) if pos['dir'] == 1 else (pos['entry'] - price)
        pnl   = dist / pip_size * pip_usd * pos['lots']
        capital += pnl
        records.append({
            'entry_time': arr_idx[pos['open_bar']],
            'exit_time':  arr_idx[bar_idx],
            'direction':  'LONG' if pos['dir'] == 1 else 'SHORT',
            'session':    pos['session'],
            'entry':      pos['entry'],
            'exit':       price,
            'sl':         pos['sl'],
            'tp':         pos['tp'],
            'lots':       pos['lots'],
            'pnl':        round(pnl, 2),
            'sl_pips':    round(abs(pos['entry'] - pos['sl']) / PIP, 1),
            'pnl_pips':   round(dist / PIP, 1),
            'reason':     reason,
            'capital':    round(capital, 2),
        })
        return pnl

    for i in range(len(df)):
        h = arr_high[i]
        l = arr_low[i]
        o = arr_open[i]

        # ── Gestión de posiciones abiertas ────────────────────────────────────
        still_open = []
        for pos in positions:
            d     = pos['dir']      # 1=long, -1=short
            entry = pos['entry']
            sl    = pos['sl']
            tp    = pos['tp']

            # Verificar SL
            sl_hit = (d == 1 and l <= sl) or (d == -1 and h >= sl)
            tp_hit = (d == 1 and h >= tp) or (d == -1 and l <= tp)

            if sl_hit and tp_hit:
                # Ambos en la misma barra: orden de aparición no determinado → SL conservador
                sl_hit, tp_hit = True, False

            if sl_hit:
                _close_pos(pos, sl, i, "SL")
                # Activar TP2 de la posición hermana si existe
                for p2 in still_open + positions:
                    if p2.get('pair_id') == pos.get('pair_id') and p2 is not pos:
                        p2['be_pending'] = True
            elif tp_hit:
                _close_pos(pos, tp, i, "TP")
                # Mover SL a BE en posición hermana (TP2)
                for p2 in still_open:
                    if p2.get('pair_id') == pos.get('pair_id') and p2 is not pos:
                        new_sl = entry + be_buf * d
                        if (d == 1 and new_sl > p2['sl']) or (d == -1 and new_sl < p2['sl']):
                            p2['sl'] = new_sl
                            p2['be_done'] = True
            else:
                still_open.append(pos)

            # Fin de sesión: cerrar si CLOSE_EOS
            if cfg.CLOSE_EOS and pos in still_open:
                sess  = pos['session']
                end_h = cfg.NY_END_H if sess == "NY" else cfg.LDN_END_H
                if arr_idx[i].hour >= end_h:
                    still_open.remove(pos)
                    _close_pos(pos, arr_close[i], i, "EOS")

        positions = still_open

        # ── Nuevas señales ─────────────────────────────────────────────────────
        row = df.iloc[i]
        for signal, direction in [('long_signal', 1), ('short_signal', -1)]:
            if not row[signal]:
                continue
            orb_rng  = row['orb_range']
            orb_high = row['orb_high']
            orb_low  = row['orb_low']
            sess     = row['session']

            entry = arr_close[i]
            if direction == 1:
                sl   = orb_low
                tp1  = entry + orb_rng * cfg.TP1_MULT
                tp2  = entry + orb_rng * cfg.TP2_MULT
            else:
                sl   = orb_high
                tp1  = entry - orb_rng * cfg.TP1_MULT
                tp2  = entry - orb_rng * cfg.TP2_MULT

            sl_pips = abs(entry - sl) / pip_size
            if sl_pips < 1:
                continue

            pair_id = f"{arr_idx[i]}_{sess}"
            lots1   = min(_pip_val(capital, cfg.RISK_PCT, sl_pips, pip_usd, half=True), cfg.MAX_LOTS)
            lots2   = min(_pip_val(capital, cfg.RISK_PCT, sl_pips, pip_usd, half=True), cfg.MAX_LOTS)

            if cfg.USE_DOUBLE_ENTRY:
                positions.append({
                    'dir': direction, 'entry': entry, 'sl': sl,
                    'tp': tp1, 'lots': lots1, 'open_bar': i,
                    'session': sess, 'pair_id': pair_id,
                    'be_done': False, 'label': 'TP1'
                })
                positions.append({
                    'dir': direction, 'entry': entry, 'sl': sl,
                    'tp': tp2, 'lots': lots2, 'open_bar': i,
                    'session': sess, 'pair_id': pair_id,
                    'be_done': False, 'label': 'TP2'
                })
            else:
                positions.append({
                    'dir': direction, 'entry': entry, 'sl': sl,
                    'tp': tp2, 'lots': lots1 + lots2, 'open_bar': i,
                    'session': sess, 'pair_id': pair_id,
                    'be_done': False, 'label': 'TP2'
                })

    # Cerrar posiciones remanentes al final
    if positions:
        last_close = arr_close[-1]
        for pos in positions:
            _close_pos(pos, last_close, len(df) - 1, "END")

    return pd.DataFrame(records)


def print_results(trades: pd.DataFrame, initial_capital: float = 50_000.0):
    if len(trades) == 0:
        print("  Sin trades.")
        return

    wins     = trades[trades['pnl'] > 0]
    losses   = trades[trades['pnl'] <= 0]
    wr       = len(wins) / len(trades) * 100
    gross_p  = wins['pnl'].sum()
    gross_l  = abs(losses['pnl'].sum())
    pf       = gross_p / gross_l if gross_l > 0 else float('inf')
    total_pnl= trades['pnl'].sum()
    ret_pct  = total_pnl / initial_capital * 100

    # Max drawdown
    eq = initial_capital + trades['pnl'].cumsum()
    peak = eq.cummax()
    dd   = ((peak - eq) / peak * 100).max()

    # Por sesión
    print(f"\n{'='*60}")
    print(f"  GBPJPY ORB — Resultados ({len(trades)} trades)")
    print(f"{'='*60}")
    print(f"  Capital inicial : ${initial_capital:>10,.0f}")
    print(f"  Capital final   : ${initial_capital + total_pnl:>10,.0f}")
    print(f"  P&L total       : ${total_pnl:>+10,.0f}  ({ret_pct:+.1f}%)")
    print(f"  Winrate         : {wr:.1f}%")
    print(f"  Profit Factor   : {pf:.2f}")
    print(f"  Max Drawdown    : {dd:.1f}%")
    print(f"  Trades ganadores: {len(wins)}")
    print(f"  Trades perdidos : {len(losses)}")

    if 'session' in trades.columns:
        print(f"\n  Por sesión:")
        for sess, grp in trades.groupby('session'):
            w = (grp['pnl'] > 0).sum()
            print(f"    {sess:7s}: {len(grp):4d} trades | WR {w/len(grp)*100:.0f}% | P&L ${grp['pnl'].sum():+,.0f}")

    if 'direction' in trades.columns:
        print(f"\n  Por dirección:")
        for d, grp in trades.groupby('direction'):
            w = (grp['pnl'] > 0).sum()
            print(f"    {d:6s}: {len(grp):4d} trades | WR {w/len(grp)*100:.0f}% | P&L ${grp['pnl'].sum():+,.0f}")

    print(f"{'='*60}\n")
