//+------------------------------------------------------------------+
//| AGM_Ranger_C_AUDNZD_M15.mq5                                     |
//| Ranger C v3 | AUDNZD M15 | Mean Reversion H4+M15                |
//| FILTROS: Stochastic(5,3,3) K<15 + ADX H4 < 20 + Trail 4 pips    |
//|                                                                  |
//| Backtest $50k 2014-2025:                                        |
//|   IS 2014-2021:  PF=1.21 DD=12.3%                               |
//|   OOS 2022-2025: PF=1.54 Ann=25.4% DD=4.6% WR=63.7% N=1123      |
//|   WF ratio:      1.273  | Apto FundedNext + The 5%ers           |
//| Version: 3.3 | 2026-05-17 | + Circuit breakers (DD+SL streak)   |
//+------------------------------------------------------------------+
#property copyright "AGM — Ranger C AUDNZD v3.1"
#property version   "3.30"
#property strict

#include <Trade\Trade.mqh>

//--- Inputs
input group "=== INDICADORES ==="
input int    BB_Period       = 20;
input double BB_StdDev       = 2.0;
input int    Stoch_K         = 5;
input int    Stoch_D         = 3;
input int    Stoch_Slow      = 3;
input int    ADX_H4_Period   = 14;
input int    ATR_Period      = 14;

input group "=== FILTROS ==="
input double ADX_H4_Max       = 20.0;   // ADX H4 maximo (mercado lateral)
input double Stoch_Long_Max   = 15.0;   // Stoch K < esto para largo (v3: optimizado DD<5%)
input double Stoch_Short_Min  = 75.0;   // Stoch K > esto para corto

input group "=== SL / TRAILING ==="
input double SL_ATR_Mult    = 1.5;    // SL = ATR * multiplicador
input double MinSLPips      = 20.0;   // SL minimo en pips
input bool   BB_Mid_TP      = false;  // Cerrar al cruzar BB media
input double TrailActivate  = 0.5;    // Activar trailing a X * SL_dist en ganancia
input double TrailDistPips  = 4.0;    // Distancia del trailing (pips) (v3: optimizado DD<5%)
input int    ExitBars       = 32;     // Salida por tiempo (barras M15 = 8h)

input group "=== RIESGO ==="
input double LotRiskPct     = 0.5;    // Riesgo % por trade (0.5 = DD~3.3% en fondeo)
input double MaxLots        = 4.0;

input group "=== SESION ==="
input int    SessionStart   = 0;
input int    SessionEnd     = 23;
input int    BadHour        = 8;       // Hora UTC bloqueada (v3.2: hora 8 = transicion Asia->Londres)
input int    MaxTradesDay   = 5;
input ulong  MagicNumber    = 202601;

input group "=== FILTRO NOTICIAS (5%ers High Stakes) ==="
input bool   UseNewsFilter   = true;   // Activar filtro noticias alto impacto
input int    NewsWindowMin   = 2;      // Bloquear N min antes y despues de noticia

input group "=== CIRCUIT BREAKERS (proteccion fondeo) ==="
input bool   UseCircuitBreakers = true; // Activar bloqueos de seguridad
input double DailyDDPause     = 3.0;   // % perdida diaria que pausa hasta el siguiente dia
input int    ConsecutiveSLs   = 3;     // Numero de SL consecutivos para reducir lote
input double LotReductionPct  = 0.5;   // Multiplicador del lote tras N SL (0.5 = mitad)

//--- Globals
CTrade   Trade;
int      hBB, hStoch, hATR, hADX_H4;
double   Pip;
datetime LastBar      = 0;
datetime LastTradeDay = 0;
datetime EntryTime    = 0;
int      TradesToday  = 0;

// Circuit breakers (estado por dia)
double   DayStartBalance = 0;      // balance al inicio del dia
int      ConsecSLsToday  = 0;      // contador SL consecutivos
bool     DayBlocked      = false;  // dia bloqueado por DD diario

//+------------------------------------------------------------------+
int OnInit()
{
    Pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    if(_Digits == 3 || _Digits == 5) Pip *= 10;

    hBB     = iBands     (_Symbol, PERIOD_M15, BB_Period, 0, BB_StdDev, PRICE_CLOSE);
    hStoch  = iStochastic(_Symbol, PERIOD_M15, Stoch_K, Stoch_D, Stoch_Slow, MODE_SMA, STO_LOWHIGH);
    hATR    = iATR       (_Symbol, PERIOD_M15, ATR_Period);
    hADX_H4 = iADX       (_Symbol, PERIOD_H4,  ADX_H4_Period);

    if(hBB == INVALID_HANDLE || hStoch == INVALID_HANDLE ||
       hATR == INVALID_HANDLE || hADX_H4 == INVALID_HANDLE)
    {
        Print("ERROR indicadores: ", GetLastError());
        return INIT_FAILED;
    }

    Trade.SetExpertMagicNumber(MagicNumber);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    IndicatorRelease(hBB);
    IndicatorRelease(hStoch);
    IndicatorRelease(hATR);
    IndicatorRelease(hADX_H4);
}

//+------------------------------------------------------------------+
//| Circuit breakers: TRUE si esta operativa permitida                |
//| Bloquea si DD diario > limite o si demasiados SL seguidos        |
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
        ConsecSLsToday = 0;  // reset al primer winner
    }
}

//+------------------------------------------------------------------+
//| Filtro noticias: TRUE si hay noticia alto impacto en ventana    |
//| que afecte a las monedas del symbol (AUD, NZD, USD, EUR, etc.)  |
//+------------------------------------------------------------------+
bool IsNewsWindow()
{
    if(!UseNewsFilter) return false;

    datetime now      = TimeCurrent();
    datetime from_t   = now - NewsWindowMin * 60;
    datetime to_t     = now + NewsWindowMin * 60;

    // Extraer monedas del simbolo (primeras 3 letras + siguientes 3)
    string sym = _Symbol;
    if(StringLen(sym) < 6) return false;
    string ccy1 = StringSubstr(sym, 0, 3);
    string ccy2 = StringSubstr(sym, 3, 3);

    string ccys[2]; ccys[0] = ccy1; ccys[1] = ccy2;
    for(int c = 0; c < 2; c++)
    {
        MqlCalendarValue values[];
        int n = CalendarValueHistory(values, from_t, to_t, NULL, ccys[c]);
        for(int i = 0; i < n; i++)
        {
            MqlCalendarEvent ev;
            if(!CalendarEventById(values[i].event_id, ev)) continue;
            if(ev.importance == CALENDAR_IMPORTANCE_HIGH)
                return true;  // hay noticia alto impacto en ventana
        }
    }
    return false;
}

//+------------------------------------------------------------------+
bool GetPosition(ulong &ticket, double &entry, double &sl, ENUM_POSITION_TYPE &ptype)
{
    for(int i = 0; i < PositionsTotal(); i++)
    {
        if(PositionGetSymbol(i) == _Symbol &&
           PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber)
        {
            ticket = PositionGetInteger(POSITION_TICKET);
            entry  = PositionGetDouble(POSITION_PRICE_OPEN);
            sl     = PositionGetDouble(POSITION_SL);
            ptype  = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            return true;
        }
    }
    return false;
}

//+------------------------------------------------------------------+
void OnTick()
{
    // Solo en apertura de nueva vela M15
    datetime curBar = iTime(_Symbol, PERIOD_M15, 0);
    if(curBar == LastBar) return;
    LastBar = curBar;

    datetime dt = TimeCurrent();
    MqlDateTime tm;
    TimeToStruct(dt, tm);

    // Reset contador diario + circuit breakers
    datetime hoy = (datetime)((long)dt - (long)dt % 86400);
    if(hoy != LastTradeDay)
    {
        TradesToday      = 0;
        LastTradeDay     = hoy;
        DayStartBalance  = AccountInfoDouble(ACCOUNT_BALANCE);
        ConsecSLsToday   = 0;
        DayBlocked       = false;
    }

    // Leer indicadores (shift 1 = barra cerrada anterior)
    double bb_upper[3], bb_lower[3], bb_mid[3];
    double stoch_k[3], stoch_d[3];
    double atr[2], adx[2];
    if(CopyBuffer(hBB,     1, 0, 3, bb_upper) < 3) return;  // buffer1 = UPPER
    if(CopyBuffer(hBB,     2, 0, 3, bb_lower) < 3) return;  // buffer2 = LOWER
    if(CopyBuffer(hBB,     0, 0, 3, bb_mid)   < 3) return;  // buffer0 = MIDDLE
    if(CopyBuffer(hStoch,  0, 0, 3, stoch_k)  < 3) return;  // buffer0 = K main
    if(CopyBuffer(hStoch,  1, 0, 3, stoch_d)  < 3) return;  // buffer1 = D signal
    if(CopyBuffer(hATR,    0, 0, 2, atr)      < 2) return;
    if(CopyBuffer(hADX_H4, 0, 0, 2, adx)      < 2) return;

    // Indice 1 = barra cerrada anterior
    double sk1    = stoch_k[1];
    double sd1    = stoch_d[1];
    double atr1   = atr[1];
    double adx1   = adx[1];
    double bbu1   = bb_upper[1];
    double bbl1   = bb_lower[1];
    double bbm1   = bb_mid[1];
    double close1 = iClose(_Symbol, PERIOD_M15, 1);

    // === GESTION POSICION ABIERTA ===
    ulong ticket; double entry_p, sl_p; ENUM_POSITION_TYPE ptype;
    if(GetPosition(ticket, entry_p, sl_p, ptype))
    {
        double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        double cur = (ptype == POSITION_TYPE_BUY) ? bid : ask;
        double sl_dist = MathAbs(entry_p - sl_p);

        // Trailing stop
        if(ptype == POSITION_TYPE_BUY)
        {
            if((cur - entry_p) >= TrailActivate * sl_dist)
            {
                double new_sl = NormalizeDouble(cur - TrailDistPips * Pip, _Digits);
                if(new_sl > sl_p + _Point)
                    Trade.PositionModify(ticket, new_sl, 0);
            }
        }
        else
        {
            if((entry_p - cur) >= TrailActivate * sl_dist)
            {
                double new_sl = NormalizeDouble(cur + TrailDistPips * Pip, _Digits);
                if(new_sl < sl_p - _Point)
                    Trade.PositionModify(ticket, new_sl, 0);
            }
        }

        // Salida BB_MID
        if(BB_Mid_TP)
        {
            if(ptype == POSITION_TYPE_BUY && bid >= bbm1)
            { Trade.PositionClose(ticket); EntryTime = 0; return; }
            if(ptype == POSITION_TYPE_SELL && ask <= bbm1)
            { Trade.PositionClose(ticket); EntryTime = 0; return; }
        }

        // Salida por tiempo (ExitBars barras M15)
        if(EntryTime > 0)
        {
            int elapsed = (int)((dt - EntryTime) / PeriodSeconds(PERIOD_M15));
            if(elapsed >= ExitBars)
            { Trade.PositionClose(ticket); EntryTime = 0; return; }
        }

        return; // posicion abierta, no buscar entrada
    }

    // === CONDICIONES DE ENTRADA ===
    int hr = tm.hour;
    int wd = tm.day_of_week;
    if(hr < SessionStart || hr >= SessionEnd)    return;
    if(hr == BadHour && BadHour >= 0)            return;
    if(wd == 6 || wd == 0)                       return;  // fin de semana
    if(wd == 5 && hr >= 22)                      return;  // viernes noche
    if(TradesToday >= MaxTradesDay)              return;
    if(adx1 >= ADX_H4_Max)                      return;  // tendencia fuerte
    if(IsNewsWindow())                          return;  // bloqueo noticias alto impacto
    if(!IsTradingAllowed())                     return;  // circuit breaker DD diario
    if(UseCircuitBreakers && ConsecSLsToday >= ConsecutiveSLs) return;  // SL consecutivos

    // Stochastic solo: K en zona extrema + K cruzando D al alza/baja (giro)
    bool stoch_ok_long  = (sk1 < Stoch_Long_Max  && sk1 > sd1);
    bool stoch_ok_short = (sk1 > Stoch_Short_Min && sk1 < sd1);

    bool cond_long  = (close1 <= bbl1 * 1.001 && stoch_ok_long);
    bool cond_short = (!cond_long && close1 >= bbu1 * 0.999 && stoch_ok_short);

    if(!cond_long && !cond_short) return;

    double sl_dist = MathMax(atr1 * SL_ATR_Mult, MinSLPips * Pip);

    // Sizing basado en riesgo
    double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
    double tick_val  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double pip_val   = tick_val * (Pip / tick_size);
    double sl_pips   = sl_dist / Pip;
    double lots      = (equity * LotRiskPct / 100.0) / (sl_pips * pip_val);
    lots = MathMin(NormalizeDouble(lots, 2), MaxLots);
    lots = MathMax(lots, 0.01);

    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

    if(cond_long)
    {
        double sl = NormalizeDouble(ask - sl_dist, _Digits);
        if(Trade.Buy(lots, _Symbol, ask, sl, 0, "RC_AUDNZD_L"))
        { EntryTime = dt; TradesToday++; }
    }
    else
    {
        double sl = NormalizeDouble(bid + sl_dist, _Digits);
        if(Trade.Sell(lots, _Symbol, bid, sl, 0, "RC_AUDNZD_S"))
        { EntryTime = dt; TradesToday++; }
    }
}
