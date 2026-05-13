"""
Minervini SEPA Backtesting Engine v3
=====================================
العودة للأصل مع إصلاح المشكلة الحقيقية:
✅ Trend Template كامل — بدون تخفيف
✅ VCP أصلي — 2 تضيقات + حجم يجف
✅ اختراق بحجم 50%+ فوق المتوسط
✅ Market Regime Filter — لا شراء في السوق الهابط
✅ قائمة 100+ سهم — لإيجاد الفرص النادرة
✅ Stage Analysis — Stage 2 فقط
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

# ─── إعدادات Minervini الأصلية ───────────────────────────────────────────────
CONFIG = {
    "start_date":        "2019-01-01",   # 6 سنوات لتغطية سوق صاعد وهابط
    "end_date":          "2024-12-31",
    "initial_capital":   100_000,
    "account_risk_pct":  0.0125,         # 1.25% خطر لكل صفقة
    "stop_loss_pct":     0.07,           # 7% Stop Loss — Minervini الأصلي
    "take_profit_pct":   0.20,           # 20% هدف أولي
    "trailing_stop_pct": 0.10,           # 10% Trailing
    "max_positions":     6,              # Minervini: لا تتشتت
    "commission":        0.001,
    # ── VCP الأصلي ──
    "vcp_min_contractions": 2,           # 2 تضيقات كما قال Minervini
    "vcp_vol_dry_ratio":    0.60,        # الحجم يجف 40%+
    "breakout_volume_ratio": 1.50,       # 50%+ فوق المتوسط عند الاختراق
    # ── Trend Template الأصلي ──
    "pct_from_high52":   0.25,           # في 25% من القمة السنوية
    "pct_from_low52":    0.30,           # 30%+ فوق القاع السنوي
}

# ─── 100+ سهم من أفضل القطاعات ─────────────────────────────────────────────
WATCHLIST = [
    # ── التكنولوجيا الكبرى ──
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD","ORCL","TSM","QCOM",
    # ── السيبراني ──
    "CRWD","PANW","ZS","FTNT","CYBR","S","OKTA","SAIL",
    # ── البرمجيات والسحابة ──
    "NOW","DDOG","SNOW","PLTR","NET","MDB","HUBS","BILL","GTLB","DOCN",
    "ADBE","CRM","INTU","WDAY","NFLX","TTD","TEAM","ZM","DOCU",
    # ── أشباه الموصلات ──
    "ARM","ANET","MRVL","LRCX","KLAC","AMAT","ASML","ONTO","ACLS",
    # ── النمو العالي ──
    "TSLA","UBER","SHOP","ABNB","DASH","DKNG","ROKU","CELH","ENPH","FSLR",
    # ── الصحة والأدوية ──
    "LLY","UNH","ISRG","DXCM","ABBV","REGN","VRTX","MRNA","IDXX",
    # ── المالية ──
    "V","MA","JPM","GS","PYPL","AFRM","COIN",
    # ── الاستهلاكي ──
    "COST","WMT","LULU","NKE","DECK","ONON","CROX",
    # ── الصناعي والطاقة ──
    "CAT","HON","GE","LMT","NOC","XOM","CVX","OXY",
    # ── ETFs للمقارنة ──
    "SMH","QQQ","SOXX","XLK","IBB",
]

# ─── تحميل البيانات ──────────────────────────────────────────────────────────
def load_data(symbols, start, end):
    data = {}
    print(f"📥 تحميل {len(symbols)} سهم (قد يستغرق ١٠ دقائق)...")
    failed = []
    for sym in symbols:
        try:
            df = yf.download(sym, start=start, end=end,
                           progress=False, auto_adjust=True)
            if len(df) < 200:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df.index = pd.to_datetime(df.index)
            data[sym] = df
        except Exception as e:
            failed.append(sym)
    print(f"  ✅ تم تحميل {len(data)} سهم | فشل: {len(failed)}\n")
    return data

# ─── حساب المؤشرات ──────────────────────────────────────────────────────────
def compute_indicators(df):
    df = df.copy()
    close = df['Close']

    # المتوسطات المتحركة
    for n in [10, 20, 50, 150, 200]:
        df[f'MA{n}'] = close.rolling(n).mean()

    # اتجاه MA200 (هل صاعد؟)
    df['MA200_slope'] = df['MA200'].diff(20)

    # ATR
    hl  = df['High'] - df['Low']
    hpc = (df['High'] - close.shift()).abs()
    lpc = (df['Low']  - close.shift()).abs()
    df['ATR14'] = pd.concat([hl,hpc,lpc],axis=1).max(axis=1).rolling(14).mean()

    # الحجم
    df['Vol_MA20']  = df['Volume'].rolling(20).mean()
    df['Vol_ratio'] = df['Volume'] / df['Vol_MA20']

    # 52 أسبوع
    df['High52w']         = close.rolling(252).max()
    df['Low52w']          = close.rolling(252).min()
    df['pct_from_high52'] = (close - df['High52w']) / df['High52w']
    df['pct_from_low52']  = (close - df['Low52w'])  / df['Low52w']

    # Bollinger لقياس التضيق
    df['BB_std']   = close.rolling(20).std()
    df['BB_width'] = df['BB_std'] / df['MA20']

    # RS مبسط (أداء السهم نسبياً لآخر 12 شهر)
    df['RS_raw'] = close / close.shift(252)

    return df

# ─── Market Regime Filter ────────────────────────────────────────────────────
def is_market_healthy(spy_data, date):
    """
    Minervini: لا تشتري أبداً عندما السوق هابط
    السوق صحي إذا: SPY > MA200 + MA200 صاعد
    """
    if spy_data is None or date not in spy_data.index:
        return True  # افتراضي: السوق صحي
    try:
        row = spy_data.loc[date]
        close  = float(row['Close'])
        ma200  = float(row['MA200'])
        slope  = float(row['MA200_slope'])
        # السوق صحي: السعر فوق MA200 والمتوسط صاعد
        return close > ma200 and slope > 0
    except:
        return True

# ─── Trend Template (8 شروط Minervini) ──────────────────────────────────────
def check_trend_template(row):
    """
    الـ 8 شروط الأصلية — لا تخفيف
    """
    try:
        c = float(row['Close'])
        return all([
            c > float(row['MA50']),              # ١. فوق MA50
            c > float(row['MA150']),             # ٢. فوق MA150
            c > float(row['MA200']),             # ٣. فوق MA200
            float(row['MA50'])  > float(row['MA150']),  # ٤. MA50 > MA150
            float(row['MA150']) > float(row['MA200']),  # ٥. MA150 > MA200
            float(row['MA200_slope']) > 0,       # ٦. MA200 صاعد
            float(row['pct_from_high52']) >= -CONFIG['pct_from_high52'],  # ٧. في 25% من القمة
            float(row['pct_from_low52'])  >= CONFIG['pct_from_low52'],    # ٨. 30%+ فوق القاع
        ])
    except:
        return False

# ─── VCP Detection (Minervini الأصلي) ───────────────────────────────────────
def detect_vcp(df, idx, lookback=65):
    """
    Volatility Contraction Pattern الأصلي:
    - 2-4 تضيقات تدريجية في السعر
    - حجم يجف عند كل تضيق
    - النافذة: ~3 أشهر
    """
    result = {"detected": False, "contractions": 0, "pivot": None, "tightness": 0}

    if idx < lookback + 10:
        return result

    window = df.iloc[idx - lookback: idx]
    n_periods = 4
    period_len = lookback // n_periods
    ranges, vols = [], []

    for i in range(n_periods):
        seg = window.iloc[i * period_len: (i+1) * period_len]
        if len(seg) < 5:
            continue
        high = seg['High'].max()
        low  = seg['Low'].min()
        mid  = seg['Close'].mean()
        price_range = (high - low) / mid if mid > 0 else 0
        ranges.append(price_range)
        vols.append(seg['Volume'].mean())

    if len(ranges) < 3:
        return result

    # عدد التضيقات التدريجية
    contractions = sum(
        1 for i in range(1, len(ranges))
        if ranges[i] < ranges[i-1] * 0.85  # كل تضيق أصغر بـ 15%+
    )

    # جفاف الحجم في آخر فترة مقارنة بأول فترة
    vol_dried = vols[-1] < vols[0] * CONFIG['vcp_vol_dry_ratio'] if vols[0] > 0 else False

    # نقطة الاختراق = أعلى سعر في آخر 15-20 يوم
    recent = df.iloc[idx-20: idx]
    pivot  = float(recent['High'].max())

    # مدى التضيق الأخير (كلما كان أقل كلما كان VCP أقوى)
    last_range = ranges[-1] if ranges else 0

    detected = (
        contractions >= CONFIG['vcp_min_contractions'] and
        vol_dried and
        last_range < 0.15  # آخر تضيق أقل من 15%
    )

    result.update({
        "detected":     detected,
        "contractions": contractions,
        "pivot":        pivot,
        "tightness":    round(last_range * 100, 1),
        "vol_dried":    vol_dried,
    })
    return result

# ─── إشارة الدخول الكاملة ────────────────────────────────────────────────────
def check_entry_signal(df, idx):
    """
    Minervini Entry:
    1. Trend Template ✅
    2. VCP (2+ contractions + vol dry) ✅
    3. Breakout above pivot + volume 50%+ ✅
    """
    signal = {"valid": False, "reason": ""}

    if idx < 255:  # نحتاج سنة كاملة من البيانات
        return signal

    row  = df.iloc[idx]
    prev = df.iloc[idx-1]

    # ١. Trend Template
    if not check_trend_template(row):
        signal["reason"] = "trend_template"
        return signal

    # ٢. VCP
    vcp = detect_vcp(df, idx)
    if not vcp["detected"]:
        signal["reason"] = f"vcp_fail"
        return signal

    # ٣. اختراق فوق Pivot
    pivot = vcp["pivot"]
    current_close = float(row['Close'])
    prev_close    = float(prev['Close'])

    broke_pivot  = prev_close <= pivot and current_close > pivot
    vol_surge    = float(row['Vol_ratio']) >= CONFIG['breakout_volume_ratio']

    if not broke_pivot:
        signal["reason"] = "no_breakout"
        return signal

    if not vol_surge:
        signal["reason"] = "weak_volume"
        return signal

    signal.update({
        "valid":        True,
        "pivot":        round(pivot, 2),
        "close":        round(current_close, 2),
        "vol_ratio":    round(float(row['Vol_ratio']), 2),
        "contractions": vcp["contractions"],
        "tightness":    vcp["tightness"],
    })
    return signal

# ─── محرك الـ Backtest ────────────────────────────────────────────────────────
class MinerviniBacktestV3:
    def __init__(self, config):
        self.cfg       = config
        self.cash      = config["initial_capital"]
        self.positions = {}
        self.trades    = []
        self.equity_curve = []
        self.skipped_regime = 0  # عدد المرات التي رفض فيها الـ Regime Filter

    def position_size(self, price, stop):
        risk_per_share = price - stop
        if risk_per_share <= 0:
            return 0
        account_risk = self.cash * self.cfg["account_risk_pct"]
        shares = int(account_risk / risk_per_share)
        # حد أقصى 20% من المحفظة لصفقة واحدة
        max_shares = int(self.cash * 0.20 / (price * (1 + self.cfg["commission"])))
        shares = min(shares, max_shares)
        return max(shares, 0)

    def open_position(self, symbol, date, price, signal):
        if symbol in self.positions:
            return
        if len(self.positions) >= self.cfg["max_positions"]:
            return
        stop   = price * (1 - self.cfg["stop_loss_pct"])
        shares = self.position_size(price, stop)
        if shares == 0:
            return
        cost = shares * price * (1 + self.cfg["commission"])
        if cost > self.cash:
            return
        self.cash -= cost
        self.positions[symbol] = {
            "shares":      shares,
            "entry_price": price,
            "entry_date":  date,
            "stop":        stop,
            "highest":     price,
            "cost":        cost,
            "signal":      signal,
        }

    def close_position(self, symbol, date, price, reason):
        if symbol not in self.positions:
            return
        pos      = self.positions.pop(symbol)
        proceeds = pos["shares"] * price * (1 - self.cfg["commission"])
        self.cash += proceeds
        pnl     = proceeds - pos["cost"]
        pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
        days    = (pd.Timestamp(date) - pd.Timestamp(pos["entry_date"])).days
        self.trades.append({
            "symbol":      symbol,
            "entry_date":  str(pos["entry_date"])[:10],
            "exit_date":   str(date)[:10],
            "entry_price": round(pos["entry_price"], 2),
            "exit_price":  round(price, 2),
            "shares":      pos["shares"],
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "days_held":   days,
            "reason":      reason,
            "contractions": pos["signal"].get("contractions", 0),
            "vol_ratio":   pos["signal"].get("vol_ratio", 0),
        })

    def update_stops(self, symbol, price, ma50):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        if price > pos["highest"]:
            pos["highest"] = price
        # Trailing Stop: أعلى من Stop الأصلي أو 10% من الذروة أو تحت MA50
        trail = pos["highest"] * (1 - self.cfg["trailing_stop_pct"])
        ma_stop = ma50 * 0.97
        pos["stop"] = max(pos["stop"], trail, ma_stop)

    def portfolio_value(self, prices):
        val = self.cash
        for sym, pos in self.positions.items():
            val += pos["shares"] * prices.get(sym, pos["entry_price"])
        return val

    def run(self, all_data, spy_data):
        print("🚀 بدء Backtest v3 — Minervini الأصلي...")
        print("📋 الشروط: Trend Template كامل + VCP 2+ + حجم 50%+ + Regime Filter\n")

        # حساب المؤشرات
        processed = {}
        for sym, df in all_data.items():
            processed[sym] = compute_indicators(df)

        # تقويم التداول
        all_dates = sorted(set().union(*[set(df.index) for df in processed.values()]))
        print(f"📅 أيام التداول: {len(all_dates)} | أسهم: {len(processed)}\n")

        regime_blocked_days = 0

        for date in all_dates:
            prices_today = {}
            market_ok = is_market_healthy(spy_data, date)

            if not market_ok:
                regime_blocked_days += 1

            # ١. تحديث المراكز الموجودة (نحافظ عليها حتى في السوق الهابط)
            for sym in list(self.positions.keys()):
                if sym not in processed or date not in processed[sym].index:
                    continue
                row   = processed[sym].loc[date]
                price = float(row['Close'])
                ma50  = float(row['MA50']) if not pd.isna(row['MA50']) else price
                prices_today[sym] = price

                self.update_stops(sym, price, ma50)
                pos = self.positions[sym]

                # Stop Loss
                if float(row['Low']) <= pos["stop"]:
                    exit_price = min(price, pos["stop"])
                    self.close_position(sym, date, exit_price, "stop_loss")
                    continue

                # Breakeven: بعد +10% نرفع Stop لنقطة الدخول
                pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
                if pnl_pct >= 0.10:
                    pos["stop"] = max(pos["stop"], pos["entry_price"] * 1.01)

            # ٢. البحث عن إشارات — فقط في السوق الصحي
            if market_ok and len(self.positions) < self.cfg["max_positions"]:
                for sym, df in processed.items():
                    if sym in self.positions or date not in df.index:
                        continue
                    idx = df.index.get_loc(date)
                    signal = check_entry_signal(df, idx)
                    if signal["valid"]:
                        price = float(df.loc[date, 'Close'])
                        self.open_position(sym, date, price, signal)
                        prices_today[sym] = price
                        if len(self.positions) >= self.cfg["max_positions"]:
                            break
            elif not market_ok and len(self.positions) < self.cfg["max_positions"]:
                self.skipped_regime += 1

            # ٣. منحنى الرأس المال
            pv = self.portfolio_value(prices_today)
            self.equity_curve.append({
                "date":            str(date)[:10],
                "portfolio_value": round(pv, 2),
                "cash":            round(self.cash, 2),
                "open_positions":  len(self.positions),
                "market_healthy":  market_ok,
            })

        # إغلاق نهاية الاختبار
        last_date = all_dates[-1]
        for sym in list(self.positions.keys()):
            if sym in processed and last_date in processed[sym].index:
                price = float(processed[sym].loc[last_date, 'Close'])
                self.close_position(sym, last_date, price, "end_of_test")

        print(f"🛡️  Regime Filter: حجب الشراء في {regime_blocked_days} يوم هابط\n")
        return self._compile_results()

    def _compile_results(self):
        if not self.trades:
            return {"error": "لا توجد صفقات — جرب توسيع قائمة الأسهم"}

        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)

        winners = trades_df[trades_df['pnl'] > 0]
        losers  = trades_df[trades_df['pnl'] <= 0]
        win_rate = len(winners) / len(trades_df) * 100 if len(trades_df) > 0 else 0

        avg_win  = winners['pnl_pct'].mean() if len(winners) else 0
        avg_loss = losers['pnl_pct'].mean()  if len(losers)  else 0
        rr_ratio = abs(avg_win / avg_loss)   if avg_loss != 0 else 0

        initial = self.cfg["initial_capital"]
        final   = equity_df['portfolio_value'].iloc[-1]
        total_return = (final - initial) / initial * 100

        equity_df['returns'] = equity_df['portfolio_value'].pct_change()
        std = equity_df['returns'].std()
        sharpe = (equity_df['returns'].mean() / std * np.sqrt(252)) if std > 0 else 0

        rolling_max = equity_df['portfolio_value'].cummax()
        max_dd = ((equity_df['portfolio_value'] - rolling_max) / rolling_max * 100).min()

        gross_profit = winners['pnl'].sum() if len(winners) else 0
        gross_loss   = abs(losers['pnl'].sum()) if len(losers) else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        spy_return = self._get_benchmark()

        # أيام السوق الهابط
        bad_days = equity_df[~equity_df['market_healthy']].shape[0]

        return {
            "version": "v3 — Minervini Original",
            "summary": {
                "period":          f"{self.cfg['start_date']} → {self.cfg['end_date']}",
                "initial_capital": f"${initial:,.0f}",
                "final_capital":   f"${final:,.0f}",
                "total_return":    f"{total_return:.1f}%",
                "spy_return":      f"{spy_return:.1f}%",
                "alpha":           f"{total_return - spy_return:.1f}%",
                "sharpe_ratio":    round(sharpe, 2),
                "max_drawdown":    f"{max_dd:.1f}%",
                "profit_factor":   round(profit_factor, 2),
                "bear_market_days": bad_days,
            },
            "trades": {
                "total":            len(trades_df),
                "winners":          len(winners),
                "losers":           len(losers),
                "win_rate":         f"{win_rate:.1f}%",
                "avg_win":          f"{avg_win:.1f}%",
                "avg_loss":         f"{avg_loss:.1f}%",
                "rr_ratio":         round(rr_ratio, 2),
                "avg_holding_days": round(trades_df['days_held'].mean(), 1),
                "best_trade":       f"{trades_df['pnl_pct'].max():.1f}%",
                "worst_trade":      f"{trades_df['pnl_pct'].min():.1f}%",
                "expectancy":       round((win_rate/100 * avg_win) + ((1-win_rate/100) * avg_loss), 2),
            },
            "exit_reasons":  trades_df['reason'].value_counts().to_dict(),
            "top_trades":    trades_df.nlargest(5, 'pnl')[
                ['symbol','entry_date','exit_date','pnl_pct','days_held','contractions','vol_ratio','reason']
            ].to_dict('records'),
            "worst_trades":  trades_df.nsmallest(5, 'pnl')[
                ['symbol','entry_date','exit_date','pnl_pct','days_held','reason']
            ].to_dict('records'),
            "raw_trades":    self.trades,
            "equity_curve":  self.equity_curve,
        }

    def _get_benchmark(self):
        try:
            spy = yf.download("SPY", start=self.cfg["start_date"],
                             end=self.cfg["end_date"], progress=False, auto_adjust=True)
            spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
            return (spy['Close'].iloc[-1] - spy['Close'].iloc[0]) / spy['Close'].iloc[0] * 100
        except:
            return 0.0

# ─── نقطة الدخول ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("  Minervini SEPA Backtesting Engine v3 — الأصل الحقيقي")
    print("=" * 65)
    print("  ✅ Trend Template 8 شروط كاملة")
    print("  ✅ VCP: 2+ تضيقات + حجم يجف 40%+")
    print("  ✅ اختراق بحجم 50%+ فوق المتوسط")
    print("  ✅ Market Regime Filter — SPY > MA200")
    print("  ✅ 100+ سهم من أفضل القطاعات")
    print("=" * 65 + "\n")

    # تحميل SPY للـ Regime Filter
    print("📥 تحميل SPY للـ Market Regime Filter...")
    try:
        spy_raw = yf.download("SPY", start=CONFIG["start_date"],
                             end=CONFIG["end_date"], progress=False, auto_adjust=True)
        spy_raw.columns = [c[0] if isinstance(c, tuple) else c for c in spy_raw.columns]
        spy_data = compute_indicators(spy_raw)
        print("  ✅ SPY جاهز\n")
    except:
        spy_data = None
        print("  ⚠️ فشل تحميل SPY — سيعمل بدون Regime Filter\n")

    # تحميل قائمة الأسهم
    data = load_data(WATCHLIST, CONFIG["start_date"], CONFIG["end_date"])

    # تشغيل الـ Backtest
    bt = MinerviniBacktestV3(CONFIG)
    results = bt.run(data, spy_data)

    # حفظ النتائج
    with open("backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # طباعة النتائج
    print("\n" + "=" * 65)
    print("  📊 نتائج v3 — Minervini الأصلي")
    print("=" * 65)

    s = results.get("summary", {})
    t = results.get("trades",  {})

    print(f"\n  💰 الأداء:")
    print(f"     الفترة:            {s.get('period')}")
    print(f"     رأس المال الأولي:  {s.get('initial_capital')}")
    print(f"     رأس المال النهائي: {s.get('final_capital')}")
    print(f"     العائد الكلي:      {s.get('total_return')}")
    print(f"     عائد S&P 500:     {s.get('spy_return')}")
    print(f"     Alpha:            {s.get('alpha')}")

    print(f"\n  📈 جودة الأداء:")
    print(f"     Sharpe Ratio:     {s.get('sharpe_ratio')}")
    print(f"     Max Drawdown:     {s.get('max_drawdown')}")
    print(f"     Profit Factor:    {s.get('profit_factor')}")
    print(f"     أيام السوق الهابط: {s.get('bear_market_days')}")

    print(f"\n  🎯 الصفقات:")
    print(f"     إجمالي:           {t.get('total')}")
    print(f"     Win Rate:         {t.get('win_rate')}")
    print(f"     متوسط الربح:      {t.get('avg_win')}")
    print(f"     متوسط الخسارة:    {t.get('avg_loss')}")
    print(f"     R:R Ratio:        {t.get('rr_ratio')}")
    print(f"     Expectancy:       {t.get('expectancy')}% لكل صفقة")
    print(f"     متوسط المدة:      {t.get('avg_holding_days')} يوم")
    print(f"     أفضل صفقة:        {t.get('best_trade')}")
    print(f"     أسوأ صفقة:        {t.get('worst_trade')}")

    print(f"\n  🏆 أفضل ٥ صفقات:")
    for tr in results.get("top_trades", []):
        print(f"     {tr['symbol']:6} | {tr['entry_date']} → {tr['exit_date']} | {tr['pnl_pct']:+.1f}% | {tr['days_held']}د | VCP:{tr['contractions']}")

    print(f"\n  ⚠️  أسوأ ٥ صفقات:")
    for tr in results.get("worst_trades", []):
        print(f"     {tr['symbol']:6} | {tr['entry_date']} → {tr['exit_date']} | {tr['pnl_pct']:+.1f}% | {tr['days_held']}د")

    print(f"\n  📤 أسباب الخروج:")
    for r, c in results.get("exit_reasons", {}).items():
        print(f"     {r:20} : {c}")

    print(f"\n  💾 النتائج محفوظة في: backtest_results.json")
    print("=" * 65)
