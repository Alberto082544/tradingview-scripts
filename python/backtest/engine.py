import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.ema_macd_v5 import add_indicators, generate_signals


class BacktestEngine:
    def __init__(
        self,
        symbol: str            = "SPY",
        interval: str          = "30m",    # "30m" | "1h" | "4h"
        initial_capital: float = 10_000,
        position_pct: float    = 0.10,
        commission: float      = 0.0005,
    ):
        self.symbol          = symbol
        self.interval        = interval
        self.initial_capital = initial_capital
        self.position_pct    = position_pct
        self.commission      = commission
        self._df_intra = None
        self._df1d     = None

    # ------------------------------------------------------------------ #
    # Descarga en bloques (soluciona el límite de 60 días de yfinance)    #
    # ------------------------------------------------------------------ #
    def _download_intraday(self) -> pd.DataFrame:
        # Límites reales de yfinance: 30m → 60d, 1h → 730d
        period = "60d" if self.interval in ("30m", "15m", "5m") else "max"
        ticker = yf.Ticker(self.symbol)
        raw    = ticker.history(period=period, interval=self.interval)

        # Aplanar columnas (evita MultiIndex en algunas versiones)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [col[0].lower() for col in raw.columns]
        else:
            raw.columns = raw.columns.str.lower()

        if hasattr(raw.index, "tz") and raw.index.tz is not None:
            raw.index = raw.index.tz_localize(None)

        return raw

    def download_data(self):
        if self._df_intra is not None:
            return self._df_intra, self._df1d

        print(f"  Descargando {self.symbol} ({self.interval}) — puede tardar unos segundos...")
        df_intra = self._download_intraday()

        # Resample solo si se pidió 4h pero se descargó en 1h
        if self.interval == "4h":
            df_intra = (
                df_intra
                .resample("4h")
                .agg({"open": "first", "high": "max", "low": "min",
                      "close": "last", "volume": "sum"})
                .dropna()
            )

        # Datos diarios para EMA 50D
        raw_1d = yf.Ticker(self.symbol).history(period="max", interval="1d")
        raw_1d.columns = raw_1d.columns.str.lower()
        raw_1d.index   = raw_1d.index.tz_localize(None)

        self._df_intra = df_intra
        self._df1d     = raw_1d
        print(f"  Datos: {len(df_intra)} barras ({df_intra.index[0].date()} → {df_intra.index[-1].date()})")
        return df_intra, raw_1d

    # ------------------------------------------------------------------ #
    # Motor de backtest                                                    #
    # ------------------------------------------------------------------ #
    def _run_on_df(self, df_intra: pd.DataFrame, df1d: pd.DataFrame) -> pd.DataFrame:
        if len(df_intra) < 210:
            return pd.DataFrame()

        df = add_indicators(df_intra.copy())
        df = generate_signals(df, df1d)

        trades   = []
        equity   = self.initial_capital
        position = None

        for i in range(1, len(df)):
            row = df.iloc[i]

            if position:
                sl, tp = position["sl"], position["tp"]

                if row["low"] <= sl:
                    exit_price, exit_type = sl, "SL"
                elif row["high"] >= tp:
                    exit_price, exit_type = tp, "TP"
                else:
                    continue

                gross   = (exit_price - position["entry"]) * position["shares"]
                fee     = exit_price * position["shares"] * self.commission
                pnl     = gross - fee
                equity += pnl

                trades.append({
                    "entry_date":  position["date"],
                    "exit_date":   df.index[i],
                    "entry_price": position["entry"],
                    "exit_price":  exit_price,
                    "exit_type":   exit_type,
                    "shares":      position["shares"],
                    "pnl":         pnl,
                    "pnl_pct":     pnl / position["equity_at_entry"],
                    "equity":      equity,
                })
                position = None

            if position is None and row.get("buy_signal") and pd.notna(row.get("sl_distance")):
                entry  = row["close"]
                sl     = entry - row["sl_distance"]
                tp     = entry + row["tp_distance"]
                shares = (equity * self.position_pct) / entry

                position = {
                    "date":            df.index[i],
                    "entry":           entry,
                    "sl":              sl,
                    "tp":              tp,
                    "shares":          shares,
                    "equity_at_entry": equity,
                }

        return pd.DataFrame(trades)

    def run(self) -> pd.DataFrame:
        df_intra, df1d = self.download_data()
        return self._run_on_df(df_intra, df1d)
