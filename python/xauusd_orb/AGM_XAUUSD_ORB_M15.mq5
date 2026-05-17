//+------------------------------------------------------------------+
//| AGM_XAUUSD_ORB_M15.mq5  v2.0 (fondeo adaptado)                  |
//| Sesion Nueva York 13:30 GMT | Solo Largos | TP1=0.5x | TP2=4.0x |
//|                                                                  |
//| Backtest $50k 2020-2025:                                        |
//|   PF=1.32 DD=7.5% WR=52.6% N=1364                              |
//|   WF=1.21 (OOS PF=1.40 vs IS PF=1.16) | MC P95 DD=9.6%          |
//|   6/6 años positivos | 100% MC sims positivas                   |
//|                                                                  |
//| v2.0 cambios para cuenta fondeo:                                |
//|   - RiskPct 0.5 -> 0.30 (DD esperado ~4.5%, balance profit/safe)|
//|   - Filtro noticias alto impacto (5%ers requirement)            |
//|   - Circuit breakers (DD diario 3% + SL streak)                 |
//| Version: 2.1 | 2026-05-17 (RiskPct ajustado a 0.30)             |
//+------------------------------------------------------------------+
#property copyright "AGM — XAUUSD ORB v2"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Inputs
input group "=== SESION NY ==="
input int    NY_Start_H    = 13;     // Hora apertura NY (GMT)
input int    NY_Start_M    = 30;     // Minuto apertura NY
input int    NY_End_H      = 20;     // Hora fin sesion NY
input int    GMT_Offset    = 0;      // Ajuste GMT del broker (0 si broker usa GMT)

input group "=== RANGO ORB (pips XAU = $0.10) ==="
input int    MinRangePips  = 40;     // Rango minimo (40 pips = $4)
input int    MaxRangePips  = 150;    // Rango maximo (150 pips = $15)

input group "=== TP / SL ==="
input double TP1_Mult      = 0.5;   // TP1 = rango x 0.5 (recoge rapido, sube WR)
input double TP2_Mult      = 4.0;   // TP2 = rango x 4.0 (objetivo tendencia)
input bool   UseDoubleEntry= true;  // Doble entrada: TP1 + TP2

input group "=== RIESGO ==="
input double RiskPct       = 0.30;  // v2.1: 0.30% (DD esperado ~4.5%, balance profit/seguridad)
input double MaxLots       = 4.0;   // Lotes maximos

input group "=== FILTROS ==="
input int    MaxTradesDay  = 1;     // Max senales por dia (XAU: 1 es suficiente)
input bool   LongOnly      = true;  // Solo largos (sesgo alcista NY demostrado)

input group "=== FILTRO NOTICIAS (5%ers requirement) ==="
input bool   UseNewsFilter = true;  // Activar filtro noticias alto impacto
input int    NewsWindowMin = 2;     // Bloquear N min antes y despues

input group "=== CIRCUIT BREAKERS (proteccion fondeo) ==="
input bool   UseCircuitBreakers = true;
input double DailyDDPause     = 3.0;   // % perdida diaria que pausa
input int    ConsecutiveSLs   = 3;     // SL consecutivos que bloquean el dia

input group "=== IDENTIFICACION ==="
input ulong  MagicNumber   = 202602;

//--- Variables globales
CTrade   trade;
datetime lastBarTime  = 0;
double   orbHigh      = 0, orbLow = 0;
bool     orbDefined   = false;
bool     orbTraded    = false;
int      tradesToday  = 0;
datetime lastDay      = 0;
double   pip;

// Circuit breakers
double   DayStartBalance = 0;
int      ConsecSLsToday  = 0;
bool     DayBlocked      = false;

//+------------------------------------------------------------------+
int OnInit()
{
    // XAU: 1 pip = $0.10 → point * 10
    if(StringFind(_Symbol, "XAU") >= 0)
        pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;
    else if(StringFind(_Symbol, "JPY") >= 0)
        pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100;
    else
        pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;

    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetDeviationInPoints(15);

    Print("XAUUSD ORB EA iniciado. Pip size=", pip,
          " MinRng=", MinRangePips, "p  MaxRng=", MaxRangePips, "p",
          " TP1=", TP1_Mult, "x  TP2=", TP2_Mult, "x");
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Filtro noticias alto impacto (USD por XAUUSD)                   |
//+------------------------------------------------------------------+
bool IsNewsWindow()
{
    if(!UseNewsFilter) return false;
    datetime now = TimeCurrent();
    datetime f = now - NewsWindowMin*60;
    datetime t = now + NewsWindowMin*60;
    // XAUUSD: filtrar noticias USD (es lo que mueve el oro)
    MqlCalendarValue values[];
    int n = CalendarValueHistory(values, f, t, NULL, "USD");
    for(int i = 0; i < n; i++)
    {
        MqlCalendarEvent ev;
        if(!CalendarEventById(values[i].event_id, ev)) continue;
        if(ev.importance == CALENDAR_IMPORTANCE_HIGH) return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Circuit breakers: TRUE si operativa permitida                    |
//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
    if(!UseCircuitBreakers) return true;
    if(DayBlocked) return false;
    double eq = AccountInfoDouble(ACCOUNT_EQUITY);
    if(DayStartBalance > 0)
    {
        double dd = 100.0 * (DayStartBalance - eq) / DayStartBalance;
        if(dd >= DailyDDPause)
        {
            DayBlocked = true;
            PrintFormat("CIRCUIT BREAKER: DD diario %.2f%% >= %.2f%%, pausando hasta proximo dia",
                        dd, DailyDDPause);
            return false;
        }
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

//+------------------------------------------------------------------+
bool IsSessionOpen()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int bm = (dt.hour - GMT_Offset + 24) % 24 * 60 + dt.min;
    int openMin = NY_Start_H * 60 + NY_Start_M;
    int endMin  = NY_End_H   * 60;
    if(dt.day_of_week == 6 || dt.day_of_week == 0) return false;
    if(dt.day_of_week == 5 && dt.hour >= 20) return false;
    return (bm >= openMin && bm < endMin);
}

bool IsOrbBar()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int bm = (dt.hour - GMT_Offset + 24) % 24 * 60 + dt.min;
    return (bm == NY_Start_H * 60 + NY_Start_M &&
            dt.day_of_week >= 1 && dt.day_of_week <= 5);
}

double CalcLots(double slDist)
{
    if(slDist <= 0) return 0;
    double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskUSD  = balance * RiskPct / 100.0;
    double slPips   = slDist / pip;
    double pipVal   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE)
                      * (pip / SymbolInfoDouble(_Symbol, SYMBOL_POINT));
    if(pipVal <= 0) return 0;
    double lots = riskUSD / (slPips * pipVal);
    lots = MathMin(NormalizeDouble(lots, 2), MaxLots);
    lots = MathMax(lots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
    return lots;
}

void CheckBreakEven()
{
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != (long)MagicNumber) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
        if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY) continue;

        double entry  = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl     = PositionGetDouble(POSITION_SL);
        double tp1Lvl = entry + (entry - sl) * TP1_Mult;

        // Mover SL a BE cuando precio supera TP1
        if(SymbolInfoDouble(_Symbol, SYMBOL_BID) >= tp1Lvl && sl < entry - pip)
        {
            trade.PositionModify(ticket, entry, PositionGetDouble(POSITION_TP));
            Print("BE activado ticket=", ticket, " en entry=", entry);
        }
    }
}

void CloseSessionPositions()
{
    if(!IsSessionOpen())
    {
        for(int i = PositionsTotal()-1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(!PositionSelectByTicket(ticket)) continue;
            if(PositionGetInteger(POSITION_MAGIC) != (long)MagicNumber) continue;
            if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
            trade.PositionClose(ticket);
        }
    }
}

//+------------------------------------------------------------------+
void OnTick()
{
    datetime currentBar = iTime(_Symbol, PERIOD_M15, 0);
    if(currentBar == lastBarTime) return;
    lastBarTime = currentBar;

    // Resetear estado diario + circuit breakers
    datetime today = iTime(_Symbol, PERIOD_D1, 0);
    if(today != lastDay)
    {
        tradesToday     = 0;
        lastDay         = today;
        orbDefined      = false;
        orbTraded       = false;
        DayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        ConsecSLsToday  = 0;
        DayBlocked      = false;
    }

    CheckBreakEven();
    CloseSessionPositions();

    if(!IsSessionOpen()) return;

    // ── Definir rango ORB en la primera barra M15 de la sesion NY ──
    if(IsOrbBar() && !orbDefined)
    {
        double h   = iHigh(_Symbol, PERIOD_M15, 1);
        double l   = iLow(_Symbol,  PERIOD_M15, 1);
        double rng = h - l;

        if(rng >= MinRangePips * pip && rng <= MaxRangePips * pip)
        {
            orbHigh    = h;
            orbLow     = l;
            orbDefined = true;
            orbTraded  = false;
            Print("ORB NY definido: High=", orbHigh, " Low=", orbLow,
                  " Rango=", DoubleToString(rng/pip, 1), " pips");
        }
        else
        {
            Print("ORB NY ignorado: rango=", DoubleToString(rng/pip,1),
                  "p fuera de [", MinRangePips, ",", MaxRangePips, "]");
        }
        return;
    }

    if(!orbDefined || orbTraded) return;
    if(tradesToday >= MaxTradesDay) return;
    if(PositionsTotal() > 0) return;

    // Filtros seguridad (5%ers + fondeo)
    if(IsNewsWindow()) return;
    if(!IsTradingAllowed()) return;
    if(UseCircuitBreakers && ConsecSLsToday >= ConsecutiveSLs) return;

    double close1 = iClose(_Symbol, PERIOD_M15, 1);
    double rng    = orbHigh - orbLow;

    // ── Senal LONG: cierre anterior supera ORB High ──────────────
    if(close1 > orbHigh)
    {
        double entry = iOpen(_Symbol, PERIOD_M15, 0);
        double sl    = NormalizeDouble(orbLow, _Digits);
        double slDist = entry - sl;
        if(slDist <= 0) return;

        double tp1 = NormalizeDouble(entry + rng * TP1_Mult, _Digits);
        double tp2 = NormalizeDouble(entry + rng * TP2_Mult, _Digits);
        double lots = CalcLots(slDist);
        if(lots <= 0) return;

        if(UseDoubleEntry)
        {
            if(trade.Buy(lots, _Symbol, 0, sl, tp1, "ORB_XAU_TP1"))
                Print("BUY TP1: entry~", entry, " sl=", sl, " tp=", tp1,
                      " lots=", lots);
            if(trade.Buy(lots, _Symbol, 0, sl, tp2, "ORB_XAU_TP2"))
                Print("BUY TP2: entry~", entry, " sl=", sl, " tp=", tp2,
                      " lots=", lots);
        }
        else
        {
            if(trade.Buy(lots*2, _Symbol, 0, sl, tp2, "ORB_XAU_LONG"))
                Print("BUY: entry~", entry, " sl=", sl, " tp=", tp2);
        }
        orbTraded = true;
        tradesToday++;
    }
    // ── Senal SHORT (LongOnly=true por defecto) ───────────────────
    else if(!LongOnly && close1 < orbLow)
    {
        double entry  = iOpen(_Symbol, PERIOD_M15, 0);
        double sl     = NormalizeDouble(orbHigh, _Digits);
        double slDist = sl - entry;
        if(slDist <= 0) return;

        double tp1 = NormalizeDouble(entry - rng * TP1_Mult, _Digits);
        double tp2 = NormalizeDouble(entry - rng * TP2_Mult, _Digits);
        double lots = CalcLots(slDist);
        if(lots <= 0) return;

        if(UseDoubleEntry)
        {
            if(trade.Sell(lots, _Symbol, 0, sl, tp1, "ORB_XAU_S_TP1"))
                Print("SELL TP1: entry~", entry, " sl=", sl, " tp=", tp1);
            if(trade.Sell(lots, _Symbol, 0, sl, tp2, "ORB_XAU_S_TP2"))
                Print("SELL TP2: entry~", entry, " sl=", sl, " tp=", tp2);
        }
        else
        {
            if(trade.Sell(lots*2, _Symbol, 0, sl, tp2, "ORB_XAU_SHORT"))
                Print("SELL: entry~", entry, " sl=", sl, " tp=", tp2);
        }
        orbTraded = true;
        tradesToday++;
    }
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("XAUUSD ORB EA detenido. Razon: ", reason);
}
//+------------------------------------------------------------------+
