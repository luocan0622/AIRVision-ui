"""Airtest 风格 HTML 测试报告生成器。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.logger import logger
from utils.step_reporter import REPORT_ROOT, StepReporter

_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{page_title}</title>
<style>
:root {{
  --bg: #0f1419;
  --bg-panel: #1a2332;
  --bg-hover: #243044;
  --bg-active: #2a3a52;
  --border: #2d3a4f;
  --text: #e8edf4;
  --text-muted: #8b9cb3;
  --green: #3dd68c;
  --red: #f56565;
  --orange: #f6ad55;
  --blue: #63b3ed;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  font-size: 13px;
  line-height: 1.5;
}}
a {{ color: var(--blue); text-decoration: none; }}
.header {{
  text-align: center;
  padding: 20px 16px 12px;
  border-bottom: 1px solid var(--border);
}}
.header h1 {{
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 1px;
  color: var(--text);
}}
.summary {{
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-panel);
}}
.summary-left, .summary-right {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}
.summary-title {{
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}}
.badge.passed {{ background: rgba(61,214,140,.15); color: var(--green); }}
.badge.failed {{ background: rgba(245,101,101,.15); color: var(--red); }}
.badge.skipped {{ background: rgba(246,173,85,.15); color: var(--orange); }}
.meta {{ color: var(--text-muted); font-size: 12px; }}
.meta span {{ margin-right: 16px; }}
.quick-view {{
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
}}
.quick-view-label {{
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 8px;
}}
.filmstrip {{
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
}}
.thumb {{
  flex: 0 0 auto;
  cursor: pointer;
  text-align: center;
  opacity: .75;
  transition: opacity .15s;
}}
.thumb:hover, .thumb.active {{ opacity: 1; }}
.thumb img {{
  width: 120px;
  height: 68px;
  object-fit: cover;
  border: 2px solid transparent;
  border-radius: 4px;
  background: #000;
}}
.thumb.active img {{ border-color: var(--blue); }}
.thumb-time {{
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}}
.main {{
  display: flex;
  height: calc(100vh - 280px);
  min-height: 400px;
}}
.sidebar {{
  width: 340px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  background: var(--bg-panel);
}}
.sidebar-toolbar {{
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}}
.filter-btn {{
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}}
.filter-btn.active {{
  border-color: var(--blue);
  color: var(--blue);
}}
.step-item {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background .12s;
}}
.step-item:hover {{ background: var(--bg-hover); }}
.step-item.active {{ background: var(--bg-active); }}
.step-icon {{ font-size: 14px; width: 18px; text-align: center; }}
.step-icon.passed {{ color: var(--green); }}
.step-icon.failed {{ color: var(--red); }}
.step-body {{ flex: 1; min-width: 0; }}
.step-name {{
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
}}
.step-dur {{
  font-size: 11px;
  color: var(--text-muted);
}}
.step-eye {{ color: var(--text-muted); font-size: 14px; }}
.detail {{
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px;
}}
.detail-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  font-size: 15px;
  font-weight: 600;
}}
.detail-stats {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}}
.stat-card {{
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 14px;
}}
.stat-label {{ color: var(--text-muted); font-size: 11px; }}
.stat-value {{ font-size: 14px; margin-top: 2px; }}
.detail-shot {{
  margin-bottom: 20px;
  text-align: center;
}}
.detail-shot img {{
  max-width: 100%;
  max-height: 480px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #000;
}}
.args-section h3 {{
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-weight: 500;
}}
.args-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}
.args-table td {{
  padding: 6px 10px;
  border: 1px solid var(--border);
  vertical-align: top;
}}
.args-table td:first-child {{
  color: var(--text-muted);
  width: 120px;
  background: var(--bg-panel);
}}
.error-box {{
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(245,101,101,.1);
  border: 1px solid rgba(245,101,101,.3);
  border-radius: 6px;
  color: var(--red);
  font-size: 12px;
  white-space: pre-wrap;
}}
.empty {{ color: var(--text-muted); padding: 40px; text-align: center; }}
</style>
</head>
<body>
<div class="header"><h1>AIRVision Test Report</h1></div>
<div class="summary" id="summary"></div>
<div class="quick-view">
  <div class="quick-view-label">快览</div>
  <div class="filmstrip" id="filmstrip"></div>
</div>
<div class="main">
  <div class="sidebar">
    <div class="sidebar-toolbar">
      <button class="filter-btn active" data-filter="all">全部</button>
      <button class="filter-btn" data-filter="passed">成功</button>
      <button class="filter-btn" data-filter="failed">失败</button>
      <button class="filter-btn" id="jump-error">跳至错误步骤</button>
    </div>
    <div id="step-list"></div>
  </div>
  <div class="detail" id="detail"></div>
</div>
<script>
const DATA = {report_json};
let currentFilter = "all";
let selectedIndex = 0;

function fmtDuration(ms) {{
  if (ms < 1000) return ms + "ms";
  const s = Math.floor(ms / 1000);
  const rem = ms % 1000;
  return s + "s " + rem + "ms";
}}

function relTime(ms, startMs) {{
  const offset = Math.max(0, ms - startMs);
  const sec = Math.floor(offset / 1000);
  const m = String(Math.floor(sec / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return m + ":" + s;
}}

function statusIcon(status) {{
  return status === "passed" ? "✓" : status === "failed" ? "✗" : "○";
}}

function renderSummary() {{
  const el = document.getElementById("summary");
  const badgeClass = DATA.status === "passed" ? "passed" : DATA.status === "failed" ? "failed" : "skipped";
  el.innerHTML = `
    <div class="summary-left">
      <div class="summary-title">
        <span>${{DATA.title}}</span>
        <span class="badge ${{badgeClass}}">${{DATA.status_label}}</span>
      </div>
      <div class="meta">
        <span>${{DATA.start_time}} — ${{DATA.end_time}}</span>
        <span>步骤数: ${{DATA.step_count}}</span>
        <span>耗时: ${{fmtDuration(DATA.duration_ms)}}</span>
      </div>
    </div>
    <div class="summary-right">
      <div class="meta"><span>作者: ${{DATA.author}}</span></div>
      <div class="meta"><span>脚本: ${{DATA.script}}</span></div>
      <div class="meta"><span>设备: ${{DATA.device}}</span></div>
    </div>`;
}}

function filteredSteps() {{
  if (currentFilter === "all") return DATA.steps;
  return DATA.steps.filter(s => s.status === currentFilter);
}}

function renderFilmstrip() {{
  const el = document.getElementById("filmstrip");
  const steps = DATA.steps.filter(s => s.screenshot);
  if (!steps.length) {{
    el.innerHTML = '<div class="empty">暂无截图</div>';
    return;
  }}
  let cumMs = 0;
  el.innerHTML = steps.map((s, i) => {{
    const t = relTime(cumMs, 0);
    cumMs += s.duration_ms;
    const active = s.index - 1 === selectedIndex ? "active" : "";
    return `<div class="thumb ${{active}}" data-idx="${{s.index - 1}}">
      <img src="${{s.screenshot}}" alt="step ${{s.index}}" loading="lazy"/>
      <div class="thumb-time">${{t}}</div>
    </div>`;
  }}).join("");
  el.querySelectorAll(".thumb").forEach(t => {{
    t.addEventListener("click", () => selectStep(+t.dataset.idx));
  }});
}}

function renderStepList() {{
  const el = document.getElementById("step-list");
  const steps = filteredSteps();
  if (!steps.length) {{
    el.innerHTML = '<div class="empty">无匹配步骤</div>';
    return;
  }}
  el.innerHTML = steps.map(s => {{
    const active = s.index - 1 === selectedIndex ? "active" : "";
    return `<div class="step-item ${{active}}" data-idx="${{s.index - 1}}">
      <span class="step-icon ${{s.status}}">${{statusIcon(s.status)}}</span>
      <div class="step-body">
        <div class="step-name">#${{s.index}} ${{s.title}}</div>
        <div class="step-dur">${{fmtDuration(s.duration_ms)}}</div>
      </div>
      <span class="step-eye">👁</span>
    </div>`;
  }}).join("");
  el.querySelectorAll(".step-item").forEach(item => {{
    item.addEventListener("click", () => selectStep(+item.dataset.idx));
  }});
}}

function renderDetail() {{
  const el = document.getElementById("detail");
  const step = DATA.steps[selectedIndex];
  if (!step) {{
    el.innerHTML = '<div class="empty">请选择步骤</div>';
    return;
  }}
  const badgeClass = step.status;
  const argsRows = Object.entries(step.args || {{}}).map(([k, v]) =>
    `<tr><td>${{k}}</td><td>${{typeof v === "object" ? JSON.stringify(v) : v}}</td></tr>`
  ).join("");
  const shot = step.screenshot
    ? `<div class="detail-shot"><img src="${{step.screenshot}}" alt="screenshot"/></div>`
    : "";
  const err = step.error
    ? `<div class="error-box">${{step.error}}</div>`
    : "";
  el.innerHTML = `
    <div class="detail-header">
      <span class="badge ${{badgeClass}}">${{step.status === "passed" ? "Passed" : step.status === "failed" ? "Failed" : "Skipped"}}</span>
      <span>Step ${{step.index}}: ${{step.title}}</span>
    </div>
    <div class="detail-stats">
      <div class="stat-card"><div class="stat-label">结果</div><div class="stat-value">${{step.status}}</div></div>
      <div class="stat-card"><div class="stat-label">时间</div><div class="stat-value">${{step.timestamp}}</div></div>
      <div class="stat-card"><div class="stat-label">耗时</div><div class="stat-value">${{fmtDuration(step.duration_ms)}}</div></div>
      <div class="stat-card"><div class="stat-label">动作</div><div class="stat-value">${{step.action}}</div></div>
    </div>
    ${{shot}}
    <div class="args-section">
      <h3>Args</h3>
      <table class="args-table">${{argsRows || '<tr><td colspan="2">无参数</td></tr>'}}</table>
    </div>
    ${{err}}`;
}}

function selectStep(idx) {{
  selectedIndex = idx;
  renderFilmstrip();
  renderStepList();
  renderDetail();
}}

document.querySelectorAll(".filter-btn[data-filter]").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".filter-btn[data-filter]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    renderStepList();
  }});
}});

document.getElementById("jump-error").addEventListener("click", () => {{
  const fail = DATA.steps.find(s => s.status === "failed");
  if (fail) selectStep(fail.index - 1);
}});

renderSummary();
if (DATA.steps.length) selectStep(0);
else {{ renderFilmstrip(); renderStepList(); renderDetail(); }}
</script>
</body>
</html>
"""


def generate_report(reporter: StepReporter) -> Path | None:
    """根据 StepReporter 数据生成单测 HTML 报告。"""
    report_dir = reporter.report_dir
    if report_dir is None:
        logger.warning("No report directory; skip Airtest report generation")
        return None

    data = reporter.to_dict()
    page_title = f"AIRVision Report - {reporter.script_name}"
    html = _REPORT_TEMPLATE.format(
        page_title=page_title,
        report_json=json.dumps(data, ensure_ascii=False),
    )

    report_path = report_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    logger.info(f"Airtest-style report saved: {report_path}")
    return report_path


def generate_session_index(reports: list[dict[str, Any]]) -> Path | None:
    """生成会话级索引页，汇总本次所有测试报告链接。"""
    if not reports:
        return None

    session_dir = Path(reports[0]["report_path"]).parent.parent
    rows = []
    for item in reports:
        rel = Path(item["report_path"]).relative_to(session_dir).as_posix()
        status = item["status"]
        badge_class = "passed" if status == "passed" else "failed" if status == "failed" else "skipped"
        rows.append(
            f'<tr>'
            f'<td><span class="badge {badge_class}">{item["status_label"]}</span></td>'
            f'<td><a href="{rel}">{item["test_id"]}</a></td>'
            f'<td>{item["script"]}</td>'
            f'<td>{item["step_count"]}</td>'
            f'<td>{item["duration_ms"]}ms</td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>AIRVision Test Session</title>
<style>
body {{ font-family: "Segoe UI","Microsoft YaHei",sans-serif; background:#0f1419; color:#e8edf4; padding:24px; }}
h1 {{ font-size:20px; margin-bottom:16px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
td,th {{ padding:10px 12px; border:1px solid #2d3a4f; text-align:left; }}
th {{ background:#1a2332; color:#8b9cb3; }}
.badge {{ padding:2px 8px; border-radius:4px; font-size:12px; }}
.badge.passed {{ background:rgba(61,214,140,.15); color:#3dd68c; }}
.badge.failed {{ background:rgba(245,101,101,.15); color:#f56565; }}
a {{ color:#63b3ed; }}
</style></head><body>
<h1>AIRVision 测试会话报告</h1>
<table><thead><tr>
<th>状态</th><th>用例</th><th>脚本</th><th>步骤数</th><th>耗时</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table>
</body></html>"""

    index_path = session_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    logger.info(f"Session index saved: {index_path}")
    return index_path
