import pandas as pd
import numpy as np
from backtest.engine import BacktestEngine


class WalkForward:
    def __init__(
        self,
        symbol: str      = "SPY",
        interval: str    = "1h",
        n_splits: int    = 5,
        train_pct: float = 0.70,
    ):
        self.symbol    = symbol
        self.interval  = interval
        self.n_splits  = n_splits
        self.train_pct = train_pct
        self._rows     = []

    def run(self) -> pd.DataFrame:
        engine = BacktestEngine(self.symbol, interval=self.interval)
        df4h, df1d = engine.download_data()

        n      = len(df4h)
        window = n // self.n_splits

        for i in range(self.n_splits):
            start    = i * window
            end      = min((i + 1) * window, n)
            split    = int(start + (end - start) * self.train_pct)

            df_is  = df4h.iloc[start:split]
            df_oos = df4h.iloc[split:end]

            trades_is  = engine._run_on_df(df_is,  df1d)
            trades_oos = engine._run_on_df(df_oos, df1d)

            self._rows.append({
                "Periodo":    i + 1,
                "IS inicio":  df4h.index[start].strftime("%Y-%m-%d"),
                "IS fin":     df4h.index[split - 1].strftime("%Y-%m-%d"),
                "IS trades":  len(trades_is),
                "IS P&L %":   f"{trades_is['pnl_pct'].sum()*100:.2f} %" if len(trades_is) > 0 else "—",
                "OOS inicio": df4h.index[split].strftime("%Y-%m-%d"),
                "OOS fin":    df4h.index[end - 1].strftime("%Y-%m-%d"),
                "OOS trades": len(trades_oos),
                "OOS P&L %":  f"{trades_oos['pnl_pct'].sum()*100:.2f} %" if len(trades_oos) > 0 else "—",
            })

        return pd.DataFrame(self._rows)

    def report(self):
        df = pd.DataFrame(self._rows)
        sep = "=" * 90
        print(f"\n{sep}")
        print("               WALK-FORWARD ANALYSIS — EMA+MACD v5")
        print(sep)
        print(df.to_string(index=False))
        print(sep)

        # Consistencia: periodos OOS positivos
        oos_values = [
            float(r["OOS P&L %"].replace(" %", ""))
            for r in self._rows
            if r["OOS P&L %"] != "—"
        ]
        if oos_values:
            positivos = sum(v > 0 for v in oos_values)
            print(f"\n  Periodos OOS positivos: {positivos}/{len(oos_values)}")
            print(f"  Consistencia:           {positivos/len(oos_values)*100:.0f} %")
            if positivos / len(oos_values) >= 0.6:
                print("  ✔ Estrategia CONSISTENTE (≥ 60 % periodos positivos)")
            else:
                print("  ✘ Posible OVERFITTING (< 60 % periodos positivos)")
        print(sep)
