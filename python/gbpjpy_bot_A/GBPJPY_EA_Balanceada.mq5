//+------------------------------------------------------------------+
//| GBPJPY EA — Estrategia Balanceada                               |
//| Pullback en tendencia con filtro EMA200 H4                      |
//| TP=3xSL | BE=0.8xSL | Sesion 07-19 UTC | SL max 30 pips        |
//| Version: 1.0 | 2026-05-08                                       |
//+------------------------------------------------------------------+
#property copyright "GBPJPY Bot — Estrategia Balanceada"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//--- Inputs del EA
input group "=== RIESGO Y CAPITAL ==="
input double LotRiskPct    = 0.5;    // Riesgo por trade (% del capital)
input double MaxLots       = 4.0;    // Lotes máximos por operación

input group "=== PARÁMETROS ESTRATEGIA ==="
input double TPMultiplier  = 3.0;    // TP = N × SL
input double BEMultiplier  = 0.8;    // Break-Even cuando ganancia >= N × SL
input int    MaxSLPips     = 30;     // SL máximo en pips (solo trades con SL <= esto)
input int    MinSLPips     = 15;     // SL mínimo en pips
input int    ExitBars      = 30;     // Salida por tiempo (barras M15)
input int    OrderExpiryBars = 24;   // Barras hasta expirar orden pendiente

input group "=== SESIÓN ==="
input int    SessionStart  = 7;      // Hora UTC de inicio
input int    SessionEnd    = 19;     // Hora UTC de fin
input int    BadHour       = 8;      // Hora UTC excluida
input int    MaxTradesDay  = 5;      // Máx operaciones por día

input group "=== INDICADORES ==="
input int    EMA_Fast      = 20;     // EMA rápida M15
input int    EMA_Slow      = 100;    // EMA lenta M15
input int    EMA_H4        = 200;    // EMA tendencia H4
input int    ATR_Period    = 14;     // Periodo ATR
input int    RSI_Period    = 14;     // Periodo RSI
input int    Range_Bars    = 20;     // Barras para calcular rango de pullback
input int    Swing_Bars    = 10;     // Barras para swing high/low del SL
input double PullbackRatio = 0.382;  // Nivel Fibonacci del retroceso

input group "=== MAGIC NUMBER ==="
input ulong  MagicNumber   = 202600; // Identificador único del EA

//--- Variables globales
CTrade trade;
datetime lastBarTime  = 0;
int      tradesToday  = 0;
datetime lastTradeDay = 0;
double   pip;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
    pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;
    if(StringFind(_Symbol, "JPY") >= 0)
        pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100;

    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetDeviationInPoints(10);

    Print("GBPJPY EA Balanceada iniciado. Pip=", pip);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Funciones auxiliares                                             |
//+------------------------------------------------------------------+
double CalcEMA(const double &prices[], int period, int shift=0)
{
    int size = ArraySize(prices);
    if(size < period + shift) return 0;

    double alpha = 2.0 / (period + 1);
    double ema   = prices[size - 1 - shift - (period - 1)];

    for(int i = size - shift - period; i < size - shift; i++)
        ema = alpha * prices[i] + (1 - alpha) * ema;
    return ema;
}

double CalcATR(int period, int shift=0)
{
    double atr = 0;
    for(int i = shift; i < shift + period; i++)
        atr += MathMax(iHigh(_Symbol, PERIOD_M15, i) - iLow(_Symbol, PERIOD_M15, i),
               MathMax(MathAbs(iHigh(_Symbol, PERIOD_M15, i) - iClose(_Symbol, PERIOD_M15, i+1)),
                       MathAbs(iLow(_Symbol,  PERIOD_M15, i) - iClose(_Symbol, PERIOD_M15, i+1))));
    return atr / period;
}

double CalcRSI(int period, int shift=0)
{
    double avgGain = 0, avgLoss = 0;
    for(int i = shift + period; i > shift; i--)
    {
        double delta = iClose(_Symbol, PERIOD_M15, i-1) - iClose(_Symbol, PERIOD_M15, i);
        if(delta > 0) avgGain += delta;
        else          avgLoss += MathAbs(delta);
    }
    avgGain /= period; avgLoss /= period;
    if(avgLoss == 0) return 100;
    double rs = avgGain / avgLoss;
    return 100 - (100 / (1 + rs));
}

double GetEMA200_H4(int shift=0)
{
    double closes[];
    int copied = CopyClose(_Symbol, PERIOD_H4, shift, 250, closes);
    if(copied < 200) return 0;
    ArraySetAsSeries(closes, false);
    return CalcEMA(closes, 200);
}

double GetRangeHigh(int bars, int shift=1)
{
    double high = iHigh(_Symbol, PERIOD_M15, shift);
    for(int i = shift + 1; i < shift + bars; i++)
        high = MathMax(high, iHigh(_Symbol, PERIOD_M15, i));
    return high;
}

double GetRangeLow(int bars, int shift=1)
{
    double low = iLow(_Symbol, PERIOD_M15, shift);
    for(int i = shift + 1; i < shift + bars; i++)
        low = MathMin(low, iLow(_Symbol, PERIOD_M15, i));
    return low;
}

double GetSwingLow(int bars, int shift=1)
{
    double low = iLow(_Symbol, PERIOD_M15, shift);
    for(int i = shift + 1; i < shift + bars; i++)
        low = MathMin(low, iLow(_Symbol, PERIOD_M15, i));
    return low;
}

double GetSwingHigh(int bars, int shift=1)
{
    double high = iHigh(_Symbol, PERIOD_M15, shift);
    for(int i = shift + 1; i < shift + bars; i++)
        high = MathMax(high, iHigh(_Symbol, PERIOD_M15, i));
    return high;
}

double CalcEMASlope(int emaPeriod, int slopeBars=5, int shift=1)
{
    double closes[];
    int needed = emaPeriod + slopeBars + shift + 10;
    int copied = CopyClose(_Symbol, PERIOD_M15, 0, needed, closes);
    if(copied < needed) return 0;
    ArraySetAsSeries(closes, false);

    double ema_now  = CalcEMA(closes, emaPeriod, shift);
    double ema_prev = CalcEMA(closes, emaPeriod, shift + slopeBars);
    return ema_now - ema_prev;
}

double CalcLots(double slDistance)
{
    if(slDistance <= 0) return 0;
    double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
    double riskUSD  = balance * LotRiskPct / 100.0;
    double slPips   = slDistance / pip;
    double pipValUSD = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE)
                       * (pip / SymbolInfoDouble(_Symbol, SYMBOL_POINT));
    if(pipValUSD <= 0) return 0;
    double lots = riskUSD / (slPips * pipValUSD);
    lots = MathMin(NormalizeDouble(lots, 2), MaxLots);
    lots = MathMax(lots, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
    return lots;
}

bool IsSessionActive()
{
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    if(dt.hour < SessionStart || dt.hour >= SessionEnd) return false;
    if(dt.hour == BadHour) return false;
    if(dt.day_of_week == 6 || dt.day_of_week == 0) return false;
    if(dt.day_of_week == 5 && dt.hour >= 20) return false;
    return true;
}

void CheckBreakEven()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != (long)MagicNumber) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

        double entry    = PositionGetDouble(POSITION_PRICE_OPEN);
        double sl       = PositionGetDouble(POSITION_SL);
        double slDist   = MathAbs(entry - sl);
        double beTarget = entry + slDist * BEMultiplier *
                          (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1);
        double currentPrice = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                              ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

        bool beTriggered = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                           ? (currentPrice >= beTarget && sl < entry)
                           : (currentPrice <= beTarget && sl > entry);

        if(beTriggered)
        {
            trade.PositionModify(ticket, entry, PositionGetDouble(POSITION_TP));
            Print("Break-Even activado en ", entry, " para ticket ", ticket);
        }
    }
}

void CheckTimeExit()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(!PositionSelectByTicket(ticket)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != (long)MagicNumber) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

        datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
        int barsHeld = Bars(_Symbol, PERIOD_M15, openTime, TimeCurrent());

        if(barsHeld >= ExitBars)
        {
            trade.PositionClose(ticket);
            Print("Salida por tiempo: ", barsHeld, " barras. Ticket ", ticket);
        }
    }
}

//+------------------------------------------------------------------+
//| Main logic — se ejecuta en cada nueva barra M15                  |
//+------------------------------------------------------------------+
void OnTick()
{
    // Solo ejecutar en nueva barra
    datetime currentBar = iTime(_Symbol, PERIOD_M15, 0);
    if(currentBar == lastBarTime) return;
    lastBarTime = currentBar;

    // Resetear contador diario
    MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
    datetime today = (datetime)(dt.year * 10000 + dt.mon * 100 + dt.mday);
    if(today != lastTradeDay) { tradesToday = 0; lastTradeDay = today; }

    // Gestión de posiciones abiertas
    CheckBreakEven();
    CheckTimeExit();

    // No abrir nuevas si hay posición o límite diario alcanzado
    if(PositionsTotal() > 0) return;
    if(!IsSessionActive()) return;
    if(tradesToday >= MaxTradesDay) return;

    // ── Calcular indicadores (usando barra anterior, shift=1) ─────
    double close1   = iClose(_Symbol, PERIOD_M15, 1);
    double close2   = iClose(_Symbol, PERIOD_M15, 2);

    // EMAs M15
    double closes_m15[];
    int needed = EMA_Slow + 15;
    if(CopyClose(_Symbol, PERIOD_M15, 0, needed, closes_m15) < needed) return;
    ArraySetAsSeries(closes_m15, false);
    double emaFast1 = CalcEMA(closes_m15, EMA_Fast, 1);
    double emaSlow1 = CalcEMA(closes_m15, EMA_Slow, 1);

    // EMA slope
    double emaFast6 = CalcEMA(closes_m15, EMA_Fast, 6);
    double emaSlope = emaFast1 - emaFast6;

    // EMA200 H4
    double ema200h4 = GetEMA200_H4(0);
    if(ema200h4 == 0) return;

    // RSI14
    double rsi1 = CalcRSI(RSI_Period, 1);
    double rsi2 = CalcRSI(RSI_Period, 2);

    // ATR14
    double atr1 = CalcATR(ATR_Period, 1);

    // Rango 20 barras
    double rangeHigh = GetRangeHigh(Range_Bars, 1);
    double rangeLow  = GetRangeLow(Range_Bars, 1);
    double rangeSize = rangeHigh - rangeLow;

    double pullbackLong  = rangeLow  + rangeSize * PullbackRatio;
    double pullbackShort = rangeHigh - rangeSize * PullbackRatio;

    // Swing high/low para SL
    double swingLow  = GetSwingLow(Swing_Bars, 1);
    double swingHigh = GetSwingHigh(Swing_Bars, 1);

    // ── Condición LONG ────────────────────────────────────────────
    bool condLong = (close1 > ema200h4) &&
                    (emaFast1 > emaSlow1) &&
                    (emaSlope > 0) &&
                    (rsi1 >= 35 && rsi1 <= 60) &&
                    (rsi1 > rsi2) &&
                    (close1 <= pullbackLong * 1.002);

    // ── Condición SHORT ───────────────────────────────────────────
    bool condShort = !condLong &&
                     (close1 < ema200h4) &&
                     (emaFast1 < emaSlow1) &&
                     (emaSlope < 0) &&
                     (rsi1 >= 40 && rsi1 <= 65) &&
                     (rsi1 < rsi2) &&
                     (close1 >= pullbackShort * 0.998);

    if(!condLong && !condShort) return;

    // ── Calcular SL/TP ────────────────────────────────────────────
    double entryPrice = iOpen(_Symbol, PERIOD_M15, 0);
    double slDist, tpDist;

    if(condLong)
        slDist = MathMax(close1 - swingLow, atr1 * 1.5);
    else
        slDist = MathMax(swingHigh - close1, atr1 * 1.5);

    // Filtro: solo trades con SL <= MaxSLPips
    double slPips = slDist / pip;
    if(slPips > MaxSLPips) return;
    if(slPips < MinSLPips) slDist = MinSLPips * pip;

    tpDist = slDist * TPMultiplier;

    double lots = CalcLots(slDist);
    if(lots <= 0) return;

    double sl, tp;
    if(condLong) {
        sl = NormalizeDouble(entryPrice - slDist, _Digits);
        tp = NormalizeDouble(entryPrice + tpDist, _Digits);
        if(trade.Buy(lots, _Symbol, 0, sl, tp, "GBPJPY_EA_Balanceada_L"))
        { tradesToday++; Print("BUY abierto. SL=", sl, " TP=", tp, " Lots=", lots); }
    } else {
        sl = NormalizeDouble(entryPrice + slDist, _Digits);
        tp = NormalizeDouble(entryPrice - tpDist, _Digits);
        if(trade.Sell(lots, _Symbol, 0, sl, tp, "GBPJPY_EA_Balanceada_S"))
        { tradesToday++; Print("SELL abierto. SL=", sl, " TP=", tp, " Lots=", lots); }
    }
}

//+------------------------------------------------------------------+
//| Deinitialization                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("GBPJPY EA Balanceada detenido. Razon: ", reason);
}
//+------------------------------------------------------------------+
