//+------------------------------------------------------------------+
//| GBPJPY ORB EA — Ruptura de Rango de Apertura                    |
//| Sesion Londres 08:00 GMT | Solo Largos | TP1=1.5x | TP2=5.0x    |
//| Version: 1.0 | 2026-05-08                                       |
//+------------------------------------------------------------------+
#property copyright "GBPJPY ORB Bot"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Inputs
input group "=== SESION ==="
input int    LDN_Start_H   = 8;      // Hora apertura Londres (GMT)
input int    LDN_Start_M   = 0;      // Minuto apertura Londres
input int    LDN_End_H     = 16;     // Hora fin sesion Londres
input int    GMT_Offset    = 0;      // Ajuste GMT del broker (0 si broker usa GMT)

input group "=== RANGO ORB ==="
input int    MinRangePips  = 5;      // Rango minimo (pips JPY)
input int    MaxRangePips  = 30;     // Rango maximo (pips JPY)

input group "=== TP / SL ==="
input double TP1_Mult      = 1.5;   // TP1 = rango x TP1_Mult
input double TP2_Mult      = 5.0;   // TP2 = rango x TP2_Mult
input bool   UseDoubleEntry= true;  // Doble entrada: TP1 + TP2

input group "=== RIESGO ==="
input double RiskPct       = 0.5;   // Riesgo por posicion (% balance)
input double MaxLots       = 4.0;   // Lotes maximos

input group "=== FILTROS ==="
input int    MaxTradesDay  = 2;     // Max senales por dia
input bool   LongOnly      = true;  // Solo largos (recomendado para GBPJPY Londres)

input group "=== IDENTIFICACION ==="
input ulong  MagicNumber   = 202601;

//--- Variables globales
CTrade   trade;
datetime lastBarTime  = 0;
datetime orbDate      = 0;
double   orbHigh      = 0, orbLow = 0;
bool     orbDefined   = false;
bool     orbTraded    = false;
int      tradesToday  = 0;
datetime lastDay      = 0;
double   pip;

//+------------------------------------------------------------------+
int OnInit()
{
    pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;
    if(StringFind(_Symbol, "JPY") >= 0)
        pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100;
    if(StringFind(_Symbol, "XAU") >= 0)
        pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;

    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetDeviationInPoints(10);

    Print("GBPJPY ORB EA iniciado. Pip=", pip);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
bool IsSessionOpen()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int bm = (dt.hour - GMT_Offset + 24) % 24 * 60 + dt.min;
    int openMin = LDN_Start_H * 60 + LDN_Start_M;
    int endMin  = LDN_End_H   * 60;
    if(dt.day_of_week == 6 || dt.day_of_week == 0) return false;
    if(dt.day_of_week == 5 && dt.hour >= 20) return false;
    return (bm >= openMin && bm < endMin);
}

bool IsOrbBar()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    int bm = (dt.hour - GMT_Offset + 24) % 24 * 60 + dt.min;
    return (bm == LDN_Start_H * 60 + LDN_Start_M &&
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

        if(SymbolInfoDouble(_Symbol, SYMBOL_BID) >= tp1Lvl && sl < entry - pip)
        {
            trade.PositionModify(ticket, entry, PositionGetDouble(POSITION_TP));
            Print("BE activado en ", entry, " ticket ", ticket);
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

    // Resetear contador diario
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    datetime today = (datetime)(dt.year*10000 + dt.mon*100 + dt.mday);
    if(today != lastDay)
    {
        tradesToday = 0;
        lastDay     = today;
        orbDefined  = false;
        orbTraded   = false;
    }

    CheckBreakEven();

    // Cierre de sesion
    CloseSessionPositions();

    if(!IsSessionOpen()) return;

    // ── Definir rango ORB en la primera barra ─────────────────────
    if(IsOrbBar() && !orbDefined)
    {
        double h = iHigh(_Symbol, PERIOD_M15, 1);
        double l = iLow(_Symbol,  PERIOD_M15, 1);
        double rng = h - l;

        if(rng >= MinRangePips * pip && rng <= MaxRangePips * pip)
        {
            orbHigh    = h;
            orbLow     = l;
            orbDefined = true;
            orbTraded  = false;
            Print("ORB definido: High=", orbHigh, " Low=", orbLow,
                  " Rango=", DoubleToString(rng/pip, 1), " pips");
        }
        return;
    }

    if(!orbDefined || orbTraded) return;
    if(tradesToday >= MaxTradesDay) return;
    if(PositionsTotal() > 0) return;

    double close1 = iClose(_Symbol, PERIOD_M15, 1);
    double rng    = orbHigh - orbLow;

    // ── Senal LONG ────────────────────────────────────────────────
    if(!LongOnly) {} // placeholder para shorts
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
            if(trade.Buy(lots, _Symbol, 0, sl, tp1, "ORB_L_TP1"))
                Print("BUY TP1: entry=", entry, " sl=", sl, " tp=", tp1);
            if(trade.Buy(lots, _Symbol, 0, sl, tp2, "ORB_L_TP2"))
                Print("BUY TP2: entry=", entry, " sl=", sl, " tp=", tp2);
        }
        else
        {
            if(trade.Buy(lots*2, _Symbol, 0, sl, tp2, "ORB_LONG"))
                Print("BUY: entry=", entry, " sl=", sl, " tp=", tp2);
        }
        orbTraded = true;
        tradesToday++;
    }
    // ── Senal SHORT (desactivada por defecto: LongOnly=true) ──────
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
            if(trade.Sell(lots, _Symbol, 0, sl, tp1, "ORB_S_TP1"))
                Print("SELL TP1: entry=", entry, " sl=", sl, " tp=", tp1);
            if(trade.Sell(lots, _Symbol, 0, sl, tp2, "ORB_S_TP2"))
                Print("SELL TP2: entry=", entry, " sl=", sl, " tp=", tp2);
        }
        else
        {
            if(trade.Sell(lots*2, _Symbol, 0, sl, tp2, "ORB_SHORT"))
                Print("SELL: entry=", entry, " sl=", sl, " tp=", tp2);
        }
        orbTraded = true;
        tradesToday++;
    }
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("GBPJPY ORB EA detenido. Razon: ", reason);
}
//+------------------------------------------------------------------+
