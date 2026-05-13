#!/usr/bin/env python3
import sys, os, json, numpy as np
sys.path.insert(0, "/root")
from datetime import datetime

ADAPTIVE_DIR = "/root/adaptive"
MEMORY_DIR   = "/root/adaptive/memory"
os.makedirs(ADAPTIVE_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR,   exist_ok=True)

SETUP_LIBRARY_PATHS = [
    f"{ADAPTIVE_DIR}/setup_library.json",
    f"{MEMORY_DIR}/setup_library.json",
]

SUGGESTIONS_PATH    = f"{MEMORY_DIR}/adaptive_suggestions.json"
MEMORY_SUMMARY_PATH = f"{MEMORY_DIR}/memory_summary.json"

def find_setup_library():
    for path in SETUP_LIBRARY_PATHS:
        if os.path.exists(path) and os.path.getsize(path) > 10:
            print(f"  [MemBuilder] Found: {path}")
            return path
    return None

def ingest_from_library(full_sync=True):
    try:
        import adaptive_memory as amem
        lib_path = find_setup_library()
        if not lib_path:
            return {"ingested": 0, "error": "setup_library.json not found"}
        with open(lib_path) as f:
            library = json.load(f)
        print(f"  [MemBuilder] Library has {len(library)} setups")
        stats = amem.get_setup_stats()
        ingested = 0
        for setup, data in library.items():
            total    = data.get("total_trades", 0)
            if total == 0:
                continue
            wins     = data.get("wins", 0)
            losses   = total - wins
            total_pnl= data.get("total_pnl", 0)
            stats[setup] = {
                "total":        total,
                "wins":         wins,
                "losses":       losses,
                "total_pnl":    round(total_pnl, 4),
                "by_regime":    {},
                "last_updated": datetime.now().isoformat(),
                "source":       "historical_full",
            }
            # Fix by_regime - normalize pnl key
            for regime, rdata in data.get("by_regime", {}).items():
                pnl_val = rdata.get("pnl", rdata.get("total_pnl", 0))
                stats[setup]["by_regime"][regime] = {
                    "wins":   rdata.get("wins", 0),
                    "losses": rdata.get("losses", 0),
                    "pnl":    round(pnl_val, 4),
                    "total":  rdata.get("total", rdata.get("wins",0)+rdata.get("losses",0)),
                }
            ingested += 1
            print(f"     {setup}: {total} trades, WR={data.get('win_rate',0):.1f}%")
        amem._write(amem.PATHS["setup_stats"], stats)
        amem.log_learning_cycle(
            source="adaptive_memory_builder_v2",
            trades_analyzed=sum(v.get("total_trades",0) for v in library.values()),
            changes_made=ingested,
            summary=f"Full sync of {ingested} setups"
        )
        print(f"  [MemBuilder] Saved {ingested} setups")
        return {"ingested": ingested, "total_setups": len(library)}
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"ingested": 0, "error": str(e)}

def generate_suggestions():
    suggestions = []
    lib_path = find_setup_library()
    if not lib_path:
        return suggestions
    with open(lib_path) as f:
        library = json.load(f)
    for setup, data in library.items():
        total = data.get("total_trades", 0)
        if total < 20:
            continue
        wr  = data.get("win_rate", 0)
        exp = data.get("expectancy", 0)
        if wr >= 60 and exp >= 0.5:
            suggestions.append({"type":"BOOST_SETUP","setup":setup,"level":1,"confidence":round(wr/100,2),"trades":total})
        elif wr <= 38:
            suggestions.append({"type":"REDUCE_SETUP","setup":setup,"level":1,"confidence":round(1-wr/100,2),"trades":total})
    with open(SUGGESTIONS_PATH, "w") as f:
        json.dump(suggestions, f, indent=2)
    return suggestions

def build_memory_summary():
    lib_path = find_setup_library()
    library  = {}
    if lib_path:
        with open(lib_path) as f:
            library = json.load(f)
    total_trades = sum(v.get("total_trades",0) for v in library.values())
    phase = "PHASE_3_MULTI_REGIME" if total_trades>=5000 else "PHASE_2_ADVANCED" if total_trades>=500 else "PHASE_1_BOOTSTRAP"
    summary = {"timestamp":datetime.now().isoformat(),"total_setups":len(library),"total_trades":total_trades,"phase":phase}
    with open(MEMORY_SUMMARY_PATH,"w") as f:
        json.dump(summary, f, indent=2)
    return summary

if __name__ == "__main__":
    print(" Adaptive Memory Builder v2 ")
    print("  Ingesting from setup library...")
    result = ingest_from_library(full_sync=True)
    print(f"  Ingested: {result.get('ingested',0)} setups")
    print("  Generating suggestions...")
    suggestions = generate_suggestions()
    print(f"  Suggestions: {len(suggestions)}")
    print("  Building memory summary...")
    summary = build_memory_summary()
    print(f"  Phase: {summary['phase']}")
    print(f"  Total trades: {summary['total_trades']}")
    print("   Memory Builder v2 ready")
