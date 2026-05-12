import json, os, requests
DATA_DIR = "/root/logs"

def _load(p, d={}):
    try:
        if os.path.exists(p):
            with open(p) as f: return json.load(f)
    except: pass
    return d

def portfolio_check(symbol, qty, price):
    heat = _load(f"{DATA_DIR}/portfolio_heat.json")
    heat_pct = float(heat.get("portfolio_heat_pct", 0))
    positions = heat.get("positions", [])
    port_val = float(heat.get("portfolio_value", 50000))
    SECTOR_MAP = {"NVDA":"Tech","AMD":"Tech","MSFT":"Tech","AAPL":"Tech","GOOGL":"Tech","META":"Tech","SMCI":"Tech","AVGO":"Tech","ARM":"Tech","TSLA":"Tech","LLY":"Health","UNH":"Health","JPM":"Fin","GS":"Fin","V":"Fin","MA":"Fin","BTCUSD":"Crypto","ETHUSD":"Crypto"}
    CORR = {"Semi":["NVDA","AMD","SMCI","AVGO","MRVL","ARM"],"MegaTech":["AAPL","MSFT","GOOGL","META"],"Crypto":["BTCUSD","ETHUSD"]}
    sector = SECTOR_MAP.get(symbol, "Other")
    sector_exp = float(heat.get("sector_exposure", {}).get(sector, 0))
    existing = [p.get("symbol","") for p in positions]
    corr_count = sum(1 for g,m in CORR.items() if symbol in m for s in existing if s in m)
    new_weight = qty * price / port_val * 100 if port_val else 0
    if heat_pct > 5.4: return False, 0.0, f"Heat {heat_pct:.1f}% BLOCKED"
    if symbol in existing: return False, 0.0, f"{symbol} already in portfolio"
    if corr_count >= 2: return False, 0.0, f"Correlation limit: {corr_count} similar positions"
    mult = 1.0
    reasons = []
    if sector_exp > 35: mult *= 0.5; reasons.append(f"Sector {sector_exp:.0f}%>35%")
    if new_weight > 15: mult *= 0.6; reasons.append(f"Weight {new_weight:.0f}%>15%")
    if heat_pct > 4.2: mult *= 0.7; reasons.append(f"Heat {heat_pct:.1f}%>70%")
    if corr_count == 1: mult *= 0.75; reasons.append("1 corr position")
    mult = round(max(0.25, min(1.0, mult)), 2)
    return True, mult, " | ".join(reasons) or "OK"
