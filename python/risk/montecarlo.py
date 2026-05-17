import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


class MonteCarlo:
    def __init__(
        self,
        trades: pd.DataFrame,
        initial_capital: float = 10_000,
        ruin_threshold: float  = 0.50,   # ruina = perder más del 50 %
        iterations: int        = 10_000,
    ):
        self.trades          = trades
        self.initial_capital = initial_capital
        self.ruin_threshold  = ruin_threshold
        self.iterations      = iterations
        self.results         = None

    def run(self) -> dict:
        returns = self.trades["pnl_pct"].values
        n       = len(returns)

        final_equities = np.empty(self.iterations)
        max_drawdowns  = np.empty(self.iterations)
        ruined         = 0

        rng = np.random.default_rng(seed=42)

        for k in range(self.iterations):
            shuffled = rng.choice(returns, size=n, replace=True)
            curve    = self.initial_capital * np.cumprod(1.0 + shuffled)

            if curve.min() < self.initial_capital * (1 - self.ruin_threshold):
                ruined += 1

            peak     = np.maximum.accumulate(curve)
            dd       = (curve - peak) / peak
            max_drawdowns[k]  = dd.min()
            final_equities[k] = curve[-1]

        self.results = {
            "final_equities":  final_equities,
            "max_drawdowns":   max_drawdowns,
            "risk_of_ruin":    ruined / self.iterations,
            "drawdown_95pct":  np.percentile(max_drawdowns, 5),   # peor 95 %
            "expected_equity": float(np.mean(final_equities)),
            "median_equity":   float(np.median(final_equities)),
            "p5_equity":       float(np.percentile(final_equities, 5)),
            "p95_equity":      float(np.percentile(final_equities, 95)),
        }
        return self.results

    def print_report(self):
        r = self.results
        sep = "=" * 52
        print(f"\n{sep}")
        print("    INFORME MONTE CARLO  ({:,} iteraciones)".format(self.iterations))
        print(sep)
        print(f"  Prob. de Ruina (pérdida > {self.ruin_threshold*100:.0f} %): "
              f"{r['risk_of_ruin']*100:.2f} %")
        print(f"  Drawdown Máx. esperado (95 % conf.):    "
              f"{r['drawdown_95pct']*100:.2f} %")
        print(f"  Capital Final Esperado:                 "
              f"${r['expected_equity']:,.2f}")
        print(f"  Capital Final Mediano:                  "
              f"${r['median_equity']:,.2f}")
        print(f"  Rango P5 – P95:                         "
              f"${r['p5_equity']:,.2f}  –  ${r['p95_equity']:,.2f}")
        print(sep)

    def plot(self, save_path: str = "reports/montecarlo.png"):
        if self.results is None:
            self.run()
        r = self.results

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle("Monte Carlo — EMA+MACD v5 (10 000 iteraciones)",
                     fontsize=13, fontweight="bold")

        # --- Distribución del capital final ---
        ax1.hist(r["final_equities"], bins=120, color="steelblue",
                 edgecolor="none", alpha=0.8)
        ax1.axvline(self.initial_capital,     color="red",    ls="--", lw=1.5,
                    label="Capital inicial")
        ax1.axvline(r["p5_equity"],           color="orange", ls="--", lw=1.5,
                    label=f"P5  ${r['p5_equity']:,.0f}")
        ax1.axvline(r["median_equity"],       color="green",  ls="--", lw=1.5,
                    label=f"Mediana  ${r['median_equity']:,.0f}")
        ax1.set_title("Distribución del Capital Final")
        ax1.set_xlabel("Capital Final ($)")
        ax1.set_ylabel("Frecuencia")
        ax1.legend(fontsize=9)

        # --- Distribución del Drawdown Máximo ---
        dd_pct = r["max_drawdowns"] * 100
        ax2.hist(dd_pct, bins=120, color="salmon", edgecolor="none", alpha=0.8)
        ax2.axvline(r["drawdown_95pct"] * 100, color="darkred", ls="--", lw=1.5,
                    label=f"DD 95 %  {r['drawdown_95pct']*100:.1f} %")
        ax2.set_title("Distribución del Drawdown Máximo")
        ax2.set_xlabel("Drawdown Máximo (%)")
        ax2.set_ylabel("Frecuencia")
        ax2.legend(fontsize=9)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Gráfico guardado → {save_path}")
