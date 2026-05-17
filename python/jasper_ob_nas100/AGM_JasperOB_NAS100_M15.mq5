//+------------------------------------------------------------------+
//| AGM_JasperOB_NAS100_M15.mq5  v1.0                                |
//| Smart Money Concepts: Order Block + FVG + EMA200 H4 + Wick      |
//|                                                                  |
//| Backtest QQQ M15 2020-2025 (proxy NAS100):                      |
//|   IS  PF=1.26 DD=4.8% N=103                                     |
//|   OOS PF=1.49 DD=3.9% Ann=5.5% N=112 WR=33% WF=1.18             |
//|   MC P95 DD=7.0% | 5/6 años positivos                          |
//|   Checklist 6/7 (N IS justo, por datos cortos)                  |
//|                                                                  |
//| Correlacion con EMA9+VWAP+RSI QQQ = 0.026 (diversifica bien)    |
//|                                                                  |
//| Filtros entrada:                                                |
//|   - OB Bullish: vela displacement+confirm+FVG (no pre-FVG)      |
//|   - Touch memory + reversal (close > high[-1])                  |
//|   - EMA200 H4: solo OBs en direccion tendencia mayor            |
//|   - Wick rechazo: vela previa con mecha >= 1.5x body            |
//|   - Circuit breakers (DD diario 3% + 3 SL streak)               |
//|   - Filtro noticias USD ±2min (5%ers requirement)               |
//|                                                                  |
//| Version: 1.0 | 2026-05-17                                       |
//+------------------------------------------------------------------+
#property copyright "AGM — Jasper OB NAS100 v1"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== IDENTIFICACION ==="
input ulong  MagicNumber     = 202621;
input string Comment_        = "AGM_NAS100_JOB";

input group "=== GESTION RIESGO ==="
input double RR              = 2.0;    // Take Profit en R (SL*RR)
input double BufferATR       = 0.5;    // SL = extremo OB +- BufferATR*ATR
input int    ATR_Period      = 14;
input double MinSLPts        = 0.5;
input double MaxSLPts        = 200.0;
input int    MaxOBBars       = 50;     // Caducidad OB en N barras
input int    MaxTradesDay    = 3;

input group "=== FILTRO TENDENCIA EMA200 H4 ==="
input bool   UseEMA200H4     = true;
input int    EMA200H4_Period = 200;

input group "=== FILTRO VELA DE RECHAZO ==="
input bool   UseWick         = true;
input double WickRatio       = 1.5;    // mecha >= ratio * body

input group "=== RIESGO ==="
input double LotRiskPct      = 0.5;
input double MaxLots         = 4.0;

input group "=== FILTRO NOTICIAS (5%ers) ==="
input bool   UseNewsFilter   = true;
input int    NewsWindowMin   = 2;

input group "=== CIRCUIT BREAKERS ==="
input bool   UseCircuitBreakers = true;
input double DailyDDPause     = 3.0;
input int    ConsecutiveSLs   = 3;

input group "=== EJECUCION ==="
input int    MaxSpreadPts    = 50;
input int    SlippagePts     = 20;

//--- Handles e indicadores
CTrade   Trade;
int      h_atr;
int      h_ema200_h4;
double   Pip;
datetime LastBar = 0;
datetime LastTradeDay = 0;
int      TradesToday = 0;

// Circuit breakers
double   DayStartBalance = 0;
int      ConsecSLsToday  = 0;
bool     DayBlocked      = false;

//--- Order Blocks activos
#define MAX_OBS 50
struct OB {
   double top;
   double bot;
   datetime created;
   bool touched;
   bool used;
};
OB BullOBs[MAX_OBS];
OB BearOBs[MAX_OBS];
int NumBullOBs = 0;
int NumBearOBs = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   Pip = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(_Digits == 3 || _Digits == 5) Pip *= 10;

   h_atr = iATR(_Symbol, PERIOD_M15, ATR_Period);
   if(UseEMA200H4)
      h_ema200_h4 = iMA(_Symbol, PERIOD_H4, EMA200H4_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(h_atr == INVALID_HANDLE || (UseEMA200H4 && h_ema200_h4 == INVALID_HANDLE))
   { Print("ERROR indicadores"); return INIT_FAILED; }

   Trade.SetExpertMagicNumber(MagicNumber);
   Trade.SetDeviationInPoints(SlippagePts);
   Trade.SetTypeFillingBySymbol(_Symbol);
   Trade.LogLevel(LOG_LEVEL_ERRORS);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(h_atr);
   if(UseEMA200H4) IndicatorRelease(h_ema200_h4);
}

//+------------------------------------------------------------------+
//| Filtro noticias USD                                              |
//+------------------------------------------------------------------+
bool IsNewsWindow()
{
   if(!UseNewsFilter) return false;
   datetime now = TimeCurrent();
   datetime f = now - NewsWindowMin*60;
   datetime t = now + NewsWindowMin*60;
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
//| Circuit breakers                                                 |
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
         PrintFormat("CIRCUIT BREAKER: DD diario %.2f%% >= %.2f%%", dd, DailyDDPause);
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
//| Helpers OB management                                            |
//+------------------------------------------------------------------+
void RemoveBullOB(int idx)
{
   for(int i = idx; i < NumBullOBs-1; i++) BullOBs[i] = BullOBs[i+1];
   NumBullOBs--;
}
void RemoveBearOB(int idx)
{
   for(int i = idx; i < NumBearOBs-1; i++) BearOBs[i] = BearOBs[i+1];
   NumBearOBs--;
}

void AddBullOB(double top, double bot, datetime when)
{
   if(NumBullOBs >= MAX_OBS) return;
   // Evitar duplicados cercanos
   for(int i = 0; i < NumBullOBs; i++)
      if(MathAbs(BullOBs[i].top - top) < Pip*2) return;
   BullOBs[NumBullOBs].top = top;
   BullOBs[NumBullOBs].bot = bot;
   BullOBs[NumBullOBs].created = when;
   BullOBs[NumBullOBs].touched = false;
   BullOBs[NumBullOBs].used = false;
   NumBullOBs++;
}
void AddBearOB(double top, double bot, datetime when)
{
   if(NumBearOBs >= MAX_OBS) return;
   for(int i = 0; i < NumBearOBs; i++)
      if(MathAbs(BearOBs[i].bot - bot) < Pip*2) return;
   BearOBs[NumBearOBs].top = top;
   BearOBs[NumBearOBs].bot = bot;
   BearOBs[NumBearOBs].created = when;
   BearOBs[NumBearOBs].touched = false;
   BearOBs[NumBearOBs].used = false;
   NumBearOBs++;
}

bool EsVelaRechazo(double o, double h, double l, double c, double ratio)
{
   double body = MathAbs(c - o);
   if(body == 0) body = 1e-9;
   double wick = (c > o) ? (MathMin(o,c) - l) : (h - MathMax(o,c));
   return wick >= ratio * body;
}

bool HasPosition(ulong &ticket)
{
   for(int i = 0; i < PositionsTotal(); i++)
      if(PositionGetSymbol(i) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == (long)MagicNumber)
      { ticket = PositionGetInteger(POSITION_TICKET); return true; }
   return false;
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

   // Posicion abierta? salir
   ulong ticket;
   if(HasPosition(ticket)) return;

   // === Lectura de barras (i = barra cerrada, i-1, i-2, i-3) ===
   double o0=iOpen(_Symbol,PERIOD_M15,1), h0=iHigh(_Symbol,PERIOD_M15,1);
   double l0=iLow(_Symbol,PERIOD_M15,1),  c0=iClose(_Symbol,PERIOD_M15,1);
   double o1=iOpen(_Symbol,PERIOD_M15,2), h1=iHigh(_Symbol,PERIOD_M15,2);
   double l1=iLow(_Symbol,PERIOD_M15,2),  c1=iClose(_Symbol,PERIOD_M15,2);
   double o2=iOpen(_Symbol,PERIOD_M15,3), h2=iHigh(_Symbol,PERIOD_M15,3);
   double l2=iLow(_Symbol,PERIOD_M15,3),  c2=iClose(_Symbol,PERIOD_M15,3);
   double o3=iOpen(_Symbol,PERIOD_M15,4), h3=iHigh(_Symbol,PERIOD_M15,4);
   double l3=iLow(_Symbol,PERIOD_M15,4),  c3=iClose(_Symbol,PERIOD_M15,4);

   // ATR
   double atr_buf[1];
   if(CopyBuffer(h_atr, 0, 1, 1, atr_buf) <= 0) return;
   double atr1 = atr_buf[0];
   if(atr1 <= 0) return;

   // === Detectar NUEVO OB en la barra recien cerrada ===
   // Bullish: c1>o1, c0>o0, l0>h2 (FVG entre vela displacement i-2 y barra actual i-1)
   // (Aqui los indices son distintos respecto al Python: 0=barra cerrada, 1=anterior, etc)
   // Mapeo Python → MQL5:
   //   Python c[i]   = MQL5 c0
   //   Python c[i-1] = MQL5 c1
   //   Python c[i-2] = MQL5 c2
   //   Python c[i-3] = MQL5 c3
   bool displ_bull  = (c1 > o1);
   bool confirm_bull= (c0 > o0);
   bool fvg_bull    = (l0 > h2);
   bool prefvg_bull = (l2 > h3) || (l1 > h3);
   if(displ_bull && confirm_bull && fvg_bull && !prefvg_bull)
      AddBullOB(h2, l2, curBar);

   bool displ_bear   = (c1 < o1);
   bool confirm_bear = (c0 < o0);
   bool fvg_bear     = (h0 < l2);
   bool prefvg_bear  = (h2 < l3) || (h1 < l3);
   if(displ_bear && confirm_bear && fvg_bear && !prefvg_bear)
      AddBearOB(h2, l2, curBar);

   // === Limpieza OBs invalidados/caducados ===
   for(int i = NumBullOBs-1; i >= 0; i--)
   {
      if(c0 < BullOBs[i].bot) { RemoveBullOB(i); continue; }
      int bars_old = iBarShift(_Symbol, PERIOD_M15, BullOBs[i].created);
      if(bars_old > MaxOBBars) { RemoveBullOB(i); continue; }
      // Touch
      if(!BullOBs[i].touched && l0 <= BullOBs[i].top && h0 >= BullOBs[i].bot)
         BullOBs[i].touched = true;
   }
   for(int i = NumBearOBs-1; i >= 0; i--)
   {
      if(c0 > BearOBs[i].top) { RemoveBearOB(i); continue; }
      int bars_old = iBarShift(_Symbol, PERIOD_M15, BearOBs[i].created);
      if(bars_old > MaxOBBars) { RemoveBearOB(i); continue; }
      if(!BearOBs[i].touched && l0 <= BearOBs[i].top && h0 >= BearOBs[i].bot)
         BearOBs[i].touched = true;
   }

   // === Filtros de entrada ===
   if(TradesToday >= MaxTradesDay) return;
   if(tm.day_of_week == 6 || tm.day_of_week == 0) return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpreadPts) return;
   if(IsNewsWindow()) return;
   if(!IsTradingAllowed()) return;
   if(UseCircuitBreakers && ConsecSLsToday >= ConsecutiveSLs) return;

   // EMA200 H4 filter
   bool trend_up_ok = true, trend_down_ok = true;
   if(UseEMA200H4)
   {
      double ema_h4_buf[1];
      if(CopyBuffer(h_ema200_h4, 0, 1, 1, ema_h4_buf) <= 0) return;
      double ema_h4 = ema_h4_buf[0];
      double close_h4 = iClose(_Symbol, PERIOD_H4, 1);
      trend_up_ok   = (close_h4 > ema_h4);
      trend_down_ok = (close_h4 < ema_h4);
   }

   // Wick rechazo filter
   bool wick_ok = !UseWick || EsVelaRechazo(o0, h0, l0, c0, WickRatio);
   if(!wick_ok) return;

   // === Buscar senal LONG: OB bullish tocado + close > high[-1] ===
   int idx_long = -1;
   if(trend_up_ok)
   {
      for(int i = 0; i < NumBullOBs; i++)
      {
         if(BullOBs[i].touched && c0 > h1 && c0 > BullOBs[i].top)
         { idx_long = i; break; }
      }
   }

   int idx_short = -1;
   if(idx_long < 0 && trend_down_ok)
   {
      for(int i = 0; i < NumBearOBs; i++)
      {
         if(BearOBs[i].touched && c0 < l1 && c0 < BearOBs[i].bot)
         { idx_short = i; break; }
      }
   }

   if(idx_long < 0 && idx_short < 0) return;

   // === Setup orden ===
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry, sl, sl_dist, tp;
   bool   is_long = (idx_long >= 0);

   if(is_long)
   {
      entry = ask;
      sl = BullOBs[idx_long].bot - BufferATR * atr1;
      sl_dist = entry - sl;
      RemoveBullOB(idx_long);  // latch
   }
   else
   {
      entry = bid;
      sl = BearOBs[idx_short].top + BufferATR * atr1;
      sl_dist = sl - entry;
      RemoveBearOB(idx_short);
   }

   if(sl_dist <= 0) return;
   double min_sl = MinSLPts * Pip;
   double max_sl = MaxSLPts * Pip;
   sl_dist = MathMax(sl_dist, min_sl);
   if(sl_dist > max_sl) return;

   tp = is_long ? entry + sl_dist * RR : entry - sl_dist * RR;

   // Sizing
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double tick_val  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double pip_val   = tick_val * (Pip / tick_size);
   double sl_pips   = sl_dist / Pip;
   double lots      = (equity * LotRiskPct / 100.0) / (sl_pips * pip_val);
   lots = MathMin(NormalizeDouble(lots, 2), MaxLots);
   lots = MathMax(lots, 0.01);

   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   bool ok;
   if(is_long) ok = Trade.Buy(lots, _Symbol, ask, sl, tp, Comment_);
   else        ok = Trade.Sell(lots, _Symbol, bid, sl, tp, Comment_);
   if(ok) TradesToday++;
}
