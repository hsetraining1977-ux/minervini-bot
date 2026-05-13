"""
Minervini SEPA Backtesting Engine v2
=====================================
تعديلات:
- تخفيف شروط VCP (contraction >= 1 بدل 2)
- تخفيف حجم الاختراق (1.2x بدل 1.5x)
- زيادة قائمة الأسهم
- تخفيف شرط القمة السنوية (30% بدل 25%)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

CONFIG = {
    "start_date":        "2020-01-01",
    "end_date":          "2024-12-31",
    "initial_capital":   100_000,
    "account_risk_pct":  0.0125,
    "stop_loss_pct":     0.07,
    "take_profit_pct":   0.20,
    "trailing_stop_pct": 0.10,
    "min_rr_ratio":      2.0,
    "max_positions":     8,         # زيادة من 6 إلى 8
    "commission":        0.001,
    # ── تعديلات VCP ──
    "vcp_min_contractions": 1,      # كان 2، الآن 1
    "vcp_volume_dry":    0.75,      # كان 0.6، الآن 0.75 (أقل صرامة)
    "breakout_volume":   1.2,       # كان 1.5، الآن 1.2
    "pct_from_high52":   0.30,      # كان 0.25، الآن 0.30
}

WATCHLIST = [
    # التكنولوجيا
    "NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "AVGO", "AMD", "ORCL", "TSM",
    # السيبراني والبرمجيات
    "CRWD", "PANW", "SNOW", "PLTR", "ARM", "ANET", "NOW", "DDOG", "ZS", "FTNT",
    "ADBE", "CRM", "INTU", "WDAY", "NFLX", "TTD", "BILL", "HUBS", "MDB", "NET",
    # النمو
    "TSLA", "UBER", "SHOP", "SQ", "ROKU", "DKNG", "ABNB", "DASH",
    # المالية
    "JPM", "GS", "V", "MA", "PYPL",
    # الصحة
    "UNH", "LLY", "ABBV", "ISRG", "DXCM",
    # الاستهلاكي والصناعي
    "COST", "WMT", "NKE", "CAT", "HON", "GE",
    # ETFs
    "SMH", "QQQ", "SOXX",
]

def load_data(symbols, start, end):
    data = {}
    print(f"📥 تحميل {len(symbols)} سهم...")
    for sym in symbols:
        try:
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
            if len(df) < 200:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df.index = pd.to_datetime(df.index)
            data[sym] = df
        except:
            pass
    print(f"  ✅ تم تحميل {len(data)} سهم\n")
    return data

def compute_indicators(df):
    df = df.copy()
    close = df['Close']
    df['MA10']  = close.rolling(10).mean()
    df['MA20']  = close.rolling(20).mean()
    df['MA50']  = close.rolling(50).mean()
    df['MA150'] = close.rolling(150).mean()
    df['MA200'] = close.rolling(200).mean()
    df['MA200_slope'] = df['MA200'].diff(20)
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Vol_ratio'] = df['Volume'] / df['Vol_MA20']
    df['High52w'] = close.rolling(252).max()
    df['Low52w']  = close.rolling(252).min()
    df['pct_from_high52'] = (close - df['High52w']) / df['High52w']
    df['pct_from_low52']  = (close - df['Low52w'])  / df['Low52w']
    df['BB_std'] = close.rolling(20).std()
    df['BB_width'] = df['BB_std'] / close.rolling(20).mean()
    return df

def check_trend_template(row):
    try:
        c = row['Close']
        return all([
            c > row['MA50'],
            c > row['MA150'],
            c > row['MA200'],
            row['MA50'] > row['MA150'],
            row['MA150'] > row['MA200'],
            row['MA200_slope'] > 0,
            row['pct_from_high52'] >= -CONFIG['pct_from_high52'],
            row['pct_from_low52']  >= 0.25,   # خفف من 0.30
        ])
    except:
        return False

def detect_vcp(df, idx, lookback=50):
    result = {"detected": False, "contractions": 0, "pivot": None, "vol_dry": False}
    if idx < lookback + 10:
        return result

    window = df.iloc[idx - lookback: idx]
    n_periods = 3
    period_len = lookback // n_periods
    ranges, vols = [], []

    for i in range(n_periods):
        seg = window.iloc[i * period_len: (i+1) * period_len]
        if len(seg) == 0:
            continue
        price_range = (seg['High'].max() - seg['Low'].min()) / seg['Close'].mean()
        ranges.append(price_range)
        vols.append(seg['Volume'].mean())

    if len(ranges) < 2:
        return result

    contractions = sum(1 for i in range(1, len(ranges)) if ranges[i] < ranges[i-1] * 0.90)
    vol_dry = vols[-1] < vols[0] * CONFIG['vcp_volume_dry'] if vols[0] > 0 else False

    recent = df.iloc[idx-15: idx]
    pivot = recent['High'].max()

    result.update({
        "detected":     contractions >= CONFIG['vcp_min_contractions'],
        "contractions": contractions,
        "pivot":        pivot,
        "vol_dry":      vol_dry,
    })
    return result

def check_entry_signal(df, idx):
    signal = {"valid": False, "reason": ""}
    if idx < 210:
        return signal

    row  = df.iloc[idx]
    prev = df.iloc[idx-1]

    if not check_trend_template(row):
        signal["reason"] = "trend_fail"
        return signal

    vcp = detect_vcp(df, idx)
    if not vcp["detected"]:
        signal["reason"] = "no_vcp"
        return signal

    pivot = vcp["pivot"]
    broke_pivot  = prev['Close'] <= pivot <= row['Close']
    volume_surge = row['Vol_ratio'] >= CONFIG['breakout_volume']

    if not broke_pivot:
        signal["reason"] = "no_breakout"
        return signal
    if not volume_surge:
        signal["reason"] = "low_volume"
        return signal

    signal.update({
        "valid": True, "pivot": pivot,
        "vol_ratio": round(row['Vol_ratio'], 2),
        "contractions": vcp["contractions"],
        "close": row['Close'],
    })
    return signal

class MinerviniBacktest:
    def __init__(self, config):
        self.cfg = config
        self.cash = config["initial_capital"]
        self.positions = {}
        self.trades = []
        self.equity_curve = []

    def position_size(self, price, stop):
        risk_per_share = price - stop
        if risk_per_share <= 0:
            return 0
        account_risk = self.cash * self.cfg["account_risk_pct"]
        shares = int(account_risk / risk_per_share)
        cost = shares * price * (1 + self.cfg["commission"])
        max_cost = self.cash * 0.20
        if cost > max_cost:
            shares = int(max_cost / (price * (1 + self.cfg["commission"])))
        return max(shares, 0)

    def open_position(self, symbol, date, price, signal):
        if symbol in self.positions or len(self.positions) >= self.cfg["max_positions"]:
            return
        stop = price * (1 - self.cfg["stop_loss_pct"])
        shares = self.position_size(price, stop)
        if shares == 0:
            return
        cost = shares * price * (1 + self.cfg["commission"])
        if cost > self.cash:
            return
        self.cash -= cost
        self.positions[symbol] = {
            "shares": shares, "entry_price": price,
            "entry_date": date, "stop": stop,
            "highest": price, "cost": cost,
        }

    def close_position(self, symbol, date, price, reason):
        if symbol not in self.positions:
            return
        pos = self.positions.pop(symbol)
        proceeds = pos["shares"] * price * (1 - self.cfg["commission"])
        self.cash += proceeds
        pnl = proceeds - pos["cost"]
        pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
        days = (pd.Timestamp(date) - pd.Timestamp(pos["entry_date"])).days
        self.trades.append({
            "symbol": symbol,
            "entry_date": str(pos["entry_date"])[:10],
            "exit_date": str(date)[:10],
            "entry_price": round(pos["entry_price"], 2),
            "exit_price": round(price, 2),
            "shares": pos["shares"],
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "days_held": days,
            "reason": reason,
        })

    def update_stops(self, symbol, current_price, ma50):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        if current_price > pos["highest"]:
            pos["highest"] = current_price
        trail = pos["highest"] * (1 - self.cfg["trailing_stop_pct"])
        ma50_stop = ma50 * 0.97
        pos["stop"] = max(pos["stop"], trail, ma50_stop)

    def portfolio_value(self, prices):
        val = self.cash
        for sym, pos in self.positions.items():
            val += pos["shares"] * prices.get(sym, pos["entry_price"])
        return val

    def run(self, all_data):
        print("🚀 بدء الـ Backtest v2...")
        processed = {sym: compute_indicators(df) for sym, df in all_data.items()}
        all_dates = sorted(set().union(*[set(df.index) for df in processed.values()]))
        print(f"📅 أيام التداول: {len(all_dates)} | أسهم: {len(processed)}\n")

        for date in all_dates:
            prices_today = {}

            for sym in list(self.positions.keys()):
                if sym not in processed or date not in processed[sym].index:
                    continue
                row = processed[sym].loc[date]
                price = float(row['Close'])
                ma50 = float(row['MA50']) if not pd.isna(row['MA50']) else price
                prices_today[sym] = price
                self.update_stops(sym, price, ma50)
                pos = self.positions[sym]
                if float(row['Low']) <= pos["stop"]:
                    self.close_position(sym, date, min(price, pos["stop"]), "stop_loss")
                    continue
                pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
                if pnl_pct >= self.cfg["take_profit_pct"]:
                    pos["stop"] = max(pos["stop"], pos["entry_price"] * 1.08)

            if len(self.positions) < self.cfg["max_positions"]:
                for sym, df in processed.items():
                    if sym in self.positions or date not in df.index:
                        continue
                    idx = df.index.get_loc(date)
                    if idx < 210:
                        continue
                    signal = check_entry_signal(df, idx)
                    if signal["valid"]:
                        price = float(df.loc[date, 'Close'])
                        self.open_position(sym, date, price, signal)
                        prices_today[sym] = price

            pv = self.portfolio_value(prices_today)
            self.equity_curve.append({
                "date": str(date)[:10],
                "portfolio_value": round(pv, 2),
                "cash": round(self.cash, 2),
                "open_positions": len(self.positions),
            })

        last_date = all_dates[-1]
        for sym in list(self.positions.keys()):
            if sym in processed and last_date in processed[sym].index:
                price = float(processed[sym].loc[last_date, 'Close'])
                self.close_position(sym, last_date, price, "end_of_test")

        return self._compile_results()

    def _compile_results(self):
        if not self.trades:
            return {"error": "لا توجد صفقات"}

        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)

        winners = trades_df[trades_df['pnl'] > 0]
        losers  = trades_df[trades_df['pnl'] <= 0]
        win_rate = len(winners) / len(trades_df) * 100

        avg_win  = winners['pnl_pct'].mean() if len(winners) else 0
        avg_loss = losers['pnl_pct'].mean()  if len(losers)  else 0
        rr_ratio = abs(avg_win / avg_loss)   if avg_loss != 0 else 0

        initial = self.cfg["initial_capital"]
        final   = equity_df['portfolio_value'].iloc[-1]
        total_return = (final - initial) / initial * 100

        equity_df['returns'] = equity_df['portfolio_value'].pct_change()
        daily_std = equity_df['returns'].std()
        sharpe = (equity_df['returns'].mean() / daily_std * np.sqrt(252)) if daily_std > 0 else 0

        rolling_max = equity_df['portfolio_value'].cummax()
        max_dd = ((equity_df['portfolio_value'] - rolling_max) / rolling_max * 100).min()

        gross_profit = winners['pnl'].sum() if len(winners) else 0
        gross_loss   = abs(losers['pnl'].sum()) if len(losers) else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        spy_return = self._get_benchmark()

        return {
            "summary": {
                "period": f"{self.cfg['start_date']} → {self.cfg['end_date']}",
                "initial_capital": f"${initial:,.0f}",
                "final_capital":   f"${final:,.0f}",
                "total_return":    f"{total_return:.1f}%",
                "spy_return":      f"{spy_return:.1f}%",
                "alpha":           f"{total_return - spy_return:.1f}%",
                "sharpe_ratio":    round(sharpe, 2),
                "max_drawdown":    f"{max_dd:.1f}%",
                "profit_factor":   round(profit_factor, 2),
            },
            "trades": {
                "total": len(trades_df),
                "winners": len(winners),
                "losers": len(losers),
                "win_rate": f"{win_rate:.1f}%",
                "avg_win":  f"{avg_win:.1f}%",
                "avg_loss": f"{avg_loss:.1f}%",
                "rr_ratio": round(rr_ratio, 2),
                "avg_holding_days": round(trades_df['days_held'].mean(), 1),
                "best_trade":  f"{trades_df['pnl_pct'].max():.1f}%",
                "worst_trade": f"{trades_df['pnl_pct'].min():.1f}%",
            },
            "exit_reasons": trades_df['reason'].value_counts().to_dict(),
            "top_trades": trades_df.nlargest(5, 'pnl')[
                ['symbol','entry_date','exit_date','pnl_pct','days_held','reason']
            ].to_dict('records'),
            "raw_trades":   self.trades,
            "equity_curve": self.equity_curve,
        }

    def _get_benchmark(self):
        try:
            spy = yf.download("SPY", start=self.cfg["start_date"],
                              end=self.cfg["end_date"], progress=False, auto_adjust=True)
            spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
            return (spy['Close'].iloc[-1] - spy['Close'].iloc[0]) / spy['Close'].iloc[0] * 100
        except:
            return 0.0

if __name__ == "__main__":
    print("=" * 60)
    print("  Minervini SEPA Backtesting Engine v2")
    print("=" * 60)

    data = load_data(WATCHLIST, CONFIG["start_date"], CONFIG["end_date"])
    bt = MinerviniBacktest(CONFIG)
    results = bt.run(data)

    with open("backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("  📊 نتائج الـ Backtest v2")
    print("=" * 60)

    s = results.get("summary", {})
    t = results.get("trades",  {})

    print(f"\n  💰 الأداء:")
    print(f"     الفترة:           {s.get('period')}")
    print(f"     رأس المال الأولي:  {s.get('initial_capital')}")
    print(f"     رأس المال النهائي: {s.get('final_capital')}")
    print(f"     العائد الكلي:      {s.get('total_return')}")
    print(f"     عائد S&P 500:     {s.get('spy_return')}")
    print(f"     Alpha:            {s.get('alpha')}")
    print(f"\n  📈 الجودة:")
    print(f"     Sharpe Ratio:     {s.get('sharpe_ratio')}")
    print(f"     Max Drawdown:     {s.get('max_drawdown')}")
    print(f"     Profit Factor:    {s.get('profit_factor')}")
    print(f"\n  🎯 الصفقات:")
    print(f"     إجمالي:           {t.get('total')}")
    print(f"     Win Rate:         {t.get('win_rate')}")
    print(f"     متوسط الربح:      {t.get('avg_win')}")
    print(f"     متوسط الخسارة:    {t.get('avg_loss')}")
    print(f"     R:R Ratio:        {t.get('rr_ratio')}")
    print(f"     أفضل صفقة:        {t.get('best_trade')}")
    print(f"\n  🏆 أفضل ٥ صفقات:")
    for tr in results.get("top_trades", []):
        print(f"     {tr['symbol']:6} | {tr['entry_date']} → {tr['exit_date']} | {tr['pnl_pct']:+.1f}% | {tr['days_held']} يوم")
    print(f"\n  📤 أسباب الخروج:")
    for r, c in results.get("exit_reasons", {}).items():
        print(f"     {r:20} : {c}")
    print("=" * 60)
