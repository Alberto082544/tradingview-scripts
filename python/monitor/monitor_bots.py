"""Monitor semanal de bots en MT5.

Uso:
  python monitor/monitor_bots.py             # ambos terminales (FundedNext + 5%ers)
  python monitor/monitor_bots.py FN           # solo FundedNext
  python monitor/monitor_bots.py FP           # solo Five Percent (5%ers)
  python monitor/monitor_bots.py --days 7     # ultimos 7 dias (defecto: semana actual)

Para cada bot muestra:
  - Trades semana
  - Wins / Losses / WR
  - PnL acumulado
  - PF realizado
  - DD maximo intra-semana
  - Status (activo si tiene posicion abierta o equity cerca)
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import argparse
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Falta MetaTrader5: pip install MetaTrader5")
    sys.exit(1)

# Bots por MagicNumber
BOTS = {
    202601: 'AUDNZD Ranger C',
    202602: 'XAUUSD ORB',
    202610: 'EURUSD MA Cross',
    202611: 'GBPUSD MA Cross (descartado)',
    202620: 'NAS100 EMA9+VWAP',
}

TERMINALES = {
    'FN':  ('FundedNext',   'C:/Program Files/FundedNext MT5 Terminal/terminal64.exe'),
    'FP':  ('Five Percent', 'C:/Program Files/Five Percent Online MetaTrader 5/terminal64.exe'),
}


def get_inicio_semana():
    """Lunes 00:00 UTC de la semana actual."""
    hoy = datetime.now()
    return datetime(hoy.year, hoy.month, hoy.day) - timedelta(days=hoy.weekday())


def analizar_terminal(nombre, path, desde):
    print("\n" + "="*78)
    print(f"  {nombre}")
    print("="*78)

    if not mt5.initialize(path=path):
        print(f"  No se pudo conectar: {mt5.last_error()}")
        return

    info = mt5.account_info()
    if info is None:
        print(f"  No hay cuenta")
        mt5.shutdown()
        return

    print(f"  Balance: ${info.balance:,.2f}  |  Equity: ${info.equity:,.2f}")
    print(f"  Server: {info.server}  |  Login: {info.login}")
    print(f"  Periodo: desde {desde.strftime('%Y-%m-%d %H:%M')} hasta ahora")

    # Posiciones abiertas
    posiciones = mt5.positions_get() or []
    abiertas_por_bot = {}
    for p in posiciones:
        abiertas_por_bot.setdefault(p.magic, 0)
        abiertas_por_bot[p.magic] += 1

    # Deals del periodo
    deals = mt5.history_deals_get(desde, datetime.now()) or []

    # Agrupar por magic
    por_bot = {}
    for d in deals:
        if d.magic not in BOTS: continue
        b = por_bot.setdefault(d.magic, {'wins':0, 'losses':0, 'pnl':0.0, 'pnls':[]})
        # Solo deals de salida (OUT)
        if d.entry == mt5.DEAL_ENTRY_OUT:
            b['pnl']     += d.profit
            b['pnls'].append(d.profit)
            if d.profit > 0:   b['wins']   += 1
            elif d.profit < 0: b['losses'] += 1

    # DD intra-periodo (aproximado por equity cumulada)
    def calc_dd(pnls):
        if not pnls: return 0
        eq = 0; peak = 0; dd = 0
        for p in pnls:
            eq += p
            if eq > peak: peak = eq
            cur_dd = peak - eq
            if cur_dd > dd: dd = cur_dd
        return dd

    print(f"\n  {'Bot':<35} {'N':>4} {'W':>3} {'L':>3} {'WR%':>5} {'PnL':>10} {'PF':>5} {'DD$':>9} {'Abier':>6}")
    print(f"  {'-'*88}")
    total_pnl = 0
    for magic, nombre_bot in BOTS.items():
        if magic not in por_bot and magic not in abiertas_por_bot:
            continue
        b = por_bot.get(magic, {'wins':0,'losses':0,'pnl':0,'pnls':[]})
        n = b['wins'] + b['losses']
        wr = (b['wins'] / n * 100) if n > 0 else 0
        wins_sum = sum(p for p in b['pnls'] if p > 0)
        loss_sum = sum(p for p in b['pnls'] if p < 0)
        pf = wins_sum / abs(loss_sum) if loss_sum != 0 else (999 if wins_sum > 0 else 0)
        dd = calc_dd(b['pnls'])
        abier = abiertas_por_bot.get(magic, 0)
        total_pnl += b['pnl']
        print(f"  {nombre_bot:<35} {n:>4} {b['wins']:>3} {b['losses']:>3} {wr:>5.1f} ${b['pnl']:>+9.0f} {pf:>5.2f} ${dd:>7.0f} {abier:>6}")

    print(f"  {'-'*88}")
    print(f"  PnL total periodo: ${total_pnl:+,.2f}")

    # Métricas globales cuenta
    pct_balance = (info.balance - info.equity) / info.balance * 100 if info.balance > 0 else 0
    print(f"  Equity floating: {-pct_balance:+.2f}% (positivo = ganando)")

    mt5.shutdown()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('terminal', nargs='?', default='ALL', help='FN, FP o ALL')
    p.add_argument('--days', type=int, default=None, help='Ultimos N dias (sino: semana actual)')
    args = p.parse_args()

    if args.days:
        desde = datetime.now() - timedelta(days=args.days)
    else:
        desde = get_inicio_semana()

    if args.terminal.upper() == 'ALL':
        for clave, (nombre, path) in TERMINALES.items():
            analizar_terminal(nombre, path, desde)
    elif args.terminal.upper() in TERMINALES:
        nombre, path = TERMINALES[args.terminal.upper()]
        analizar_terminal(nombre, path, desde)
    else:
        print(f"Terminal desconocido. Usa: FN, FP, ALL")


if __name__ == '__main__':
    main()
