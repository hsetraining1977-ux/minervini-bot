#!/usr/bin/env python3
"""
Database Test — db_test.py
"""
import sys
sys.path.insert(0, '/root')
from database import init_database, insert_trade_log, insert_rejection_log, insert_market_snapshot, fetch_recent_trades, fetch_recent_rejections, get_stats

def run_tests():
    print("\n" + "="*50)
    print("  🧪 Database Test Suite")
    print("="*50)

    # Test 1: Init
    print("\n[1] Initializing tables...")
    assert init_database(), "❌ init_database failed"
    print("    ✅ Tables created")

    # Test 2: Insert trade
    print("\n[2] Inserting test trade log...")
    trade = {"symbol": "NVDA", "score": 87.5, "rating": "HOT", "decision": "SCAN",
             "current_price": 210.5, "stop_loss": 204.17, "target_1": 229.93,
             "target_2": 249.37, "position_size": 45, "market_regime": "RISK_ON",
             "rv": 1.2, "orb_breakout": True, "mtf_alignment": True}
    assert insert_trade_log(trade), "❌ insert_trade_log failed"
    print("    ✅ Trade log inserted")

    # Test 3: Insert rejection
    print("\n[3] Inserting test rejection log...")
    rejection = {"symbol": "META", "reason": "LOW_SCORE", "score": 25.0,
                 "warnings": ["macro weak", "below vwap"], "market_regime": "RISK_ON"}
    assert insert_rejection_log(rejection), "❌ insert_rejection_log failed"
    print("    ✅ Rejection log inserted")

    # Test 4: Insert snapshot
    print("\n[4] Inserting market snapshot...")
    snapshot = {"spy": 520.5, "vix": 17.2, "dxy": 97.8,
                "market_regime": "RISK_ON", "breadth": 0.65, "risk_on": True}
    assert insert_market_snapshot(snapshot), "❌ insert_market_snapshot failed"
    print("    ✅ Market snapshot inserted")

    # Test 5: Fetch
    print("\n[5] Fetching recent trades...")
    trades = fetch_recent_trades(5)
    assert len(trades) > 0, "❌ No trades found"
    print(f"    ✅ Found {len(trades)} trade(s)")
    for t in trades:
        print(f"    → {t['symbol']} | {t['rating']} | Score:{t['score']} | {t['market_regime']}")

    # Test 6: Stats
    print("\n[6] Database stats...")
    stats = get_stats()
    print(f"    ✅ Trades: {stats['total_trades']} | Rejections: {stats['total_rejections']} | Snapshots: {stats['total_snapshots']}")

    print("\n" + "="*50)
    print("  ✅ ALL TESTS PASSED — DATABASE READY")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_tests()
