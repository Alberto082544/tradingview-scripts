"""
GT-Score — funcion objetivo robusta anti-overfitting para opt de estrategias.

Inspirado en Sheppert (2026), Journal of Risk and Financial Management.
https://www.mdpi.com/1911-8074/19/2/48

Combina 4 componentes ponderados (cada uno normalizado a [0,1]):
- 40% Probabilistic Sharpe Ratio (PSR) — Sharpe descontando skew/kurt y N
- 25% p-value t-test bilateral sobre returns medios != 0
- 20% Consistencia temporal — % de anyos positivos
- 15% TVaR / Expected Shortfall al 95% (cola izquierda)

Resultado: score en [0, 1]. Mayor = mejor combo.

Comparado con score legacy (mezcla de PF_IS, PF_OOS, DD), GT-Score:
- Penaliza N pequeno (PSR)
- Penaliza ruido (p-value)
- Penaliza regimen-dependencia (consistencia)
- Penaliza colas gordas (TVaR)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def probabilistic_sharpe_ratio(returns: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """
    Probabilistic Sharpe Ratio (Bailey & Lopez de Prado).
    Devuelve P(SR_real > sr_benchmark) considerando skew, kurtosis y N.

    Ventaja sobre Sharpe simple: penaliza N pequeno y colas gordas.
    Rango: [0, 1]. >0.95 = significativamente mejor que benchmark.
    """
    n = len(returns)
    if n < 30:
        return 0.0
    mean_r = float(np.mean(returns))
    std_r = float(np.std(returns, ddof=1))
    if std_r <= 0:
        return 0.0
    sr = mean_r / std_r
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns))  # excess kurtosis
    # Varianza del estimador SR (Mertens 2002)
    sr_var = (1.0 - skew * sr + ((kurt) / 4.0) * sr ** 2) / (n - 1)
    if sr_var <= 0:
        return 0.0
    sr_std = np.sqrt(sr_var)
    z = (sr - sr_benchmark) / sr_std
    return float(stats.norm.cdf(z))


def pvalue_returns(returns: np.ndarray, side: str = "right") -> float:
    """
    Test t de una muestra sobre H0: media = 0.
    side='right': test unilateral H1: media > 0 (lo que queremos en trading).

    Devuelve p-value. Menor = mas significativo.
    """
    if len(returns) < 30:
        return 1.0
    t_stat, p_two_sided = stats.ttest_1samp(returns, 0.0)
    if side == "right":
        # unilateral: H1: media > 0
        return float(p_two_sided / 2) if t_stat > 0 else 1.0
    return float(p_two_sided)


def consistency_by_year(pnls: np.ndarray, timestamps: np.ndarray) -> float:
    """
    % de anyos calendario con PnL agregado > 0.
    Rango: [0, 1]. 1.0 = todos los anyos positivos.
    """
    if timestamps is None or len(timestamps) == 0:
        return 0.5
    df = pd.DataFrame({"pnl": pnls, "ts": pd.to_datetime(timestamps)})
    df["year"] = df["ts"].dt.year
    yearly = df.groupby("year")["pnl"].sum()
    if len(yearly) == 0:
        return 0.0
    return float((yearly > 0).mean())


def expected_shortfall(returns: np.ndarray, alpha: float = 0.95) -> float:
    """
    ES (Expected Shortfall) al nivel alpha. Media de las peores (1-alpha) returns.
    Devuelve un numero NEGATIVO (perdida esperada en cola).

    ES_95 = E[R | R <= VaR_95]
    Mayor magnitud (mas negativo) = colas mas gordas = peor.
    """
    if len(returns) < 20:
        return 0.0
    threshold = float(np.percentile(returns, (1.0 - alpha) * 100))
    tail = returns[returns <= threshold]
    if len(tail) == 0:
        return 0.0
    return float(np.mean(tail))


def gt_score(
    pnls,
    timestamps=None,
    capital: float = 50_000.0,
    weights: dict | None = None,
    return_details: bool = False,
):
    """
    GT-Score compuesto.

    Args:
        pnls: array-like de PnLs por trade ($).
        timestamps: array-like opcional de fechas (datetime-like) para consistencia anual.
        capital: capital inicial usado en el backtest, para normalizar a returns.
        weights: dict con pesos {psr, pval, cons, tvar}. Default 40/25/20/15.
        return_details: si True devuelve dict con componentes; si False devuelve solo score.

    Returns:
        float en [0, 1] (o dict si return_details=True).
    """
    if weights is None:
        weights = {"psr": 0.40, "pval": 0.25, "cons": 0.20, "tvar": 0.15}
    w_sum = sum(weights.values())
    if not np.isclose(w_sum, 1.0):
        weights = {k: v / w_sum for k, v in weights.items()}

    pnls = np.asarray(pnls, dtype=float)
    if len(pnls) < 30:
        result = {"gt_score": 0.0, "reason": "N<30 trades"}
        return result if return_details else 0.0

    returns = pnls / capital  # returns por trade sobre capital

    # 1. PSR
    psr_val = probabilistic_sharpe_ratio(returns, sr_benchmark=0.0)
    n_psr = psr_val  # ya en [0,1]

    # 2. p-value (unilateral derecho)
    pval = pvalue_returns(returns, side="right")
    n_pval = max(0.0, 1.0 - pval)  # p=0.01 -> 0.99

    # 3. Consistencia anual
    cons_val = consistency_by_year(pnls, timestamps)
    n_cons = cons_val

    # 4. TVaR (Expected Shortfall)
    es_val = expected_shortfall(returns, alpha=0.95)
    mean_ret = float(returns.mean())
    if mean_ret > 0:
        # Normalizar: ratio ES/mean. Si ES = -mean (mismo magnitud) -> 0.5
        # ES nunca debe ser positivo para una distribucion normal de returns
        ratio = abs(es_val) / mean_ret if mean_ret > 0 else 999.0
        # Heuristica: ratio < 5 → ok (n~1), ratio > 30 → cola gorda (n~0)
        n_tvar = float(np.clip(1.0 - (ratio - 5) / 25.0, 0.0, 1.0))
    else:
        n_tvar = 0.0

    # Score compuesto
    score = (
        weights["psr"] * n_psr
        + weights["pval"] * n_pval
        + weights["cons"] * n_cons
        + weights["tvar"] * n_tvar
    )

    if return_details:
        return {
            "gt_score": float(score),
            "components_raw": {
                "psr": psr_val,
                "pvalue": pval,
                "consistency": cons_val,
                "tvar_es95": es_val,
            },
            "components_normalized": {
                "psr": n_psr,
                "pval": n_pval,
                "cons": n_cons,
                "tvar": n_tvar,
            },
            "weights": weights,
            "n_trades": len(pnls),
            "mean_return": mean_ret,
        }
    return float(score)


if __name__ == "__main__":
    # Test de humo con datos sinteticos
    np.random.seed(42)
    # caso 1: edge positivo, ruido normal, 1000 trades
    rng = np.random.default_rng(42)
    pnls_good = rng.normal(50, 200, 1000)  # mean +50$, std 200$
    timestamps_good = pd.date_range("2014-01-01", periods=1000, freq="3D")
    print("--- Estrategia buena (mean +$50/trade, 1000 trades, 8 anyos) ---")
    print(gt_score(pnls_good, timestamps_good, return_details=True))

    # caso 2: edge cero, ruido
    pnls_noise = rng.normal(0, 200, 1000)
    timestamps_noise = pd.date_range("2014-01-01", periods=1000, freq="3D")
    print("\n--- Estrategia ruido (mean 0$, 1000 trades) ---")
    print(gt_score(pnls_noise, timestamps_noise, return_details=True))

    # caso 3: cola gorda (algunos trades muy malos)
    pnls_fat = rng.normal(50, 200, 950).tolist() + [-2000] * 50  # 50 trades de -$2000
    pnls_fat = np.array(pnls_fat)
    rng.shuffle(pnls_fat)
    timestamps_fat = pd.date_range("2014-01-01", periods=1000, freq="3D")
    print("\n--- Estrategia cola gorda (50 trades -$2000) ---")
    print(gt_score(pnls_fat, timestamps_fat, return_details=True))

    # caso 4: pocos trades
    pnls_few = rng.normal(50, 200, 25)
    print("\n--- Estrategia pocos trades (N=25) ---")
    print(gt_score(pnls_few, return_details=True))
