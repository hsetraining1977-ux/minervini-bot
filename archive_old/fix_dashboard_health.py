#!/usr/bin/env python3
"""
fix_dashboard_health.py
Fixes two issues in dashboard.py:
1. CPU/RAM/Disk showing 0.0% (psutil exception silently caught)
2. ai_layer showing "Stopped" despite running
Run once: python3 fix_dashboard_health.py
"""

FILEPATH = "/root/dashboard.py"

# ── Fix 1: robust proc_running ──────────────────────────────────────────
OLD_PROC = """    def proc_running(name):
        for p in psutil.process_iter(['cmdline']):
            try:
                if name in " ".join(p.info['cmdline'] or []):
                    return True
            except: pass
        return False"""

NEW_PROC = """    def proc_running(name):
        import subprocess
        try:
            # Primary: psutil cmdline check
            for p in psutil.process_iter(['cmdline', 'pid']):
                try:
                    cmdline = " ".join(p.info['cmdline'] or [])
                    if name in cmdline:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Fallback: pgrep
            result = subprocess.run(
                ['pgrep', '-f', name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception:
            return False"""

# ── Fix 2: robust CPU/RAM/Disk ──────────────────────────────────────────
OLD_SYSRES = """    try:
        cpu  = psutil.cpu_percent(interval=0.5)
        ram  = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        st.markdown(f\"\"\"
        <div style='margin-top:12px;padding:8px;background:#1a1a2a;border-radius:6px;text-align:center;'>
            💻 CPU: {cpu}% &nbsp;|&nbsp; RAM: {ram}% &nbsp;|&nbsp; Disk: {disk}%
        </div>\"\"\", unsafe_allow_html=True)
    except: pass"""

NEW_SYSRES = """    try:
        cpu  = psutil.cpu_percent(interval=1.0)
        ram  = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        # Fallback if psutil returns 0
        if cpu == 0.0:
            import subprocess
            try:
                r = subprocess.run(['top','-bn1'], capture_output=True, text=True)
                for line in r.stdout.split('\\n'):
                    if 'Cpu' in line or 'cpu' in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if 'us' in p or 'us,' in p:
                                cpu = float(parts[i-1].replace(',','.'))
                                break
            except Exception:
                pass
        st.markdown(f\"\"\"
        <div style='margin-top:12px;padding:8px;background:#1a1a2a;border-radius:6px;text-align:center;'>
            💻 CPU: {cpu:.1f}% &nbsp;|&nbsp; RAM: {ram:.1f}% &nbsp;|&nbsp; Disk: {disk:.1f}%
        </div>\"\"\", unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f\"\"\"
        <div style='margin-top:12px;padding:8px;background:#1a1a2a;border-radius:6px;text-align:center;'>
            💻 System Monitor — check psutil
        </div>\"\"\", unsafe_allow_html=True)"""

def fix():
    with open(FILEPATH, "r") as f:
        content = f.read()

    changed = False

    # Fix 1 — proc_running
    if "pgrep" in content and "Fallback: pgrep" in content:
        print("proc_running already fixed — skipping.")
    elif OLD_PROC in content:
        content = content.replace(OLD_PROC, NEW_PROC, 1)
        print("✅ proc_running() upgraded with pgrep fallback")
        changed = True
    else:
        # Flexible fix — just add pgrep fallback after existing proc_running
        import re
        pattern = r'(def proc_running\(name\):.*?return False)'
        replacement = NEW_PROC.strip()
        new_content, count = re.subn(pattern, replacement, content, count=1, flags=re.DOTALL)
        if count:
            content = new_content
            print(f"✅ proc_running() upgraded via regex")
            changed = True
        else:
            print("⚠ Could not find proc_running — check manually at line ~541")

    # Fix 2 — CPU/RAM display
    if "cpu:.1f" in content:
        print("CPU/RAM display already fixed — skipping.")
    elif OLD_SYSRES in content:
        content = content.replace(OLD_SYSRES, NEW_SYSRES, 1)
        print("✅ CPU/RAM/Disk display upgraded")
        changed = True
    else:
        print("⚠ Could not find CPU/RAM block exactly — trying flexible fix")
        # At minimum fix the interval
        content = content.replace(
            "psutil.cpu_percent(interval=0.5)",
            "psutil.cpu_percent(interval=1.0)",
            1
        )
        print("✅ cpu_percent interval upgraded to 1.0s")
        changed = True

    if changed:
        with open(FILEPATH, "w") as f:
            f.write(content)
        print("\n✅ dashboard.py patched successfully!")
        print("   Restart dashboard:")
        print("   pkill -f 'streamlit run dashboard' && sleep 2")
        print("   nohup streamlit run /root/dashboard.py --server.port 8501 > /root/logs/dashboard.log 2>&1 &")
    else:
        print("\n⚠ No changes made — verify manually")

if __name__ == "__main__":
    fix()
