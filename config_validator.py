#!/usr/bin/env python3
"""
config_validator.py — Secure Config Validation
Minervini Trading Bot | Production Stabilization
- Validates all required API keys exist
- Ensures no keys leak in logs/dashboard/telegram
- Reports config health
"""

import os, sys, re
from pathlib import Path

try:
    from logger import get_logger
    log = get_logger("config_validator")
except ImportError:
    import logging
    log = logging.getLogger("config_validator")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

# ── Required keys ─────────────────────────────────────────────
REQUIRED_KEYS = {
    "ALPACA_API_KEY":    "Alpaca trading",
    "ALPACA_SECRET_KEY": "Alpaca trading",
    "TELEGRAM_BOT_TOKEN":"Telegram alerts",
    "TELEGRAM_CHAT_ID":  "Telegram chat target",
    "ANTHROPIC_API_KEY": "Claude AI layer",
}

OPTIONAL_KEYS = {
    "FRED_API_KEY":      "Macro data (FRED)",
    "FINNHUB_API_KEY":   "Market data (Finnhub)",
    "ALPHA_VANTAGE_KEY": "Market data (Alpha Vantage)",
}

# ── Patterns that should NEVER appear in logs ─────────────────
SENSITIVE_PATTERNS = [
    r'sk-ant-api[a-zA-Z0-9_\-]{20,}',  # Anthropic keys
    r'(pk|sk)_[a-zA-Z0-9]{20,}',        # Alpaca keys
    r'\d{10}:[a-zA-Z0-9_\-]{35}',       # Telegram bot tokens
]


def mask(value: str) -> str:
    """Show only first 8 chars of a key."""
    if not value:
        return "NOT SET"
    return value[:8] + "..." + f"({len(value)} chars)"


def validate_keys() -> tuple[bool, list]:
    """Check all required keys exist."""
    missing = []
    warnings = []
    all_ok = True

    print("\n🔑 API Key Validation")
    print("=" * 45)

    for key, purpose in REQUIRED_KEYS.items():
        value = os.getenv(key, "")
        if not value:
            print(f"  ❌ {key:30s} MISSING  ({purpose})")
            missing.append(key)
            all_ok = False
        else:
            print(f"  ✅ {key:30s} {mask(value)}")

    print("\n📋 Optional Keys:")
    for key, purpose in OPTIONAL_KEYS.items():
        value = os.getenv(key, "")
        if not value:
            print(f"  ⚠️  {key:30s} NOT SET  ({purpose})")
            warnings.append(key)
        else:
            print(f"  ✅ {key:30s} {mask(value)}")

    return all_ok, missing


def scan_logs_for_leaks() -> list:
    """Scan log files for accidentally leaked API keys."""
    leaks = []
    log_paths = [
        "/root/logs/system.log",
        "/root/logs/errors.log",
        "/root/ai.out",
        "/root/orchestrator.out",
        "/root/telegram.out",
    ]

    print("\n🔍 Scanning Logs for Key Leaks")
    print("=" * 45)

    for log_path in log_paths:
        if not os.path.exists(log_path):
            continue
        try:
            with open(log_path, "r", errors="ignore") as f:
                content = f.read()
            for pattern in SENSITIVE_PATTERNS:
                matches = re.findall(pattern, content)
                if matches:
                    leaks.append({
                        "file": log_path,
                        "pattern": pattern,
                        "count": len(matches)
                    })
                    print(f"  ⚠️  LEAK DETECTED in {os.path.basename(log_path)}: {len(matches)} match(es)")
                    log.error(f"Key leak detected in {log_path} — pattern: {pattern[:30]}")
        except Exception as e:
            print(f"  ⚠️  Could not scan {log_path}: {e}")

    if not leaks:
        print("  ✅ No key leaks detected in logs")

    return leaks


def validate_env_file_permissions():
    """Ensure .env is not world-readable."""
    env_path = "/root/.env"
    print("\n🔒 File Permissions Check")
    print("=" * 45)
    try:
        stat = os.stat(env_path)
        mode = oct(stat.st_mode)[-3:]
        world_readable = int(mode[-1]) >= 4
        if world_readable:
            print(f"  ⚠️  .env permissions: {mode} — world-readable! Run: chmod 600 /root/.env")
            os.chmod(env_path, 0o600)
            print(f"  ✅ Fixed: chmod 600 applied")
        else:
            print(f"  ✅ .env permissions: {mode} — OK")
    except Exception as e:
        print(f"  ⚠️  Could not check .env permissions: {e}")


def check_alpaca_connectivity():
    """Test actual Alpaca API connection."""
    print("\n🔌 API Connectivity Test")
    print("=" * 45)
    import requests

    key    = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")

    if not key or not secret:
        print("  ⚠️  Alpaca keys missing — skipping")
        return False

    try:
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={
                "APCA-API-KEY-ID":     key,
                "APCA-API-SECRET-KEY": secret,
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            equity = float(data.get("equity", 0))
            print(f"  ✅ Alpaca API: Connected | Portfolio: ${equity:,.2f}")
            return True
        else:
            print(f"  ❌ Alpaca API: HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Alpaca API: {e}")
        return False


def main():
    print("\n" + "=" * 50)
    print("  CONFIG VALIDATOR — Minervini Trading Bot")
    print("=" * 50)

    keys_ok, missing = validate_keys()
    leaks = scan_logs_for_leaks()
    validate_env_file_permissions()
    alpaca_ok = check_alpaca_connectivity()

    print("\n📊 Summary")
    print("=" * 45)
    print(f"  API Keys:     {'✅ All present' if keys_ok else f'❌ Missing: {missing}'}")
    print(f"  Log Leaks:    {'✅ None' if not leaks else f'⚠️  {len(leaks)} files affected'}")
    print(f"  Alpaca API:   {'✅ Connected' if alpaca_ok else '❌ Failed'}")
    print()

    if not keys_ok:
        print(f"  ⚠️  Add missing keys to /root/.env and restart")
        sys.exit(1)

    print("  ✅ Config validation passed\n")
    return True


if __name__ == "__main__":
    main()
