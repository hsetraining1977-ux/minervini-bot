#!/usr/bin/env python3
"""
fix_panic_narrative.py
One-time patch: fixes _fallback_narrative() in adaptive_learning.py
so regime_narrative only highlights regimes ADJACENT to or matching
the current regime — not whatever regime had best historical PnL.
Run once: python3 fix_panic_narrative.py
"""

FILEPATH = "/root/adaptive_learning.py"

OLD_NARRATIVE = '''        "regime_narrative": f"{best_regime} conditions produce best outcomes based on current data.",'''

NEW_NARRATIVE = '''        "regime_narrative": _regime_narrative_smart(context),'''

SMART_FUNCTION = '''
def _regime_narrative_smart(context: dict) -> str:
    """
    Generate a regime narrative that is relevant to the CURRENT regime,
    not just the historically best regime.

    Rules:
    1. If current regime == best regime → celebrate it.
    2. If current regime is adjacent to best → note the transition risk.
    3. If best regime is completely different (e.g. PANIC when STRONG_RISK_ON) →
       show current regime performance instead, mention best only as footnote.
    """
    current  = context.get("regime", "UNKNOWN")
    perf     = context.get("regime_performance", {})

    # Adjacent regime map
    ADJACENT = {
        "STRONG_RISK_ON": ["RISK_ON"],
        "RISK_ON":        ["STRONG_RISK_ON", "NEUTRAL"],
        "NEUTRAL":        ["RISK_ON", "CHOPPY"],
        "CHOPPY":         ["NEUTRAL", "RISK_OFF"],
        "RISK_OFF":       ["CHOPPY", "PANIC"],
        "PANIC":          ["RISK_OFF"],
    }

    if not perf:
        return f"Operating in {current} regime. Monitor setup performance as data accumulates."

    # Find best regime by win rate (min 50 trades to be valid)
    valid = {r: d for r, d in perf.items() if d.get("trades", 0) >= 50}
    if not valid:
        return f"Insufficient trade data. Focusing on {current} regime setups."

    best_regime = max(valid, key=lambda r: valid[r].get("win_rate", 0))
    best_wr     = valid[best_regime].get("win_rate", 0)
    curr_data   = perf.get(current, {})
    curr_wr     = curr_data.get("win_rate", 0)
    curr_trades = curr_data.get("trades", 0)

    adjacent = ADJACENT.get(current, [])

    if current == best_regime:
        return (
            f"{current} shows strongest win rate ({best_wr:.1f}%) across all regimes. "
            f"Current conditions are optimal — prioritize high-conviction setups."
        )
    elif best_regime in adjacent:
        return (
            f"Current {current} regime (WR {curr_wr:.1f}%). "
            f"Adjacent {best_regime} historically stronger ({best_wr:.1f}% WR) — "
            f"watch for regime transition signals."
        )
    else:
        # Best regime is irrelevant to current conditions
        if curr_trades >= 50:
            return (
                f"{current} regime: {curr_wr:.1f}% win rate across {curr_trades} trades. "
                f"Focus on setups optimized for current conditions."
            )
        else:
            return (
                f"Building {current} regime data ({curr_trades} trades so far). "
                f"Applying conservative sizing until statistical confidence improves."
            )

'''

def fix():
    with open(FILEPATH, "r") as f:
        content = f.read()

    if "_regime_narrative_smart" in content:
        print("_regime_narrative_smart already exists — no fix needed.")
        return

    # 1) Insert smart function before _fallback_narrative
    if "def _fallback_narrative" not in content:
        print("ERROR: cannot find '_fallback_narrative' anchor.")
        return
    content = content.replace(
        "def _fallback_narrative",
        SMART_FUNCTION + "def _fallback_narrative",
        1
    )

    # 2) Replace the old narrative line
    if OLD_NARRATIVE in content:
        content = content.replace(OLD_NARRATIVE, NEW_NARRATIVE, 1)
        print("✅ Replaced regime_narrative with _regime_narrative_smart()")
    else:
        # Try flexible match
        import re
        pattern = r'"regime_narrative":\s*f".*?best outcomes.*?",'
        replacement = '"regime_narrative": _regime_narrative_smart(context),'
        new_content, count = re.subn(pattern, replacement, content)
        if count:
            content = new_content
            print(f"✅ Replaced regime_narrative via regex ({count} occurrence)")
        else:
            print("⚠ Could not find regime_narrative line — check manually.")
            print("  Search for: 'best outcomes based on current data'")

    with open(FILEPATH, "w") as f:
        f.write(content)

    print("✅ PANIC narrative fix applied to adaptive_learning.py")
    print("   No restart needed — next learning cycle will use new logic.")

if __name__ == "__main__":
    fix()
