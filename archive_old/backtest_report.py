"""
Backtest Report Generator
==========================
يولّد تقرير HTML تفاعلي من نتائج الـ Backtest
"""

import json
import sys
from datetime import datetime

def generate_html_report(results: dict, output_file: str = "backtest_report.html"):
    s  = results.get("summary", {})
    t  = results.get("trades",  {})
    eq = results.get("equity_curve", [])
    top_trades = results.get("top_trades", [])
    raw_trades = results.get("raw_trades", [])
    exit_reasons = results.get("exit_reasons", {})

    # ─ بيانات منحنى الرأس المال ─
    dates  = [r["date"] for r in eq]
    values = [r["portfolio_value"] for r in eq]

    # ─ بيانات الصفقات ─
    trades_rows = ""
    for tr in sorted(raw_trades, key=lambda x: x["exit_date"], reverse=True)[:50]:
        color = "#0F6E56" if tr["pnl"] > 0 else "#A32D2D"
        sign  = "+" if tr["pnl"] > 0 else ""
        trades_rows += f"""
        <tr>
          <td>{tr['symbol']}</td>
          <td>{tr['entry_date']}</td>
          <td>{tr['exit_date']}</td>
          <td>${tr['entry_price']:.2f}</td>
          <td>${tr['exit_price']:.2f}</td>
          <td style="color:{color};font-weight:500">{sign}{tr['pnl_pct']:.1f}%</td>
          <td style="color:{color};font-weight:500">{sign}${tr['pnl']:,.0f}</td>
          <td>{tr['days_held']}</td>
          <td><span class="badge badge-{tr['reason']}">{tr['reason']}</span></td>
        </tr>"""

    # حساب توزيع الأرباح
    pnl_dist = {"خسارة > 10%": 0, "خسارة 5-10%": 0, "خسارة 0-5%": 0,
                "ربح 0-10%": 0, "ربح 10-20%": 0, "ربح > 20%": 0}
    for tr in raw_trades:
        p = tr["pnl_pct"]
        if   p < -10:  pnl_dist["خسارة > 10%"] += 1
        elif p < -5:   pnl_dist["خسارة 5-10%"] += 1
        elif p < 0:    pnl_dist["خسارة 0-5%"]  += 1
        elif p < 10:   pnl_dist["ربح 0-10%"]   += 1
        elif p < 20:   pnl_dist["ربح 10-20%"]  += 1
        else:          pnl_dist["ربح > 20%"]    += 1

    alpha_val = s.get('alpha', '0%').replace('%','')
    alpha_color = "#0F6E56" if float(alpha_val) >= 0 else "#A32D2D"

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Minervini Backtest Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; background: #f5f4f0; color: #2c2c2a; direction: rtl; }}
  .header {{ background: #26215C; color: white; padding: 28px 40px; }}
  .header h1 {{ font-size: 22px; font-weight: 500; }}
  .header p  {{ font-size: 13px; opacity: 0.7; margin-top: 4px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 28px 20px; }}
  .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 12px; padding: 20px; border: 1px solid rgba(0,0,0,0.08); }}
  .kpi-label {{ font-size: 12px; color: #888; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 26px; font-weight: 500; }}
  .kpi-sub   {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .green {{ color: #0F6E56; }}
  .red   {{ color: #A32D2D; }}
  .section-title {{ font-size: 15px; font-weight: 500; margin-bottom: 16px; color: #3C3489; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #f5f4f0; padding: 10px 12px; text-align: right; font-weight: 500; color: #555; border-bottom: 2px solid #e8e7e3; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #f0efe9; }}
  tr:hover td {{ background: #fafaf8; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }}
  .badge-stop_loss   {{ background: #FCEBEB; color: #A32D2D; }}
  .badge-end_of_test {{ background: #E6F1FB; color: #185FA5; }}
  .badge-take_profit {{ background: #EAF3DE; color: #3B6D11; }}
  canvas {{ max-height: 280px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 Minervini SEPA — تقرير Backtesting</h1>
  <p>{s.get('period')} &nbsp;|&nbsp; تم الإنشاء: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>

<div class="container">

  <!-- KPIs -->
  <div class="grid-4">
    <div class="card">
      <div class="kpi-label">العائد الإجمالي</div>
      <div class="kpi-value {'green' if '+' not in s.get('total_return','') and float(s.get('total_return','0%').replace('%','')) >= 0 else 'red'}">{s.get('total_return')}</div>
      <div class="kpi-sub">{s.get('initial_capital')} → {s.get('final_capital')}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Alpha (vs S&P 500)</div>
      <div class="kpi-value" style="color:{alpha_color}">{s.get('alpha')}</div>
      <div class="kpi-sub">S&P 500: {s.get('spy_return')}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Sharpe Ratio</div>
      <div class="kpi-value">{s.get('sharpe_ratio')}</div>
      <div class="kpi-sub">أعلى من 1.0 = جيد &nbsp;|&nbsp; أعلى من 2.0 = ممتاز</div>
    </div>
    <div class="card">
      <div class="kpi-label">Max Drawdown</div>
      <div class="kpi-value red">{s.get('max_drawdown')}</div>
      <div class="kpi-sub">Profit Factor: {s.get('profit_factor')}</div>
    </div>
  </div>

  <div class="grid-4">
    <div class="card">
      <div class="kpi-label">Win Rate</div>
      <div class="kpi-value green">{t.get('win_rate')}</div>
      <div class="kpi-sub">{t.get('winners')} ربح / {t.get('losers')} خسارة</div>
    </div>
    <div class="card">
      <div class="kpi-label">متوسط الربح</div>
      <div class="kpi-value green">{t.get('avg_win')}</div>
      <div class="kpi-sub">أسوأ خسارة: {t.get('worst_trade')}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Reward:Risk</div>
      <div class="kpi-value">{t.get('rr_ratio')}x</div>
      <div class="kpi-sub">الهدف: 2.0x أو أعلى</div>
    </div>
    <div class="card">
      <div class="kpi-label">إجمالي الصفقات</div>
      <div class="kpi-value">{t.get('total')}</div>
      <div class="kpi-sub">متوسط مدة: {t.get('avg_holding_days')} يوم</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="grid-2">
    <div class="card">
      <div class="section-title">📈 منحنى رأس المال</div>
      <canvas id="equityChart"></canvas>
    </div>
    <div class="card">
      <div class="section-title">📊 توزيع الصفقات حسب النتيجة</div>
      <canvas id="distChart"></canvas>
    </div>
  </div>

  <!-- Trades Table -->
  <div class="card">
    <div class="section-title">🗂️ آخر ٥٠ صفقة</div>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>السهم</th><th>تاريخ الدخول</th><th>تاريخ الخروج</th>
            <th>سعر الدخول</th><th>سعر الخروج</th>
            <th>العائد %</th><th>الربح/الخسارة</th>
            <th>الأيام</th><th>سبب الخروج</th>
          </tr>
        </thead>
        <tbody>{trades_rows}</tbody>
      </table>
    </div>
  </div>

</div>

<script>
const dates  = {json.dumps(dates[::5])};
const values = {json.dumps(values[::5])};
const distLabels = {json.dumps(list(pnl_dist.keys()))};
const distData   = {json.dumps(list(pnl_dist.values()))};

new Chart(document.getElementById('equityChart'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [{{
      label: 'قيمة المحفظة',
      data: values,
      borderColor: '#3C3489',
      backgroundColor: 'rgba(60,52,137,0.08)',
      borderWidth: 2,
      pointRadius: 0,
      fill: true,
      tension: 0.3
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ maxTicksLimit: 8, font: {{ size: 11 }} }} }},
      y: {{ ticks: {{ callback: v => '$' + (v/1000).toFixed(0) + 'k', font: {{ size: 11 }} }} }}
    }}
  }}
}});

new Chart(document.getElementById('distChart'), {{
  type: 'bar',
  data: {{
    labels: distLabels,
    datasets: [{{
      data: distData,
      backgroundColor: ['#F09595','#F7C1C1','#FAC775','#9FE1CB','#5DCAA5','#1D9E75'],
      borderRadius: 6,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ font: {{ size: 11 }} }} }},
      y: {{ ticks: {{ font: {{ size: 11 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ تم إنشاء التقرير: {output_file}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "backtest_results.json"
    with open(input_file, encoding="utf-8") as f:
        results = json.load(f)
    generate_html_report(results)
