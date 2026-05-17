"""
GBPJPY ORB — Generador de señales
Estrategia: Ruptura del rango de la primera barra M15 de la sesión.
Sesiones: Nueva York (13:30 GMT) y Londres (08:00 GMT).
"""
import numpy as np
import pandas as pd


PIP = 0.01  # Par JPY: 1 pip = 0.01


def add_indicators(df_m15: pd.DataFrame) -> pd.DataFrame:
    df = df_m15.copy()
    df['hour']   = df.index.hour
    df['minute'] = df.index.minute
    df['dow']    = df.index.dayofweek   # 0=Lun, 4=Vie
    df['bar_min'] = df['hour'] * 60 + df['minute']
    return df


def generate_signals(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """
    Genera señales ORB barra a barra.
    Columnas de salida:
      long_signal, short_signal: bool
      orb_high, orb_low, orb_range: precio
      session: "NY" | "LONDON"
    """
    df = df.copy()
    df['long_signal']  = False
    df['short_signal'] = False
    df['orb_high']  = np.nan
    df['orb_low']   = np.nan
    df['orb_range'] = np.nan
    df['session']   = ""

    pip_size  = getattr(cfg, '_pip', PIP)
    min_range = cfg.MIN_RANGE_PIPS * pip_size
    max_range = cfg.MAX_RANGE_PIPS * pip_size

    sessions = []
    if cfg.SESSION in ("NY", "BOTH"):
        sessions.append(("NY",     cfg.NY_START_H  * 60 + cfg.NY_START_M,  cfg.NY_END_H  * 60))
    if cfg.SESSION in ("LONDON", "BOTH"):
        sessions.append(("LONDON", cfg.LDN_START_H * 60 + cfg.LDN_START_M, cfg.LDN_END_H * 60))

    # Estado por sesión: se resetea cada día
    state = {s[0]: {"defined": False, "high": 0.0, "low": 0.0, "traded": False}
             for s in sessions}
    current_date = None
    trades_today = 0

    arr_idx     = df.index
    arr_high    = df['high'].values
    arr_low     = df['low'].values
    arr_close   = df['close'].values
    arr_bar_min = df['bar_min'].values
    arr_dow     = df['dow'].values

    for i in range(len(df)):
        date = arr_idx[i].date()
        if date != current_date:
            current_date = date
            trades_today = 0
            for s in state:
                state[s] = {"defined": False, "high": 0.0, "low": 0.0, "traded": False}

        if arr_dow[i] >= 5:   # Fin de semana
            continue
        if trades_today >= cfg.MAX_TRADES_DAY:
            continue

        bm = arr_bar_min[i]
        for sess_name, open_min, end_min in sessions:
            st = state[sess_name]

            # ── Primera barra de sesión: definir rango ────────────────────────
            if bm == open_min and not st["defined"]:
                rng = arr_high[i] - arr_low[i]
                if min_range <= rng <= max_range:
                    st["defined"] = True
                    st["high"]    = arr_high[i]
                    st["low"]     = arr_low[i]
                continue

            # ── Fin de sesión: invalidar rango sin señal ──────────────────────
            if bm >= end_min:
                st["defined"] = False
                st["traded"]  = False
                continue

            # ── Buscar ruptura ────────────────────────────────────────────────
            if st["defined"] and not st["traded"]:
                rng = st["high"] - st["low"]
                direction = getattr(cfg, 'DIRECTION', 'BOTH')
                if arr_close[i] > st["high"] and direction != "SHORT_ONLY":
                    df.iloc[i, df.columns.get_loc('long_signal')]  = True
                    df.iloc[i, df.columns.get_loc('orb_high')]  = st["high"]
                    df.iloc[i, df.columns.get_loc('orb_low')]   = st["low"]
                    df.iloc[i, df.columns.get_loc('orb_range')] = rng
                    df.iloc[i, df.columns.get_loc('session')]   = sess_name
                    st["traded"] = True
                    trades_today += 1
                elif arr_close[i] < st["low"] and direction != "LONG_ONLY":
                    df.iloc[i, df.columns.get_loc('short_signal')] = True
                    df.iloc[i, df.columns.get_loc('orb_high')]  = st["high"]
                    df.iloc[i, df.columns.get_loc('orb_low')]   = st["low"]
                    df.iloc[i, df.columns.get_loc('orb_range')] = rng
                    df.iloc[i, df.columns.get_loc('session')]   = sess_name
                    st["traded"] = True
                    trades_today += 1

    return df
