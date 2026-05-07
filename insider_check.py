import yfinance as yf
from datetime import datetime, timedelta

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
            details.append("Revenue " + str(round(rev*100,1)) + "%")
        if margin and margin > 0.10:
            score += 1
            details.append("Margin " + str(round(margin*100,1)) + "%")
        inst = ticker.institutional_holders
        if inst is not None and not inst.empty:
            pct = inst.head(10)['% Out'].sum()
            if pct > 30:
                score += 1
                details.append("Institutional " + str(round(pct,1)) + "%")
    except:
        pass
    return score, details

symbols = ["NVDA","GOOGL","TSM","AMD","AVGO"]
print("Smart Money Analysis")
print("=" * 40)
for s in symbols:
    score, details = smart_money_score(s)
    print(s + " Score:" + str(score) + "/6")
    for d in details:
        print("  + " + d)
