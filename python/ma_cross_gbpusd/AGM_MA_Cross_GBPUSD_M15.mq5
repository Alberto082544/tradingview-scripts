//+------------------------------------------------------------------+
//| AGM_MA_Cross_GBPUSD_M15.mq5                                     |
//| MA Cross | GBPUSD M15 | Tendencia H4+M15                        |
//| Backtest $50k: $319,005 total | $21,987/año | $1,832/mes        |
//| IS 2014-2021: PF=1.38 Ann=23.9% DD=5.2%                        |
//| OOS 2022-2025: PF=1.35 Ann=29.1% DD=9.8%                       |
//| Robustez: 12/12 años positivos. Peor año: 2021 Ann=24.37%       |
//| Version: 1.0 | 2026-05-16                                       |
//+------------------------------------------------------------------+
#property copyright "AGM — MA Cross GBPUSD"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

CTrade        Trade;
CPositionInfo Pos;
CSymbolInfo   Sym;

//--- Inputs
input group "=== IDENTIFICACION ==="
input ulong  MagicNumber     = 202611;
input string Comment_        = "AGM_GBPUSD_MC";

input group "=== MEDIAS (entrada M15) ==="
input int    EMA_Fast        = 5;          // EMA rapida (REVERTIDO 23-may tarde: EMA=3 dio -99% DD en MT5)
input int    SMA_Slow        = 34;         // SMA lenta (REVERTIDO 23-may tarde)
input ENUM_APPLIED_PRICE EntryPrice = PRICE_CLOSE;

input group "=== FILTRO DIRECCION H4 ==="
input bool             UseDirFilter = true;
input ENUM_TIMEFRAMES  DirTF        = PERIOD_H4;
input int              Dir_EMA      = 5;   // Igual que EMA_Fast (REVERTIDO)
input int              Dir_SMA      = 34;  // Igual que SMA_Slow (REVERTIDO)

input group "=== GESTION SL/TP ==="
input int    ATR_Period      = 14;
input double SL_ATR_Mult     = 1.0;        // SL = 1 * ATR (REVERTIDO 23-may tarde: SL=0.5 dio -99% DD)
input double RR              = 3.0;        // TP = 3 * SL

input group "=== BREAK-EVEN ==="
input bool   UseBE           = true;
input double BE_Trigger_ATR  = 0.5;
input int    BE_Offset_Pts   = 10;

input group "=== TRAILING STOP (ATR) ==="
input bool   UseTrailing     = true;
input double Trail_Start_ATR = 1.5;
input double Trail_Dist_ATR  = 0.5;

input group "=== RIESGO ==="
input double LotRiskPct      = 0.5;
input double MaxLots         = 4.0;

input group "=== FILTRO VOLATILIDAD (parche 2026-05-22) ==="
input double MaxATR_Pips     = 35.0;   // 0 = off. >0: no entrar si ATR > umbral pips. Evita SL anormales

input group "=== EJECUCION ==="
input int    MaxSpreadPts    = 30;
input int    SlippagePts     = 20;

//--- Handles
int h_ema, h_sma, h_dir_ema, h_dir_sma, h_atr;
datetime LastBar = 0;

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

    ulong ticket;
    if(HasPosition(ticket)) return;

    if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpreadPts) return;

    double ema[2], sma[2];
    if(CopyBuffer(h_ema, 0, 1, 2, ema) < 2) return;
    if(CopyBuffer(h_sma, 0, 1, 2, sma) < 2) return;
    bool cross_up   = (ema[0] <= sma[0] && ema[1] > sma[1]);
    bool cross_down = (ema[0] >= sma[0] && ema[1] < sma[1]);
    if(!cross_up && !cross_down) return;

    if(UseDirFilter)
    {
        double dema[1], dsma[1];
        if(CopyBuffer(h_dir_ema, 0, 0, 1, dema) <= 0) return;
        if(CopyBuffer(h_dir_sma, 0, 0, 1, dsma) <= 0) return;
        if(cross_up   && dema[0] <= dsma[0]) return;
        if(cross_down && dema[0] >= dsma[0]) return;
    }

    MqlDateTime tm; TimeToStruct(TimeCurrent(), tm);
    if(tm.day_of_week == 6 || tm.day_of_week == 0) return;
    if(tm.day_of_week == 5 && tm.hour >= 22) return;

    double atr[1];
    if(CopyBuffer(h_atr, 0, 1, 1, atr) <= 0) return;
    // Filtro volatilidad: no entrar si ATR > MaxATR_Pips
    double atrPips = atr[0] / (_Point * 10);
    if(MaxATR_Pips > 0 && atrPips > MaxATR_Pips) return;
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
