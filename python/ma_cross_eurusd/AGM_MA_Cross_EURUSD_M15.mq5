//+------------------------------------------------------------------+
//| AGM_MA_Cross_EURUSD_M15.mq5  v2.0 (DD<5%)                       |
//| MA Cross | EURUSD M15 | Tendencia H4+M15                        |
//| Parametros: EMA8/SMA34, SL=2xATR, RR=2.5, Trail=0.5, BE=0.5     |
//|                                                                  |
//| Backtest $50k 2014-2025:                                        |
//|   IS  PF=1.25 DD=??                                              |
//|   OOS PF=1.41 Ann=24.4% DD=4.8% N=1622                          |
//|   WF=1.128 | Apto FundedNext + The 5%ers                       |
//| Version: 2.3 | 2026-05-17 | + Circuit breakers (DD+SL streak)   |
//+------------------------------------------------------------------+
#property copyright "AGM — MA Cross EURUSD v2.1"
#property version   "2.30"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

CTrade        Trade;
CPositionInfo Pos;
CSymbolInfo   Sym;

//--- Inputs
input group "=== IDENTIFICACION ==="
input ulong  MagicNumber     = 202610;
input string Comment_        = "AGM_EURUSD_MC";

input group "=== MEDIAS (entrada M15) ==="
input int    EMA_Fast        = 8;          // EMA rapida (v2: optimizado DD<5%)
input int    SMA_Slow        = 34;         // SMA lenta (v2: optimizado DD<5%)
input ENUM_APPLIED_PRICE EntryPrice = PRICE_CLOSE;

input group "=== FILTRO DIRECCION H4 ==="
input bool             UseDirFilter = true;
input ENUM_TIMEFRAMES  DirTF        = PERIOD_H4;
input int              Dir_EMA      = 8;   // Igual que EMA_Fast
input int              Dir_SMA      = 34;  // Igual que SMA_Slow

input group "=== GESTION SL/TP ==="
input int    ATR_Period      = 14;
input double SL_ATR_Mult     = 2.0;        // SL = 2 * ATR
input double RR              = 2.5;        // TP = 2.5 * SL (v2: optimizado DD<5%)

input group "=== BREAK-EVEN ==="
input bool   UseBE           = true;
input double BE_Trigger_ATR  = 0.5;       // Activar BE a 0.5*ATR de ganancia
input int    BE_Offset_Pts   = 10;        // Offset BE en puntos

input group "=== TRAILING STOP (ATR) ==="
input bool   UseTrailing     = true;
input double Trail_Start_ATR = 1.5;       // Iniciar trailing a 1.5*ATR
input double Trail_Dist_ATR  = 0.5;       // Distancia trailing = 0.5*ATR

input group "=== RIESGO ==="
input double LotRiskPct      = 0.4;        // (v2: 0.4 = DD~3.8% margen fondeo 5%)
input double MaxLots         = 4.0;

input group "=== EJECUCION ==="
input int    MaxSpreadPts    = 30;
input int    SlippagePts     = 20;

input group "=== FILTRO NOTICIAS (5%ers High Stakes) ==="
input bool   UseNewsFilter   = true;   // Activar filtro noticias alto impacto
input int    NewsWindowMin   = 2;      // Bloquear N min antes y despues

input group "=== FILTRO HORARIO ==="
input int    BadHour         = 15;     // Hora UTC bloqueada (v2.2: hora 15 = sangra USA open)

input group "=== CIRCUIT BREAKERS (proteccion fondeo) ==="
input bool   UseCircuitBreakers = true; // Activar bloqueos de seguridad
input double DailyDDPause     = 3.0;   // % perdida diaria que pausa hasta el siguiente dia
input int    ConsecutiveSLs   = 3;     // Numero de SL consecutivos para bloquear el dia

//--- Handles
int h_ema, h_sma, h_dir_ema, h_dir_sma, h_atr;
datetime LastBar = 0;

// Circuit breakers (estado por dia)
datetime LastTradeDay    = 0;
double   DayStartBalance = 0;
int      ConsecSLsToday  = 0;
bool     DayBlocked      = false;

//+------------------------------------------------------------------+
int OnInit()
{
    if(!Sym.Name(_Symbol)) return INIT_FAILED;
    Trade.SetExpertMagicNumber(MagicNumber);
    Trade.SetDeviationInPoints(SlippagePts);
    Trade.SetTypeFillingBySymbol(_Symbol);
    Trade.LogLevel(LOG_LEVEL_ERRORS);

    h_ema     = iMA(_Symbol, PERIOD_M15, EMA_Fast, 0, MODE_EMA, EntryPrice);
    h_sma     = iMA(_Symbol, PERIOD_M15, SMA_Slow, 0, MODE_SMA, EntryPrice);
    h_dir_ema = iMA(_Symbol, DirTF,      Dir_EMA,  0, MODE_EMA, PRICE_CLOSE);
    h_dir_sma = iMA(_Symbol, DirTF,      Dir_SMA,  0, MODE_SMA, PRICE_CLOSE);
    h_atr     = iATR(_Symbol, PERIOD_M15, ATR_Period);

    if(h_ema == INVALID_HANDLE || h_sma == INVALID_HANDLE ||
       h_dir_ema == INVALID_HANDLE || h_dir_sma == INVALID_HANDLE ||
       h_atr == INVALID_HANDLE)
    { Print("Error handles"); return INIT_FAILED; }

    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
    IndicatorRelease(h_ema); IndicatorRelease(h_sma);
    IndicatorRelease(h_dir_ema); IndicatorRelease(h_dir_sma);
    IndicatorRelease(h_atr);
}

//+------------------------------------------------------------------+
//| Circuit breakers: TRUE si esta operativa permitida                |
//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
    if(!UseCircuitBreakers) return true;
    if(DayBlocked) return false;
    double eq = AccountInfoDouble(ACCOUNT_EQUITY);
    if(DayStartBalance > 0)
    {
        double daily_dd_pct = 100.0 * (DayStartBalance - eq) / DayStartBalance;
        if(daily_dd_pct >= DailyDDPause)
        {
            DayBlocked = true;
            PrintFormat("CIRCUIT BREAKER: DD diario %.2f%% >= %.2f%%, pausando hasta proximo dia",
                        daily_dd_pct, DailyDDPause);
            return false;
        }
    }
    return true;
}

//+------------------------------------------------------------------+
//| Trade transaction handler: cuenta SL consecutivos                |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    if(!UseCircuitBreakers) return;
    if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
    HistoryDealSelect(trans.deal);
    if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != (long)MagicNumber) return;
    if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
    double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
    if(profit < 0)
    {
        ConsecSLsToday++;
        PrintFormat("Circuit breaker: SL consecutivo %d/%d", ConsecSLsToday, ConsecutiveSLs);
    }
    else if(profit > 0)
    {
        ConsecSLsToday = 0;
    }
}

//+------------------------------------------------------------------+
//| Filtro noticias: TRUE si hay noticia alto impacto en ventana    |
//| que afecte a las monedas del symbol (EUR, USD, etc.)            |
//+------------------------------------------------------------------+
bool IsNewsWindow()
{
    if(!UseNewsFilter) return false;
    datetime now    = TimeCurrent();
    datetime from_t = now - NewsWindowMin * 60;
    datetime to_t   = now + NewsWindowMin * 60;

    string sym = _Symbol;
    if(StringLen(sym) < 6) return false;
    string ccys[2];
    ccys[0] = StringSubstr(sym, 0, 3);
    ccys[1] = StringSubstr(sym, 3, 3);

    for(int c = 0; c < 2; c++)
    {
        MqlCalendarValue values[];
        int n = CalendarValueHistory(values, from_t, to_t, NULL, ccys[c]);
        for(int i = 0; i < n; i++)
        {
            MqlCalendarEvent ev;
            if(!CalendarEventById(values[i].event_id, ev)) continue;
            if(ev.importance == CALENDAR_IMPORTANCE_HIGH) return true;
        }
    }
    return false;
}

//+------------------------------------------------------------------+
bool HasPosition(ulong &ticket)
{
    for(int i = 0; i < PositionsTotal(); i++)
        if(Pos.SelectByIndex(i) && Pos.Symbol() == _Symbol && Pos.Magic() == MagicNumber)
        { ticket = Pos.Ticket(); return true; }
    return false;
}

void ManagePosition()
{
    if(!UseBE && !UseTrailing) return;
    double atr[1];
    if(CopyBuffer(h_atr, 0, 0, 1, atr) <= 0) return;
    double atrNow = atr[0];
    long stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
    double minDist = stops * _Point;

    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        if(!Pos.SelectByIndex(i)) continue;
        if(Pos.Symbol() != _Symbol || Pos.Magic() != MagicNumber) continue;

        ulong  ticket = Pos.Ticket();
        double entry  = Pos.PriceOpen();
        double curSL  = Pos.StopLoss();
        double curTP  = Pos.TakeProfit();
        bool   isBuy  = (Pos.PositionType() == POSITION_TYPE_BUY);
        double price  = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        double profit = isBuy ? (price - entry) : (entry - price);
        double newSL  = curSL;

        if(UseBE && profit >= BE_Trigger_ATR * atrNow)
        {
            double beSL = isBuy ? entry + BE_Offset_Pts * _Point
                                : entry - BE_Offset_Pts * _Point;
            if(isBuy  && beSL > newSL) newSL = beSL;
            if(!isBuy && (newSL == 0 || beSL < newSL)) newSL = beSL;
        }
        if(UseTrailing && profit >= Trail_Start_ATR * atrNow)
        {
            double trSL = isBuy ? price - Trail_Dist_ATR * atrNow
                                : price + Trail_Dist_ATR * atrNow;
            if(isBuy  && trSL > newSL) newSL = trSL;
            if(!isBuy && (newSL == 0 || trSL < newSL)) newSL = trSL;
        }
        if(newSL != curSL && newSL > 0)
        {
            newSL = NormalizeDouble(newSL, _Digits);
            bool ok = isBuy ? (price - newSL >= minDist) : (newSL - price >= minDist);
            if(ok) Trade.PositionModify(ticket, newSL, curTP);
        }
    }
}

//+------------------------------------------------------------------+
void OnTick()
{
    ManagePosition();

    datetime curBar = iTime(_Symbol, PERIOD_M15, 0);
    if(curBar == LastBar) return;
    LastBar = curBar;

    // Reset diario circuit breakers
    datetime dt = TimeCurrent();
    datetime hoy = (datetime)((long)dt - (long)dt % 86400);
    if(hoy != LastTradeDay)
    {
        LastTradeDay     = hoy;
        DayStartBalance  = AccountInfoDouble(ACCOUNT_BALANCE);
        ConsecSLsToday   = 0;
        DayBlocked       = false;
    }

    ulong ticket;
    if(HasPosition(ticket)) return;

    // Circuit breakers
    if(!IsTradingAllowed()) return;
    if(UseCircuitBreakers && ConsecSLsToday >= ConsecutiveSLs) return;

    // Spread filter
    if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpreadPts) return;

    // Cruce EMA/SMA en barra cerrada
    double ema[2], sma[2];
    if(CopyBuffer(h_ema, 0, 1, 2, ema) < 2) return;
    if(CopyBuffer(h_sma, 0, 1, 2, sma) < 2) return;
    bool cross_up   = (ema[0] <= sma[0] && ema[1] > sma[1]);
    bool cross_down = (ema[0] >= sma[0] && ema[1] < sma[1]);
    if(!cross_up && !cross_down) return;

    // Filtro direccion H4
    if(UseDirFilter)
    {
        double dema[1], dsma[1];
        if(CopyBuffer(h_dir_ema, 0, 0, 1, dema) <= 0) return;
        if(CopyBuffer(h_dir_sma, 0, 0, 1, dsma) <= 0) return;
        if(cross_up   && dema[0] <= dsma[0]) return;
        if(cross_down && dema[0] >= dsma[0]) return;
    }

    // Fin de semana
    MqlDateTime tm; TimeToStruct(TimeCurrent(), tm);
    if(tm.day_of_week == 6 || tm.day_of_week == 0) return;

    // Filtro hora mala (v2.2)
    if(BadHour >= 0 && tm.hour == BadHour) return;

    // Filtro noticias alto impacto (5%ers requirement)
    if(IsNewsWindow()) return;
    if(tm.day_of_week == 5 && tm.hour >= 22) return;

    double atr[1];
    if(CopyBuffer(h_atr, 0, 1, 1, atr) <= 0) return;
    double slDist = atr[0] * SL_ATR_Mult;
    double tpDist = slDist * RR;

    Sym.RefreshRates();
    double ask = Sym.Ask(), bid = Sym.Bid();
    bool   isBuy = cross_up;
    double price  = isBuy ? ask : bid;
    double sl     = isBuy ? price - slDist : price + slDist;
    double tp     = isBuy ? price + tpDist : price - tpDist;

    long stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
    double minDist = stops * _Point;
    if(isBuy)  { if(price-sl < minDist) sl = price-minDist; if(tp-price < minDist) tp = price+minDist; }
    else        { if(sl-price < minDist) sl = price+minDist; if(price-tp < minDist) tp = price-minDist; }
    sl = NormalizeDouble(sl, _Digits);
    tp = NormalizeDouble(tp, _Digits);

    double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
    double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double pipVal   = tickVal * (_Point * 10 / tickSize);
    double slPips   = slDist / (_Point * 10);
    double lots     = MathMin((equity * LotRiskPct / 100.0) / (slPips * pipVal), MaxLots);
    double step     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    lots = MathMax(MathFloor(lots/step)*step, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
    if(lots <= 0) return;

    if(isBuy) Trade.Buy(lots,  _Symbol, ask, sl, tp, Comment_);
    else      Trade.Sell(lots, _Symbol, bid, sl, tp, Comment_);
}
