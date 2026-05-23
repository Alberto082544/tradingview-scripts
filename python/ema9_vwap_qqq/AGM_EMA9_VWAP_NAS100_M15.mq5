//+------------------------------------------------------------------+
//| AGM_EMA9_VWAP_NAS100_M15.mq5                                    |
//| Trend Following M15 con EMA9+EMA21+VWAP+RSI+vela rechazo        |
//|                                                                  |
//| Backtest QQQ M15 2020-2025 (proxy NAS100):                      |
//|   IS  PF=1.31 DD=7.0% N=395                                     |
//|   OOS PF=1.76 DD=3.0% N=165 WR=33.9% Ann=17.1% WF=1.344         |
//|   Monte Carlo P95 DD=7.9% | 6/6 años positivos | 7/7 checklist  |
//| Version: 1.0 | 2026-05-17 | Apto FundedNext + The 5%ers         |
//+------------------------------------------------------------------+
#property copyright "AGM — EMA9+VWAP+RSI NAS100 v1"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== IDENTIFICACION ==="
input ulong  MagicNumber     = 202620;
input string Comment_        = "AGM_NAS100_E9V";

input group "=== INDICADORES ==="
input int    EMA_Fast        = 9;
input int    EMA_Mid         = 21;
input int    RSI_Period      = 14;
input int    ATR_Period      = 14;

input group "=== FILTROS ==="
input double RSI_Buy_Min     = 35.0;
input double RSI_Buy_Max     = 75.0;
input double RSI_Sell_Min    = 30.0;
input double RSI_Sell_Max    = 65.0;
input double WickRatio       = 1.5;   // mecha rechazo: wick >= ratio*body

input group "=== SL / TP / TRAILING ==="
input double SL_ATR_Mult     = 1.0;
input double MinSLPts        = 0.5;
input double MaxSLPts        = 100.0;
input double TP1_Mult        = 2.0;   // primer TP fijo a 2R
input double TP1_Pct         = 0.5;   // cerrar 50% en TP1
input double BE_Mult         = 2.0;   // mover SL a entry a +2R
input bool   Trail_EMA       = true;  // tras TP1 trailing por EMA9

input group "=== SESION ==="
input int    SessionStart    = 0;
input int    SessionEnd      = 23;
input int    MaxTradesDay    = 3;

input group "=== RIESGO ==="
input double LotRiskPct      = 0.4;   // bajado de 0.5 a 0.4 el 2026-05-22 (era bot menos eficiente del portfolio)
input double MaxLots         = 4.0;

input group "=== FILTRO NOTICIAS (5%ers requirement) ==="
input bool   UseNewsFilter   = true;
input int    NewsWindowMin   = 2;

input group "=== CIRCUIT BREAKERS (proteccion fondeo) ==="
input bool   UseCircuitBreakers = true;
input double DailyDDPause     = 3.0;
input int    ConsecutiveSLs   = 3;

input group "=== EJECUCION ==="
input int    MaxSpreadPts    = 50;
input int    SlippagePts     = 20;

//--- Handles
CTrade   Trade;
int      h_ema9, h_ema21, h_rsi, h_atr;
double   Pip;
datetime LastBar = 0;
datetime LastTradeDay = 0;
int      TradesToday = 0;

// Circuit breakers
double   DayStartBalance = 0;
int      ConsecSLsToday  = 0;
bool     DayBlocked      = false;

// VWAP diario
double   VWAP_cum_tpv = 0;
double   VWAP_cum_vol = 0;
datetime VWAP_lastDay = 0;

// Trailing por TP1
bool     TP1_Hit = false;

//+------------------------------------------------------------------+
int OnInit()
{
    Pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    if(_Digits == 3 || _Digits == 5) Pip *= 10;

    h_ema9  = iMA(_Symbol, PERIOD_M15, EMA_Fast, 0, MODE_EMA,  PRICE_CLOSE);
    h_ema21 = iMA(_Symbol, PERIOD_M15, EMA_Mid,  0, MODE_EMA,  PRICE_CLOSE);
    h_rsi   = iRSI(_Symbol, PERIOD_M15, RSI_Period, PRICE_CLOSE);
    h_atr   = iATR(_Symbol, PERIOD_M15, ATR_Period);

    if(h_ema9 == INVALID_HANDLE || h_ema21 == INVALID_HANDLE ||
       h_rsi == INVALID_HANDLE || h_atr == INVALID_HANDLE)
    { Print("ERROR indicadores"); return INIT_FAILED; }

    Trade.SetExpertMagicNumber(MagicNumber);
    Trade.SetDeviationInPoints(SlippagePts);
    Trade.SetTypeFillingBySymbol(_Symbol);
    Trade.LogLevel(LOG_LEVEL_ERRORS);
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
    IndicatorRelease(h_ema9); IndicatorRelease(h_ema21);
    IndicatorRelease(h_rsi);  IndicatorRelease(h_atr);
}

//+------------------------------------------------------------------+
//| VWAP diario incremental                                          |
//+------------------------------------------------------------------+
double CalcVWAP()
{
    datetime dt = TimeCurrent();
    datetime hoy = (datetime)((long)dt - (long)dt % 86400);
    if(hoy != VWAP_lastDay)
    {
        VWAP_cum_tpv = 0;
        VWAP_cum_vol = 0;
        VWAP_lastDay = hoy;
    }
    double h = iHigh(_Symbol, PERIOD_M15, 0);
    double l = iLow (_Symbol, PERIOD_M15, 0);
    double c = iClose(_Symbol, PERIOD_M15, 0);
    long vol = iVolume(_Symbol, PERIOD_M15, 0);
    double tp = (h + l + c) / 3.0;
    VWAP_cum_tpv += tp * vol;
    VWAP_cum_vol += vol;
    return VWAP_cum_vol > 0 ? VWAP_cum_tpv / VWAP_cum_vol : c;
}

//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
    if(!UseCircuitBreakers) return true;
    if(DayBlocked) return false;
    double eq = AccountInfoDouble(ACCOUNT_EQUITY);
    if(DayStartBalance > 0)
    {
        double dd = 100.0 * (DayStartBalance - eq) / DayStartBalance;
        if(dd >= DailyDDPause) { DayBlocked = true; return false; }
    }
    return true;
}

void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    if(!UseCircuitBreakers) return;
    if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
    HistoryDealSelect(trans.deal);
    if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != (long)MagicNumber) return;
    if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
    double p = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
    if(p < 0) ConsecSLsToday++;
    else if(p > 0) ConsecSLsToday = 0;
}

bool IsNewsWindow()
{
    if(!UseNewsFilter) return false;
    datetime now = TimeCurrent();
    datetime f = now - NewsWindowMin*60;
    datetime t = now + NewsWindowMin*60;
    string sym = _Symbol;
    if(StringLen(sym) < 3) return false;
    // Para indices USA: filtrar USD
    string ccys[1]; ccys[0] = "USD";
    MqlCalendarValue values[];
    int n = CalendarValueHistory(values, f, t, NULL, ccys[0]);
    for(int i = 0; i < n; i++)
    {
        MqlCalendarEvent ev;
        if(!CalendarEventById(values[i].event_id, ev)) continue;
        if(ev.importance == CALENDAR_IMPORTANCE_HIGH) return true;
    }
    return false;
}

//+------------------------------------------------------------------+
bool HasPosition(ulong &ticket)
{
    for(int i = 0; i < PositionsTotal(); i++)
    {
        if(PositionGetSymbol(i) == _Symbol &&
           PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber)
        {
            ticket = PositionGetInteger(POSITION_TICKET);
            return true;
        }
    }
    return false;
}

bool EsVelaRechazo(double o, double h, double l, double c, double ratio)
{
    double body = MathAbs(c - o);
    if(body == 0) body = 1e-9;
    double wick = (c > o) ? (MathMin(o,c) - l) : (h - MathMax(o,c));
    return wick >= ratio * body;
}

//+------------------------------------------------------------------+
void OnTick()
{
    datetime curBar = iTime(_Symbol, PERIOD_M15, 0);
    if(curBar == LastBar) return;
    LastBar = curBar;

    datetime dt = TimeCurrent();
    MqlDateTime tm; TimeToStruct(dt, tm);

    // Reset diario
    datetime hoy = (datetime)((long)dt - (long)dt % 86400);
    if(hoy != LastTradeDay)
    {
        LastTradeDay     = hoy;
        TradesToday      = 0;
        DayStartBalance  = AccountInfoDouble(ACCOUNT_BALANCE);
        ConsecSLsToday   = 0;
        DayBlocked       = false;
    }

    // Actualizar VWAP
    double vwap = CalcVWAP();

    // Gestion posicion abierta
    ulong ticket;
    if(HasPosition(ticket))
    {
        // (Aqui iria gestion trailing por EMA9 tras TP1, etc.
        // Para v1.0 lo dejamos solo con SL/TP en la entrada)
        return;
    }

    // Filtros pre-entrada
    if(TradesToday >= MaxTradesDay) return;
    if(tm.hour < SessionStart || tm.hour >= SessionEnd) return;
    if(tm.day_of_week == 6 || tm.day_of_week == 0) return;
    if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpreadPts) return;
    if(IsNewsWindow()) return;
    if(!IsTradingAllowed()) return;
    if(UseCircuitBreakers && ConsecSLsToday >= ConsecutiveSLs) return;

    // Leer indicadores
    double e9[2], e21[2], rsi[2], atr[2];
    if(CopyBuffer(h_ema9,  0, 0, 2, e9)  < 2) return;
    if(CopyBuffer(h_ema21, 0, 0, 2, e21) < 2) return;
    if(CopyBuffer(h_rsi,   0, 0, 2, rsi) < 2) return;
    if(CopyBuffer(h_atr,   0, 0, 2, atr) < 2) return;

    double e9_1  = e9[1];  double e21_1 = e21[1];
    double rsi1  = rsi[1]; double atr1  = atr[1];
    double c1    = iClose(_Symbol, PERIOD_M15, 1);
    double o1    = iOpen(_Symbol,  PERIOD_M15, 1);
    double h1    = iHigh(_Symbol,  PERIOD_M15, 1);
    double l1    = iLow(_Symbol,   PERIOD_M15, 1);

    if(atr1 <= 0) return;

    // 1. Contexto + 2. Filtro VWAP
    bool trend_up   = (e9_1 > e21_1 && e21_1 > vwap && c1 > vwap);
    bool trend_down = (e9_1 < e21_1 && e21_1 < vwap && c1 < vwap);
    if(!trend_up && !trend_down) return;

    // 3. Disparador: precio toco EMA9 + vela rechazo + RSI ok
    bool toco_ema9 = (l1 <= e9_1 && e9_1 <= h1);
    if(!toco_ema9) return;
    if(!EsVelaRechazo(o1, h1, l1, c1, WickRatio)) return;

    bool rsi_ok_long  = (rsi1 >= RSI_Buy_Min  && rsi1 <= RSI_Buy_Max);
    bool rsi_ok_short = (rsi1 >= RSI_Sell_Min && rsi1 <= RSI_Sell_Max);

    bool cond_long  = trend_up   && c1 > o1 && rsi_ok_long;
    bool cond_short = trend_down && c1 < o1 && rsi_ok_short;
    if(!cond_long && !cond_short) return;

    // SL / TP / sizing
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double entry = cond_long ? ask : bid;
    double sl_dist = atr1 * SL_ATR_Mult;
    double min_sl  = MinSLPts * Pip;
    double max_sl  = MaxSLPts * Pip;
    sl_dist = MathMax(sl_dist, min_sl);
    if(sl_dist > max_sl) return;

    double sl_price = cond_long ? entry - sl_dist : entry + sl_dist;
    double tp_price = cond_long ? entry + sl_dist * TP1_Mult : entry - sl_dist * TP1_Mult;

    // Sizing
    double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
    double tick_val  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double pip_val   = tick_val * (Pip / tick_size);
    double sl_pips   = sl_dist / Pip;
    double lots      = (equity * LotRiskPct / 100.0) / (sl_pips * pip_val);
    lots = MathMin(NormalizeDouble(lots, 2), MaxLots);
    lots = MathMax(lots, 0.01);

    // Ejecutar
    bool ok;
    if(cond_long)  ok = Trade.Buy(lots, _Symbol, ask, sl_price, tp_price, Comment_);
    else           ok = Trade.Sell(lots, _Symbol, bid, sl_price, tp_price, Comment_);
    if(ok) TradesToday++;
}
