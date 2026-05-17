#!/usr/bin/env python3
"""
system_audit.py — Minervini AI Full System Audit
Phase 1: Analyze running processes, CPU, RAM, files, duplicates, orphans.
Generates: system_audit.json, system_process_map.json, resource_hotspots.json
"""

import os, json, subprocess, time, re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

REPORTS_DIR = Path("/root/reports")
REPORTS_DIR.mkdir(exist_ok=True)

ROOT = Path("/root")

# ── Helpers ───────────────────────────────────────────────────────────────

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except:
        return ""

def mb(b):
    return round(b / 1024 / 1024, 1)

# ── 1. Running Processes ──────────────────────────────────────────────────

def audit_processes():
    out = run("ps aux --no-headers")
    procs = []
    python_procs = []

    for line in out.splitlines():
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        user, pid, cpu, mem = parts[0], parts[1], parts[2], parts[3]
        cmd = parts[10]

        p = {
            "pid": pid,
            "cpu": float(cpu),
            "mem": float(mem),
            "cmd": cmd[:120],
        }
        procs.append(p)

        if "python" in cmd and "grep" not in cmd:
            script = cmd.split("/")[-1].split(" ")[0]
            python_procs.append({
                "pid": pid,
                "script": script,
                "cpu": float(cpu),
                "mem": float(mem),
                "cmd": cmd[:120],
            })

    # Detect duplicates
    script_count = defaultdict(list)
    for p in python_procs:
        script_count[p["script"]].append(p["pid"])

    duplicates = {s: pids for s, pids in script_count.items() if len(pids) > 1}

    return {
        "total_processes": len(procs),
        "python_processes": python_procs,
        "python_count": len(python_procs),
        "duplicate_scripts": duplicates,
        "duplicate_count": len(duplicates),
    }

# ── 2. CPU / RAM / Disk ───────────────────────────────────────────────────

def audit_resources():
    # CPU
    cpu_line = run("top -bn1 | grep 'Cpu(s)'")
    cpu_used = 0.0
    m = re.search(r'(\d+\.?\d*)\s*us', cpu_line)
    if m:
        cpu_used = float(m.group(1))

    # RAM
    mem_line = run("free -m")
    ram_total = ram_used = ram_free = 0
    for line in mem_line.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            ram_total, ram_used, ram_free = int(parts[1]), int(parts[2]), int(parts[3])

    # Disk
    disk_line = run("df -h /")
    disk_used = disk_total = disk_pct = "?"
    for line in disk_line.splitlines():
        if line.startswith("/"):
            parts = line.split()
            disk_total, disk_used, disk_pct = parts[1], parts[2], parts[4]

    # Top CPU consumers
    top_cpu = run("ps aux --sort=-%cpu --no-headers | head -10")
    top_consumers = []
    for line in top_cpu.splitlines():
        parts = line.split(None, 10)
        if len(parts) >= 11:
            top_consumers.append({
                "pid": parts[1],
                "cpu": parts[2],
                "mem": parts[3],
                "cmd": parts[10][:80],
            })

    return {
        "cpu_used_pct": cpu_used,
        "ram_total_mb": ram_total,
        "ram_used_mb": ram_used,
        "ram_free_mb": ram_free,
        "ram_used_pct": round(ram_used / ram_total * 100, 1) if ram_total else 0,
        "disk_total": disk_total,
        "disk_used": disk_used,
        "disk_used_pct": disk_pct,
        "top_cpu_consumers": top_consumers,
    }

# ── 3. File Classification ────────────────────────────────────────────────

CORE_SYSTEM = {
    "master_orchestrator.py",
    "ai_layer.py",
    "ai_trade_review.py",
    "auto_monitor.py",
    "institutional_layer.py",
    "institutional_regime_classifier.py",
    "intraday_engine.py",
    "regime_sync.py",
    "reliability_layer.py",
    "adaptive_learning.py",
    "adaptive_memory.py",
    "adaptive_scoring.py",
    "adaptive_review_engine.py",
    "breadth_engine.py",
    "sector_rotation_engine.py",
    "volatility_regime_engine.py",
    "liquidity_engine.py",
    "macro_intelligence.py",
    "market_intelligence.py",
    "decision_engine.py",
    "trade_center.py",
    "portfolio_engine.py",
    "portfolio_guard.py",
    "capital_allocator.py",
    "risk_simulator.py",
    "insider_check.py",
    "smart_execution_engine.py",
    "paper_execution.py",
    "dashboard.py",
    "adaptive_dashboard.py",
    "institutional_dashboard.py",
    "health_monitor.py",
    "health_dashboard.py",
    "resource_monitor.py",
    "auto_restart.py",
    "log_rotator.py",
    "telegram_commands.py",
    "telegram_trade_cards.py",
    "smart_telegram_reporter.py",
    "market_session_manager.py",
    "event_awareness.py",
    "config.py",
    "database.py",
    "data_sources.py",
    "logger.py",
    "start_system.sh",
    "stop_system.sh",
    "run_ai_layer.sh",
}

RESEARCH = {
    "historical_replay_engine.py",
    "historical_learning_daemon.py",
    "setup_replay_library.py",
    "regime_replay_engine.py",
    "replay_dashboard_tab.py",
    "adaptive_memory_builder.py",
    "correlation_engine.py",
    "fundamental_engine.py",
    "trade_analytics.py",
    "trade_journal.py",
    "trade_lifecycle.py",
    "trade_plan_generator.py",
    "performance_dashboard.py",
    "portfolio_dashboard.py",
    "position_management_dashboard.py",
    "lifecycle_dashboard.py",
    "paper_performance_dashboard.py",
}

ARCHIVE_PATTERNS = [
    "_old", "_backup", "_new", "fix_", "test_",
    "priority1_", "priority2_", "priority3_",
    "phase2_", "phase3_",
]

def classify_files():
    all_py = list(ROOT.glob("*.py"))
    all_sh = list(ROOT.glob("*.sh"))
    all_files = all_py + all_sh

    core = []
    research = []
    archive = []
    unused = []
    unknown = []

    for f in all_files:
        name = f.name
        if name in CORE_SYSTEM:
            size = f.stat().st_size
            core.append({"file": name, "size_kb": round(size/1024, 1)})
        elif name in RESEARCH:
            size = f.stat().st_size
            research.append({"file": name, "size_kb": round(size/1024, 1)})
        elif any(p in name for p in ARCHIVE_PATTERNS):
            size = f.stat().st_size
            archive.append({"file": name, "size_kb": round(size/1024, 1)})
        else:
            size = f.stat().st_size
            unknown.append({"file": name, "size_kb": round(size/1024, 1)})

    return {
        "core_system": core,
        "core_count": len(core),
        "research": research,
        "research_count": len(research),
        "archive_candidates": archive,
        "archive_count": len(archive),
        "unknown": unknown,
        "unknown_count": len(unknown),
        "total_files": len(all_files),
    }

# ── 4. Log Analysis ───────────────────────────────────────────────────────

def audit_logs():
    logs_dir = ROOT / "logs"
    if not logs_dir.exists():
        return {"error": "No logs directory"}

    log_files = []
    total_size = 0
    oversized = []

    for f in logs_dir.glob("*"):
        if f.is_file():
            size = f.stat().st_size
            total_size += size
            age_days = (time.time() - f.stat().st_mtime) / 86400
            entry = {
                "file": f.name,
                "size_mb": round(size/1024/1024, 2),
                "age_days": round(age_days, 1),
            }
            log_files.append(entry)
            if size > 10 * 1024 * 1024:  # > 10MB
                oversized.append(entry)

    log_files.sort(key=lambda x: x["size_mb"], reverse=True)

    return {
        "total_size_mb": round(total_size/1024/1024, 1),
        "file_count": len(log_files),
        "top_10_largest": log_files[:10],
        "oversized_logs": oversized,
        "oversized_count": len(oversized),
    }

# ── 5. Telegram Spam Detection ────────────────────────────────────────────

def audit_telegram():
    spam_sources = []
    py_files = list(ROOT.glob("*.py"))

    for f in py_files:
        try:
            content = f.read_text(errors="ignore")
            count = content.count("send_telegram")
            if count > 0:
                # Check if has session guard
                has_guard = "is_market_open" in content or "session_state" in content or "should_send" in content
                spam_sources.append({
                    "file": f.name,
                    "send_telegram_calls": count,
                    "has_session_guard": has_guard,
                    "risk": "LOW" if has_guard else "HIGH",
                })
        except:
            pass

    spam_sources.sort(key=lambda x: x["send_telegram_calls"], reverse=True)
    high_risk = [s for s in spam_sources if s["risk"] == "HIGH"]

    return {
        "files_with_telegram": len(spam_sources),
        "high_risk_spam_files": high_risk,
        "high_risk_count": len(high_risk),
        "all_sources": spam_sources,
    }

# ── 6. Process Map ────────────────────────────────────────────────────────

def build_process_map():
    """Map which scripts call which other scripts."""
    py_files = list(ROOT.glob("*.py"))
    dep_map = {}

    for f in py_files:
        try:
            content = f.read_text(errors="ignore")
            imports = []
            for line in content.splitlines():
                if line.startswith("from ") or line.startswith("import "):
                    m = re.match(r'(?:from|import)\s+(\w+)', line)
                    if m:
                        mod = m.group(1) + ".py"
                        if (ROOT / mod).exists():
                            imports.append(mod)
            if imports:
                dep_map[f.name] = list(set(imports))
        except:
            pass

    return dep_map

# ── MAIN ──────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*55)
    print("  MINERVINI AI — SYSTEM AUDIT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    print("\n[1/6] Auditing processes...")
    procs = audit_processes()
    print(f"  Python processes: {procs['python_count']}")
    print(f"  Duplicates: {procs['duplicate_count']}")
    if procs['duplicate_scripts']:
        for s, pids in procs['duplicate_scripts'].items():
            print(f"    ⚠ {s}: PIDs {pids}")

    print("\n[2/6] Auditing resources...")
    resources = audit_resources()
    print(f"  CPU: {resources['cpu_used_pct']}%")
    print(f"  RAM: {resources['ram_used_mb']}MB / {resources['ram_total_mb']}MB ({resources['ram_used_pct']}%)")
    print(f"  Disk: {resources['disk_used']} / {resources['disk_total']} ({resources['disk_used_pct']})")

    print("\n[3/6] Classifying files...")
    files = classify_files()
    print(f"  Core system: {files['core_count']} files")
    print(f"  Research:    {files['research_count']} files")
    print(f"  Archive:     {files['archive_count']} files")
    print(f"  Unknown:     {files['unknown_count']} files")

    print("\n[4/6] Auditing logs...")
    logs = audit_logs()
    print(f"  Total logs: {logs.get('total_size_mb', 0)} MB")
    print(f"  Oversized:  {logs.get('oversized_count', 0)} files")

    print("\n[5/6] Auditing Telegram spam...")
    telegram = audit_telegram()
    print(f"  High-risk files: {telegram['high_risk_count']}")
    for f in telegram['high_risk_spam_files']:
        print(f"    ⚠ {f['file']}: {f['send_telegram_calls']} calls, no session guard")

    print("\n[6/6] Building dependency map...")
    dep_map = build_process_map()
    print(f"  Mapped {len(dep_map)} files with dependencies")

    # ── Save reports ──────────────────────────────────────────────────────
    audit = {
        "timestamp": datetime.now().isoformat(),
        "processes": procs,
        "resources": resources,
        "files": files,
        "logs": logs,
        "telegram": telegram,
    }

    process_map = {
        "timestamp": datetime.now().isoformat(),
        "running_python": procs["python_processes"],
        "duplicates": procs["duplicate_scripts"],
    }

    hotspots = {
        "timestamp": datetime.now().isoformat(),
        "cpu_used_pct": resources["cpu_used_pct"],
        "top_cpu": resources["top_cpu_consumers"],
        "oversized_logs": logs.get("oversized_logs", []),
        "telegram_spam": telegram["high_risk_spam_files"],
        "duplicate_processes": procs["duplicate_scripts"],
        "unknown_files": files["unknown"],
    }

    (REPORTS_DIR / "system_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False)
    )
    (REPORTS_DIR / "system_process_map.json").write_text(
        json.dumps(process_map, indent=2, ensure_ascii=False)
    )
    (REPORTS_DIR / "resource_hotspots.json").write_text(
        json.dumps(hotspots, indent=2, ensure_ascii=False)
    )

    # Dependency map
    arch = {
        "timestamp": datetime.now().isoformat(),
        "core_files": [f["file"] for f in files["core_system"]],
        "research_files": [f["file"] for f in files["research"]],
        "archive_candidates": [f["file"] for f in files["archive_candidates"]],
        "unknown_files": [f["file"] for f in files["unknown"]],
        "dependency_map": dep_map,
    }
    (REPORTS_DIR / "architecture_map.json").write_text(
        json.dumps(arch, indent=2, ensure_ascii=False)
    )

    print("\n" + "="*55)
    print("  ✅ AUDIT COMPLETE")
    print(f"  Reports saved to: /root/reports/")
    print("="*55)

    # ── Print action items ────────────────────────────────────────────────
    print("\n📋 RECOMMENDED ACTIONS:")
    if procs["duplicate_count"] > 0:
        print(f"  🔴 Kill {procs['duplicate_count']} duplicate processes")
    if resources["cpu_used_pct"] > 50:
        print(f"  🔴 CPU {resources['cpu_used_pct']}% — check top consumers")
    if telegram["high_risk_count"] > 0:
        print(f"  🟡 Add session guards to {telegram['high_risk_count']} Telegram files")
    if logs.get("oversized_count", 0) > 0:
        print(f"  🟡 Rotate {logs['oversized_count']} oversized log files")
    if files["unknown_count"] > 0:
        print(f"  🟡 Review {files['unknown_count']} unknown files")
    if files["archive_count"] > 0:
        print(f"  ⚪ Archive {files['archive_count']} old/temp files")

    print()
    return audit

if __name__ == "__main__":
    main()
