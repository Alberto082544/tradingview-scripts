"""Filtra los CSV de optimizaciones existentes por DD<5% en OOS.
Si no hay candidatos, sugiere si vale la pena re-optimizar."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

REPORTS = os.path.join(os.path.dirname(__file__), '..', 'reports')

ARCHIVOS = {
    'MA Cross EURUSD M15':  'MA_Cross_EURUSD_Opt_Results.csv',
    'MA Cross GBPUSD M15':  'MA_Cross_GBPUSD_Opt_Results.csv',
    'Ranger C AUDNZD M15':  'Ranger_C_AUDNZD_Opt_Results.csv',
}

DD_MAX = 5.0  # The 5%ers / FundedNext 5%


def filtrar_csv(nombre, ruta):
    print(f"\n{'='*90}")
    print(f"  {nombre}")
    print(f"{'='*90}")
    if not os.path.exists(ruta):
        print(f"  No existe: {ruta}")
        return
    df = pd.read_csv(ruta)
    n_total = len(df)
    print(f"  Total combos: {n_total}")

    apt = df[(df['oos_dd'] < DD_MAX) & (df['oos_pf'] > 1.0) & (df['oos_n'] >= 100)].copy()
    print(f"  Aptos (OOS DD<{DD_MAX}%, PF>1, N>=100): {len(apt)}")

    if len(apt) == 0:
        print("  ⚠️  Sin candidatos — re-optimizar con grid conservador o reducir LotRiskPct")
        m_dd = df[(df['oos_pf'] > 1.0) & (df['oos_n'] >= 100)].sort_values('oos_dd').head(5)
        print(f"\n  Top 5 por DD bajo (sin restriccion DD<{DD_MAX}%):")
        cols_avail = [c for c in
                      ['EMA_Fast','SMA_Slow','SL_ATR_Mult','RR','Trail_Dist','BE_Trigger',
                       'ADX_H4_Max','RSI_Long_Max','RSI_Short_Min','MinSLPips','TrailDistPips','ExitBars',
                       'is_pf','oos_pf','oos_dd','oos_ann','oos_n','wf_ratio']
                      if c in df.columns]
        print(m_dd[cols_avail].to_string(index=False))
    else:
        apt = apt.sort_values('oos_ann', ascending=False)
        cols_avail = [c for c in
                      ['EMA_Fast','SMA_Slow','SL_ATR_Mult','RR','Trail_Dist','BE_Trigger',
                       'ADX_H4_Max','RSI_Long_Max','RSI_Short_Min','MinSLPips','TrailDistPips','ExitBars',
                       'is_pf','oos_pf','oos_dd','oos_ann','oos_n','wf_ratio']
                      if c in df.columns]
        print(f"\n  TOP 5 por retorno anual:")
        print(apt[cols_avail].head(5).to_string(index=False))


def main():
    for nombre, fname in ARCHIVOS.items():
        filtrar_csv(nombre, os.path.join(REPORTS, fname))


if __name__ == '__main__':
    main()
