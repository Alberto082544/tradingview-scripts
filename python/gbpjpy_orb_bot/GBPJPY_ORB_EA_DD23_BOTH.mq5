//+------------------------------------------------------------------+
//| GBPJPY ORB EA — DD23 Ambas Direcciones                          |
//| Londres 08:00 GMT | Largos + Cortos | TP1=1.5x | TP2=2.0x       |
//| WR: 48.9% | PF: 1.08 | DD: 23.5% | P&L: +$66,882               |
//| Version: 1.0 | 2026-05-08                                       |
//+------------------------------------------------------------------+
#property copyright "GBPJPY ORB Bot DD23"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

input group "=== SESION LONDRES ==="
input int    LDN_Start_H   = 8;
input int    LDN_Start_M   = 0;
input int    LDN_End_H     = 16;
input int    GMT_Offset    = 0;

input group "=== RANGO ORB ==="
input int    MinRangePips  = 5;
input int    MaxRangePips  = 30;

input group "=== TP / SL ==="
input double TP1_Mult      = 1.5;
input double TP2_Mult      = 2.0;   // TP2 corto: 2x rango, mejora WR a 48.9%
input bool   UseDoubleEntry= true;

input group "=== RIESGO ==="
input double RiskPct       = 0.5;
input double MaxLots       = 4.0;

input group "=== FILTROS ==="
input int    MaxTradesDay  = 2;
input bool   LongOnly      = false; // BOTH: largos y cortos

input group "=== IDENTIFICACION ==="
input ulong  MagicNumber   = 202603;

CTrade   trade;
datetime lastBarTime = 0;
double   orbHigh = 0, orbLow = 0;
bool     orbDefined = false;
bool     orbTraded  = false;
int      tradesToday = 0;
datetime lastDay = 0;
double   pip;

int OnInit()
{
    pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100; // JPY
    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetDeviationInPoints(10);
    Print("GBPJPY ORB DD23 BOTH iniciado. TP1=", TP1_Mult, "x TP2=", TP2_Mult, "x");
    return INIT_SUCCEEDED;
}

bool IsSessionOpen()
{
    MqlDateTime dt; TimeToStruct(TimeGMT(), dt);
    int bm = (dt.hour - GMT_Offset + 24) % 24 * 60 + dt.min;
    int openMin = LDN_Start_H * 60 + LDN_Start_M;
    int endMin  = LDN_End_H * 60;
    if(dt.day_of_week == 6 || dt.day_of_week == 0) return false;
    return (bm >= openMin && bm < endMin);
}

bool IsOrbBar()
{
    MqlDateTime dt; TimeToStruct(TimeGMT(), dt);
    int bm = (dt.hour - GMT_Offset + 24) % 24 * 60 + dt.min;
    return (bm == LDN_Start_H * 60 + LDN_Start_M &&
            dt.day_of_week >= 1 && dt.day_of_week <= 5);
}

double CalcLots(double slDist)
{
    if(slDist <= 0) return 0;
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskUSD = balance * RiskPct / 100.0;
    double slPips  = slDist / pip;
    double pipVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE)
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

        double entry = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl    = PositionGetDouble(POSITION_SL);
        int    ptype = (int)PositionGetInteger(POSITION_TYPE);
        double tp1lvl;

        if(ptype == POSITION_TYPE_BUY)
        {
            tp1lvl = entry + (entry - sl) * TP1_Mult;
            if(SymbolInfoDouble(_Symbol, SYMBOL_BID) >= tp1lvl && sl < entry - pip)
                trade.PositionModify(ticket, entry, PositionGetDouble(POSITION_TP));
        }
        else
        {
            tp1lvl = entry - (sl - entry) * TP1_Mult;
            if(SymbolInfoDouble(_Symbol, SYMBOL_ASK) <= tp1lvl && sl > entry + pip)
                trade.PositionModify(ticket, entry, PositionGetDouble(POSITION_TP));
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

void OnTick()
{
    datetime currentBar = iTime(_Symbol, PERIOD_M15, 0);
    if(currentBar == lastBarTime) return;
    lastBarTime = currentBar;

    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    datetime today = (datetime)(dt.year*10000 + dt.mon*100 + dt.mday);
    if(today != lastDay)
    {
        tradesToday = 0; lastDay = today;
        orbDefined = false; orbTraded = false;
    }

    CheckBreakEven();
    CloseSessionPositions();
    if(!IsSessionOpen()) return;

    if(IsOrbBar() && !orbDefined)
    {
        double h = iHigh(_Symbol, PERIOD_M15, 1);
        double l = iLow(_Symbol,  PERIOD_M15, 1);
        double rng = h - l;
        if(rng >= MinRangePips * pip && rng <= MaxRangePips * pip)
        {
            orbHigh = h; orbLow = l;
            orbDefined = true; orbTraded = false;
            Print("ORB: High=", orbHigh, " Low=", orbLow, " Rng=", DoubleToString(rng/pip,1), "p");
        }
        return;
    }

    if(!orbDefined || orbTraded) return;
    if(tradesToday >= MaxTradesDay) return;
    if(PositionsTotal() > 0) return;

    double close1 = iClose(_Symbol, PERIOD_M15, 1);
    double rng    = orbHigh - orbLow;

    // LONG
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
        trade.Buy(lots, _Symbol, 0, sl, tp1, "ORB_L_TP1");
        trade.Buy(lots, _Symbol, 0, sl, tp2, "ORB_L_TP2");
        orbTraded = true; tradesToday++;
        Print("BUY: entry~", entry, " sl=", sl, " tp1=", tp1, " tp2=", tp2);
    }
    // SHORT
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
        trade.Sell(lots, _Symbol, 0, sl, tp1, "ORB_S_TP1");
        trade.Sell(lots, _Symbol, 0, sl, tp2, "ORB_S_TP2");
        orbTraded = true; tradesToday++;
        Print("SELL: entry~", entry, " sl=", sl, " tp1=", tp1, " tp2=", tp2);
    }
}

void OnDeinit(const int reason)
{
    Print("GBPJPY ORB DD23 BOTH detenido.");
}
