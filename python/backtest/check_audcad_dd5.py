"""Filtra Ranger_C_AUDCAD_Opt_Results.csv buscando DD<5%."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd

PATH = os.path.join(os.path.dirname(__file__), '..', 'reports', 'Ranger_C_AUDCAD_Opt_Results.csv')

df = pd.read_csv(PATH)
print(f"Total combos AUDCAD: {len(df)}")
print(f"Columnas: {list(df.columns)}\n")

# Filtros: OOS DD<5%, PF>1, N suficiente
apt = df[(df['oos_dd'] < 5.0) & (df['oos_pf'] > 1.0) & (df['oos_n'] >= 100)].copy()
print(f"Aptos DD<5% + PF>1 + N>=100: {len(apt)}")

if len(apt) > 0:
    apt = apt.sort_values('oos_ann', ascending=False)
    cols = [c for c in df.columns if c in
            ['ADX_H4_Max','RSI_Long_Max','RSI_Short_Min','StochMode','Stoch_Long_Max',
             'Stoch_Short_Min','MinSLPips','TrailDistPips','ExitBars',
             'is_pf','oos_pf','oos_dd','oos_ann','oos_n','wf_ratio','wf']]
    print("\nTop 10:")
    print(apt[cols].head(10).to_string(index=False))
else:
    print("\n⚠️  Sin combos con DD<5% en optimización actual")
    print("\nTop 5 por DD más bajo:")
    cols = [c for c in df.columns if c in
            ['ADX_H4_Max','RSI_Long_Max','StochMode','MinSLPips','TrailDistPips','ExitBars',
             'is_pf','oos_pf','oos_dd','oos_ann','oos_n','wf_ratio','wf']]
    print(df.sort_values('oos_dd').head(5)[cols].to_string(index=False))
