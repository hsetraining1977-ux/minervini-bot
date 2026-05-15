"""
reliability_layer.py
RELIABILITY & SAFETY LAYER
Minervini Bot — PAPER TRADING ONLY
- Duplicate trade protection
- API safety with retry/backoff
- Stale data detection
- Position reconciliation
- Risk emergency mode
"""

import json, os, time, datetime, logging, requests
sys.path = __import__("sys").path
import sys
sys.path.insert(0, "/root")

log = logging.getLogger("reliability")
DATA_DIR   = "/root/logs"
PAPER_ONLY = True

# ── Config ────────────────────────────────────────────────────────────────────
STALE_DATA_MINS = 15     # block if data older than 5 min
DUPLICATE_WINDOW_HRS = 24    # no same symbol within 24hrs
MAX_DRAWDOWN_PCT      = 5.0  # emergency at 5% drawdown
CONSECUTIVE_LOSSES    = 3    # emergency after 3 losses
VIX_EMERGENCY         = 35   # emergency if VIX > 35
PORTFOLIO_VALUE       = 50_000.0

def _load(path, default={}):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save error: {e}")

def _tg(msg: str):
    try:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=8
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# 1. DUPLICATE TRADE PROTECTION
# ══════════════════════════════════════════════════════════════════════════════
TRADE_LOG_FILE = f"{DATA_DIR}/trade_log_today.json"

def is_duplicate_trade(symbol: str, direction: str = "LONG") -> tuple:
    """Check if symbol was traded recently. Returns (is_dup, reason)."""
    today = datetime.date.today().isoformat()
    log_data = _load(TRADE_LOG_FILE, {"date": today, "trades": []})

    # Reset if new day
    if log_data.get("date") != today:
        log_data = {"date": today, "trades": []}
        _save(TRADE_LOG_FILE, log_data)

    now    = datetime.datetime.now()
    window = datetime.timedelta(hours=DUPLICATE_WINDOW_HRS)

    for trade in log_data.get("trades", []):
        if trade.get("symbol") != symbol:
            continue
        if trade.get("direction") != direction:
            continue
        trade_time = datetime.datetime.fromisoformat(trade.get("timestamp", "2000-01-01"))
        if now - trade_time < window:
            return True, f"{symbol} already traded at {trade_time.strftime('%H:%M')} today"

    return False, ""

def log_trade_execution(symbol: str, direction: str = "LONG", entry: float = 0):
    """Record trade execution to prevent duplicates."""
    today    = datetime.date.today().isoformat()
    log_data = _load(TRADE_LOG_FILE, {"date": today, "trades": []})

    if log_data.get("date") != today:
        log_data = {"date": today, "trades": []}

    log_data["trades"].append({
        "symbol":    symbol,
        "direction": direction,
        "entry":     entry,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    _save(TRADE_LOG_FILE, log_data)
    log.info(f"[DupProtect] Logged: {symbol} {direction} @ {entry}")

# ══════════════════════════════════════════════════════════════════════════════
# 2. API SAFETY LAYER — retry + exponential backoff
# ══════════════════════════════════════════════════════════════════════════════
def safe_alpaca_get(endpoint: str, max_retries: int = 3) -> dict:
    """Alpaca GET with retry and exponential backoff."""
    from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    base = "https://paper-api.alpaca.markets"
    for attempt in range(max_retries):
        try:
            r = requests.get(f"{base}{endpoint}", headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            log.warning(f"API {endpoint} → {r.status_code} (attempt {attempt+1})")
        except requests.exceptions.ConnectionError:
            log.error(f"API connection failed (attempt {attempt+1})")
            _tg(f"⚠️ *API OUTAGE* attempt {attempt+1}/{max_retries}\n`{endpoint}`")
        except Exception as e:
            log.error(f"API error: {e}")

        wait = (2 ** attempt) * 1.5   # 1.5s, 3s, 6s
        log.info(f"Retrying in {wait:.0f}s...")
        time.sleep(wait)

    # Fail-safe mode
    log.error(f"API FAILED after {max_retries} attempts: {endpoint}")
    _tg(f"🔴 *API OUTAGE — FAIL-SAFE MODE*\n`{endpoint}` failed {max_retries}x\n⚠️ PAPER ONLY")
    _activate_fail_safe("API outage")
    return {}

def safe_alpaca_post(endpoint: str, payload: dict, max_retries: int = 3) -> dict:
    """Alpaca POST with retry and exponential backoff."""
    from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Content-Type":        "application/json",
    }
    base = "https://paper-api.alpaca.markets"
    for attempt in range(max_retries):
        try:
            r = requests.post(f"{base}{endpoint}", headers=headers,
                              json=payload, timeout=10)
            if r.status_code in (200, 201):
                return r.json()
            log.warning(f"POST {endpoint} → {r.status_code}: {r.text[:100]}")
            if r.status_code in (400, 422):
                return r.json()   # don't retry client errors
        except Exception as e:
            log.error(f"POST error: {e}")

        wait = (2 ** attempt) * 1.5
        time.sleep(wait)

    return {}

def _activate_fail_safe(reason: str):
    """Activate fail-safe mode (blocks aggressive entries)."""
    state = _load(f"{DATA_DIR}/emergency_mode.json", {})
    state["fail_safe"]  = True
    state["reason"]     = reason
    state["activated_at"] = datetime.datetime.now().isoformat()
    _save(f"{DATA_DIR}/emergency_mode.json", state)

# ══════════════════════════════════════════════════════════════════════════════
# 3. STALE DATA DETECTION
# ══════════════════════════════════════════════════════════════════════════════
def check_data_freshness() -> tuple:
    """
    Check if market data is fresh enough for trading.
    Returns (is_fresh, age_minutes, reason).
    """
    mi_path = f"{DATA_DIR}/market_intelligence.json"
    if not os.path.exists(mi_path):
        return False, 999, "market_intelligence.json not found"

    mtime       = os.path.getmtime(mi_path)
    age_mins    = (time.time() - mtime) / 60

    if age_mins > STALE_DATA_MINS:
        msg = f"Market data stale: {age_mins:.1f} min > {STALE_DATA_MINS} min limit"
        log.warning(msg)
        _tg(f"⚠️ *STALE DATA DETECTED*\nAge: `{age_mins:.1f}` min\nExecution BLOCKED\n⚠️ PAPER ONLY")
        return False, round(age_mins, 1), msg

    return True, round(age_mins, 1), "Data fresh"

# ══════════════════════════════════════════════════════════════════════════════
# 4. POSITION RECONCILIATION
# ══════════════════════════════════════════════════════════════════════════════
def reconcile_positions() -> dict:
    """
    Compare Alpaca positions vs local JSON.
    Alert and sync on mismatch.
    PAPER TRADING ONLY.
    """
    # Alpaca live positions
    alpaca_data  = safe_alpaca_get("/v2/positions")
    alpaca_syms  = set()
    if isinstance(alpaca_data, list):
        alpaca_syms = {p.get("symbol", "") for p in alpaca_data}

    # Local positions
    local_trades = _load(f"{DATA_DIR}/paper_trades.json", {})
    local_syms   = set()
    for tid, t in local_trades.items():
        if t.get("status") in ("ACTIVE", "PARTIAL"):
            local_syms.add(t.get("symbol", ""))

    in_alpaca_not_local = alpaca_syms - local_syms
    in_local_not_alpaca = local_syms - alpaca_syms
    mismatches          = bool(in_alpaca_not_local or in_local_not_alpaca)

    if mismatches:
        msg = (
            f"⚠️ *POSITION MISMATCH — PAPER*\n"
            f"Alpaca only: `{in_alpaca_not_local or 'None'}`\n"
            f"Local only:  `{in_local_not_alpaca or 'None'}`\n"
            f"Action: syncing local → Alpaca"
        )
        log.warning(f"Position mismatch: {msg}")
        _tg(msg)

        # Sync: update local to match Alpaca
        if isinstance(alpaca_data, list):
            for pos in alpaca_data:
                sym = pos.get("symbol", "")
                if sym in in_alpaca_not_local:
                    tid = f"SYNC_{sym}_{int(time.time())}"
                    local_trades[tid] = {
                        "symbol":      sym,
                        "status":      "ACTIVE",
                        "entry_price": float(pos.get("avg_entry_price", 0)),
                        "shares":      float(pos.get("qty", 0)),
                        "synced_from": "alpaca",
                        "timestamp":   datetime.datetime.now().isoformat(),
                    }
            _save(f"{DATA_DIR}/paper_trades.json", local_trades)
            log.info("Positions synced from Alpaca")

    return {
        "alpaca_symbols": list(alpaca_syms),
        "local_symbols":  list(local_syms),
        "mismatches":     mismatches,
        "synced":         mismatches,
        "timestamp":      datetime.datetime.now().isoformat(),
    }

# ══════════════════════════════════════════════════════════════════════════════
# 5. RISK EMERGENCY MODE
# ══════════════════════════════════════════════════════════════════════════════
def check_emergency_conditions() -> dict:
    """
    Check for emergency conditions and activate SAFE MODE if needed.
    PAPER TRADING ONLY.
    """
    perf    = _load(f"{DATA_DIR}/paper_performance.json", {})
    mi      = _load(f"{DATA_DIR}/market_intelligence.json", {})

    total_pnl   = float(perf.get("total_pnl", 0))
    losses      = perf.get("losses", 0)
    wins        = perf.get("wins", 0)
    recent      = perf.get("recent_results", [])
    vix         = float(mi.get("vix", mi.get("vix_level", 20)))
    drawdown    = abs(float(perf.get("max_drawdown", 0)))
    dd_pct      = drawdown / PORTFOLIO_VALUE * 100

    # Count consecutive losses
    consec_losses = 0
    for r in reversed(recent[-10:]):
        if r < 0:
            consec_losses += 1
        else:
            break

    triggers    = []
    emergency   = False

    if dd_pct > MAX_DRAWDOWN_PCT:
        triggers.append(f"Drawdown {dd_pct:.1f}% > {MAX_DRAWDOWN_PCT}%")
        emergency = True

    if consec_losses >= CONSECUTIVE_LOSSES:
        triggers.append(f"{consec_losses} consecutive losses")
        emergency = True

    if vix > VIX_EMERGENCY:
        triggers.append(f"VIX {vix:.1f} > {VIX_EMERGENCY}")
        emergency = True

    state_path = f"{DATA_DIR}/emergency_mode.json"
    state      = _load(state_path, {"active": False})

    if emergency and not state.get("active"):
        state = {
            "active":       True,
            "triggers":     triggers,
            "activated_at": datetime.datetime.now().isoformat(),
            "mode":         "SAFE",
            "size_mult":    0.5,
            "block_aggressive": True,
            "paper_only":   True,
        }
        _save(state_path, state)
        _tg(
            f"🚨 *EMERGENCY SAFE MODE ACTIVATED — PAPER*\n"
            + "\n".join(f"• {t}" for t in triggers)
            + f"\n\n📉 Size reduced 50%\n🚫 Aggressive entries blocked\n⚠️ PAPER ONLY"
        )
        log.warning(f"EMERGENCY MODE: {triggers}")

    elif not emergency and state.get("active"):
        state["active"] = False
        state["deactivated_at"] = datetime.datetime.now().isoformat()
        _save(state_path, state)
        _tg("✅ *EMERGENCY MODE CLEARED — PAPER*\nResuming normal operations.")
        log.info("Emergency mode cleared")

    return {
        "emergency":       emergency,
        "triggers":        triggers,
        "dd_pct":          round(dd_pct, 2),
        "consec_losses":   consec_losses,
        "vix":             vix,
        "state":           state,
    }

# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED SAFETY CHECK — call this before any trade
# ══════════════════════════════════════════════════════════════════════════════
def pre_trade_safety_check(symbol: str, direction: str = "LONG") -> tuple:
    """
    Run all safety checks before a trade.
    Returns (approved, reason).
    PAPER TRADING ONLY.
    """
    # 1. Stale data
    fresh, age, reason = check_data_freshness()
    if not fresh:
        return False, f"STALE DATA: {reason}"

    # 2. Duplicate protection
    is_dup, dup_reason = is_duplicate_trade(symbol, direction)
    if is_dup:
        return False, f"DUPLICATE: {dup_reason}"

    # 3. Emergency mode
    em_state = _load(f"{DATA_DIR}/emergency_mode.json", {})
    if em_state.get("active") and em_state.get("block_aggressive"):
        return False, f"EMERGENCY MODE: {em_state.get('triggers', [])}"

    # 4. Kill switch
    ks = _load(f"{DATA_DIR}/kill_switch.json", {})
    if ks.get("active"):
        return False, f"KILL SWITCH: {ks.get('reason', 'Active')}"

    return True, "All safety checks passed"

def get_size_multiplier_from_safety() -> float:
    """Return size multiplier based on emergency/safety state."""
    em = _load(f"{DATA_DIR}/emergency_mode.json", {})
    if em.get("active"):
        return float(em.get("size_mult", 0.5))
    fs = em.get("fail_safe")
    if fs:
        return 0.25
    return 1.0
