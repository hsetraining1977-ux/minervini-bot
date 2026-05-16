from decision_engine import get_buy_decision
from rs_rating import filter_by_rs
from config import ALPACA_KEY, ALPACA_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime, time as dtime
import time
import requests
import pytz

trading_client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

STARTER_PCT = 0.05
STOP_LOSS_PCT = 0.07
STOP_LOSS_CRYPTO = 0.10
VOLUME_THRESHOLD = 1.5
MAX_STOCKS = 8
SCALE_UP_PCT = 0.08
CHECK_INTERVAL = 300
ACCOUNT_RISK_PCT = 0.0125
MIN_SMART_SCORE = 3

WATCHLIST = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","TSM","AVGO",
    "AMD","ORCL","CRWD","PANW","SNOW","PLTR","ARM","ANET",
    "NOW","DDOG","ZS","FTNT","ADBE","CRM","INTU","WDAY",
    "NFLX","TTD","TSLA","UBER","JPM","GS","V","MA",
    "UNH","LLY","ABBV","XOM","CVX","COST","WMT","NKE",
    "CAT","HON","GE","LMT","SMH","QQQ","SOXX","XLK","ARKK"
]

CRYPTO_LIST = ["BTC-USD","ETH-USD"]
performance_log = {"wins": 0, "losses": 0, "consecutive_losses": 0}
traded_today = []

def send_telegram(message):
    try:
        url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("[TG] sent")
    except Exception as e:
        print("[TG] error: " + str(e))

def is_market_open():
    ny = pytz.timezone('America/New_York')
    now = datetime.now(ny)
    if now.weekday() >= 5:
        return False
    return dtime(9, 30) <= now.time() <= dtime(16, 0)

def get_account():
    account = trading_client.get_account()
    return float(account.cash), float(account.portfolio_value), trading_client.get_all_positions()

def get_exposure_level(losses):
    if losses <= 2:
        return "NORMAL", STARTER_PCT
    elif losses <= 4:
        return "REDUCED", STARTER_PCT * 0.5
    elif losses <= 6:
        return "MINIMAL", STARTER_PCT * 0.25
    else:
        return "CASH", 0

def calc_position_size(portfolio, stop_pct):
    risk_amount = portfolio * ACCOUNT_RISK_PCT
    position_size = risk_amount / stop_pct
    return min(position_size, portfolio * 0.25)

def smart_money_score(symbol):
    score = 0
    details = []
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        eps = info.get('earningsGrowth', 0)
        rev = info.get('revenueGrowth', 0)
        margin = info.get('profitMargins', 0)
        if eps and eps > 0.25:
            score += 2
            details.append("EPS " + str(round(eps*100,1)) + "%")
        if rev and rev > 0.20:
            score += 2
            details.append("Rev " + str(round(rev*100,1)) + "%")
        if margin and margin > 0.10:
            score += 1
            details.append("Margin " + str(round(margin*100,1)) + "%")
        inst = ticker.institutional_holders
        if inst is not None and not inst.empty:
            pct = inst.head(10)['% Out'].sum()
            if pct > 30:
                score += 1
                details.append("Inst " + str(round(pct,1)) + "%")
    except:
        pass
    return score, details

def check_options_activity(symbol):
    try:
        ticker = yf.Ticker(symbol)
        options_dates = ticker.options
        if not options_dates:
            return False, 0
        nearest = options_dates[0]
        chain = ticker.option_chain(nearest)
        calls = chain.calls
        puts = chain.puts
        if calls.empty or puts.empty:
            return False, 0
        call_vol = calls['volume'].sum()
        put_vol = puts['volume'].sum()
        if put_vol == 0:
            return False, 0
        pc_ratio = put_vol / call_vol
        unusual_calls = call_vol > calls['openInterest'].sum() * 0.5
        bullish = pc_ratio < 0.7 and unusual_calls
        return bullish, round(pc_ratio, 2)
    except:
        return False, 0

def check_short_interest(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        short_pct = info.get('shortPercentOfFloat', 0)
        if short_pct and short_pct > 0.20:
            return True, short_pct
        return False, short_pct
    except:
        return False, 0

def check_unusual_volume(symbol, avg_vol):
    try:
        ticker = yf.Ticker(symbol)
        bars = ticker.history(period="5d")
        if bars.empty:
            return False, 0
        vol_today = bars['Volume'].iloc[-1]
        vol_ratio = vol_today / avg_vol if avg_vol > 0 else 0
        return vol_ratio > 2.0, round(vol_ratio, 1)
    except:
        return False, 0

def check_trend_template(symbol):
    try:
        ticker = yf.Ticker(symbol)
        bars = ticker.history(period="300d")
        if bars.empty or len(bars) < 200:
            return False, {}
        close = bars['Close']
        volume = bars['Volume']
        ma50 = close.rolling(50).mean().iloc[-1]
        ma150 = close.rolling(150).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        ma200_old = close.rolling(200).mean().iloc[-22]
        price = close.iloc[-1]
        high52 = close.tail(252).max()
        low52 = close.tail(252).min()
        avg_vol = volume.rolling(50).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol
        above_low = (price - low52) / low52
        below_high = (high52 - price) / high52
        conditions = [
            price > ma50,
            price > ma150,
            price > ma200,
            ma50 > ma150,
            ma150 > ma200,
            ma200 > ma200_old,
            above_low >= 0.30,
            below_high <= 0.25,
        ]
        data = {
            "price": price,
            "vol_ratio": vol_ratio,
            "avg_vol": avg_vol,
            "stop_price": price * (1 - STOP_LOSS_PCT),
        }
        return all(conditions), data
    except Exception as e:
        print("TT error " + symbol + ": " + str(e))
        return False, {}

def check_vcp(symbol):
    try:
        ticker = yf.Ticker(symbol)
        bars = ticker.history(period="120d")
        if bars.empty or len(bars) < 60:
            return False
        close = bars['Close']
        high = bars['High']
        low = bars['Low']
        volume = bars['Volume']
        avg_vol = volume.rolling(50).mean().iloc[-1]
        recent_vol = volume.tail(5).mean()
        vol_dry = recent_vol < avg_vol * 0.7
        recent_range = (high.tail(10).max() - low.tail(10).min()) / close.tail(10).mean()
        mid_range = (high.tail(30).iloc[:20].max() - low.tail(30).iloc[:20].min()) / close.tail(30).iloc[:20].mean()
        early_range = (high.tail(60).iloc[:30].max() - low.tail(60).iloc[:30].min()) / close.tail(60).iloc[:30].mean()
        contracting = recent_range < mid_range * 0.7 and mid_range < early_range * 0.8
        tight = recent_range < 0.06
        return contracting and tight and vol_dry
    except:
        return False

def check_breakout(symbol, avg_vol):
    try:
        ticker = yf.Ticker(symbol)
        bars = ticker.history(period="60d")
        if bars.empty:
            return False
        close = bars['Close']
        volume = bars['Volume']
        high_20d = close.tail(20).iloc[:-1].max()
        price = close.iloc[-1]
        vol_surge = volume.iloc[-1] > avg_vol * VOLUME_THRESHOLD
        return price > high_20d and vol_surge
    except:
        return False

def monitor_positions(positions):
    for pos in positions:
        symbol = pos.symbol
        entry = float(pos.avg_entry_price)
        current = float(pos.current_price)
        qty = float(pos.qty)
        pl_pct = (current - entry) / entry * 100
        is_crypto = symbol in CRYPTO_LIST
        stop_pct = STOP_LOSS_CRYPTO if is_crypto else STOP_LOSS_PCT
        stop = entry * (1 - stop_pct)
        print("  " + symbol + " $" + str(round(current,2)) +
              " PL:" + str(round(pl_pct,1)) + "%" +
              " Stop:$" + str(round(stop,2)))
        if current <= stop:
            send_telegram("STOP LOSS\n" + symbol +
                          "\nPrice: $" + str(round(current,2)) +
                          "\nLoss: " + str(round(pl_pct,1)) + "%")
            try:
                trading_client.submit_order(MarketOrderRequest(
                    symbol=symbol,
                    qty=int(qty) if not is_crypto else qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC if is_crypto else TimeInForce.DAY
                ))
                performance_log["losses"] += 1
                performance_log["consecutive_losses"] += 1
                send_telegram("Sold " + symbol)
                print("  SOLD: " + symbol)
            except Exception as e:
                send_telegram("SELL FAILED " + symbol + ": " + str(e))
        elif pl_pct >= 10:
            send_telegram("Move stop to breakeven!\n" + symbol +
                          " +" + str(round(pl_pct,1)) + "%")
        elif pl_pct >= SCALE_UP_PCT * 100:
            send_telegram("Profit!\n" + symbol +
                          " +" + str(round(pl_pct,1)) + "%")

def scan_crypto(open_symbols, portfolio, num_positions):
    for symbol in CRYPTO_LIST:
        if symbol in open_symbols or num_positions >= MAX_STOCKS:
            continue
        try:
            ticker = yf.Ticker(symbol)
            bars = ticker.history(period="200d")
            if bars.empty or len(bars) < 100:
                continue
            close = bars['Close']
            volume = bars['Volume']
            ma50 = close.rolling(50).mean().iloc[-1]
            ma100 = close.rolling(100).mean().iloc[-1]
            ma200 = close.rolling(200).mean().iloc[-1]
            price = close.iloc[-1]
            high20 = close.tail(20).iloc[:-1].max()
            avg_vol = volume.rolling(50).mean().iloc[-1]
            vol_ratio = volume.iloc[-1] / avg_vol
            low52 = close.tail(365).min()
            high52 = close.tail(365).max()
            above_low = (price - low52) / low52
            below_high = (high52 - price) / high52
            conditions = [
                price > ma50,
                price > ma100,
                price > ma200,
                ma50 > ma100,
                ma100 > ma200,
                above_low >= 0.30,
                below_high <= 0.30,
            ]
            if all(conditions):
                breakout = price > high20 and vol_ratio >= 1.4
                stop_price = price * (1 - STOP_LOSS_CRYPTO)
                pos_size = calc_position_size(portfolio, STOP_LOSS_CRYPTO)
                if breakout:
                    send_telegram("Crypto Opportunity!\n" + symbol +
                                  "\nPrice: $" + str(round(price,2)) +
                                  "\nVol: " + str(round(vol_ratio,1)) + "x" +
                                  "\nStop: $" + str(round(stop_price,2)))
                    try:
                        trading_client.submit_order(MarketOrderRequest(
                            symbol=symbol,
                            notional=str(round(pos_size,2)),
                            side=OrderSide.BUY,
                            time_in_force=TimeInForce.GTC
                        ))
                        traded_today.append(symbol)
                        performance_log["consecutive_losses"] = 0
                        send_telegram("Bought Crypto!\n" + symbol +
                                      "\nValue: $" + str(round(pos_size,2)))
                        num_positions += 1
                    except Exception as e:
                        send_telegram("Crypto BUY FAILED: " + str(e))
        except Exception as e:
            print("Crypto error: " + str(e))

def run_scan(scan_count):
    now = datetime.now()
    market_open = is_market_open()
    status = "OPEN" if market_open else "CLOSED"
    print("")
    print("=" * 55)
    print("Scan #" + str(scan_count) + " | " + now.strftime("%Y-%m-%d %H:%M") + " | " + status)
    print("=" * 55)

    cash, portfolio, positions = get_account()
    open_symbols = [p.symbol for p in positions]
    level, pct = get_exposure_level(performance_log["consecutive_losses"])

    msg = ("Scan #" + str(scan_count) + " | " + status + "\n" +
           "Portfolio: $" + str(round(portfolio,2)) + "\n" +
           "Cash: $" + str(round(cash,2)) + "\n" +
           "Positions: " + str(len(positions)) + "/" + str(MAX_STOCKS) + "\n" +
           "Exposure: " + level + "\n" +
           "Wins: " + str(performance_log["wins"]) +
           " | Losses: " + str(performance_log["losses"]))
    send_telegram(msg)

    if level == "CASH":
        send_telegram("WARNING: CASH mode")
        return

    if positions:
        print("Monitoring positions:")
        monitor_positions(positions)

    scan_crypto(open_symbols, portfolio, len(positions))

    if not market_open:
        print("Market CLOSED")
        return

    if len(positions) >= MAX_STOCKS:
        send_telegram("Max positions reached")
        return

    print("Scanning " + str(len(WATCHLIST)) + " stocks...")
    opportunities = []
    watching = []

    for symbol in WATCHLIST:
        if symbol in open_symbols or symbol in traded_today:
            continue
        qualified, data = check_trend_template(symbol)
        if not qualified:
            continue
        score, details = smart_money_score(symbol)
        if score < MIN_SMART_SCORE:
            continue
        is_vcp = check_vcp(symbol)
        bullish_options, pc_ratio = check_options_activity(symbol)
        high_short, short_pct = check_short_interest(symbol)
        unusual_vol, vol_ratio = check_unusual_volume(symbol, data['avg_vol'])
        if is_vcp:
            breakout = check_breakout(symbol, data['avg_vol'])
            if breakout:
                bonus = ""
                if bullish_options:
                    bonus += " Options Bullish"
                if high_short:
                    bonus += " Short Squeeze"
                if unusual_vol:
                    bonus += " Unusual Vol " + str(vol_ratio) + "x"
                opportunities.append((symbol, data, score, details, bonus))
                print("OPPORTUNITY: " + symbol +
                      " Score:" + str(score) + "/6" + bonus)
            else:
                watching.append(symbol + " $" + str(round(data['price'],2)) +
                                " VCP Score:" + str(score))
        else:
            watching.append(symbol + " $" + str(round(data['price'],2)) +
                            " Score:" + str(score))


    if opportunities:
        msg = "ENTRY OPPORTUNITY!\n\n"
        for symbol, data, score, details, bonus in opportunities:
            pos_size = calc_position_size(portfolio, STOP_LOSS_PCT)
            shares = int(pos_size / data['price'])
            msg += (symbol + " Score:" + str(score) + "/6\n" +
                    "Price: $" + str(round(data['price'],2)) + "\n" +
                    "Shares: " + str(shares) + "\n" +
                    "Stop: $" + str(round(data['stop_price'],2)) + "\n" +
                    ", ".join(details) + "\n" +
                    bonus + "\n\n")
        send_telegram(msg)

        for symbol, data, score, details, bonus in opportunities:
            if len(positions) >= MAX_STOCKS:
                break
            pos_size = calc_position_size(portfolio, STOP_LOSS_PCT)
            shares = int(pos_size / data['price'])
            if shares < 1:
                continue
            try:
                trading_client.submit_order(MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                ))
                performance_log["consecutive_losses"] = 0
                traded_today.append(symbol)
                send_telegram("Bought!\n" + symbol +
                              " x" + str(shares) +
                              " @$" + str(round(data["price"],2)) + "\nStop: $" + str(round(data["stop_price"],2)) +
                              "\nScore: " + str(score) + "/6")
                print("BOUGHT: " + str(shares) + " " + symbol)
            except Exception as e:
                send_telegram("BUY FAILED " + symbol + ": " + str(e))
    else:
        print("No opportunities")

send_telegram("SEPA + Smart Money System!\n" +
              "Scanning " + str(len(WATCHLIST)) + " stocks\n" +
              "Trend + VCP + Fundamentals\n" +
              "Options + Short Interest\n" +
              "Account Risk: 1.25%")
print("SEPA + Smart Money Running")

scan_count = 0
while True:
    try:
        scan_count += 1
        if datetime.now().hour == 0 and datetime.now().minute < 5:
            traded_today.clear()
        run_scan(scan_count)
        time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        send_telegram("System stopped")
        break
    except Exception as e:
        print("Error: " + str(e))
        send_telegram("Error: " + str(e))
        time.sleep(60)
