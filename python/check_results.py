import pandas as pd

trades = pd.read_csv('reports/trades_gbpjpy.csv')
n    = len(trades)
wr   = (trades['pnl'] > 0).mean() * 100
pnl  = trades['pnl'].sum()
avg_w = trades.loc[trades['pnl'] > 0, 'pnl'].mean() if wr > 0 else 0
avg_l = trades.loc[trades['pnl'] < 0, 'pnl'].mean() if wr < 100 else 0
max_dd = (trades['equity'].cummax() - trades['equity']).max()
exits  = trades['exit_type'].value_counts().to_dict()
longs  = (trades['direction'] == 'long').sum()
shorts = (trades['direction'] == 'short').sum()
final  = trades['equity'].iloc[-1]

print("=== RESULTADOS BACKTEST (111 trades) ===")
print(f"Trades: {n}")
print(f"WinRate: {wr:.1f}%")
print(f"PnL total: {pnl:.2f} USD")
print(f"Equity final: {final:.2f} USD")
print(f"Avg ganancia: {avg_w:.2f}")
print(f"Avg perdida: {avg_l:.2f}")
print(f"Max Drawdown: {max_dd:.2f}")
print(f"Salidas: {exits}")
print(f"Long: {longs}  Short: {shorts}")
